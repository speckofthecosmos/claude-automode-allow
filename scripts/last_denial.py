#!/usr/bin/env python3
"""Print the most recent auto-mode classifier denials for the current project.

Reads the Claude Code session transcripts for the working directory
(~/.claude/projects/<cwd-slug>/*.jsonl) and, unless --main-only, the
subagent transcripts of those sessions
(~/.claude/projects/<cwd-slug>/<session>/subagents/agent-<id>.jsonl, with the
Agent-tool description in the sibling agent-<id>.meta.json), finds every tool_result the
classifier denied, pairs each with the tool_use it answered, and prints the
newest ones: timestamp, session, rule tag, tool, description and input.

Nothing is written. Credentials never appear here: the input printed is the
command or arguments the agent sent, which is what the classifier judged.

Usage: python3 last_denial.py [-n N] [--json] [--main-only]
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

DENIAL_PREFIX = "Permission for this action was denied by the Claude Code auto mode classifier"
TAG_RE = re.compile(r"Reason: \[([^\]]+)\]")


def project_dir(cwd):
    """Claude Code names the project dir by the cwd with every '/' turned into '-'."""
    slug = cwd.replace("/", "-")
    return Path.home() / ".claude" / "projects" / slug


def iter_rows(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def blocks(row):
    content = row.get("message", {}).get("content")
    return content if isinstance(content, list) else []


def subagent_meta(path):
    """Return (session_id, description) for a subagents/agent-<id>.jsonl path."""
    session = path.parent.parent.name
    desc = None
    try:
        with open(path.with_suffix(".meta.json"), encoding="utf-8") as fh:
            desc = json.load(fh).get("description")
    except (OSError, ValueError):
        pass
    return session, desc


def collect(paths):
    denials = []
    for path in paths:
        is_sub = path.parent.name == "subagents"
        if is_sub:
            session, agent_desc = subagent_meta(path)
            origin = f"subagent {path.stem.removeprefix('agent-')[:8]}"
        else:
            session, agent_desc, origin = path.stem, None, "main"
        uses = {}
        for row in iter_rows(path):
            for b in blocks(row):
                if b.get("type") == "tool_use":
                    uses[b.get("id")] = b
                elif b.get("type") == "tool_result":
                    text = b.get("content")
                    if isinstance(text, list):
                        text = " ".join(x.get("text", "") for x in text if isinstance(x, dict))
                    if not isinstance(text, str) or not text.startswith(DENIAL_PREFIX):
                        continue
                    use = uses.get(b.get("tool_use_id"), {})
                    m = TAG_RE.search(text)
                    denials.append({
                        "timestamp": row.get("timestamp"),
                        "session": session,
                        "origin": origin,
                        "agent_description": agent_desc,
                        "tag": m.group(1) if m else None,
                        "tool": use.get("name"),
                        "description": (use.get("input") or {}).get("description"),
                        "input": use.get("input"),
                    })
    denials.sort(key=lambda d: d["timestamp"] or "")
    return denials


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", type=int, default=3, help="how many recent denials to show (default 3)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--cwd", default=os.getcwd(), help="project directory (default: current)")
    ap.add_argument("--main-only", action="store_true", help="skip subagent transcripts (the pre-2026-10-07 behaviour)")
    args = ap.parse_args()

    pdir = project_dir(os.path.abspath(args.cwd))
    paths = sorted(pdir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
    if not args.main_only:
        subs = []
        for main in paths:
            sdir = pdir / main.stem / "subagents"
            if sdir.is_dir():
                subs.extend(sdir.glob("*.jsonl"))
        paths = paths + subs
    if not paths:
        sys.exit(f"no transcripts under {pdir}")

    denials = collect(paths)[-args.n:]
    if not denials:
        sys.exit("no classifier denials found in the recent transcripts for this project")

    if args.json:
        print(json.dumps(denials, indent=2))
        return

    for d in reversed(denials):
        print(f"=== {d['timestamp']}  session {d['session'][:8]}  {d['origin']}  [{d['tag']}]  tool={d['tool']}")
        if d["agent_description"]:
            print(f"    subagent: {d['agent_description']}")
        if d["description"]:
            print(f"    description: {d['description']}")
        inp = d["input"] or {}
        for key, val in inp.items():
            if key == "description":
                continue
            val = val if isinstance(val, str) else json.dumps(val)
            val = val if len(val) <= 600 else val[:600] + " …"
            print(f"    {key}: {val}")
        print()


if __name__ == "__main__":
    main()
