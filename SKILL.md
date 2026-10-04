---
name: shipcast
description: "Turn a project's Claude Code logs and git commits into a finished X post: harvest a digest, write the copy, render a card (4:5) and an animated 9:16 clip in the project's style, send both to the user's Telegram, and — after an explicit yes — post it to X through the logged-in browser. Use when the user says yes to 'Should I make an X post for this?', or asks for a ship log, a changelog post, build-in-public content, 'post the update', 'make a post out of this', 'shipcast'."
---

# shipcast

What Claude Code logs anyway becomes a post. No second changelog to maintain: the logs
**are** the raw material.

**Nothing goes public without a yes for that exact post.** shipcast builds the post, sends it
to the user's own Telegram chat, and posts to X only when the human confirms — through a
logged-in browser, not an API. There are no social media API keys here.

## When to offer it

After you finish a **meaningful, larger update** in a project that has a shipcast style
(a new feature, a visible change, a release, a fixed bug users noticed), end your final
message with one short question:

> Should I make an X post for this?

Write it in the language you are talking to the user in. Not after typos, refactors,
config tweaks, tests, or work-in-progress. At most once per update — if they said no, don't
ask again for the same thing.

- **No** → do nothing. No draft, no message.
- **Yes** → run the flow below, start to finish, without further questions.

## Flow

### 1. Harvest the digest

```bash
python3 ~/.claude/skills/shipcast/scripts/harvest.py --project /path/to/project --since 1d
```

Returns commits, the most-touched files, and the Claude sessions (titles + prompts) in that
window. `--since` understands `24h`, `7d`, `2w`. For a post about the update you just
finished, `1d` is usually right; widen it if the work spans more days. If nothing comes
back, nothing happened — don't invent a post, say so.

The header names the **style** matched for this project. `Style: default` means none
matches — offer to create one (see Styles).

### 2. Write the post

Find **the one thing** that makes a difference to users. One post = one topic. The rest is
evidence, not a list.

| The log says | The post says |
| --- | --- |
| `fix: null check in scoreDeal()` | nothing — too small, unless it was a visible bug |
| `feat: background scan worker` | "The scan now keeps running in the background" |
| 14 commits on auth | "Login is rebuilt: no more logouts after 24 h" |

Non-negotiable:

- **Benefit, not mechanics.** Nobody outside the repo knows `scoreDeal()`.
- **Invent nothing.** If it isn't in the digest, it isn't in the post. No estimated numbers,
  no roadmap promises.
- **Nothing internal.** No paths, keys, client names, unreleased pricing, or security holes
  whose fix isn't shipped.
- **No hype vocabulary.** A developer showing what runs — warm, not a changelog, not an ad.
- **At most three emoji per caption**, only where one carries meaning.
- **If the style has a `link`, the caption ends with it.** The card itself stays link-free.

Create `drafts/YYYY-MM-DD-slug/post.json` inside the shipcast folder:

```json
{
  "project": "/path/to/project",
  "eyebrow": "SHIP LOG · PROJECT",
  "headline": "The scan runs in the background now",
  "bullets": [
    "**Live scan** keeps going while you scroll",
    "Results show up the moment they're ready",
    "🎮 Works the same on phone and desktop"
  ],
  "meta": "14 commits",
  "captions": {
    "default": "Built this week: …",
    "x": "…max 280 characters including hashtags and link…"
  },
  "hashtags": ["#buildinpublic"]
}
```

`project` is what the style is matched against; `"style": "<name>"` forces one. Leave
`handle` out and the style's own handle is used.

Measurements the layout depends on: **headline ≤ 60 characters**, **2–4 bullets of ≤ 85
characters**, `**bold**` on at most one fragment per bullet. `meta` is **one** real number
from the digest. The eyebrow is just `SHIP LOG · PROJECT`.

Optional: **`photo`** (a fresh screenshot that burns into the card; absolute, relative to
the draft, or relative to `project`), **`footnote`** (footer line), and a bullet may
**start with a single emoji** to become that row's icon tile.

### 3. Render

```bash
python3 ~/.claude/skills/shipcast/scripts/render.py ~/.claude/skills/shipcast/drafts/2026-10-04-live-scan
```

Produces `card.png` (1080×1350), `story.png` (1080×1920) and `clip.mp4` (9:16). If the
style has `styles/<name>.clip.html`, the clip is a real animation (`clip_seconds`, default
8 s, 30 fps, frame by frame over the DevTools protocol); otherwise a slow zoom over the
still. `--style <name>` forces a style, `--no-video` skips the clip.

**Look at `card.png` afterwards** (Read tool): text running out, a bad headline break, a
crowded footer? Shorten the text and re-render — don't touch the template. For the clip,
check a contact sheet instead of watching it:
`ffmpeg -i clip.mp4 -vf "select=not(mod(n\,30)),scale=270:-1,tile=4x2" -frames:v 1 sheet.png`

### 4. Send it to the phone

```bash
python3 ~/.claude/skills/shipcast/scripts/telegram.py ~/.claude/skills/shipcast/drafts/2026-10-04-live-scan
```

The clip goes first, then the X caption as its own message so it copies cleanly. This is
not a publish and needs no extra yes. `telegram.json` in the draft stops a double send;
after a re-render use `--force`. Then tell the user it's on their phone.

If it says Telegram is not set up, walk them through **Telegram setup** in `INSTALL.md`.
Telegram is optional — without it, skip this step and show the card and caption in the chat.

### 5. Post to X — only after a yes

Show the X caption (and the card, if you haven't) and ask one question:

> Should I post this on X now?

- **No** → stop. It's on their phone; they can post it themselves.
- **Yes** → post it through the logged-in browser:

```bash
python3 ~/.claude/skills/shipcast/scripts/post_x.py ~/.claude/skills/shipcast/drafts/2026-10-04-live-scan
```

It writes the X caption (plus hashtags not already in it) into the composer, attaches
`clip.mp4` (or `card.png` when there is no clip), waits until X has processed the video,
presses post and checks for the confirmation. It prints the account it posted as — if that
isn't the style's `x_handle`/`handle`, say so. `posted.json` stops a double post.

A yes counts for that one post only. Never post without asking, never post a changed text
without asking again. `--dry-run` fills everything and stops before the button.

If it says **not logged in**: run `post_x.py --login`, tell the human to sign in to X in
the browser window that opens (once — the profile keeps the session), then retry.

## Styles — one per project

```
styles/<name>.json        match list, handle, link, fonts, CSS tokens, the mark
styles/<name>.html        optional — only when the layout itself differs
styles/<name>.clip.html   optional — the animated 9:16 clip
```

Your own styles go in `~/.config/shipcast/styles/` (or `$SHIPCAST_STYLES`), so updating
shipcast never touches them; a local style with a shipped name wins.

`match` is a list of substrings tested against the project path. Tokens land in a `:root`
block: `canvas`, `surface`, `ink`, `soft`, `faint`, `accent`, `line`, `display`, `body`,
`mono`, `radius`, `case`. `mark` is the inline SVG in the header — draw one, never a stock
icon. `link` ends every caption, `x_handle` is the X account when `handle` isn't one.

Shipped: `default` (dark studio look) and `synagy` (toybox card: paper, solid lip, sticker,
jelly tiles, with an 8 s animated clip).

**Creating one** — once per project:

1. **Read the source.** Grep the project's CSS/theme for color tokens and font imports
   (`:root`, `tailwind.config`, `fonts.googleapis`). Real values beat a guess.
2. **Write `styles/<name>.json`** with `match`, `handle`, `link`, `fonts` (a Google Fonts
   `@import`) and `vars`.
3. **Add `<name>.html` only when the design language really differs.** Start from
   `templates/card.html` and keep every placeholder: `{{fonts}}`, `{{vars}}`, `{{w}}`,
   `{{h}}`, `{{pad}}`, `{{size}}`, `{{mark}}`, `{{eyebrow}}`, `{{headline}}`, `{{bullets}}`,
   `{{handle}}`, `{{meta}}`.
4. **Animated clip (optional):** copy `styles/synagy.clip.html`. It keeps the card
   placeholders plus `{{link}}`, builds its timeline with WAAPI (`element.animate`), pauses
   everything, and exposes `seek(ms)` and a `ready` promise. Aim for ~8 s, simple, juicy:
   pops with overshoot, a squash on landing, staggered headline, an end card with handle
   and link.
5. **Render a test draft, look at it, fix what the human names.**
   `python3 ~/.claude/skills/shipcast/test_shipcast.py` checks every style still renders.

Never bend a post's text to fit a style, and never restyle a project on a whim.

## When something breaks

- **"No Chrome/Chromium found"** → install one or set `CHROME=/path/to/chrome`.
- **X changed its page** (composer or button not found) → the selectors at the top of
  `scripts/post_x.py` need an update; meanwhile the post is on Telegram to post by hand.
- **`No module named 'websockets'`** → `python3 -m pip install --user websockets`.
- **Fonts look wrong** → fonts load from Google Fonts at render time; offline you get the
  system fallback.
- **Self-test**: `python3 ~/.claude/skills/shipcast/test_shipcast.py`
