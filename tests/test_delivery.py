"""Novelty-weighted delivery: the always-on block is teaching material — full on
a context's FIRST cue, compressed to one line on repeats (trigger lines are
edit-specific signal and always appear). Keyed per transcript_path so every
fresh subagent context gets the full cue once (subagents have their own
transcript files). Measured motive: 77 cues / 108 evaluations on day one — the
identical ~1.2KB block repeated is wallpaper; the varying trigger lines are
what a consumer notices."""

import time as _time

import dovetail.state as dstate
from dovetail.cues import ALWAYS_ON, PREAMBLE
from dovetail.hook import author_decision


def _payload(
    transcript,
    agent_id=None,
    content="import json\nfor item in items:\n    rows.append(json.loads(item))",
):
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/loader.py", "content": content},
        "transcript_path": transcript,
    }
    if agent_id is not None:
        payload["agent_id"] = agent_id
    return payload


def test_first_cue_is_full_then_compressed(tmp_path, monkeypatch):
    monkeypatch.setenv("DOVETAIL_STATE_DIR", str(tmp_path))
    transcript = "/sessions/main.jsonl"

    first, meta1 = author_decision(_payload(transcript))
    assert ALWAYS_ON in first and meta1["delivery"] == "full"

    second, meta2 = author_decision(_payload(transcript))
    assert ALWAYS_ON not in second and meta2["delivery"] == "compressed"
    assert PREAMBLE in second
    assert "Loop / query / fetch" in second  # trigger lines always appear
    assert "shown in full earlier" in second  # one-line stand-in for the core


def test_subagent_gets_full_cue_despite_main_context_state(tmp_path, monkeypatch):
    """Measured harness reality (2026-07-11 payload capture): subagents receive
    the PARENT's transcript_path but carry their own agent_id — the context key
    must include it, or every fresh implementer is starved of the full cue."""
    monkeypatch.setenv("DOVETAIL_STATE_DIR", str(tmp_path))
    author_decision(_payload("/sessions/main.jsonl"))  # main consumes the full cue

    cue, meta = author_decision(_payload("/sessions/main.jsonl", agent_id="agent-a1"))
    assert ALWAYS_ON in cue and meta["delivery"] == "full"

    cue2, meta2 = author_decision(_payload("/sessions/main.jsonl", agent_id="agent-a1"))
    assert ALWAYS_ON not in cue2 and meta2["delivery"] == "compressed"

    cue3, meta3 = author_decision(_payload("/sessions/main.jsonl", agent_id="agent-b2"))
    assert ALWAYS_ON in cue3 and meta3["delivery"] == "full"


def test_different_sessions_are_distinct_contexts(tmp_path, monkeypatch):
    monkeypatch.setenv("DOVETAIL_STATE_DIR", str(tmp_path))
    author_decision(_payload("/sessions/main.jsonl"))
    cue, meta = author_decision(_payload("/sessions/other.jsonl"))
    assert ALWAYS_ON in cue and meta["delivery"] == "full"


def test_no_transcript_path_means_full_and_stateless(tmp_path, monkeypatch):
    """Payloads without a transcript_path can't be keyed — always full, and no
    state file is written."""
    monkeypatch.setenv("DOVETAIL_STATE_DIR", str(tmp_path))
    payload = _payload(None)
    del payload["transcript_path"]
    cue, meta = author_decision(payload)
    assert ALWAYS_ON in cue and meta["delivery"] == "full"
    cue2, meta2 = author_decision(payload)
    assert ALWAYS_ON in cue2 and meta2["delivery"] == "full"
    assert list(tmp_path.iterdir()) == []


def test_full_cue_reshown_after_refresh_window(tmp_path, monkeypatch):
    """Marathon insurance: after the refresh window (context may have compacted
    away the earlier cue), the full block is shown again."""
    monkeypatch.setenv("DOVETAIL_STATE_DIR", str(tmp_path))
    transcript = "/sessions/main.jsonl"
    author_decision(_payload(transcript))
    monkeypatch.setattr(
        dstate, "_now", lambda: _time.time() + dstate.REFRESH_SECONDS + 60
    )
    cue, meta = author_decision(_payload(transcript))
    assert ALWAYS_ON in cue and meta["delivery"] == "full"


def test_state_failure_degrades_to_full_cue(monkeypatch):
    """The advisory contract outranks dampening: unusable state dir → full cue,
    no exception."""
    monkeypatch.setenv("DOVETAIL_STATE_DIR", "/dev/null/nope")
    cue, meta = author_decision(_payload("/sessions/main.jsonl"))
    assert ALWAYS_ON in cue and meta["delivery"] == "full"


def test_stale_state_files_are_cleaned(tmp_path, monkeypatch):
    monkeypatch.setenv("DOVETAIL_STATE_DIR", str(tmp_path))
    stale = tmp_path / "deadbeef.json"
    stale.write_text("{}")
    old = _time.time() - dstate.STALE_SECONDS - 60
    import os

    os.utime(stale, (old, old))
    author_decision(_payload("/sessions/main.jsonl"))
    assert not stale.exists()
