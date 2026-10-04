#!/usr/bin/env python3
"""Self-test: python3 test_shipcast.py — fails loudly when the logic is broken."""
import json, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
import harvest, render, telegram, post_x

# --- time window parsing
assert abs((harvest.since_dt("24h") - harvest.since_dt("1d")).total_seconds()) < 1
assert round((harvest.since_dt("1d") - harvest.since_dt("2w")).total_seconds() / 3600) == 312
try:
    harvest.since_dt("yesterday"); assert False, "an invalid --since must abort"
except SystemExit:
    pass

# --- project path -> log folder (that is how the folders under ~/.claude/projects are named)
assert harvest.slug("/home/user") == "-home-user"
assert harvest.slug("/mnt/d/Vault/locales/personal-os") == "-mnt-d-Vault-locales-personal-os"

# --- the digest redacts anything that could be a key (the digest becomes the post)
assert harvest.scrub("key=sk-ABCDEFGHIJKLMNOP out") == "key=[redacted] out"
assert harvest.scrub("token ghp_" + "a" * 36) == "token [redacted]"
assert harvest.scrub("- fix: null check in scoreDeal()") == "- fix: null check in scoreDeal()"

# --- bullets: **bold** becomes <b>, everything else is escaped
h = render.bullets_html(["**Live scan** runs <now>"])
assert h == "<li><span><b>Live scan</b> runs &lt;now&gt;</span></li>", h
# The span is not cosmetic: without it the line falls apart into two columns in the flex li.
assert "<span>" in render.bullets_html(["plain"])

# --- template: no placeholder is left behind
out = render.build_html({"headline": "Test", "bullets": ["a"], "eyebrow": "E",
                         "handle": "@h", "meta": "m"}, 1080, 1350, 64, 62)
assert "{{" not in out, "unreplaced placeholder in the template"
# A long headline shrinks, otherwise it runs out of the card
big = render.build_html({"headline": "T" * 80, "bullets": []}, 1080, 1350, 64, 62)
assert "font-size:40px" in big, "a long headline must be set smaller"

# --- styles: a project maps to its style, the CLI flag beats everything
render.LOCAL_STYLES = Path("/nonexistent")  # only the shipped styles, whatever is installed locally
assert render.pick_style("/home/you/projects/synagy-web") == "synagy"
assert render.pick_style("/tmp/some-other-project") == "default"
assert render.style_for({"style": "synagy"})[0] == "synagy"
assert render.style_for({"project": "/x/synagy"})[0] == "synagy"
assert render.style_for({"project": "/x/synagy"}, "default")[0] == "default"
assert render.load_style("synagy")["clip"], "synagy ships an animated clip"

# --- a local style folder adds styles and overrides shipped ones by name
with tempfile.TemporaryDirectory() as d:
    (Path(d) / "mine.json").write_text('{"match": ["my-app"], "vars": {"accent": "#f00"}}')
    render.LOCAL_STYLES = Path(d)
    assert render.pick_style("/x/my-app") == "mine"
    assert render.load_style("mine")["template"] == render.TEMPLATE
    render.LOCAL_STYLES = Path("/nonexistent")

# --- every style renders a complete card: no placeholder left, tokens injected
sample = {"headline": "H", "bullets": ["**a** b"], "eyebrow": "E", "meta": "m"}
for f in sorted((Path(__file__).parent / "styles").glob("*.json")):
    s = render.load_style(f.stem)
    out = render.build_html(sample, 1080, 1350, 64, 62, s)
    assert "{{" not in out, f"unreplaced placeholder in style {f.stem}"
    assert "--accent" in out, f"style {f.stem} defines no accent"
# The style supplies the handle when the post does not name one.
assert "synagy.games" in render.build_html(sample, 1080, 1350, 64, 62, render.load_style("synagy"))

# --- telegram config: comments skipped, quotes stripped
with tempfile.TemporaryDirectory() as d:
    f = Path(d) / "telegram.env"
    f.write_text('# comment\nTELEGRAM_BOT_TOKEN="123:abc"\nTELEGRAM_CHAT_ID=42\n')
    assert telegram.read_env(f) == {"TELEGRAM_BOT_TOKEN": "123:abc", "TELEGRAM_CHAT_ID": "42"}

# --- X caption: hashtags appended once, never doubled; clip beats card
assert post_x.caption({"captions": {"x": "New #game"}, "hashtags": ["#game", "#indie"]}) == "New #game\n\n#indie"
assert post_x.caption({"headline": "only"}) == "only"
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    assert post_x.media(d) is None
    (d / "card.png").write_bytes(b""); assert post_x.media(d).name == "card.png"
    (d / "clip.mp4").write_bytes(b""); assert post_x.media(d).name == "clip.mp4"

print("all checks green")
