# dovetail

Automatic, preventive **code-quality cues** for Claude Code — a personal plugin.

Passive CLAUDE.md rules decay: loaded at session start, they get buried as context
grows, so by the time Claude is deep in code they no longer bind. Every existing
tool is after-the-fact (`/code-review` = bugs, `/simplify` = quality cleanup).
dovetail re-surfaces the concerns *while* Claude writes — and only those no
after-the-fact tool covers.

Two **advisory** hooks (Python 3, stdlib only). They **never block, never edit,
never touch the network, and exit 0 on every path.**

- **PreToolUse (`Edit|Write`) — author-time cue.** Before a code change lands,
  injects a compact cue: a lean always-on core plus any *triggered* cue whose
  pattern is in the pending diff (dependency-vetting, blast-radius safety,
  breaking-change, secrets/trust-boundary, runtime-cost, survey-before-reuse).
  Silent on trivial / cosmetic / out-of-lane (docs, data, lockfiles) changes —
  proportional-first, to avoid banner-blindness.
- **Stop — finish nudge.** When the turn actually wrote non-trivial code, injects
  one compact finish check (complete-the-change sweep, re-read-as-a-stranger,
  tests-assert-edges) plus a one-line **structural-decision declaration** when a
  new module / boundary / data-shape appeared. Honours `stop_hook_active`;
  composes with the existing `test-claim-guard` Stop hook.

## Layout

```
.claude-plugin/plugin.json   plugin manifest
hooks/hooks.json             hook wiring (python3 "${CLAUDE_PLUGIN_ROOT}/bin/...")
bin/pretool.py  bin/stop.py  thin stdin→stdout entrypoints (always exit 0)
dovetail/
  detect.py   triggers, is_trivial, is_watched_file, is_structural
  change.py   parse a PreToolUse tool_input → (file_path, added_text, is_new_file)
  cues.py     the cue payload (compact; < 2KB per injection)
  hook.py     orchestration (author_context / finish_context)
tests/        83 tests — run: python3 -m pytest -q
```

## Install (local)

Load the directory as a local plugin in Claude Code, **or** wire the two commands
straight into `~/.claude/settings.json` `hooks` (PreToolUse matcher `Edit|Write`,
Stop unmatched) using absolute paths to `bin/pretool.py` / `bin/stop.py`. Restart
the session, then make a real non-trivial edit and confirm the cue appears (and a
trivial one stays silent).

## Sync

dovetail is personal env-tooling — it should ride the `~/.claude` sync
(claude-everywhere), not a published repo. Invoked via `python3 "...script"`
(not the exec bit) so it survives sync regardless of file-mode propagation.

## Design of record

`~/projects/private/project-ideas/projects/dovetail.md` (spec) +
`dovetail-adr-stack.md` (ADR + doc-verified hook contracts).
