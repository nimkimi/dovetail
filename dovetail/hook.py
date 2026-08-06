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


def author_context(payload: object) -> "str | None":
    """PreToolUse → the advisory cue to inject, or None to stay silent."""
    if not isinstance(payload, dict):
        return None
    change = parse_change(payload.get("tool_name", ""), payload.get("tool_input"))
    if change is None:
        return None
    # Out of lane (docs / data / lockfiles): never cue, even if a trigger pattern
    # happens to appear in prose.
    if not is_watched_file(change.file_path):
        return None
    triggers = detect_triggers(change.added_text, change.file_path)
    if change.is_new_file and "reuse" not in triggers:
        triggers.append("reuse")
    # Cosmetic edit with nothing high-signal → silent (proportional-first).
    if is_trivial(change.added_text, change.file_path) and not triggers:
        return None
    return build_author_cue(triggers)


# Transcripts grow to tens of MB in marathon sessions and the Stop hook runs on
# EVERY stop — read only this much of the file's tail. When the turn boundary
# (last user record) isn't inside it, finish_context bails silently rather
# than falling back to an unbounded read: a turn this large already got one
# advisory nudge's worth of value long ago.
_TAIL_BYTES = 1 * 1024 * 1024


def _load_jsonl(path: str, tail_bytes: "int | None" = None) -> list:
    records = []
    try:
        with open(path, encoding="utf-8") as f:
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


def _turn_edits(records: list) -> "list[tuple[str, dict]]":
    """(name, input) for each Edit/Write tool_use after the last user record."""
    last_user = -1
    for i, record in enumerate(records):
        if record.get("type") == "user":
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


def finish_context(payload: object) -> "str | None":
    """Stop → the finish nudge to inject, or None to stay silent."""
    if not isinstance(payload, dict):
        return None
    if payload.get("stop_hook_active"):  # loop guard — already re-prompted once
        return None
    transcript_path = payload.get("transcript_path")
    if not transcript_path or not os.path.exists(transcript_path):
        return None
    records = _load_jsonl(transcript_path, tail_bytes=_TAIL_BYTES)
    if not any(r.get("type") == "user" for r in records):
        # The turn boundary fell outside the tail window — bail rather than
        # pay for an unbounded full-file read.
        return None
    wrote_code = False
    structural = False
    for name, tool_input in _turn_edits(records):
        change = parse_change(name, tool_input)
        if change is None or not is_watched_file(change.file_path):
            continue
        triggers = detect_triggers(change.added_text, change.file_path)
        if triggers or not is_trivial(change.added_text, change.file_path):
            wrote_code = True
        if is_structural(change.added_text):
            structural = True
    if not wrote_code:
        return None
    return build_finish_cue(structural)
