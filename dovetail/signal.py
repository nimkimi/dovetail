"""Weekly tuning signals over the fire log.

Pure, stdlib-only, deterministic thresholds. Returns a report string ONLY when
a signal trips: the caller writes into PENDING-UPDATES.md, whose contract is
"flag present = action needed" — a quiet week must produce nothing, or the
flag becomes wallpaper (the exact failure the cues themselves guard against).
Eval floors keep small samples from firing: a hot rate over a handful of
records is noise, not signal.
"""

WINDOW_DAYS = 7
AUTHOR_RATE_MAX = 0.60   # banner-blindness line, with post-narrowing headroom
AUTHOR_MIN_EVALS = 100
TAIL_BAIL_RATE_MAX = 0.05  # boundary-outside-tail share that argues a bigger tail cap
STOP_MIN_EVALS = 50


def weekly_signals(records: list, now: float) -> "str | None":
    """Tuning signals from the last WINDOW_DAYS of fire-log records, or None."""
    cutoff = now - WINDOW_DAYS * 86400
    recent = [r for r in records if isinstance(r, dict) and r.get("ts", 0) >= cutoff]
    author = [r for r in recent if r.get("surface") == "author"]
    stop = [r for r in recent if r.get("surface") == "stop"]
    lines = []
    if len(author) >= AUTHOR_MIN_EVALS:
        rate = sum(1 for r in author if r.get("decision") == "cue") / len(author)
        if rate > AUTHOR_RATE_MAX:
            lines.append(
                f"- author cue rate {rate:.0%} over {len(author)} evals "
                f"(above {AUTHOR_RATE_MAX:.0%}) — banner-blindness risk; retune cue "
                f"weight on the per-trigger split (dovetail/report.summarize)"
            )
    if len(stop) >= STOP_MIN_EVALS:
        rate = sum(1 for r in stop if r.get("reason") == "boundary-outside-tail") / len(stop)
        if rate > TAIL_BAIL_RATE_MAX:
            lines.append(
                f"- stop tail-cap bails on {rate:.0%} of {len(stop)} evals "
                f"(above {TAIL_BAIL_RATE_MAX:.0%}) — measured evidence to raise _TAIL_BYTES"
            )
    if not lines:
        return None
    return "dovetail weekly telemetry signals:\n" + "\n".join(lines)
