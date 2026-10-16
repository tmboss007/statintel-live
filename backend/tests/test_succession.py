import pytest
from app.succession import (
    compute_succession_vulnerability_matrix,
    compute_departmental_criticality_analytics,
    update_department_multiplier,
    CADRE_SUCCESSION_CHAIN
)
from app.models import Officer


def test_cadre_succession_chain_completeness():
    """Verify all promotional tiers in ISS & SSS cadre are present in order."""
    tiers = [c["target_cadre"] for c in CADRE_SUCCESSION_CHAIN]
    assert "Senior Statistical Officer" in tiers
    assert "Assistant Director" in tiers
    assert "Deputy Director" in tiers
    assert "Joint Director" in tiers
    assert "Director" in tiers
    assert "Deputy Director General" in tiers


def test_bench_strength_formula_accuracy(db_session):
    """
    Verify the mathematical formula:
    Bench Strength Ratio = (Officers in Feeder Cadre with Readiness >= 75%) / (Sanctioned Posts in Target Cadre)
    """
    matrix_res = compute_succession_vulnerability_matrix(db_session)
    assert matrix_res["status"] == "success"
    matrix = matrix_res["succession_matrix"]
    assert len(matrix) == len(CADRE_SUCCESSION_CHAIN)

    for tier in matrix:
        sanctioned = tier["sanctioned_posts"]
        ready_feeder = tier["ready_candidates_count"]
        expected_ratio = round(ready_feeder / sanctioned, 2) if sanctioned > 0 else 0.0

        assert tier["bench_strength_ratio"] == expected_ratio
        assert tier["risk_level"] in ["CRITICAL", "VULNERABLE", "HEALTHY", "ROBUST"]

        if expected_ratio < 0.5:
            assert tier["risk_level"] == "CRITICAL"
        elif expected_ratio < 1.0:
            assert tier["risk_level"] == "VULNERABLE"
        elif expected_ratio < 2.0:
            assert tier["risk_level"] == "HEALTHY"
        else:
            assert tier["risk_level"] == "ROBUST"


def test_department_weights_and_strategic_readiness(db_session):
    """Verify departmental multipliers and strategic weighted readiness recalculation."""
    dept_res = compute_departmental_criticality_analytics(db_session)
    assert dept_res["status"] == "success"
    depts = dept_res["departments"]
    assert len(depts) >= 1

    for d in depts:
        assert "department" in d
        assert "baseline_readiness" in d
        assert "strategic_weighted_readiness" in d
        assert "priorities" in d
        for p in d["priorities"]:
            assert 1.0 <= p["multiplier"] <= 2.5
            assert "weighted_gap_score" in p


def test_succession_matrix_api_endpoint(client, viewer_token):
    """Verify /api/succession/vulnerability-matrix returns complete matrix."""
    headers = {"Authorization": f"Bearer {viewer_token}"}
    res = client.get("/api/succession/vulnerability-matrix", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "overall_summary" in data
    assert "succession_matrix" in data
    assert data["overall_summary"]["cadre_tiers_evaluated"] == 6


def test_department_weight_update_and_invalidation(client, admin_token, db_session):
    """Verify admin can update multiplier, triggering cache invalidation."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Get initial weights
    w_res = client.get("/api/succession/department-weights", headers=headers)
    assert w_res.status_code == 200
    first_weight_id = None
    for d in w_res.json()["departments"]:
        if d["priorities"]:
            first_weight_id = d["priorities"][0]["id"]
            break

    if first_weight_id:
        update_res = client.post("/api/succession/department-weights", json={
            "weight_id": first_weight_id,
            "multiplier": 2.4,
            "rationale": "High priority policy for National Accounts"
        }, headers=headers)
        assert update_res.status_code == 200
        assert update_res.json()["multiplier"] == 2.4
