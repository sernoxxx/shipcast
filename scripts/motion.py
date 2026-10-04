"""Animated template -> mp4. The page exposes seek(ms) and a `ready` promise; Chrome is driven
over the DevTools protocol, one seek + one capture per frame, piped straight into ffmpeg.
Deterministic: the same post renders the same video every time, no real-time recording."""
import asyncio, base64, json, shutil, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

import websockets


async def _cdp(url):
    ws = await websockets.connect(url, max_size=None, ping_interval=None)
    ids = iter(range(1, 10**9))

    async def call(method, **params):
        i = next(ids)
        await ws.send(json.dumps({"id": i, "method": method, "params": params}))
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), 60))
            if m.get("id") == i:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})
    return ws, call


def _port(profile, proc):
    f = Path(profile) / "DevToolsActivePort"
    end = time.time() + 30
    while time.time() < end:
        if f.is_file() and f.read_text().strip():
            return int(f.read_text().split()[0])
        if proc.poll() is not None:
            sys.exit("Chrome exited before DevTools came up")
        time.sleep(.1)
    sys.exit("Chrome DevTools never came up")


async def _render(chrome, html_file, out_mp4, w, h, seconds, fps):
    profile = tempfile.mkdtemp(prefix="shipcast-")
    proc = subprocess.Popen(
        [chrome, "--headless=new", "--no-sandbox", "--hide-scrollbars", "--mute-audio",
         "--remote-debugging-port=0", f"--user-data-dir={profile}", f"--window-size={w},{h}",
         "--force-device-scale-factor=1", "--disable-background-timer-throttling",
         "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows",
         "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ff = None
    try:
        port = _port(profile, proc)
        pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list"))
        page = next(p for p in pages if p.get("type") == "page")
        ws, call = await _cdp(page["webSocketDebuggerUrl"])
        await call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
        await call("Page.enable")
        await call("Page.navigate", url=Path(html_file).as_uri())
        r = await call("Runtime.evaluate", awaitPromise=True, returnByValue=True,
                       expression="new Promise(r=>{const go=()=>window.ready?window.ready.then(r):setTimeout(go,50);go()})")
        if not r.get("result", {}).get("value"):
            sys.exit(f"clip template never became ready: {r}")

        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-i", "-",
             "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
             "-vf", f"scale={w}:{h},format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-r", str(fps), "-c:a", "aac", "-b:a", "64k", "-shortest", "-movflags", "+faststart",
             str(out_mp4)], stdin=subprocess.PIPE)
        for i in range(int(seconds * fps)):
            await call("Runtime.evaluate", expression=f"seek({i * 1000 / fps:.3f})")
            img = await call("Page.captureScreenshot", format="jpeg", quality=95,
                             clip={"x": 0, "y": 0, "width": w, "height": h, "scale": 1})
            ff.stdin.write(base64.b64decode(img["data"]))
        ff.stdin.close()
        if ff.wait() != 0:
            sys.exit("ffmpeg failed on the animated clip")
        await ws.close()
    finally:
        if ff and ff.poll() is None:
            ff.kill()
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


def render_motion(chrome, html_file, out_mp4, w=1080, h=1920, seconds=8, fps=30):
    asyncio.run(_render(chrome, html_file, out_mp4, w, h, seconds, fps))
