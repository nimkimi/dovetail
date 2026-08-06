"""Regression tests for the Stop hook against REAL Claude Code transcript shapes.

The v0.1.0 fixtures were hand-authored and encoded a wrong shared assumption:
that only human messages have type "user". In real transcripts, TOOL RESULTS
also arrive as type "user" records (role user, content list holding a
tool_result block). With the old parsing, the "last user record" always landed
on the last tool result, the scan window shrank to the final text-only
assistant message, and finish_context returned None on every tool-using turn —
the Stop cue was vacuous in production from install (2026-06-18) until this
fix. Verified against a real transcript on 2026-07-11: 27 Edit/Write tool_use
records, finish_context -> None.

Record shapes below are derived from a real session transcript (the
real-sample-fixtures rule): a human record's message.content is a plain STRING
(or a list of non-tool_result blocks); a tool-result record's message.content
is a list containing a {"type": "tool_result"} block.
"""

import json

from dovetail.hook import finish_context


def _human(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def _tool_result(tool_use_id="toolu_01"):
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_use_id, "content": "ok"}
            ],
        },
    }


def _assistant_edit(file_path, new_string):
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Making the change."},
                {
                    "type": "tool_use",
                    "name": "Edit",
                    "input": {"file_path": file_path, "new_string": new_string},
                },
            ],
        },
    }


def _assistant_text(text="Done."):
    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


CODE = "import json\nfor item in items:\n    rows.append(json.loads(item))"


def _write_transcript(tmp_path, records):
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return str(path)


def test_finish_fires_when_tool_results_follow_the_edit(tmp_path):
    """The real-turn shape: human ask -> assistant edits -> TOOL RESULT comes
    back as a type-user record -> assistant wraps up. The tool_result record
    must NOT reset the turn boundary."""
    records = [
        _human("please fix the loader"),
        _assistant_edit("/repo/src/loader.py", CODE),
        _tool_result(),
        _assistant_text(),
    ]
    path = _write_transcript(tmp_path, records)
    cue = finish_context({"transcript_path": path, "stop_hook_active": False})
    assert cue is not None and "[dovetail] Finish check" in cue


def test_edits_before_the_last_human_message_do_not_count(tmp_path):
    """Turn scoping still holds: an edit in a PRIOR turn (before the latest
    human message) must not trigger the finish cue for this turn."""
    records = [
        _human("please fix the loader"),
        _assistant_edit("/repo/src/loader.py", CODE),
        _tool_result(),
        _assistant_text(),
        _human("thanks! now just answer a question, no code"),
        _assistant_text("Here is the answer."),
    ]
    path = _write_transcript(tmp_path, records)
    assert finish_context({"transcript_path": path, "stop_hook_active": False}) is None


def test_human_message_with_list_content_is_a_turn_boundary(tmp_path):
    """Human records sometimes carry list content (text blocks) — still a
    boundary, as long as no block is a tool_result."""
    records = [
        _human([{"type": "text", "text": "old turn"}]),
        _assistant_edit("/repo/src/old.py", CODE),
        _tool_result(),
        _human([{"type": "text", "text": "new turn, prose only please"}]),
        _assistant_text(),
    ]
    path = _write_transcript(tmp_path, records)
    assert finish_context({"transcript_path": path, "stop_hook_active": False}) is None
