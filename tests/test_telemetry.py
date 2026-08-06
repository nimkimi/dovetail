"""Fire-rate telemetry: every hook evaluation appends one JSONL record locally
so cue-weight tuning (banner-blindness) runs on measured fire rates instead of
vibes. Telemetry must never break a hook: any logging failure is swallowed."""

import json
import os

import dovetail.log as dlog
from dovetail.hook import author_decision, finish_decision


PAYLOAD_CUE = {
    "tool_name": "Write",
    "tool_input": {
        "file_path": "/repo/src/loader.py",
        "content": "import json\nfor item in items:\n    rows.append(json.loads(item))",
    },
}
PAYLOAD_OUT_OF_LANE = {
    "tool_name": "Write",
    "tool_input": {"file_path": "/repo/notes.md", "content": "for x in y: pass"},
}


def test_author_decision_returns_context_and_meta():
    context, meta = author_decision(PAYLOAD_CUE)
    assert context is not None
    assert meta["decision"] == "cue"
    assert "runtime-cost" in meta["triggers"]
    assert meta["ext"] == "py"


def test_author_decision_silent_out_of_lane():
    context, meta = author_decision(PAYLOAD_OUT_OF_LANE)
    assert context is None
    assert meta["decision"] == "silent"
    assert meta["reason"] == "out-of-lane"


def test_log_event_appends_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("DOVETAIL_LOG_DIR", str(tmp_path))
    dlog.log_event("author", {"decision": "cue", "triggers": ["reuse"], "ext": "py"})
    dlog.log_event("stop", {"decision": "silent", "reason": "no-code"})
    lines = (tmp_path / "fire-log.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["surface"] == "author" and first["decision"] == "cue"
    assert "ts" in first


def test_log_event_never_raises(monkeypatch):
    monkeypatch.setenv("DOVETAIL_LOG_DIR", "/dev/null/nope")
    dlog.log_event("author", {"decision": "cue"})  # must not raise


def test_finish_decision_meta(tmp_path):
    path = tmp_path / "t.jsonl"
    records = [
        {"type": "user", "message": {"role": "user", "content": "go"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Write",
                        "input": PAYLOAD_CUE["tool_input"],
                    }
                ],
            },
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    context, meta = finish_decision(
        {"transcript_path": str(path), "stop_hook_active": False}
    )
    assert context is not None
    assert meta["decision"] == "cue" and meta["structural"] is False


def test_summarize_counts_by_surface_and_trigger():
    from dovetail.report import summarize

    records = [
        {"surface": "author", "decision": "cue", "triggers": ["reuse", "runtime-cost"]},
        {"surface": "author", "decision": "silent", "reason": "trivial"},
        {"surface": "author", "decision": "cue", "triggers": ["reuse"]},
        {"surface": "stop", "decision": "cue", "triggers": []},
    ]
    s = summarize(records)
    assert s["author"]["evaluations"] == 3
    assert s["author"]["cues"] == 2
    assert s["author"]["triggers"]["reuse"] == 2
    assert s["stop"]["cues"] == 1
