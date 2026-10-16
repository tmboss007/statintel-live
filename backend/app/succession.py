"""
StatIntel Strategic Cadre Intelligence & Succession Planning Engine
-------------------------------------------------------------------
Implements:
1. Cadre Succession Vulnerability Matrix
   Mathematical formula:
   Bench Strength Ratio = (Officers in Feeder Cadre with Readiness >= 75%) / (Sanctioned Posts in Target Cadre)
2. Dynamic Departmental Skill Criticality Weighting
   Applies multipliers (1.0x - 2.0x) to priority skills per statistical directorate.
"""
from typing import Any
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .models import Officer, Skill, DepartmentSkillWeight
from .analytics import _normalize, SKILL_ALIASES

# Official MoSPI / Indian Statistical System Cadre Succession Chain
CADRE_SUCCESSION_CHAIN = [
    {
        "id": "sso_succession",
        "target_cadre": "Senior Statistical Officer",
        "feeder_cadre": "Junior Statistical Officer",
        "default_sanctioned": 14,
        "critical_threshold": 75.0,
        "cadre_tier": "operational",
        "responsibilities": "Independent survey operations, sample supervision, primary data validation."
    },
    {
        "id": "ad_succession",
        "target_cadre": "Assistant Director",
        "feeder_cadre": "Senior Statistical Officer",
        "default_sanctioned": 10,
        "critical_threshold": 75.0,
        "cadre_tier": "senior",
        "responsibilities": "Divisional reporting, survey design oversight, database validation pipelines."
    },
    {
        "id": "dd_succession",
        "target_cadre": "Deputy Director",
        "feeder_cadre": "Assistant Director",
        "default_sanctioned": 8,
        "critical_threshold": 78.0,
        "cadre_tier": "senior",
        "responsibilities": "National accounts consolidation, index compilation, econometric modeling."
    },
    {
        "id": "jd_succession",
        "target_cadre": "Joint Director",
        "feeder_cadre": "Deputy Director",
        "default_sanctioned": 6,
        "critical_threshold": 80.0,
        "cadre_tier": "executive",
        "responsibilities": "Inter-ministerial data harmonization, microdata release standards, AI audit."
    },
    {
        "id": "dir_succession",
        "target_cadre": "Director",
        "feeder_cadre": "Joint Director",
        "default_sanctioned": 5,
        "critical_threshold": 82.0,
        "cadre_tier": "executive",
        "responsibilities": "Directorate executive leadership, national survey policy, international compliance (SDMX)."
    },
    {
        "id": "ddg_succession",
        "target_cadre": "Deputy Director General",
        "feeder_cadre": "Director",
        "default_sanctioned": 3,
        "critical_threshold": 85.0,
        "cadre_tier": "executive",
        "responsibilities": "Apex statistical authority, national statistical committee oversight."
    }
]

# Baseline Strategic Department Priorities
DEFAULT_DEPARTMENT_PRIORITIES = {
    "National Accounts Division": [
        ("Time series analysis", 1.9, "Quarterly GDP and macroeconomic indicator compilation"),
        ("Python & reproducible analysis", 1.8, "Modernizing automated national accounts pipelines"),
        ("SQL & data management", 1.6, "Relational extraction from tax and corporate registers"),
        ("Data visualisation", 1.4, "Executive dashboards for Ministry and NITI Aayog"),
    ],
    "Field Operations Division": [
        ("Survey design & questionnaire", 2.0, "Nationwide socio-economic surveys (PLFS, NSS)"),
        ("Applied sampling methodology", 1.9, "Multi-stage stratified sampling and weight estimation"),
        ("Data ethics & privacy", 1.5, "DPDP Act compliance and survey respondent privacy"),
        ("SQL & data management", 1.4, "CAPI field data ingestion and consistency checks"),
    ],
    "Price Statistics Division": [
        ("Time series analysis", 2.0, "CPI/WPI inflation seasonal adjustments"),
        ("Python & reproducible analysis", 1.8, "Web-scraping and automated price index validation"),
        ("Data visualisation", 1.5, "Inflation trajectory charts for Reserve Bank of India"),
    ],
    "Economic Statistics Division": [
        ("SQL & data management", 1.9, "Annual Survey of Industries (ASI) microdata management"),
        ("Applied sampling methodology", 1.7, "Enterprise sampling and factory frame maintenance"),
        ("AI / machine learning foundations", 1.5, "Automated classification of industrial activity (NIC)"),
    ],
    "Coordination & Administration": [
        ("Data ethics & privacy", 1.8, "National data sharing and accessibility protocols"),
        ("Data visualisation", 1.7, "SDG indicator progress reports"),
        ("Python & reproducible analysis", 1.5, "Administrative reporting automation"),
    ]
}


def compute_succession_vulnerability_matrix(db: Session) -> dict[str, Any]:
    """
    Computes the complete Cadre Succession Vulnerability Matrix across all ISS/SSS tiers.
    """
    officers = db.scalars(select(Officer)).all()
    matrix = []

    total_sanctioned = 0
    total_ready_candidates = 0
    critical_vacancies_count = 0

    for level in CADRE_SUCCESSION_CHAIN:
        target_role = level["target_cadre"]
        feeder_role = level["feeder_cadre"]
        threshold = level["critical_threshold"]

        # Current incumbents in target cadre
        incumbents = [
            o for o in officers 
            if o.current_role and o.current_role.lower() == target_role.lower()
        ]

        # Feeder pool officers
        feeder_officers = [
            o for o in officers 
            if o.current_role and o.current_role.lower() == feeder_role.lower()
        ]

        # Feeder officers with readiness >= threshold (75%+)
        ready_feeder = [
            o for o in feeder_officers 
            if (o.readiness or 0) >= threshold
        ]

        # Feeder officers in pipeline (60% to threshold)
        pipeline_feeder = [
            o for o in feeder_officers 
            if 60.0 <= (o.readiness or 0) < threshold
        ]

        # Sanctioned posts: use actual incumbents count if larger, otherwise default sanctioned
        sanctioned_posts = max(len(incumbents) + 2, level["default_sanctioned"])
        bench_strength_ratio = round(len(ready_feeder) / sanctioned_posts, 2) if sanctioned_posts > 0 else 0.0

        # Risk Classification
        if bench_strength_ratio < 0.5:
            risk_level = "CRITICAL"
            risk_label = "Severe Succession Deficit"
            risk_color = "#dc2626"
            recommendation = f"Immediate leadership vacuum risk. Fast-track upskilling for top {len(pipeline_feeder)} pipeline candidates in {feeder_role}."
            critical_vacancies_count += 1
        elif bench_strength_ratio < 1.0:
            risk_level = "VULNERABLE"
            risk_label = "Fragile Candidate Depth"
            risk_color = "#d97706"
            recommendation = f"Succession pipeline is constrained. Target competency remediation in Phase 2 for {feeder_role} cohort."
        elif bench_strength_ratio < 2.0:
            risk_level = "HEALTHY"
            risk_label = "Adequate Bench Strength"
            risk_color = "#2563eb"
            recommendation = f"Adequate succession depth. Maintain continuous career pathway tracking."
        else:
            risk_level = "ROBUST"
            risk_label = "Talent Surplus"
            risk_color = "#16a34a"
            recommendation = f"High candidate readiness. Potential for cross-divisional deployment."

        # Sort ready candidates by readiness desc, years in role desc, gaps asc
        sorted_candidates = sorted(
            feeder_officers,
            key=lambda o: (-(o.readiness or 0), -(o.years_in_role or 0), o.open_gaps or 0)
        )

        top_candidates = [
            {
                "id": o.id,
                "name": o.name,
                "department": o.department or "Unassigned",
                "current_role": o.current_role,
                "readiness": round(o.readiness, 1),
                "years_in_role": o.years_in_role,
                "open_gaps": o.open_gaps,
                "status": "ready" if (o.readiness or 0) >= threshold else ("near_ready" if (o.readiness or 0) >= 60.0 else "developing"),
                "missing_skills": [s.strip() for s in (o.missing_skills or "").replace("|", ";").split(";") if s.strip()][:3]
            }
            for o in sorted_candidates[:5]
        ]

        total_sanctioned += sanctioned_posts
        total_ready_candidates += len(ready_feeder)

        matrix.append({
            "id": level["id"],
            "target_cadre": target_role,
            "feeder_cadre": feeder_role,
            "cadre_tier": level["cadre_tier"],
            "responsibilities": level["responsibilities"],
            "sanctioned_posts": sanctioned_posts,
            "current_incumbents_count": len(incumbents),
            "feeder_pool_size": len(feeder_officers),
            "ready_candidates_count": len(ready_feeder),
            "pipeline_candidates_count": len(pipeline_feeder),
            "critical_threshold": threshold,
            "bench_strength_ratio": bench_strength_ratio,
            "risk_level": risk_level,
            "risk_label": risk_label,
            "risk_color": risk_color,
            "strategic_recommendation": recommendation,
            "top_candidates": top_candidates
        })

    overall_ratio = round(total_ready_candidates / total_sanctioned, 2) if total_sanctioned > 0 else 0.0

    return {
        "status": "success",
        "overall_summary": {
            "total_sanctioned_evaluated": total_sanctioned,
            "total_ready_feeder_officers": total_ready_candidates,
            "overall_bench_strength_ratio": overall_ratio,
            "critical_vulnerabilities": critical_vacancies_count,
            "cadre_tiers_evaluated": len(matrix)
        },
        "succession_matrix": matrix
    }


def seed_department_skill_weights_if_empty(db: Session):
    """Seed baseline department skill multipliers if table is empty."""
    count = db.scalar(select(func.count(DepartmentSkillWeight.id))) or 0
    if count == 0:
        for dept, priorities in DEFAULT_DEPARTMENT_PRIORITIES.items():
            for skill, mult, rationale in priorities:
                db.add(DepartmentSkillWeight(
                    department=dept,
                    skill_name=skill,
                    multiplier=mult,
                    rationale=rationale
                ))
        db.commit()


def compute_departmental_criticality_analytics(db: Session) -> dict[str, Any]:
    """
    Computes department-level weighted readiness based on custom skill criticality multipliers (1.0x - 2.0x).
    """
    seed_department_skill_weights_if_empty(db)
    officers = db.scalars(select(Officer)).all()
    skills = db.scalars(select(Skill)).all()
    weights_rows = db.scalars(select(DepartmentSkillWeight)).all()

    # Map weights: (dept, skill_name_norm) -> row
    weight_map = {}
    for w in weights_rows:
        weight_map[(w.department.lower(), w.skill_name.lower())] = w

    # Group officers by department
    dept_officers = {}
    for o in officers:
        dept = o.department or "Unassigned"
        dept_officers.setdefault(dept, []).append(o)

    departments_result = []

    for dept_name, off_list in dept_officers.items():
        base_readiness_avg = round(sum(o.readiness for o in off_list) / len(off_list), 1) if off_list else 0.0

        # Department priority weights
        dept_weights = [w for w in weights_rows if w.department.lower() == dept_name.lower()]
        
        # Calculate weighted gap severity and strategic readiness
        weighted_gap_accum = 0.0
        weight_sum = 0.0
        priority_breakdown = []

        for pw in dept_weights:
            # How many officers in this department have a gap in this skill?
            canonical = _normalize(pw.skill_name)
            aliases = {canonical, *(_normalize(a) for a in SKILL_ALIASES.get(pw.skill_name.lower(), []))}

            gap_count = sum(
                1 for o in off_list 
                if any(m in aliases for m in [_normalize(x) for x in (o.missing_skills or "").replace("|", ";").split(";") if x.strip()])
            )
            gap_pct = round((gap_count / len(off_list)) * 100, 1) if off_list else 0.0
            weighted_score = round(gap_pct * pw.multiplier, 1)

            weighted_gap_accum += (100.0 - gap_pct) * pw.multiplier
            weight_sum += pw.multiplier

            priority_breakdown.append({
                "id": pw.id,
                "skill_name": pw.skill_name,
                "multiplier": pw.multiplier,
                "rationale": pw.rationale,
                "officers_with_gap": gap_count,
                "gap_percentage": gap_pct,
                "weighted_gap_score": weighted_score
            })

        # Weighted strategic readiness
        strategic_readiness = round(weighted_gap_accum / weight_sum, 1) if weight_sum > 0 else base_readiness_avg

        departments_result.append({
            "department": dept_name,
            "officer_count": len(off_list),
            "baseline_readiness": base_readiness_avg,
            "strategic_weighted_readiness": strategic_readiness,
            "readiness_delta": round(strategic_readiness - base_readiness_avg, 1),
            "priorities": priority_breakdown
        })

    departments_result.sort(key=lambda d: -d["officer_count"])

    return {
        "status": "success",
        "departments": departments_result
    }


def update_department_multiplier(db: Session, weight_id: int, multiplier: float, rationale: str = "") -> dict:
    """Updates a department skill multiplier between 1.0x and 2.0x."""
    mult = max(1.0, min(2.5, round(multiplier, 2)))
    rec = db.get(DepartmentSkillWeight, weight_id)
    if not rec:
        raise ValueError(f"Weight record with ID {weight_id} not found")
    rec.multiplier = mult
    if rationale:
        rec.rationale = rationale
    db.commit()
    db.refresh(rec)
    return {
        "status": "success",
        "id": rec.id,
        "department": rec.department,
        "skill_name": rec.skill_name,
        "multiplier": rec.multiplier,
        "rationale": rec.rationale
    }
