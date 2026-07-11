"""Orchestration for both hooks — pure functions over a parsed payload so the
`bin/` entrypoints stay thin stdin/stdout glue.

Both surfaces are ADVISORY: they return a context string or None, and the
entrypoints always exit 0. Nothing here blocks, edits, or touches the network.
"""

import json
import os

from dovetail.change import parse_change
from dovetail.cues import build_author_cue, build_finish_cue
from dovetail.detect import detect_triggers, is_structural, is_trivial, is_watched_file
from dovetail.state import mark_full_shown, should_compress


def _ext(file_path: str) -> str:
    basename = file_path.replace("\\", "/").rsplit("/", 1)[-1]
    return basename.rsplit(".", 1)[-1].lower() if "." in basename else ""


def author_decision(payload: object) -> "tuple[str | None, dict]":
    """PreToolUse → (advisory cue or None, telemetry meta). Meta carries the
    decision and its inputs (triggers, extension, silent reason) — never file
    contents or paths."""
    if not isinstance(payload, dict):
        return None, {"decision": "silent", "reason": "not-a-change"}
    change = parse_change(payload.get("tool_name", ""), payload.get("tool_input"))
    if change is None:
        return None, {"decision": "silent", "reason": "not-a-change"}
    # Out of lane (docs / data / lockfiles): never cue, even if a trigger pattern
    # happens to appear in prose.
    if not is_watched_file(change.file_path):
        return None, {"decision": "silent", "reason": "out-of-lane"}
    triggers = detect_triggers(change.added_text, change.file_path)
    if change.is_new_file and "reuse" not in triggers:
        triggers.append("reuse")
    ext = _ext(change.file_path)
    # Cosmetic edit with nothing high-signal → silent (proportional-first).
    if is_trivial(change.added_text, change.file_path) and not triggers:
        return None, {"decision": "silent", "reason": "trivial", "ext": ext}
    # Novelty-weighted delivery: the full always-on block teaches once per
    # context; repeats within the refresh window get the one-line stand-in.
    # Trigger lines always appear. Context key = transcript_path + agent_id:
    # measured harness reality (2026-07-11 payload capture) is that subagents
    # receive the PARENT's transcript_path but carry their own agent_id — key
    # on the pair or every fresh implementer is starved of the full cue.
    # Payloads without a transcript_path can't be keyed → always full, no state.
    transcript_path = payload.get("transcript_path")
    context_key = (
        f"{transcript_path}|{payload.get('agent_id') or ''}"
        if transcript_path
        else None
    )
    compressed = bool(context_key) and should_compress(context_key)
    if context_key and not compressed:
        mark_full_shown(context_key)
    return build_author_cue(triggers, compressed=compressed), {
        "decision": "cue",
        "triggers": triggers,
        "ext": ext,
        "delivery": "compressed" if compressed else "full",
        "new_file": change.is_new_file,
    }


def author_context(payload: object) -> "str | None":
    """PreToolUse → the advisory cue to inject, or None to stay silent."""
    return author_decision(payload)[0]


# Transcripts grow to tens of MB in marathon sessions and the Stop hook runs on
# EVERY stop — read only this much of the file's tail. The turn boundary (last
# human message) is almost always inside it; when it is not, the caller falls
# back to a full read so a long tool-heavy turn never loses its boundary.
_TAIL_BYTES = 16 * 1024 * 1024


def _load_jsonl(path: str, tail_bytes: "int | None" = None) -> list:
    records = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            if tail_bytes is not None:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size > tail_bytes:
                    f.seek(size - tail_bytes)
                    f.readline()  # drop the partial line the seek landed in
                else:
                    f.seek(0)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        return []
    return records


def _is_human_message(record: dict) -> bool:
    """True for a real human turn boundary. In real transcripts TOOL RESULTS
    also arrive as type "user" records (role user, content list holding a
    tool_result block) — counting those as boundaries made the Stop scan window
    collapse to the final text-only message, so the finish cue never fired on
    any tool-using turn (vacuous in production 2026-06-18 → 2026-07-11). A
    human record's content is a plain string, or a list with no tool_result
    block. Residual: system-injected user records (task notifications) still
    count as boundaries — an edit made before a mid-turn notification is
    missed; acceptable, the notification-triggered work itself is covered."""
    if record.get("type") != "user":
        return False
    content = record.get("message", {}).get("content")
    if isinstance(content, list):
        return not any(
            isinstance(block, dict) and block.get("type") == "tool_result"
            for block in content
        )
    return True


def _turn_edits(records: list) -> "list[tuple[str, dict]]":
    """(name, input) for each Edit/Write tool_use after the last HUMAN message
    (tool-result records are not turn boundaries — see _is_human_message)."""
    last_user = -1
    for i, record in enumerate(records):
        if _is_human_message(record):
            last_user = i
    edits = []
    for record in records[last_user + 1:]:
        if record.get("type") != "assistant":
            continue
        content = record.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("name") in ("Edit", "Write")
            ):
                edits.append((block.get("name"), block.get("input") or {}))
    return edits


def finish_decision(payload: object) -> "tuple[str | None, dict]":
    """Stop → (finish nudge or None, telemetry meta)."""
    if not isinstance(payload, dict):
        return None, {"decision": "silent", "reason": "bad-payload"}
    if payload.get("stop_hook_active"):  # loop guard — already re-prompted once
        return None, {"decision": "silent", "reason": "loop-guard"}
    transcript_path = payload.get("transcript_path")
    if not transcript_path or not os.path.exists(transcript_path):
        return None, {"decision": "silent", "reason": "no-transcript"}
    records = _load_jsonl(transcript_path, tail_bytes=_TAIL_BYTES)
    if not any(_is_human_message(r) for r in records):
        # The turn boundary fell outside the tail window — pay the full read
        # rather than silently mis-scoping the turn.
        records = _load_jsonl(transcript_path)
    wrote_code = False
    structural = False
    touched: "list[str]" = []  # in-lane basenames, deduped, turn order
    for name, tool_input in _turn_edits(records):
        change = parse_change(name, tool_input)
        if change is None or not is_watched_file(change.file_path):
            continue
        basename = change.file_path.replace("\\", "/").rsplit("/", 1)[-1]
        if basename not in touched:
            touched.append(basename)
        triggers = detect_triggers(change.added_text, change.file_path)
        if triggers or not is_trivial(change.added_text, change.file_path):
            wrote_code = True
        if is_structural(change.added_text):
            structural = True
    if not wrote_code:
        return None, {"decision": "silent", "reason": "no-code"}
    return build_finish_cue(structural, tuple(touched)), {
        "decision": "cue",
        "structural": structural,
        "files": len(touched),
    }


def finish_context(payload: object) -> "str | None":
    """Stop → the finish nudge to inject, or None to stay silent."""
    return finish_decision(payload)[0]
