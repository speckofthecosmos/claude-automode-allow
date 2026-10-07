#!/usr/bin/env python3
"""Append prose entries to autoMode.allow or autoMode.environment in ~/.claude/settings.json.

The classifier reads autoMode only from the USER settings file, so that is
the only file this touches. The file holds credential literals inside
permission entries, so nothing here prints its contents: output is key
names, list lengths and the entries added or removed.

Steps: back up to ~/.claude/backups/settings.json.<UTC stamp>.bak, load,
make sure the target list exists and starts with "$defaults" (without it the
built-in list is replaced, not extended), drop each existing entry that
contains a --replace substring (so one class entry supersedes the narrow
ones it widens), append each entry that is not already present, write
back with the file's own indent, re-parse, and check every top-level key
survived.

Usage: python3 add_allow.py "<entry>" ["<entry>" ...]
       python3 add_allow.py --section environment "<entry>"
       python3 add_allow.py --replace "<substring of old entry>" [--replace "<another>"] "<entry>"
       python3 add_allow.py --remove "<substring of old entry>"
       python3 add_allow.py --dry-run "<entry>"
       python3 add_allow.py --list [--section environment]
"""
import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SETTINGS = Path.home() / ".claude" / "settings.json"
BACKUPS = Path.home() / ".claude" / "backups"
SECTIONS = ("allow", "environment", "soft_deny")


def detect_indent(text):
    m = re.search(r"\n([ \t]+)\S", text)
    return m.group(1) if m else "  "


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entries", nargs="*", help="prose rules to append")
    ap.add_argument("--section", choices=SECTIONS, default="allow",
                    help="which autoMode list to write (default: allow)")
    ap.add_argument("--replace", metavar="SUBSTRING", action="append", default=[],
                    help="remove the one existing entry containing this substring before appending; "
                         "repeatable, so several narrow entries can collapse into one class entry")
    ap.add_argument("--remove", metavar="SUBSTRING", action="append", default=[],
                    help="remove the one existing entry containing this substring; needs no new entry")
    ap.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    ap.add_argument("--list", action="store_true", help="print the section's current entries and exit")
    args = ap.parse_args()

    text = SETTINGS.read_text(encoding="utf-8")
    data = json.loads(text)
    before_keys = sorted(data)
    auto = data.setdefault("autoMode", {})
    target = auto.setdefault(args.section, [])

    if args.list:
        print(f"autoMode.{args.section} has {len(target)} entries:")
        for e in target:
            print(f"  - {e}")
        return
    if not args.entries and not args.remove:
        ap.error("give at least one entry, --remove, or --list")

    changed = []
    if "$defaults" not in target:
        target.insert(0, "$defaults")
        changed.append("+ $defaults")

    for sub in args.replace + args.remove:
        hits = [e for e in target if e != "$defaults" and sub in e]
        if len(hits) != 1:
            sys.exit(f"--replace/--remove {sub!r} must match exactly one entry; matched {len(hits)}")
        target.remove(hits[0])
        changed.append(f"- {hits[0]}")

    for entry in args.entries:
        entry = entry.strip()
        if not entry:
            continue
        if entry in target:
            print(f"already present, skipped: {entry}")
            continue
        target.append(entry)
        changed.append(f"+ {entry}")

    print(f"top-level keys: {len(before_keys)}; autoMode.{args.section} length: {len(target)}")
    for c in changed:
        print(f"  {c}")
    if not changed:
        print("nothing to change")
        return
    if args.dry_run:
        print("dry run: file not written")
        return

    BACKUPS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = BACKUPS / f"settings.json.{stamp}.bak"
    shutil.copy2(SETTINGS, backup)

    out = json.dumps(data, indent=detect_indent(text), ensure_ascii=False) + "\n"
    SETTINGS.write_text(out, encoding="utf-8")

    check = json.loads(SETTINGS.read_text(encoding="utf-8"))
    missing = set(before_keys) - set(check)
    if missing or check["autoMode"][args.section] != target:
        sys.exit(f"validation failed (missing keys: {sorted(missing)}); restore from {backup}")
    print(f"written; backup at {backup}")
    print("next: run `claude auto-mode config` and confirm the entry appears, then `claude auto-mode critique`")


if __name__ == "__main__":
    main()
