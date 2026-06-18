import json

from dovetail.hook import author_context, finish_context


# ---- author_context (PreToolUse) ----

def test_author_cue_fires_on_nontrivial_code_write():
    ctx = author_context({
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/app/calc.py", "content": "for i in items:\n    work(i)\n"},
    })
    assert ctx is not None
    assert "runtime-cost" in ctx or "Loop" in ctx
    assert "Advisory" in ctx  # preamble present


def test_author_cue_silent_on_trivial_edit():
    ctx = author_context({
        "tool_name": "Edit",
        "tool_input": {"file_path": "/repo/app/calc.py", "old_string": "x", "new_string": ")"},
    })
    assert ctx is None


def test_author_cue_silent_on_unknown_tool():
    assert author_context({"tool_name": "Bash", "tool_input": {"command": "ls"}}) is None


def test_author_cue_silent_on_malformed_payload():
    assert author_context("not a dict") is None
    assert author_context({"tool_name": "Edit", "tool_input": None}) is None


def test_author_cue_silent_on_non_code_file_even_with_trigger_prose():
    # A markdown doc mentioning "DELETE FROM" is prose, not code — must stay silent.
    ctx = author_context({
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/README.md", "content": "Run DELETE FROM users to reset.\n"},
    })
    assert ctx is None


def test_author_cue_includes_reuse_on_new_file(tmp_path):
    target = tmp_path / "brand_new.py"  # does not exist → is_new_file
    ctx = author_context({
        "tool_name": "Write",
        "tool_input": {"file_path": str(target), "content": "def helper():\n    return compute()\n"},
    })
    assert ctx is not None
    assert "survey" in ctx  # reuse cue


# ---- finish_context (Stop) ----

def _write_transcript(tmp_path, records):
    p = tmp_path / "transcript.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return str(p)


def _assistant_tool_use(name, tool_input):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": tool_input},
    ]}}


def test_finish_silent_when_stop_hook_active():
    assert finish_context({"stop_hook_active": True, "transcript_path": "/nope"}) is None


def test_finish_silent_when_transcript_missing():
    assert finish_context({"transcript_path": "/does/not/exist.jsonl"}) is None


def test_finish_fires_when_turn_wrote_code(tmp_path):
    tp = _write_transcript(tmp_path, [
        {"type": "user", "message": {"content": "add a charge function"}},
        _assistant_tool_use("Edit", {
            "file_path": "/repo/app/billing.py",
            "old_string": "pass",
            "new_string": "def charge(user):\n    return sum(i.price for i in user.cart)\n",
        }),
    ])
    ctx = finish_context({"transcript_path": tp, "stop_hook_active": False})
    assert ctx is not None
    assert "sweep" in ctx and "stranger" in ctx


def test_finish_silent_when_no_code_changed_this_turn(tmp_path):
    tp = _write_transcript(tmp_path, [
        {"type": "user", "message": {"content": "what does this do?"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "It charges users."}]}},
    ])
    assert finish_context({"transcript_path": tp, "stop_hook_active": False}) is None


def test_finish_appends_structural_when_new_class_introduced(tmp_path):
    tp = _write_transcript(tmp_path, [
        {"type": "user", "message": {"content": "add a gateway"}},
        _assistant_tool_use("Write", {
            "file_path": "/repo/app/gateway.py",
            "content": "class PaymentGateway:\n    def charge(self):\n        ...\n",
        }),
    ])
    ctx = finish_context({"transcript_path": tp, "stop_hook_active": False})
    assert ctx is not None
    assert "Structural" in ctx


def test_finish_ignores_edits_before_last_user_record(tmp_path):
    # An edit in a PRIOR turn must not make THIS (question-only) turn fire.
    tp = _write_transcript(tmp_path, [
        {"type": "user", "message": {"content": "first task"}},
        _assistant_tool_use("Write", {"file_path": "/repo/a.py", "content": "for x in y:\n    go(x)\n"}),
        {"type": "user", "message": {"content": "thanks, now explain it"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Sure."}]}},
    ])
    assert finish_context({"transcript_path": tp, "stop_hook_active": False}) is None
