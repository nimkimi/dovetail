#!/usr/bin/env python3
"""dovetail PreToolUse hook — advisory author-time cue.

Reads the pending Edit/Write from stdin, and on a non-trivial code change emits
a compact quality cue via `additionalContext`. ADVISORY ONLY: never blocks,
never edits, never touches the network, and exits 0 on every path — including
malformed input or an unexpected internal error.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dovetail.hook import author_decision
from dovetail.log import log_event


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return  # malformed stdin → stay silent
    try:
        context, meta = author_decision(payload)
        # Enriched at the logging boundary, not in the pure decision: agent_id
        # ("" = main session) makes the subagent/main split analyzable — a
        # month of data had no field that could tell them apart (2026-08-09).
        meta["agent_id"] = (payload.get("agent_id") or "") if isinstance(payload, dict) else ""
        log_event("author", meta)
    except Exception:
        return  # an internal error must never break the host's tool call
    if context:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            }
        }))


if __name__ == "__main__":
    main()
    sys.exit(0)
