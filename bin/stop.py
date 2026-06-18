#!/usr/bin/env python3
"""dovetail Stop hook — advisory finish nudge.

Reads the Stop payload from stdin, parses the turn's transcript to see whether
non-trivial code was written this turn, and if so emits one compact finish cue
via `additionalContext`. ADVISORY ONLY: honours `stop_hook_active`, never
blocks, never edits, never touches the network, and exits 0 on every path.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dovetail.hook import finish_context


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return  # malformed stdin → stay silent
    try:
        context = finish_context(payload)
    except Exception:
        return  # an internal error must never break the host turn-end
    if context:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": context,
            }
        }))


if __name__ == "__main__":
    main()
    sys.exit(0)
