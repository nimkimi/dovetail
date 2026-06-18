from dovetail.change import parse_change


def test_parses_edit_new_string_as_added_text():
    change = parse_change("Edit", {
        "file_path": "/repo/app/calc.py",
        "old_string": "x = 1",
        "new_string": "x = compute(items)",
        "replace_all": False,
    })
    assert change.file_path == "/repo/app/calc.py"
    assert change.added_text == "x = compute(items)"
    assert change.is_new_file is False


def test_parses_write_content_as_added_text():
    change = parse_change("Write", {
        "file_path": "/repo/app/new_module.py",
        "content": "def f():\n    return 1\n",
    })
    assert change.added_text == "def f():\n    return 1\n"


def test_write_to_missing_path_is_new_file(tmp_path):
    target = tmp_path / "brand_new.py"
    change = parse_change("Write", {"file_path": str(target), "content": "y = 2\n"})
    assert change.is_new_file is True


def test_write_to_existing_path_is_not_new_file(tmp_path):
    target = tmp_path / "exists.py"
    target.write_text("old\n")
    change = parse_change("Write", {"file_path": str(target), "content": "new\n"})
    assert change.is_new_file is False


def test_unknown_tool_returns_none():
    assert parse_change("Bash", {"command": "ls"}) is None


def test_malformed_tool_input_returns_none():
    assert parse_change("Edit", None) is None
