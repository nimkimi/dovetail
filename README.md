# dovetail

Automatic, preventive **code-quality cues** for Claude Code.

Passive CLAUDE.md rules decay: loaded at session start, they get buried as context
grows, so by the time Claude is deep in code they no longer bind. Every existing
tool is after-the-fact (`/code-review` = bugs, `/simplify` = quality cleanup).
dovetail re-surfaces the concerns *while* Claude writes — and only those no
after-the-fact tool covers.

Two **advisory** hooks (Python 3, stdlib only). They **never block, never edit,
never touch the network, and exit 0 on every path.**

- **PreToolUse (`Edit|Write`) — author-time cue.** Before a code change lands,
  injects a compact cue: the always-on core plus any *triggered* cue whose
  pattern is in the pending diff (dependency-vetting, blast-radius safety,
  breaking-change, secrets/trust-boundary, runtime-cost, survey-before-reuse).
  Silent on trivial / cosmetic / out-of-lane (docs, data, lockfiles) changes —
  proportional-first, to avoid banner-blindness.
- **Novelty-weighted delivery.** The full always-on block is teaching material:
  each context gets it ONCE (re-shown after 45 min — compaction insurance);
  repeats collapse it to a one-line stand-in while trigger lines (edit-specific
  signal) always appear. Context = `transcript_path + agent_id`: measured
  harness reality is that subagent hooks receive the PARENT's transcript_path
  but carry their own `agent_id`, so every fresh implementer subagent still
  gets the full cue once. (Motive: 71% measured fire rate on day one — the
  identical block repeated is wallpaper.) State: tiny per-context files under
  `~/.dovetail/state`; any state failure degrades to the full cue.
- **Stop — finish nudge.** When the turn actually wrote non-trivial code, injects
  one compact finish check (complete-the-change sweep — **naming the turn's
  touched in-lane files** as the concrete sweep list, re-read-as-a-stranger,
  tests-assert-edges) plus a one-line **structural-decision declaration** when a
  new module / boundary / data-shape appeared. Honours `stop_hook_active`;
  composes with the existing `test-claim-guard` Stop hook.
- **Reaches subagents.** PreToolUse cues fire inside subagent contexts too
  (verified live) — in orchestrated builds the implementers who write most of
  the code are cued, not just the controller.

## Layout

```
.claude-plugin/plugin.json   plugin manifest
hooks/hooks.json             hook wiring (python3 "${CLAUDE_PLUGIN_ROOT}/bin/...")
bin/pretool.py  bin/stop.py  thin stdin→stdout entrypoints (always exit 0)
dovetail/
  detect.py   triggers, is_trivial, is_watched_file, is_structural
  change.py   parse a PreToolUse tool_input → (file_path, added_text, is_new_file)
  cues.py     the cue payload (compact; < 2KB per injection)
  hook.py     orchestration (author/finish decisions + real-transcript parsing)
  state.py    per-context delivery state (full-once, compressed repeats)
  log.py      local fire-rate telemetry → ~/.dovetail/fire-log.jsonl
  report.py   summarize(records): per-surface fire rates + trigger counts
  signal.py   weekly tuning signals computed from the fire log (pure)
bin/weekly_signal.py         prints tuning signals; point any scheduler at it
tests/        115 tests — run: .venv/bin/python -m pytest -q
              (test dep lives in .venv; runtime stays stdlib-only.
               Setup once: python3 -m venv .venv && .venv/bin/pip install pytest)
```

## Telemetry

Every hook evaluation appends one metadata-only JSONL record (decision,
triggers, extension — never paths or content) to `~/.dovetail/fire-log.jsonl`
(override dir via `DOVETAIL_LOG_DIR`). This is the evidence base for tuning
cue weight against banner-blindness: measure real fire rates before changing
cue text. A 2026-07-11 control-vs-cue eval (20 reps) found ceiling effects on
focused scenarios — no basis to trim OR to prove lines load-bearing — so the
cue text stays until real-session fire rates say otherwise. Summarize with:
`python3 -c "import json,sys; sys.path.insert(0,'.'); from dovetail.report import summarize; print(json.dumps(summarize([json.loads(l) for l in open(__import__('os').path.expanduser('~/.dovetail/fire-log.jsonl'))]), indent=2))"`

## Install

From the repo's own marketplace, inside Claude Code:

```
/plugin marketplace add nimkimi/dovetail
/plugin install dovetail@dovetail
```

If the install summary asks for it, run `/reload-plugins`; hooks load on the
next session start in any case. Then make a real, non-trivial code edit and
confirm the cue appears (and that a trivial one stays silent). Update later
with `/plugin marketplace update dovetail`.

Manual alternative: clone the repo and wire the two commands straight into
`~/.claude/settings.json` `hooks` — PreToolUse matcher `Edit|Write` running
`python3 "<clone>/bin/pretool.py"`, and an unmatched Stop hook running
`python3 "<clone>/bin/stop.py"`. (`python3` invocation is deliberate: the
hooks don't depend on the exec bit surviving a sync.)

**Never keep both wirings.** Installed as a plugin AND wired in
`settings.json`, the same cues fire twice — pick one.

## Status

dovetail is personal tooling: it runs in all of my own Claude Code sessions
and its tuning follows my own fire-log telemetry. The repo is public to be
read and borrowed. MIT licensed — see [LICENSE](LICENSE).
