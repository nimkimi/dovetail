"""Parse a PreToolUse payload into the fields dovetail's cue logic needs.

Field names are exact to the Claude Code hook contract: Edit carries
`old_string`/`new_string`/`replace_all`; Write carries `content`. Only Edit and
Write are code-change tools — any other tool yields None and the hook stays
silent.
"""

import os
from dataclasses import dataclass


@dataclass
class Change:
    file_path: str
    added_text: str
    is_new_file: bool


def parse_change(tool_name: str, tool_input: object) -> "Change | None":
    """Return the pending Change, or None for a tool shape dovetail ignores."""
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path") or ""
    if tool_name == "Edit":
        return Change(file_path, tool_input.get("new_string") or "", is_new_file=False)
    if tool_name == "Write":
        is_new = not (file_path and os.path.exists(file_path))
        return Change(file_path, tool_input.get("content") or "", is_new_file=is_new)
    return None
