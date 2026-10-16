import pytest
from app.pathway import generate_structured_roadmap, score_video_candidate, VERIFIED_VIDEO_CATALOG
from app.assessment import get_quiz_questions, evaluate_quiz_submission, QUESTION_BANK
from app.models import Officer


def test_differentiated_pathway_generation(db_session):
    """Verify structured roadmap generation adapts to officer profile and cadre tier."""
    priya = db_session.query(Officer).filter(Officer.name == "Priya Sharma").first()
    assert priya is not None

    roadmap = generate_structured_roadmap(
        officer_id=priya.id,
        target_role="Senior Statistical Officer",
        weekly_hours=4,
        preferred_style="applied",
        content_level="operational",
        db=db_session
    )

    assert "officer_name" in roadmap
    assert "phases" in roadmap
    assert len(roadmap["phases"]) > 0
    assert "current_readiness" in roadmap
    assert "projected_readiness" in roadmap
    assert roadmap["cadre_tier"] in ["operational", "senior", "executive"]


def test_verified_video_catalog_and_scoring():
    """Verify that video scoring strictly verifies domain fit and cadre level alignment."""
    sample_video = {
        "id": "test_vid_123",
        "title": "Data Analysis Tutorial for Census Enumerators",
        "channel": "National Statistical Systems",
        "channel_type": "government_academic",
        "duration_min": 35,
        "views": 50000,
        "like_ratio": 0.98,
        "url": "https://www.youtube.com/watch?v=test_vid_123",
        "focus": "Sampling and validation",
        "verified_standard": "UNSD Standard",
        "level": "operational"
    }

    # Operational score
    op_score = score_video_candidate(
        sample_video,
        skill_name="Survey methodology",
        weekly_hours=4,
        preferred_style="applied",
        cadre_tier="operational"
    )
    assert 30.0 <= op_score <= 100.0

    # Executive score for operational video should be penalized
    exec_score = score_video_candidate(
        sample_video,
        skill_name="Survey methodology",
        weekly_hours=4,
        preferred_style="applied",
        cadre_tier="executive"
    )
    assert exec_score < op_score, "Executive score should be lower for purely operational training"


def test_competency_examination_and_certification(db_session):
    """Verify examination generation, scoring, and certificate issuance."""
    priya = db_session.query(Officer).filter(Officer.name == "Priya Sharma").first()
    assert priya is not None

    # Fetch quiz questions
    quiz = get_quiz_questions("sql & data management", cadre_tier="operational", phase_order=1)
    assert len(quiz["questions"]) >= 3

    # Look up correct answers from canonical bank
    raw_pool = QUESTION_BANK["sql & data management"]["operational"]
    correct_map = {q["id"]: q["correct_index"] for q in raw_pool}
    answers = {str(q["id"]): correct_map[q["id"]] for q in quiz["questions"] if q["id"] in correct_map}

    result = evaluate_quiz_submission(
        officer_id=priya.id,
        skill_name="sql & data management",
        cadre_tier="operational",
        phase_order=1,
        target_role=priya.target_role,
        answers=answers,
        db=db_session
    )

    assert result["score"] == 100.0
    assert result["passed"] is True
    assert result["certificate_uuid"] is not None
    assert result["new_readiness"] >= result["new_readiness"] - result["readiness_gain"]
