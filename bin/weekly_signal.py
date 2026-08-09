#!/usr/bin/env python3
"""dovetail weekly telemetry signal — run by the weekly maintenance job.

Prints tuning signals from the last week of fire-log data, or nothing when the
week is quiet. Read-only over the log, stdlib-only, exits 0 on every path —
the weekly job appends any output to its PENDING-UPDATES.md flag file, so
output means "action needed" and silence means the flag stays untouched.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dovetail.signal import weekly_signals


def main():
    log_path = os.path.join(
        os.environ.get("DOVETAIL_LOG_DIR") or os.path.expanduser("~/.dovetail"),
        "fire-log.jsonl",
    )
    records = []
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        return  # no log yet → nothing to report
    report = weekly_signals(records, time.time())
    if report:
        print(report)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # a broken report must never fail the weekly job
    sys.exit(0)
