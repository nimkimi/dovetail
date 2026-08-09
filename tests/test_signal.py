"""Weekly tuning signals: a report ONLY when a threshold trips — the flag file
the wrapper writes into means "action needed", so a quiet week must yield None.
"""

from dovetail.signal import weekly_signals

NOW = 1_800_000_000.0
DAY = 86_400.0


def author(decision="cue", age_days=1.0):
    return {"ts": NOW - age_days * DAY, "surface": "author", "decision": decision}


def stop(reason=None, age_days=1.0):
    record = {"ts": NOW - age_days * DAY, "surface": "stop", "decision": "silent"}
    if reason:
        record["reason"] = reason
    return record


def test_quiet_week_yields_none():
    records = [author("cue") for _ in range(40)] + [author("silent") for _ in range(60)]
    assert weekly_signals(records, NOW) is None


def test_hot_author_rate_trips():
    records = [author("cue") for _ in range(70)] + [author("silent") for _ in range(30)]
    out = weekly_signals(records, NOW)
    assert out is not None
    assert "author cue rate" in out
    assert "70%" in out


def test_hot_rate_below_eval_floor_stays_quiet():
    # 45/50 would be alarming — but 50 evals is noise, not signal.
    records = [author("cue") for _ in range(45)] + [author("silent") for _ in range(5)]
    assert weekly_signals(records, NOW) is None


def test_tail_bail_share_trips():
    records = [stop("boundary-outside-tail") for _ in range(6)] + [stop("no-code") for _ in range(94)]
    out = weekly_signals(records, NOW)
    assert out is not None
    assert "tail-cap" in out


def test_records_outside_the_window_are_ignored():
    # A hot week 30 days ago must not fire today's flag.
    records = [author("cue", age_days=30.0) for _ in range(200)]
    assert weekly_signals(records, NOW) is None


def test_malformed_records_are_skipped():
    records = ["junk", None, 42] + [author("silent") for _ in range(100)]
    assert weekly_signals(records, NOW) is None
