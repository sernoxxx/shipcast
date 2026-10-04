#!/usr/bin/env python3
"""Post a draft to X through the logged-in browser — no API keys, no credits.

    python3 post_x.py drafts/2026-10-04-some-update [--dry-run] [--force]
    python3 post_x.py --login          # opens x.com in the shipcast browser, sign in once

Text: the draft's X caption. Media: clip.mp4 when there is one, else card.png.
Only run this after the human said yes to this exact post. A dry run stops right before the
button: composer filled, media attached, nothing sent. posted.json in the draft stops a
second post (--force overrides).
"""
import argparse, asyncio, json, sys, time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser import Browser

COMPOSER = 'div[data-testid="tweetTextarea_0"]'
FILE_INPUT = 'input[data-testid="fileInput"]'
POST_BTN = ('button[data-testid="tweetButtonInline"]:not([aria-disabled="true"]), '
            'button[data-testid="tweetButton"]:not([aria-disabled="true"])')


def caption(post):
    """The X caption; hashtags are appended only when the caption doesn't carry them yet."""
    caps = post.get("captions", {})
    text = (caps.get("x") or caps.get("default") or post.get("headline", "")).strip()
    tags = [t for t in post.get("hashtags", []) if t not in text]
    return f"{text}\n\n{' '.join(tags)}" if tags else text


def media(d):
    for name in ("clip.mp4", "card.png"):
        if (d / name).is_file():
            return d / name
    return None


async def logged_in(page):
    """The account switcher only exists for a session that is actually signed in."""
    return bool(await page.eval(
        "!!document.querySelector('[data-testid=\"SideNav_AccountSwitcher_Button\"]')"
        " || !!document.querySelector('[data-testid=\"AppTabBar_Profile_Link\"]')"))


async def account(page):
    """@handle of the signed-in account, read from the side nav."""
    return await page.eval(
        "(()=>{const t=(document.querySelector('[data-testid=\"SideNav_AccountSwitcher_Button\"]')"
        "||{}).innerText||''; const m=t.match(/@\\w+/); return m?m[0]:''})()") or ""


async def post(text, file, dry_run):
    async with Browser() as b:
        # An own tab: another tool may be using the current one in the same browser.
        page = await b.page(reuse=False)
        try:
            return await _post(page, text, file, dry_run)
        finally:
            await b.send("Target.closeTarget", targetId=page.target)


async def _post(page, text, file, dry_run):
    await page.goto("https://x.com/home")
    await page.wait('[data-testid="SideNav_AccountSwitcher_Button"], [data-testid="loginButton"], a[href="/login"]', 15)
    if (await page.eval("location.href")).startswith("chrome-error:"):
        print("x.com did not load in this browser (offline, or X refuses a headless browser)",
              file=sys.stderr)
        return 1
    if not await logged_in(page):
        print("not logged in to X — run post_x.py --login and sign in once", file=sys.stderr)
        return 2
    who = await account(page)
    await page.goto("https://x.com/compose/post")

    if not await page.wait(COMPOSER, 20):
        print("composer did not appear", file=sys.stderr)
        return 1
    if not await page.type(COMPOSER, text):
        print("could not write into the composer", file=sys.stderr)
        return 1
    if file:
        if not await page.upload(FILE_INPUT, file):
            print("no file input in the composer", file=sys.stderr)
            return 1
        end = time.time() + 90
        while time.time() < end:
            if await page.eval('!!document.querySelector(\'[data-testid="attachments"] :is(img,video)\')'):
                break
            await asyncio.sleep(.5)
        else:
            print("media never showed up in the composer", file=sys.stderr)
            return 1

    # The button stays disabled while X processes the video — that wait is the check.
    if not await page.wait(POST_BTN, 180):
        print("post button stayed disabled", file=sys.stderr)
        return 1
    if dry_run:
        print(f"dry run as {who or 'unknown account'} — composer is filled, nothing sent")
        return 0

    await page.click(POST_BTN)
    end = time.time() + 45
    while time.time() < end:
        gone = not await page.eval(f"!!document.querySelector('{COMPOSER}')")
        toast = await page.eval(
            "(document.querySelector('[data-testid=\"toast\"]')||{}).innerText||''")
        if toast or gone:
            print(f"posted as {who or 'unknown account'}"
                  f"{' — ' + toast.replace(chr(10), ' ') if toast else ''}")
            return 0
        await asyncio.sleep(1)
    print("clicked post but saw no confirmation — check the timeline", file=sys.stderr)
    return 1


async def login():
    async with Browser() as b:
        page = await b.page()
        await page.goto("https://x.com/login")
    print("browser is open on x.com — sign in there, the profile keeps the session")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft", nargs="?")
    ap.add_argument("--dry-run", action="store_true", help="fill everything, don't press post")
    ap.add_argument("--force", action="store_true", help="post again even if already posted")
    ap.add_argument("--login", action="store_true", help="open x.com to sign in once")
    a = ap.parse_args()
    if a.login:
        return asyncio.run(login())
    if not a.draft:
        ap.error("give a draft folder or --login")

    d = Path(a.draft).resolve()
    p = json.loads((d / "post.json").read_text())
    log = d / "posted.json"
    if log.is_file() and not a.force and not a.dry_run:
        print(f"already posted ({json.loads(log.read_text())['posted']}) — --force posts again")
        return 0
    text, file = caption(p), media(d)
    if len(text) > 280:
        sys.exit(f"X caption is {len(text)} characters, the limit is 280 — shorten captions.x")
    rc = asyncio.run(post(text, file, a.dry_run))
    if rc == 0 and not a.dry_run:
        log.write_text(json.dumps({"posted": datetime.now().isoformat(timespec="seconds"),
                                   "to": "x", "media": file.name if file else None}, indent=2))
    return rc


if __name__ == "__main__":
    sys.exit(main())
