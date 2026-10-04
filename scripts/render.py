#!/usr/bin/env python3
"""post.json -> card.png (4:5), story.png (9:16), clip.mp4 (9:16; 6s zoom, or animated if the style has a .clip.html).

Renders with the installed Chrome/Chromium (no Playwright) and ffmpeg.
"""
import argparse, base64, html, json, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "card.html"
STYLES = ROOT / "styles"
# Your own styles live outside the repo, so an update never touches them. Same name = yours wins.
LOCAL_STYLES = Path(os.environ.get("SHIPCAST_STYLES", "~/.config/shipcast/styles")).expanduser()
# 4:5 for the feed (X/IG/FB), 9:16 for Reels/TikTok/Shorts.
FORMATS = {"card": (1080, 1350, 64, 62), "story": (1080, 1920, 72, 68)}

CHROME_CANDIDATES = [
    os.environ.get("CHROME"), "google-chrome", "google-chrome-stable", "chromium",
    "chromium-browser", "brave-browser", "microsoft-edge",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]

def find_chrome():
    for c in CHROME_CANDIDATES:
        if c and (shutil.which(c) or Path(c).is_file()):
            return shutil.which(c) or c
    sys.exit("No Chrome/Chromium found. Install one or set CHROME=/path/to/chrome.")

def style_files():
    """name -> styles/<name>.json, the local folder overriding the shipped one."""
    found = {}
    for d in (STYLES, LOCAL_STYLES):
        for f in sorted(d.glob("*.json")) if d.is_dir() else []:
            found[f.stem] = f
    return found

def pick_style(hint):
    """Project path or name -> style name. First style whose 'match' list hits, else default."""
    for f in style_files().values():
        if any(m.lower() in str(hint).lower() for m in json.loads(f.read_text()).get("match", [])):
            return f.stem
    return "default"

def load_style(name):
    """A style is styles/<name>.json; styles/<name>.html replaces the template if it exists."""
    f = style_files().get(name)
    if not f:
        sys.exit(f"Unknown style '{name}' — available: " + ", ".join(sorted(style_files())))
    s = json.loads(f.read_text())
    own = f.parent / f"{name}.html"
    s["template"] = own if own.is_file() else TEMPLATE
    # styles/<name>.clip.html: an animated reel instead of a zoom over the still.
    motion = f.parent / f"{name}.clip.html"
    s["clip"] = motion if motion.is_file() else None
    return s

def style_for(post, override=None):
    """CLI flag beats post.json 'style' beats a match on post.json 'project'."""
    name = override or post.get("style") or pick_style(post.get("project", ""))
    return name, load_style(name)

def split_icon(text):
    """A leading emoji is the row's icon, not part of the sentence. '' when there is none."""
    head, _, rest = str(text).partition(" ")
    if head and not head.isascii():
        return head, rest.lstrip()
    return "", str(text)

def bullets_html(items):
    out = []
    for b in items:
        icon, text = split_icon(b)
        # **bold** -> <b>, everything else is escaped.
        parts = html.escape(text).split("**")
        inner = "".join(p if i % 2 == 0 else f"<b>{p}</b>" for i, p in enumerate(parts))
        tile = f"<i>{html.escape(icon)}</i>" if icon else ""
        out.append(f"<li>{tile}<span>{inner}</span></li>")
    return "\n".join(out)

def photo_var(post, draft_dir):
    """post 'photo' -> a --photo token the template can drop into background-image."""
    src = post.get("photo")
    if not src:
        return ""
    f = Path(src) if Path(src).is_absolute() else (draft_dir / src)
    if not f.is_file():
        f2 = Path(post.get("project", "")) / src
        if not f2.is_file():
            sys.exit(f"photo not found: {src}")
        f = f2
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp"}.get(f.suffix.lower(), "image/png")
    return f"--photo:url('data:{mime};base64,{base64.b64encode(f.read_bytes()).decode()}');"

def build_html(post, w, h, pad, size, style=None, draft_dir=None, template=None):
    style = style or load_style("default")
    tpl = Path(template or style["template"]).read_text()
    # The headline shrinks when it gets long — otherwise it breaks out of the card.
    n = len(post.get("headline", ""))
    size = size - 12 if n > 46 else size
    size = size - 10 if n > 70 else size
    values = {
        "w": w, "h": h, "pad": pad, "size": size,
        "fonts": style.get("fonts", ""),
        "vars": ":root{" + "".join(f"--{k}:{v};" for k, v in style.get("vars", {}).items())
                + photo_var(post, draft_dir or Path(".")) + "}",
        "mark": style.get("mark", ""),
        "eyebrow": html.escape(post.get("eyebrow", "SHIP LOG")),
        "headline": html.escape(post.get("headline", "")),
        "bullets": bullets_html(post.get("bullets", [])),
        "handle": html.escape(post.get("handle") or style.get("handle", "")),
        "meta": html.escape(post.get("meta", "")),
        "footnote": html.escape(post.get("footnote") or style.get("footnote", "")),
        "link": html.escape(style.get("link", "")),
    }
    for k, v in values.items():
        tpl = tpl.replace("{{%s}}" % k, str(v))
    return tpl

def shot(chrome, html_file, png, w, h):
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                    "--force-device-scale-factor=1", f"--window-size={w},{h}",
                    f"--screenshot={png}", f"--virtual-time-budget=4000", html_file.as_uri()],
                   check=True, capture_output=True, timeout=120)
    if not Path(png).exists():
        sys.exit(f"Chrome wrote no image: {png}")

def clip(story_png, out_mp4, seconds=6):
    """Still image -> video with a slow zoom. Silent audio track, or TikTok/IG get fussy."""
    fps, frames = 25, 25 * seconds
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(story_png),
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", str(seconds),
        "-vf", (f"scale=2160:-2,zoompan=z='min(zoom+0.00045,1.10)':d={frames}"
                f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps},format=yuv420p"),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "64k", "-shortest", "-movflags", "+faststart", str(out_mp4),
    ], check=True, capture_output=True, timeout=300)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft", help="draft folder containing post.json")
    ap.add_argument("--no-video", action="store_true", help="images only, no mp4")
    ap.add_argument("--style", help="force a style from styles/ (default: auto-detected)")
    a = ap.parse_args()

    d = Path(a.draft).resolve()
    post = json.loads((d / "post.json").read_text())
    style_name, style = style_for(post, a.style)
    print(f"style: {style_name}")
    chrome = find_chrome()

    for name, (w, h, pad, size) in FORMATS.items():
        f = d / f"{name}.html"
        f.write_text(build_html(post, w, h, pad, size, style, d))
        shot(chrome, f, d / f"{name}.png", w, h)
        print(f"✓ {name}.png ({w}x{h})")

    if not a.no_video:
        if not shutil.which("ffmpeg"):
            sys.exit("ffmpeg missing — needed for TikTok/Shorts (or use --no-video)")
        if style.get("clip"):
            from motion import render_motion
            secs = style.get("clip_seconds", 8)
            w, h, pad, size = FORMATS["story"]
            f = d / "clip.html"
            f.write_text(build_html(post, w, h, pad, size, style, d, template=style["clip"]))
            render_motion(chrome, f, d / "clip.mp4", w, h, secs)
            print(f"✓ clip.mp4 ({secs}s, {w}x{h}, animated)")
        else:
            clip(d / "story.png", d / "clip.mp4")
            print("✓ clip.mp4 (6s, 1080x1920)")

if __name__ == "__main__":
    main()
