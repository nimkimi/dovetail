"""Per-context delivery state for novelty-weighted cueing.

Keyed by an opaque context key (transcript_path + agent_id — subagents share
the parent's transcript_path but carry their own agent_id): every context gets the full always-on
block on its first cue, compressed repeats afterwards. Stored as one tiny JSON
file per context under ~/.dovetail/state (override via DOVETAIL_STATE_DIR).
Every failure degrades to "show the full cue" — dampening must never break the
hook's advisory contract, and over-showing is the safe direction.
"""

import hashlib
import json
import os
import time

# Marathon insurance: a compacted context may have lost the earlier full cue,
# so re-show the full block after this window regardless of state.
REFRESH_SECONDS = 45 * 60
# Context state is worthless once its session is long gone.
STALE_SECONDS = 7 * 24 * 3600


def _now() -> float:
    return time.time()


def _state_dir() -> str:
    return os.environ.get("DOVETAIL_STATE_DIR") or os.path.expanduser(
        "~/.dovetail/state"
    )


def _path_for(context_key: str) -> str:
    digest = hashlib.sha1(
        context_key.encode("utf-8", "replace")
    ).hexdigest()[:16]
    return os.path.join(_state_dir(), digest + ".json")


def should_compress(context_key: str) -> bool:
    """True when this context saw the full always-on block within the refresh
    window. Unreadable/missing state reads as False (show the full cue)."""
    try:
        with open(_path_for(context_key), encoding="utf-8") as f:
            full_shown_at = json.load(f).get("full_shown_at", 0)
        return (_now() - full_shown_at) < REFRESH_SECONDS
    except Exception:
        return False


def mark_full_shown(context_key: str) -> None:
    """Record a full showing; opportunistically drop stale peer files. Failures
    are swallowed — the worst outcome is a repeated full cue."""
    try:
        directory = _state_dir()
        os.makedirs(directory, exist_ok=True)
        _clean_stale(directory)
        with open(_path_for(context_key), "w", encoding="utf-8") as f:
            json.dump({"full_shown_at": _now()}, f)
    except Exception:
        pass


def _clean_stale(directory: str) -> None:
    cutoff = _now() - STALE_SECONDS
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except OSError:
            pass
