"""Marathon-transcript safety: the Stop hook reads only a bounded tail of the
transcript (they reach tens of MB in long sessions and the hook runs on EVERY
stop), but must fall back to a full read when the tail contains no human
message — otherwise a long tool-heavy turn would lose its boundary and the
finish cue would go silently vacuous again."""

import json

import dovetail.hook as hook
from dovetail.hook import finish_context
from tests.test_real_transcript import (
    CODE,
    _assistant_edit,
    _assistant_text,
    _human,
    _tool_result,
    _write_transcript,
)


def test_tail_window_falls_back_to_full_read_when_no_human_in_tail(
    tmp_path, monkeypatch
):
    """Human boundary early, then a long tool-result run pushing it outside a
    tiny tail budget: the fallback full read must still find the edit."""
    records = [_human("fix the loader"), _assistant_edit("/repo/src/loader.py", CODE)]
    records += [_tool_result(f"toolu_{i}") for i in range(50)]
    records += [_assistant_text()]
    path = _write_transcript(tmp_path, records)
    monkeypatch.setattr(hook, "_TAIL_BYTES", 200)
    cue = finish_context({"transcript_path": path, "stop_hook_active": False})
    assert cue is not None and "[dovetail] Finish check" in cue


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
