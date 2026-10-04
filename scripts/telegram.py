"""Send a draft's clip to your own phone through a Telegram bot, so you can post it to X by hand.
Two messages: the video, then the X caption on its own so it copies cleanly. Not a publish:
it only goes to the one chat you configured.

    python3 telegram.py drafts/2026-10-04-some-update [--force]
    python3 telegram.py --find-chat      # after you sent your bot any message: prints + saves the chat id
    python3 telegram.py --test           # one test message

Config (environment wins over the file): TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, or the same keys
in ~/.config/shipcast/telegram.env (override the path with SHIPCAST_TELEGRAM_ENV).
"""
import argparse, json, os, subprocess, sys
from datetime import datetime
from pathlib import Path

ENV = Path(os.environ.get("SHIPCAST_TELEGRAM_ENV", "~/.config/shipcast/telegram.env")).expanduser()


def read_env(path=ENV):
    env = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"\'')
    return env


def config(need_chat=True):
    env = read_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN")
    chat = (os.environ.get("TELEGRAM_CHAT_ID") or env.get("TELEGRAM_CHAT_ID")
            or env.get("TELEGRAM_HOME_CHANNEL"))
    if not token or (need_chat and not chat):
        sys.exit(f"Telegram is not set up: put TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in {ENV}")
    return token, chat


def call(token, method, fields=None, files=None):
    cmd = ["curl", "-sS", "--max-time", "300", f"https://api.telegram.org/bot{token}/{method}"]
    for k, v in (fields or {}).items():
        cmd += ["--form-string", f"{k}={v}"]
    for k, v in (files or {}).items():
        cmd += ["-F", f"{k}=@{v}"]
    r = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    if not r.get("ok"):
        sys.exit(f"Telegram {method}: {r.get('description')}")
    return r["result"]


def find_chat():
    token, _ = config(need_chat=False)
    chats = {u[k]["chat"]["id"] for u in call(token, "getUpdates")
             for k in ("message", "channel_post") if k in u}
    if not chats:
        sys.exit("No messages yet — open your bot in Telegram, send it any message, then run this again.")
    chat = sorted(chats)[-1]
    lines = [l for l in (ENV.read_text().splitlines() if ENV.is_file() else [])
             if not l.startswith("TELEGRAM_CHAT_ID=")]
    if not any(l.startswith("TELEGRAM_BOT_TOKEN=") for l in lines):
        lines.append(f"TELEGRAM_BOT_TOKEN={token}")
    lines.append(f"TELEGRAM_CHAT_ID={chat}")
    ENV.parent.mkdir(parents=True, exist_ok=True)
    ENV.write_text("\n".join(lines) + "\n")
    ENV.chmod(0o600)
    print(f"chat id {chat} saved to {ENV}")


def send(draft, force=False):
    d = Path(draft).resolve()
    post = json.loads((d / "post.json").read_text())
    clip = d / "clip.mp4"
    if not clip.is_file():
        sys.exit(f"no clip.mp4 in {d} — render first")
    log = d / "telegram.json"
    if log.is_file() and not force:
        print(f"already sent ({json.loads(log.read_text())['sent']}) — --force sends again")
        return

    token, chat = config()
    caps = post.get("captions", {})
    text = caps.get("x") or caps.get("default", "")
    headline = post.get("headline", d.name)
    call(token, "sendVideo", {"chat_id": chat, "supports_streaming": "true", "width": "1080",
                              "height": "1920", "caption": f"Ship log: {headline}\nX caption follows as its own message."},
         {"video": clip})
    if text:
        call(token, "sendMessage", {"chat_id": chat, "text": text, "disable_web_page_preview": "true"})
    log.write_text(json.dumps({"sent": datetime.now().isoformat(timespec="seconds")}, indent=2))
    print("✓ sent to Telegram (video + X caption)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft", nargs="?")
    ap.add_argument("--force", action="store_true", help="send again even if already sent")
    ap.add_argument("--find-chat", action="store_true", help="read the chat id from your bot's inbox")
    ap.add_argument("--test", action="store_true", help="send one test message")
    a = ap.parse_args()
    if a.find_chat:
        find_chat()
    elif a.test:
        token, chat = config()
        call(token, "sendMessage", {"chat_id": chat, "text": "shipcast is connected ✓"})
        print("✓ test message sent")
    elif a.draft:
        send(a.draft, a.force)
    else:
        ap.error("give a draft folder, --find-chat or --test")


if __name__ == "__main__":
    main()
