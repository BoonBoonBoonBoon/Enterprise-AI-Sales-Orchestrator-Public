from tiers.tier_2.leads_orchestrator.qualification.lifecycle import (
    build_staging_qualification_update,
    normalize_qualification_status,
)


def test_normalize_qualification_status_defaults_to_pending():
    assert normalize_qualification_status(None) == "pending"
    assert normalize_qualification_status("") == "pending"
    assert normalize_qualification_status("  ") == "pending"
    assert normalize_qualification_status("unknown") == "pending"


def test_normalize_qualification_status_allows_expected_values():
    assert normalize_qualification_status("qualified") == "qualified"
    assert normalize_qualification_status("nurture") == "nurture"
    assert normalize_qualification_status("disqualified") == "disqualified"
    assert normalize_qualification_status("fast_track") == "fast_track"
    assert normalize_qualification_status("PENDING") == "pending"


def test_build_staging_qualification_update_sets_expected_fields():
    update = build_staging_qualification_update(decision="qualified", promote=True, score=88)

    assert update["qualification_status"] == "qualified"
    assert update["promotion_ready"] is True
    assert update["completeness_score"] == 0.88
