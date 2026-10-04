#!/usr/bin/env python3
"""Drive a real Chromium browser over the DevTools protocol — a logged-in profile instead of API keys.

The profile lives in ~/.config/shipcast/browser-profile (override: SHIPCAST_BROWSER_PROFILE),
so a login done once stays. Nothing here is site-specific; post_x.py builds on it.
"""
import asyncio, json, os, shutil, subprocess, sys, time, urllib.request
from pathlib import Path

import websockets

PROFILE = Path(os.environ.get("SHIPCAST_BROWSER_PROFILE", "~/.config/shipcast/browser-profile")).expanduser()
PORT = int(os.environ.get("SHIPCAST_BROWSER_PORT", "9334"))
# Whatever Chromium build this machine has. Brave and Chrome speak the same protocol.
BROWSERS = [os.environ.get("CHROME"), "brave-browser", "google-chrome", "google-chrome-stable",
            "chromium", "chromium-browser", "microsoft-edge"]


def browser_binary():
    for b in BROWSERS:
        if b and (shutil.which(b) or Path(b).is_file()):
            return shutil.which(b) or b
    sys.exit("No Chromium-based browser found. Install one or set CHROME=/path/to/binary.")


def endpoint(timeout=0.6):
    """The debug endpoint, or None when no browser of ours is listening."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=timeout) as r:
            return json.load(r)["webSocketDebuggerUrl"]
    except Exception:
        return None


def ensure_browser(headless=False):
    """Reuse the running debug browser, else start one on our own profile.

    Chromium refuses --remote-debugging-port on the default profile, so this
    profile is deliberately separate: log in once here, it stays logged in.
    """
    ws = endpoint()
    if ws:
        return ws
    PROFILE.mkdir(parents=True, exist_ok=True)
    args = [browser_binary(), f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
            "--no-first-run", "--no-default-browser-check", "--disable-brave-update",
            "--restore-last-session=false", "about:blank"]
    if headless:
        args.insert(1, "--headless=new")
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    for _ in range(80):                      # cold start of a real browser takes a moment
        time.sleep(.25)
        ws = endpoint()
        if ws:
            return ws
    sys.exit("Browser did not come up on the debug port.")


class Page:
    """One tab, attached over CDP. Every call is a plain awaitable."""

    def __init__(self, sock, session):
        self.sock, self.session, self.n = sock, session, 0

    async def send(self, method, **params):
        self.n += 1
        await self.sock.send(json.dumps(
            {"id": self.n, "method": method, "params": params, "sessionId": self.session}))
        while True:
            msg = json.loads(await self.sock.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    async def eval(self, expr, await_promise=False):
        r = await self.send("Runtime.evaluate", expression=expr, returnByValue=True,
                            awaitPromise=await_promise, userGesture=True)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"].get("text", "js error"))
        return r.get("result", {}).get("value")

    async def goto(self, url):
        await self.send("Page.navigate", url=url)
        await self.wait_ready()

    async def wait_ready(self, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if await self.eval("document.readyState === 'complete'"):
                    return True
            except RuntimeError as e:
                # A redirect while loading tears the context away; just keep waiting.
                if "navigated or closed" not in str(e) and "context" not in str(e).lower():
                    raise
            await asyncio.sleep(.25)
        return False

    async def wait(self, selector, timeout=30):
        """Wait for a selector to exist. Returns False on timeout — callers decide."""
        end = time.time() + timeout
        js = f"!!document.querySelector({json.dumps(selector)})"
        while time.time() < end:
            if await self.eval(js):
                return True
            await asyncio.sleep(.3)
        return False

    async def click(self, selector):
        return await self.eval(
            f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
            f"if(!e)return false; e.scrollIntoView({{block:'center'}}); e.click(); return true}})()")

    async def type(self, selector, text):
        """Focus the field, then let the browser insert the text like a human paste.

        React editors ignore a value assignment; Input.insertText goes through the
        same path a real keystroke takes.
        """
        ok = await self.eval(
            f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
            f"if(!e)return false; e.scrollIntoView({{block:'center'}}); e.focus(); return true}})()")
        if not ok:
            return False
        for i, line in enumerate(text.split("\n")):
            if i:
                for ev in ("keyDown", "keyUp"):   # Enter, so newlines survive in contenteditable
                    await self.send("Input.dispatchKeyEvent", type=ev, key="Enter",
                                    code="Enter", windowsVirtualKeyCode=13, nativeVirtualKeyCode=13)
            if line:
                await self.send("Input.insertText", text=line)
        return True

    async def upload(self, selector, *files):
        """Put files into a file input — works even when the input is hidden."""
        doc = await self.send("DOM.getDocument")
        node = await self.send("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
        if not node.get("nodeId"):
            return False
        await self.send("DOM.setFileInputFiles",
                        files=[str(Path(f).resolve()) for f in files], nodeId=node["nodeId"])
        return True


class Browser:
    """Connection to the browser itself; hands out pages."""

    def __init__(self, headless=False):
        self.url = ensure_browser(headless)
        self.sock = None
        self.n = 0

    async def __aenter__(self):
        self.sock = await websockets.connect(self.url, max_size=64 * 1024 * 1024)
        return self

    async def __aexit__(self, *exc):
        await self.sock.close()

    async def send(self, method, **params):
        self.n += 1
        await self.sock.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.sock.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    async def page(self, url=None, reuse=True):
        """A tab to work in: the current one when there is a usable one, else a new one."""
        target = None
        if reuse:
            for t in (await self.send("Target.getTargets"))["targetInfos"]:
                if t["type"] == "page" and not t["url"].startswith("devtools://"):
                    target = t["targetId"]
                    break
        if target is None:
            target = (await self.send("Target.createTarget", url=url or "about:blank"))["targetId"]
            url = None
        s = (await self.send("Target.attachToTarget", targetId=target, flatten=True))["sessionId"]
        page = Page(self.sock, s)
        page.target = target
        await page.send("Page.enable")
        await page.send("Runtime.enable")
        await page.send("DOM.enable")
        if url:
            await page.goto(url)
        return page
