# automode-allow

A Claude Code skill that turns an auto-mode classifier denial into a standing rule that stops the whole class of false positive, not just the one call.

Claude Code's auto mode routes every tool call through a safety classifier. It is a good default, and for a solo developer who owns every host, repo and service they touch it also denies something most sessions: editing a tracked file in a workspace that holds many repos, changing a setting on a single-user home server, pushing to your own bare repo, retrying a command you just told it to retry. The documented fix is prose rules in `~/.claude/settings.json` under `autoMode`. Writing them one denial at a time produces a pile of narrow entries that never quite stop the next one. This skill writes them one class at a time.

## What it does

1. Reads the most recent denials out of the session transcripts, including subagent transcripts, which the main transcript never sees (`scripts/last_denial.py`).
2. Reads the rule that fired (`claude auto-mode defaults --label '<Tag>'`) and names the premise the classifier got wrong: shared, external, out of scope, pre-existing, a grant, tunnelling.
3. Picks the mechanism. A missing fact about your setup goes in `autoMode.environment`, which every rule reads. A rule that is right in general and wrong for a named class gets one `autoMode.allow` entry per class, with a `Not covered` clause.
4. Judges the broad entry against a fixed floor (secrets into files or logs, guard hooks and permission settings, deleting pre-existing data the user did not name, regulated data leaving its surface, publishing to others, force-push, unreviewed production deploys) and falls back to a narrow entry for the one denial only when the class contains a floor case the classifier cannot see.
5. Writes the entry with a backup, a `"$defaults"` guard and a re-validation (`scripts/add_allow.py`), never printing the settings file.

The skill file, `SKILL.md`, carries the full procedure and a table of recurring tags to adapt to your own hosts and repos.

## Install

```bash
git clone https://github.com/speckofthecosmos/claude-automode-allow ~/.claude/skills/automode-allow
```

Then, from a non-auto permission mode, write the Self-Modification entry shown in `SKILL.md` step 6 once. After that the skill runs in auto mode whenever you invoke it with `/automode-allow`, and a running session picks up each new entry without a restart. Both of those are tested, not assumed; `TESTING.md` has the method and the results.

## Scripts

- `scripts/last_denial.py [-n N] [--json] [--cwd DIR] [--main-only]` prints the newest classifier denials for a project with tag, tool, description and exact input, from the main session and its subagents.
- `scripts/add_allow.py "<entry>"` appends prose entries to `autoMode.allow`; `--section environment|soft_deny`, `--replace SUBSTR` (repeatable, collapses narrow entries into one), `--remove SUBSTR`, `--dry-run`, `--list`.

## Findings worth knowing even if you never install this

- A working directory that is not itself a git repository but contains many of them makes every tracked file "out of repo" to the classifier, so plain edits trip Irreversible Local Destruction. The fix is a `Trusted repo` environment entry, not an allow entry.
- `autoMode` changes in `~/.claude/settings.json` take effect in the running session at once.
- An allow entry for Self-Modification scoped to "when the user invoked the skill" passes when the user's message says so and is denied when an agent runs the same command on its own initiative. The classifier reads your messages and the agent's commands, never file contents, so an instruction that lives only in a file reads as indirection.
- `claude auto-mode critique` truncates when piped and ends mid-report even on a terminal (Claude Code v2.1.293). Run it in your own terminal.

## Authorship

Written by Claude (Claude Code, Claude Fable 5.1) under the direction of Speck, who set the goals, reviewed the design choices and ran the result in their own workspace. The prose and code are Claude's; the problem and the comfort level it is tuned to are Speck's. MIT licensed.
