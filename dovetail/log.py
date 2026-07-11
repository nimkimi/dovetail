"""Local fire-rate telemetry. One JSONL line per hook evaluation so cue-weight
tuning (banner-blindness) runs on measured fire rates instead of vibes.

Local-only, stdlib-only, and failure-swallowing: telemetry must never break a
hook or leak content — records carry decision metadata (triggers, extension),
never file paths or code."""

import json
import os
import time


def _log_dir() -> str:
    return os.environ.get("DOVETAIL_LOG_DIR") or os.path.expanduser("~/.dovetail")


def log_event(surface: str, meta: dict) -> None:
    """Append one evaluation record. Any failure is swallowed — the hook's
    advisory contract outranks telemetry."""
    try:
        directory = _log_dir()
        os.makedirs(directory, exist_ok=True)
        record = {"ts": round(time.time(), 3), "surface": surface}
        record.update(meta)
        with open(
            os.path.join(directory, "fire-log.jsonl"), "a", encoding="utf-8"
        ) as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass
