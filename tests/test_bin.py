"""End-to-end: pipe real sample stdin through the hook entrypoints and assert
the advisory JSON contract + exit 0 on every path."""

import json
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin"


def run_hook(script, stdin_text):
    return subprocess.run(
        [sys.executable, str(BIN / script)],
        input=stdin_text,
        capture_output=True,
        text=True,
    )


def context_of(stdout):
    if not stdout.strip():
        return None
    return json.loads(stdout)["hookSpecificOutput"]["additionalContext"]


# ---- PreToolUse ----

def test_pretool_emits_cue_on_loop_write():
    proc = run_hook("pretool.py", json.dumps({
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/app/calc.py", "content": "for i in items:\n    work(i)\n"},
    }))
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "Loop" in data["hookSpecificOutput"]["additionalContext"]


def test_pretool_silent_on_trivial_edit():
    proc = run_hook("pretool.py", json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": "/repo/app/calc.py", "old_string": "x", "new_string": ")"},
    }))
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_pretool_emits_dep_vet_on_manifest():
    proc = run_hook("pretool.py", json.dumps({
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/repo/package.json",
            "old_string": "{}",
            "new_string": '    "left-pad": "^1.3.0",',
        },
    }))
    assert proc.returncode == 0
    assert "typosquat" in context_of(proc.stdout)


def test_pretool_exit0_and_silent_on_malformed_json():
    proc = run_hook("pretool.py", "this is not json{")
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


# ---- Stop ----

def _transcript(tmp_path, records):
    p = tmp_path / "transcript.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return str(p)


def test_stop_emits_finish_when_turn_wrote_code(tmp_path):
    tp = _transcript(tmp_path, [
        {"type": "user", "message": {"content": "add it"}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Write",
             "input": {"file_path": "/repo/app/x.py", "content": "def f(xs):\n    return sum(i for i in xs)\n"}},
        ]}},
    ])
    proc = run_hook("stop.py", json.dumps({"transcript_path": tp, "stop_hook_active": False}))
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["hookSpecificOutput"]["hookEventName"] == "Stop"
    assert "sweep" in data["hookSpecificOutput"]["additionalContext"]


def test_stop_silent_when_no_code_changed(tmp_path):
    tp = _transcript(tmp_path, [{"type": "user", "message": {"content": "hi"}}])
    proc = run_hook("stop.py", json.dumps({"transcript_path": tp, "stop_hook_active": False}))
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_stop_silent_when_loop_guard_active():
    proc = run_hook("stop.py", json.dumps({"transcript_path": "/whatever", "stop_hook_active": True}))
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
