from dovetail.cues import build_author_cue, build_finish_cue

CAP = 2048  # <2KB target; the hard hook output cap is 10000 chars


def test_author_cue_has_preamble_and_core():
    cue = build_author_cue([])
    assert "Advisory" in cue
    assert "network" in cue
    assert "Proportional" in cue
    assert "YAGNI" in cue
    assert "Chesterton" in cue


def test_author_cue_includes_triggered_dep_vet_content():
    assert "typosquat" in build_author_cue(["dep-vet"])


def test_author_cue_includes_blast_radius_content():
    assert "idempotent" in build_author_cue(["blast-radius"])


def test_author_cue_includes_failure_path_secrets():
    assert "secrets" in build_author_cue(["failure-path"])


def test_untriggered_cue_is_absent():
    assert "typosquat" not in build_author_cue([])


def test_triggers_are_deduped():
    assert build_author_cue(["dep-vet", "dep-vet"]).count("typosquat") == 1


def test_author_cue_stays_under_size_cap():
    cue = build_author_cue(
        ["blast-radius", "breaking-change", "failure-path", "dep-vet", "runtime-cost", "reuse"]
    )
    assert len(cue) <= CAP


def test_finish_cue_has_sweep_reread_edges():
    cue = build_finish_cue(False)
    assert "sweep" in cue
    assert "stranger" in cue
    assert "edges" in cue
    assert "Structural" not in cue


def test_finish_cue_appends_structural_declaration():
    assert "Structural" in build_finish_cue(True)
