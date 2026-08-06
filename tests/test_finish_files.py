"""The finish cue names the turn's touched in-lane files — a concrete sweep
list beats the generic instruction (finish_decision already parses exactly
this data). Also: author telemetry records new_file so the reuse-trigger
narrowing question can be decided from real data."""

import json

from dovetail.hook import author_decision, finish_decision

CODE = "import json\nfor item in items:\n    rows.append(json.loads(item))"


def _assistant_edit(file_path):
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "Edit",
                    "input": {"file_path": file_path, "new_string": CODE},
                }
            ],
        },
    }


def _transcript(tmp_path, file_paths):
    records = [{"type": "user", "message": {"role": "user", "content": "go"}}]
    records += [_assistant_edit(p) for p in file_paths]
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return str(path)


def test_finish_cue_names_touched_files(tmp_path):
    path = _transcript(
        tmp_path, ["/repo/src/hook.py", "/repo/src/cues.py", "/repo/notes.md"]
    )
    cue, meta = finish_decision({"transcript_path": path, "stop_hook_active": False})
    assert "hook.py" in cue and "cues.py" in cue
    assert "notes.md" not in cue  # out-of-lane files are not sweep targets
    assert meta["files"] == 2


def test_finish_cue_dedupes_and_caps_the_file_list(tmp_path):
    paths = [f"/repo/src/m{i}.py" for i in range(12)] + ["/repo/src/m0.py"]
    cue, meta = finish_decision(
        {"transcript_path": _transcript(tmp_path, paths), "stop_hook_active": False}
    )
    assert cue.count("m0.py") == 1  # deduped
    assert "+4 more" in cue  # 12 distinct, cap 8
    assert meta["files"] == 12


def test_author_meta_records_new_file(tmp_path):
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(tmp_path / "brand-new.py"), "content": CODE},
    }
    _, meta = author_decision(payload)
    assert meta["new_file"] is True

    existing = tmp_path / "existing.py"
    existing.write_text("x = 1\n")
    payload2 = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(existing), "content": CODE},
    }
    _, meta2 = author_decision(payload2)
    assert meta2["new_file"] is False
