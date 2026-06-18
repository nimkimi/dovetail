"""Guard the install contract: a malformed or misplaced manifest is a silent
non-load, so validate the manifests parse and wire the hooks correctly."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_plugin_json_is_valid_and_named():
    data = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert data["name"] == "dovetail"
    assert "version" in data


def test_hooks_json_wires_pretooluse_scoped_to_edit_write():
    data = json.loads((ROOT / "hooks" / "hooks.json").read_text())
    pre = data["hooks"]["PreToolUse"][0]
    assert pre["matcher"] == "Edit|Write"
    assert "${CLAUDE_PLUGIN_ROOT}/bin/pretool.py" in pre["hooks"][0]["command"]


def test_hooks_json_wires_stop():
    data = json.loads((ROOT / "hooks" / "hooks.json").read_text())
    stop = data["hooks"]["Stop"][0]
    assert "${CLAUDE_PLUGIN_ROOT}/bin/stop.py" in stop["hooks"][0]["command"]


def test_hook_commands_point_to_real_scripts():
    assert (ROOT / "bin" / "pretool.py").exists()
    assert (ROOT / "bin" / "stop.py").exists()
