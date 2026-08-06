"""Summarize the fire log: per surface, evaluations vs cues (fire rate) and
per-trigger counts — the evidence base for tuning cue weight."""


def summarize(records: list) -> dict:
    surfaces: dict = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        surface = surfaces.setdefault(
            record.get("surface", "?"),
            {"evaluations": 0, "cues": 0, "triggers": {}, "silent_reasons": {}},
        )
        surface["evaluations"] += 1
        if record.get("decision") == "cue":
            surface["cues"] += 1
            for trigger in record.get("triggers") or []:
                surface["triggers"][trigger] = surface["triggers"].get(trigger, 0) + 1
        else:
            reason = record.get("reason", "?")
            surface["silent_reasons"][reason] = (
                surface["silent_reasons"].get(reason, 0) + 1
            )
    return surfaces
