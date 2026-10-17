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


def test_multiturn_grounded_copilot_memory(db_session):
    """Verify that execute_grounded_conversation leverages chat_history and contextual follow-ups."""
    from app.pathway import execute_grounded_conversation

    sample_roadmap = {
        "officer_name": "Priya Sharma",
        "current_role": "Junior Statistical Officer",
        "target_role": "Senior Statistical Officer",
        "weekly_hours": 4,
        "estimated_weeks": 6,
        "current_readiness": 52.0,
        "projected_readiness": 78.0,
        "phases": [
            {
                "order": 1,
                "skill": "Applied Sampling Methodology",
                "milestone": "Design PPS sampling scheme for NSSO socio-economic round",
                "gap_severity": 85.0,
                "severity_level": "critical",
                "items": [
                    {
                        "id": "samp_vid_01",
                        "title": "Stratified and Cluster Sampling",
                        "channel": "CrashCourse",
                        "duration_min": 25,
                        "verified_standard": "UNSD Standard"
                    }
                ]
            },
            {
                "order": 2,
                "skill": "Data Quality & Validation",
                "milestone": "Implement Fellegi-Holt consistency checking pipeline",
                "gap_severity": 72.0,
                "severity_level": "high",
                "items": [
                    {
                        "id": "qual_vid_01",
                        "title": "Automated Microdata Imputation",
                        "channel": "Eurostat",
                        "duration_min": 30,
                        "verified_standard": "Eurostat Standard"
                    }
                ]
            }
        ],
        "candidate_id_pool": ["samp_vid_01", "qual_vid_01"]
    }

    # Turn 1: Initial query
    res1 = execute_grounded_conversation(
        current_roadmap=sample_roadmap,
        user_message="Why is sampling placed first in my pathway?",
        db=db_session
    )
    assert res1["status"] == "success"
    assert "reply" in res1
    assert "explanation" in res1
    assert len(res1["reply"]) > 20
    assert res1["action_taken"] == "explain_priority"

    # Turn 2: Contextual follow-up referring to Step 2 / Fellegi-Holt consistency
    history = [
        {"sender": "user", "message": "Why is sampling placed first in my pathway?"},
        {"sender": "advisor", "message": res1["reply"]}
    ]
    res2 = execute_grounded_conversation(
        current_roadmap=sample_roadmap,
        user_message="Can you explain Step 2 of the Fellegi-Holt consistency check again?",
        db=db_session,
        chat_history=history
    )
    assert res2["status"] == "success"
    assert "reply" in res2
    assert "explanation" in res2
    assert len(res2["reply"]) > 20
    # Response must contextualize Step 2 or Fellegi-Holt methodology
    assert "Phase 2" in res2["reply"] or "Fellegi-Holt" in res2["reply"] or "Data Quality" in res2["reply"]


def test_persistent_chat_api_endpoints(client, officer_user, db_session):
    """Verify /api/pathway/chat/send and /api/pathway/chat/history endpoints persist multi-turn dialog."""
    token = officer_user["token"]
    officer = officer_user["officer"]
    headers = {"Authorization": f"Bearer {token}"}

    # Send message 1
    resp1 = client.post(
        "/api/pathway/chat/send",
        headers=headers,
        json={
            "officer_id": officer.id,
            "message": "What is the recommended weekly pace for my preparation?"
        }
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "success"
    assert "reply" in data1
    assert len(data1["reply"]) > 0

    # Retrieve history
    hist_resp = client.get(f"/api/pathway/chat/history/{officer.id}", headers=headers)
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert len(hist) >= 2  # 1 user + 1 advisor message
    assert hist[0]["sender"] == "user"
    assert hist[1]["sender"] == "advisor"
    assert hist[1]["message"] == data1["reply"]

    # Send message 2 (contextual follow-up)
    resp2 = client.post(
        "/api/pathway/chat/send",
        headers=headers,
        json={
            "officer_id": officer.id,
            "message": "Can you explain the Fellegi-Holt consistency check again?"
        }
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "success"
    assert "reply" in data2
    assert len(data2["reply"]) > 0
    assert "Fellegi-Holt" in data2["reply"] or "consistency" in data2["reply"].lower()


def test_certificate_pdf_generation_and_verification(client, db_session):
    """Verify certificate PDF generation and scannable verification endpoint."""
    from app.models import Certificate
    from app.assessment import generate_certificate_pdf
    import uuid

    cert_uuid = f"CERT-TEST-{uuid.uuid4().hex[:8].upper()}"
    cert = Certificate(
        cert_uuid=cert_uuid,
        officer_id=99999,  # Detached officer id
        officer_name="Sunita Deshmukh",
        skill_name="Python & Reproducible Analysis",
        cadre_tier="senior",
        target_role="Assistant Director",
        score=94.5
    )
    db_session.add(cert)
    db_session.commit()

    # 1. Test verification endpoint
    v_resp = client.get(f"/api/assessment/certificate/{cert_uuid}/verify")
    assert v_resp.status_code == 200
    v_data = v_resp.json()
    assert v_data["status"] == "valid"
    assert v_data["officer_name"] == "Sunita Deshmukh"

    # 2. Test PDF generation directly with None officer
    pdf_bytes = generate_certificate_pdf(cert, None)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")

    # 3. Test PDF download endpoint
    dl_resp = client.get(f"/api/assessment/certificate/{cert_uuid}/pdf")
    assert dl_resp.status_code == 200
    assert dl_resp.headers["content-type"] == "application/pdf"
    assert len(dl_resp.content) > 1000


def test_officer_progress_tracking_and_readiness_uplift(client, officer_user, db_session):
    """Verify item toggles update officer progress and accurately uplift readiness score."""
    token = officer_user["token"]
    officer = officer_user["officer"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Fetch initial progress
    get_res = client.get(f"/api/pathway/progress/{officer.id}", headers=headers)
    assert get_res.status_code == 200
    init_data = get_res.json()
    base_readiness = init_data["base_readiness"]

    # 2. Mark a video completed
    toggle_res1 = client.post(
        "/api/pathway/progress/toggle",
        headers=headers,
        json={
            "officer_id": officer.id,
            "item_type": "video_lecture",
            "item_key": "video:samp_vid_01",
            "item_title": "Stratified and Cluster Sampling",
            "completed": True
        }
    )
    assert toggle_res1.status_code == 200
    data1 = toggle_res1.json()
    assert data1["status"] == "success"
    assert data1["completed"] is True
    assert data1["completed_videos"] >= 1
    assert data1["current_readiness"] >= base_readiness + 1.5

    # 3. Mark a task completed
    toggle_res2 = client.post(
        "/api/pathway/progress/toggle",
        headers=headers,
        json={
            "officer_id": officer.id,
            "item_type": "phase_task",
            "item_key": "task:nss_stratification_exercise",
            "item_title": "Design NSSO stratified sampling frame",
            "completed": True
        }
    )
    assert toggle_res2.status_code == 200
    data2 = toggle_res2.json()
    assert data2["completed_tasks"] >= 1
    assert data2["current_readiness"] >= data1["current_readiness"] + 1.0

    # 4. Unmark video and verify graceful recalculation
    unmark_res = client.post(
        "/api/pathway/progress/toggle",
        headers=headers,
        json={
            "officer_id": officer.id,
            "item_type": "video_lecture",
            "item_key": "video:samp_vid_01",
            "completed": False
        }
    )
    assert unmark_res.status_code == 200
    unmark_data = unmark_res.json()
    assert unmark_data["completed"] is False
    assert unmark_data["current_readiness"] < data2["current_readiness"]
