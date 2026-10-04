# shipcast

Claude Code already logs every session. **shipcast** turns that into a finished X post —
a card, an animated 9:16 clip and the caption — in your project's own style, and sends it
to your phone on Telegram. Say yes once more and it posts it to X for you, through your
logged-in browser.

After every meaningful update, Claude asks:

> Should I make an X post for this?

**No** → nothing happens. **Yes** → a couple of minutes later the clip and the caption are
in your Telegram. Then: *"Should I post this on X now?"* — yes, and it goes out with the
video and the caption.

No social media API keys, nothing public without your yes, no second changelog to maintain.

## Install

Give Claude Code this repo's link and say:

```
Install this and set it up in my Claude Code: https://github.com/sernoxxx/shipcast
```

Claude follows [`INSTALL.md`](INSTALL.md): checks the requirements, clones the skill to
`~/.claude/skills/shipcast`, adds the "ask after updates" rule to `~/.claude/CLAUDE.md`,
connects your own Telegram bot (you create it with @BotFather in a minute), lets you sign
in to X once in a browser window, and sends a test post.

Requirements: Python 3.9+, ffmpeg, and Chrome/Chromium/Brave/Edge for rendering.

## What you get

| File | What |
| --- | --- |
| `card.png` | 1080×1350, the still for the feed |
| `story.png` | 1080×1920 |
| `clip.mp4` | 9:16, animated (~8 s) if the style ships a clip, otherwise a slow zoom |

Everything lands in `drafts/<date>-<slug>/` next to its `post.json`.

## Styles

Each project gets its own look, picked by matching the project path. Shipped:

- **default** — dark studio look
- **synagy** — toybox card for [Synagy Games](https://synagy-studio.vercel.app), with an
  animated clip

Your own styles go in `~/.config/shipcast/styles/` — Claude can build one from your
project's CSS or a few reference images. See [`SKILL.md`](SKILL.md).

## Manual use

```bash
python3 scripts/harvest.py --project ~/code/my-app --since 7d   # what happened
python3 scripts/render.py drafts/2026-10-04-my-update           # card + clip
python3 scripts/telegram.py drafts/2026-10-04-my-update         # to your phone
python3 scripts/post_x.py drafts/2026-10-04-my-update           # to X (after your yes)
python3 test_shipcast.py                                        # self-test
```

## License

MIT
