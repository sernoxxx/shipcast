# Install shipcast — instructions for Claude Code

> **Human:** give your Claude Code agent the link to this repo and say
> *"Install this and set it up in my Claude Code."* Everything below is for the agent.

---

You are installing **shipcast**, a Claude Code skill. After every meaningful, larger update
it asks the user whether to make an X post; on a yes it renders a card plus an animated
clip in the project's style and sends both to the user's Telegram, so they can post it from
their phone. It never posts anywhere by itself and needs no social media API keys.

Do these steps in order. Talk to the user in their language. Ask only where it says so.

## 1. Check the requirements

```bash
python3 --version          # 3.9 or newer
ffmpeg -version | head -1
git --version
```

Plus one Chromium-based browser (Chrome, Chromium, Brave or Edge). If something is missing,
install it with the system's package manager (ask before using `sudo`). If the browser is
in an unusual place, remember its path for `CHROME=`.

Then the one Python package the animated clip needs:

```bash
python3 -m pip install --user websockets || python3 -m pip install --user --break-system-packages websockets
```

## 2. Install the skill

```bash
git clone https://github.com/sernoxxx/shipcast.git ~/.claude/skills/shipcast
python3 ~/.claude/skills/shipcast/test_shipcast.py
```

The self-test must print `all checks green`. If the folder already exists, `git -C
~/.claude/skills/shipcast pull` instead.

## 3. Add the "ask after updates" rule

Append this block to `~/.claude/CLAUDE.md` (create the file if it doesn't exist; don't
duplicate the block if it's already there). This is what makes every future session ask.

```markdown
## shipcast — offer an X post after bigger updates

When you finish a meaningful, larger update in a project that matches a shipcast style
(see `~/.claude/skills/shipcast/styles/` and `~/.config/shipcast/styles/`), end your final message
with one short question in the user's language: "Should I make an X post for this?"
Only for real features, visible changes, releases or noticeable fixes — never for typos,
refactors, config or tests, and at most once per update.
No → do nothing. Yes → use the shipcast skill end to end: harvest, write post.json,
render the card and the animated clip, send it via telegram.py. Never post to X yourself.
```

If the user only wants this for specific projects, put the block in those projects'
`CLAUDE.md` instead and say so.

## 4. Telegram setup

The post arrives through a Telegram bot that belongs to the user. Tell them:

1. Open Telegram, search **@BotFather**, send `/newbot`, pick any name.
   BotFather replies with a token like `123456789:AA...`.
2. Paste that token here in the chat. *(Or, if they prefer not to paste it, they write
   `TELEGRAM_BOT_TOKEN=<token>` into `~/.config/shipcast/telegram.env` themselves.)*
3. Open the new bot in Telegram and send it any message, e.g. `hi`.

Then you:

```bash
mkdir -p ~/.config/shipcast
printf 'TELEGRAM_BOT_TOKEN=%s\n' '<token>' > ~/.config/shipcast/telegram.env
chmod 600 ~/.config/shipcast/telegram.env
python3 ~/.claude/skills/shipcast/scripts/telegram.py --find-chat
python3 ~/.claude/skills/shipcast/scripts/telegram.py --test
```

`--find-chat` reads the chat id from the bot's inbox and saves it. `--test` must arrive on
their phone as "shipcast is connected ✓". Never echo the token back or put it anywhere else.

## 5. Pick the style

Ask which project(s) shipcast is for. Then:

- If a shipped style in `~/.claude/skills/shipcast/styles/` already fits (its `match`
  catches the project path), you're done — `synagy` is shipped for Synagy Games projects.
  If the folder name doesn't contain the match word, add `"style": "synagy"` to every
  `post.json`, or copy the style to `~/.config/shipcast/styles/` and extend its `match`.
- Otherwise offer to create one, following **Styles → Creating one** in `SKILL.md`. Own
  styles always go in `~/.config/shipcast/styles/`, never into the cloned repo.

## 6. Prove it works

Make one test post about the project's recent work: follow the flow in `SKILL.md`
(harvest `--since 7d`, write `post.json`, render, look at `card.png`, send via Telegram).
Tell the user it's on their phone and that from now on you'll ask after bigger updates.

## Updating later

```bash
git -C ~/.claude/skills/shipcast pull && python3 ~/.claude/skills/shipcast/test_shipcast.py
```

Drafts (`drafts/`), Telegram config and own styles live outside version control, so a pull
never touches them.
