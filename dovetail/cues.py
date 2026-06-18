"""The cue payload — the steering text dovetail injects.

Primary weight on dovetail's UNIQUE concerns (dependency-vetting, blast-radius
safety, breaking-change, secrets/trust-boundary, runtime-cost, survey-before-
reuse); only a LIGHT touch on the quality cluster `/simplify` owns. Every line
is concrete and verb-first — no bare virtues. Kept compact: the assembled
author cue stays under the <2KB target (hard hook cap is 10000 chars).
"""

PREAMBLE = (
    "[dovetail] Advisory cues — suggestions, not edits. Don't act beyond the "
    "asked scope; never make a network call."
)

ALWAYS_ON = (
    "Always, sized to this change:\n"
    "- Proportional first — trivial / in-scope / cosmetic? Just make the change.\n"
    "- Stay in scope — touch only what this change needs (plus orphans it creates); "
    "spotted-but-untouched bad code is a one-line NOTE, not an unasked edit.\n"
    "- Conform to the local idiom — match the neighbour (errors, naming, structure, "
    "tests); this repo's conventions beat any default.\n"
    "- YAGNI — build only what THIS needs; no speculative abstraction; never shorten a "
    "guard / validation / error branch for brevity; before deleting a non-obvious line "
    "find its reason (Chesterton's Fence) and state the bet if you cut it.\n"
    "- Read 10x (light — /simplify owns the deep pass) — name for intent; comment the "
    "WHY, not the what; expand an unreadable one-liner."
)

# Loud / unique first; the quality cluster is already covered above.
TRIGGER_ORDER = [
    "blast-radius",
    "breaking-change",
    "failure-path",
    "dep-vet",
    "runtime-cost",
    "reuse",
]

TRIGGER_CUES = {
    "blast-radius": (
        "- High blast radius (destructive / migration / retried / shared state) — "
        "reversible? idempotent if it runs twice? race-safe? The one worth interrupting for."
    ),
    "breaking-change": (
        "- Contract surface (public API / wire-or-JSON / DB schema / env var / CLI flag) — "
        "breaking-until-proven-additive; check every consumer before you ship it."
    ),
    "failure-path": (
        "- Fallible call (I/O / network / parse / external) — handle vs propagate, never an "
        "empty catch; never echo secrets/tokens into logs or errors; validate untrusted input "
        "at the boundary; release resources on the error path too."
    ),
    "dep-vet": (
        "- New dependency — flag it. Offline signals: already a transitive dep? name plausibly "
        "typosquatted? lockfile-pinned? Don't add a load-bearing dep silently."
    ),
    "runtime-cost": (
        "- Loop / query / fetch — O(n^2)? an N+1? invariant work trapped in the loop? an "
        "unbounded fetch? hoist or bound it."
    ),
    "reuse": (
        "- New file / import — survey first: grep for an existing util/dep that already does "
        "this; prefer native > existing dep > new dep. Name what you reused, or say none fit."
    ),
}

FINISH = (
    "[dovetail] Finish check — before you call this done:\n"
    "- Complete the change — sweep every caller, test, doc, config, and dead branch it "
    "touched (plus types, if the language has them). Leave nothing dangling.\n"
    "- Re-read your diff as a stranger — any line you'd stop to decode? a name drifted off "
    "what the code does now? a new path with no log/metric where its neighbours have one?\n"
    "- Tests assert behaviour + edges (proportional) — real outcomes incl. the edges you "
    "reasoned about (empty / boundary / failure); match the repo's style; no suite → say so, "
    "don't invent one."
)

FINISH_STRUCTURAL = (
    "- Structural-decision declaration — a new module / boundary / data-shape appeared this "
    "turn: state it in one line so the decision is visible, not silent."
)


def build_author_cue(triggers: "list[str]") -> str:
    """Preamble + always-on core + each present trigger's cue (priority order,
    deduped). Iterating the fixed order both orders and de-duplicates."""
    parts = [PREAMBLE, ALWAYS_ON]
    parts.extend(TRIGGER_CUES[key] for key in TRIGGER_ORDER if key in triggers)
    return "\n".join(parts)


def build_finish_cue(structural: bool) -> str:
    """The finish nudge, plus the one-line structural declaration when a new
    module / boundary / data-shape was introduced this turn."""
    return FINISH + ("\n" + FINISH_STRUCTURAL if structural else "")
