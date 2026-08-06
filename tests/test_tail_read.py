"""Marathon-transcript safety: the Stop hook reads only a bounded 1MB tail of
the transcript (they reach tens of MB in long sessions and the hook runs on
EVERY stop). When the tail contains no human boundary the turn is a giant one
that already got its advisory value long ago — the hook bails silently and
NEVER pays an unbounded full read; the bail is telemetered so the cap size is
tunable on measured fire rates."""

import json

import dovetail.hook as hook
from dovetail.hook import finish_context, finish_decision
from tests.test_real_transcript import (
    CODE,
    _assistant_edit,
    _assistant_text,
    _human,
    _tool_result,
    _write_transcript,
)


def test_tail_bytes_constant_is_1mb():
    assert hook._TAIL_BYTES == 1 * 1024 * 1024


def test_bails_silently_when_no_human_in_tail_and_never_reads_full_file(
    tmp_path, monkeypatch
):
    """Human boundary early, then a long tool-result run pushing it outside a
    tiny tail budget: silent bail, telemetered reason, and the full transcript
    is never read."""
    records = [_human("fix the loader"), _assistant_edit("/repo/src/loader.py", CODE)]
    records += [_tool_result(f"toolu_{i}") for i in range(50)]
    records += [_assistant_text()]
    path = _write_transcript(tmp_path, records)
    monkeypatch.setattr(hook, "_TAIL_BYTES", 200)

    calls = []
    real_load = hook._load_jsonl

    def spy(p, tail_bytes=None):
        calls.append(tail_bytes)
        if tail_bytes is None:
            raise AssertionError("finish must never read the full transcript")
        return real_load(p, tail_bytes=tail_bytes)

    monkeypatch.setattr(hook, "_load_jsonl", spy)

    cue, meta = finish_decision({"transcript_path": path, "stop_hook_active": False})
    assert cue is None
    assert meta == {"decision": "silent", "reason": "boundary-outside-tail"}
    assert calls == [200]


def test_tail_window_suffices_when_boundary_is_recent(tmp_path, monkeypatch):
    """Boundary and edit inside the tail: the bounded read alone answers, and a
    partial first line from the seek must not break parsing."""
    records = [_human("old turn " + "x" * 500), _assistant_text("old answer")]
    records += [
        _human("new turn: fix it"),
        _assistant_edit("/repo/src/loader.py", CODE),
        _tool_result(),
        _assistant_text(),
    ]
    path = _write_transcript(tmp_path, records)
    tail = len(json.dumps(records[-4])) + len(json.dumps(records[-3])) + len(
        json.dumps(records[-2])
    ) + len(json.dumps(records[-1])) + 40
    monkeypatch.setattr(hook, "_TAIL_BYTES", tail)
    cue = finish_context({"transcript_path": path, "stop_hook_active": False})
    assert cue is not None and "[dovetail] Finish check" in cue
