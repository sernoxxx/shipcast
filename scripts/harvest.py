#!/usr/bin/env python3
"""A project's Claude Code logs + git commits -> a compact markdown digest.

Collects only, judges nothing. What becomes a post is Claude's call.
"""
import argparse, json, os, re, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render  # only for pick_style

def since_dt(s):
    m = re.fullmatch(r"(\d+)([dhw])", s.strip())
    if not m:
        raise SystemExit(f"--since: '{s}' — expected e.g. 7d, 24h, 2w")
    hours = int(m.group(1)) * {"h": 1, "d": 24, "w": 168}[m.group(2)]
    return datetime.now(timezone.utc) - timedelta(hours=hours)

# Anything that looks like a key: long unbroken strings plus the known token prefixes.
# The digest ends up in a public post — better one word too many redacted than a key in
# the feed.
SECRETISH = re.compile(r"(?:sk-|ghp_|gho_|github_pat_|xox[abpsr]-|ya29\.|EAA|AIza|glpat-)[A-Za-z0-9._-]{8,}"
                       r"|[A-Za-z0-9+/_-]{32,}={0,2}")

def scrub(text):
    """Strip everything from the digest that could be a credential."""
    return SECRETISH.sub("[redacted]", text)

def slug(path):
    """Project path -> folder name under ~/.claude/projects (every non-alphanumeric becomes '-')."""
    return re.sub(r"[^a-zA-Z0-9]", "-", str(path))

def session_files(project):
    """All transcripts of the project — including sessions from subfolders, because in a
    monorepo/vault Claude often runs one level deeper."""
    root = Path.home() / ".claude" / "projects"
    pref = slug(project)
    dirs = [d for d in root.glob(f"{pref}*") if d.is_dir()]
    return [f for d in dirs for f in d.glob("*.jsonl")]

def read_sessions(project, cutoff):
    out = []
    for f in sorted(session_files(project), key=lambda p: p.stat().st_mtime, reverse=True):
        if datetime.fromtimestamp(f.stat().st_mtime, timezone.utc) < cutoff:
            continue
        title, prompts, last = None, [], None
        for line in f.read_text(errors="replace").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            t = e.get("type")
            if t == "ai-title":
                title = e.get("aiTitle") or title
            elif t == "last-prompt":
                last = e.get("lastPrompt")
            elif t == "user" and not e.get("isMeta"):
                c = (e.get("message") or {}).get("content")
                if isinstance(c, str) and c.strip() and not c.lstrip().startswith("<"):
                    prompts.append(" ".join(c.split())[:220])
        out.append({"title": title, "date": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc)
                    .strftime("%Y-%m-%d"), "prompts": prompts[:8], "last": last})
    return out

def git(project, args):
    try:
        r = subprocess.run(["git", "-C", str(project)] + args, capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.getcwd(), help="project directory (default: cwd)")
    ap.add_argument("--since", default="7d", help="time window: 7d, 24h, 2w (default 7d)")
    ap.add_argument("--out", default="-", help="output file, or - for stdout")
    a = ap.parse_args()

    project = Path(a.project).resolve()
    cutoff = since_dt(a.since)
    iso = cutoff.strftime("%Y-%m-%d")

    style = render.pick_style(project)
    note = "" if style != "default" else "  (nothing matches this project — offer to create one)"
    L = [f"# Work digest: {project.name}", f"Window: since {iso} ({a.since})",
         f"Style: {style}{note}", ""]

    commits = git(project, ["log", f"--since={iso}", "--pretty=- %ad %s", "--date=short", "--no-merges"])
    L += ["## Commits", commits or "_none (no repo, or nothing committed)_", ""]

    files = git(project, ["log", f"--since={iso}", "--name-only", "--pretty=format:"])
    if files:
        top = {}
        for f in files.splitlines():
            if f.strip():
                top[f] = top.get(f, 0) + 1
        ranked = sorted(top.items(), key=lambda kv: -kv[1])[:15]
        L += ["## Most touched", *[f"- {f} ({n}x)" for f, n in ranked], ""]

    sessions = read_sessions(project, cutoff)
    L.append("## Claude Code sessions")
    if not sessions:
        L.append("_no sessions in this window_")
    for s in sessions:
        L.append(f"\n### {s['date']} — {s['title'] or 'untitled'}")
        L += [f"- {p}" for p in s["prompts"]]
    L.append("")

    text = scrub("\n".join(L))
    if a.out == "-":
        sys.stdout.write(text)
    else:
        Path(a.out).write_text(text)
        print(f"written: {a.out} ({len(text)} chars)")

if __name__ == "__main__":
    main()
