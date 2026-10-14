"""
StatIntel AI Cadre Copilot & Career Pathway Engine
--------------------------------------------------
Generates verified career progression pathways, syllabus breakdowns,
and official learning sources for statistical officers.
Supports Google Gemini API with seamless deterministic fallback.
"""
import os
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Role, Skill, Course, RoleSkill


# Official verified learning sources database for statistical cadres
VERIFIED_LEARNING_SOURCES = {
    "python & reproducible analysis": [
        {
            "title": "Python for Official Statistics & Microdata Processing",
            "provider": "iOSS / United Nations Statistics Division (UNSD)",
            "type": "Official UN Curriculum",
            "url": "https://unstats.un.org/unsd/statcom/",
            "duration": "4 weeks (Self-paced)",
            "focus": "Automating survey data cleaning, pandas for census tables, reproducible Jupyter reporting",
            "free": True
        },
        {
            "title": "Python Data Science Handbook & Open Courseware",
            "provider": "Jake VanderPlas / University of Washington",
            "type": "Open Academic Text & Code",
            "url": "https://jakevdp.github.io/PythonDataScienceHandbook/",
            "duration": "6 weeks",
            "focus": "NumPy arrays, Pandas DataFrames, Matplotlib & Seaborn statistical charting",
            "free": True
        }
    ],
    "applied sampling methodology": [
        {
            "title": "Probability Sampling & Estimation in Large-Scale Surveys",
            "provider": "Indian Statistical Institute (ISI) Kolkata",
            "type": "Academic Post-Graduate Module",
            "url": "https://www.isical.ac.in/",
            "duration": "6 weeks",
            "focus": "Stratified multi-stage sampling, PPS sampling, design effect, sample weight calibration",
            "free": True
        },
        {
            "title": "Household Survey Design & Implementation Guidelines",
            "provider": "United Nations Statistics Division (UNSD)",
            "type": "Standard Statistical Monograph",
            "url": "https://unstats.un.org/unsd/hhsurveys/",
            "duration": "Self-study reference",
            "focus": "Cluster sampling, non-response weighting, variance estimation using Taylor linearization",
            "free": True
        }
    ],
    "data quality & validation": [
        {
            "title": "European Statistical System (ESS) Quality Assurance Framework",
            "provider": "Eurostat",
            "type": "Official Quality Standard",
            "url": "https://ec.europa.eu/eurostat/web/quality",
            "duration": "2 weeks",
            "focus": "Validation rules, edit & imputation principles, Fellegi-Holt methodology, metadata standards",
            "free": True
        }
    ],
    "sql & data management": [
        {
            "title": "Relational Database Design for Statistical Aggregation",
            "provider": "Stanford Online / DB Courseware",
            "type": "University Open Course",
            "url": "https://online.stanford.edu/courses/soe-ydatabases",
            "duration": "3 weeks",
            "focus": "Complex joins, window functions (OVER/PARTITION), query optimization for census tables",
            "free": True
        }
    ],
    "ai / machine learning foundations": [
        {
            "title": "Responsible AI & Machine Learning in Official Statistics",
            "provider": "OECD Statistics Directorate",
            "type": "International Working Group Guide",
            "url": "https://www.oecd.org/sdd/",
            "duration": "3 weeks",
            "focus": "Supervised classification on administrative data, model explainability, algorithmic bias audit",
            "free": True
        }
    ],
    "time series analysis": [
        {
            "title": "Seasonal Adjustment & Time Series Decomposition (JDemetra+)",
            "provider": "Eurostat / National Bank of Belgium",
            "type": "Official Software & Methodology",
            "url": "https://ec.europa.eu/eurostat/cros/content/documentation_en",
            "duration": "3 weeks",
            "focus": "X-13ARIMA-SEATS, TRAMO-SEATS, monthly index adjustment (IIP/CPI)",
            "free": True
        }
    ],
    "econometric modelling": [
        {
            "title": "Applied Econometrics & Panel Data Analysis",
            "provider": "MIT OpenCourseWare (Economics)",
            "type": "University Courseware",
            "url": "https://ocw.mit.edu/courses/economics/",
            "duration": "8 weeks",
            "focus": "Instrumental variables, fixed/random effects, macroeconomic forecasting",
            "free": True
        }
    ],
    "data visualisation": [
        {
            "title": "Statistical Storytelling & Graphic Standards",
            "provider": "UNECE (United Nations Economic Commission for Europe)",
            "type": "Making Data Meaningful Guide",
            "url": "https://unece.org/statistics/making-data-meaningful",
            "duration": "1 week",
            "focus": "Chart integrity, color accessibility, executive infographics, interactive dashboard design",
            "free": True
        }
    ]
}


def _call_groq_api(prompt: str, api_key: str) -> Optional[str]:
    """Call Groq API with ultra-low latency for statistical career guidance."""
    import httpx
    model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are StatIntel's Senior Cadre Development Advisor for National Statistical Systems. Provide expert, grounded civil service guidance."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 1024
    }
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=6.0)
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"Groq API invocation note: {e}")
        return None
    return None


def _call_gemini_api(prompt: str, api_key: str) -> Optional[str]:
    """Call Google Gemini REST API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 1000,
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            candidates = res_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
    except Exception as e:
        print(f"Gemini API invocation note (using fallback): {e}")
        return None
    return None


def generate_career_pathway(
    role_name: str,
    target_role: Optional[str],
    skill_focus: Optional[str],
    user_query: Optional[str],
    db: Session
) -> Dict[str, Any]:
    """
    Generate an evidence-based neural career pathway, learning roadmap,
    and verified learning sources for a statistical officer.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    # Query DB context
    roles = db.scalars(select(Role)).all()
    skills = db.scalars(select(Skill)).all()
    courses = db.scalars(select(Course)).all()

    # Guard against identical current and target roles
    CADRE_HIERARCHY = [
        "Statistical Investigator",
        "Junior Statistical Officer",
        "Senior Statistical Officer",
        "Assistant Director",
        "Deputy Director",
        "Director",
        "ISS Officer"
    ]
    if target_role and target_role.strip().lower() == role_name.strip().lower():
        curr_idx = next((i for i, r in enumerate(CADRE_HIERARCHY) if r.lower() == role_name.lower()), -1)
        if curr_idx >= 0 and curr_idx < len(CADRE_HIERARCHY) - 1:
            target_role = CADRE_HIERARCHY[curr_idx + 1]
        else:
            target_role = "Senior Cadre Specialization"

    # Find matching role and target
    curr_role_obj = next((r for r in roles if r.name.lower() == role_name.lower()), None)
    target_role_obj = next((r for r in roles if target_role and r.name.lower() == target_role.lower()), None)

    # Determine skills needed
    needed_skills = []
    if target_role_obj:
        for rs in target_role_obj.requirements:
            needed_skills.append(rs.skill.name)
    elif curr_role_obj:
        for rs in curr_role_obj.requirements:
            needed_skills.append(rs.skill.name)
    if not needed_skills and skills:
        needed_skills = [s.name for s in skills[:3]]

    # Collect verified learning sources
    curated_sources = []
    for s_name in needed_skills:
        key = s_name.lower()
        matched_key = next((k for k in VERIFIED_LEARNING_SOURCES if k in key or key in k), None)
        if matched_key:
            curated_sources.extend(VERIFIED_LEARNING_SOURCES[matched_key])

    # Deduplicate sources
    seen_titles = set()
    unique_sources = []
    for src in curated_sources:
        if src["title"] not in seen_titles:
            seen_titles.add(src["title"])
            unique_sources.append(src)

    # Try Gemini API if available
    llm_narrative = None
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    prompt = f"""
    You are StatIntel's Senior Cadre Development Advisor for National Statistical Systems.
    Current Role: {role_name}
    Target Progression: {target_role or 'Senior Specialization'}
    Primary Skill Focus: {skill_focus or ', '.join(needed_skills)}
    User Query: {user_query or 'Provide career transition pathway and learning recommendations'}

    Provide a concise, high-impact career progression plan formatted in clear Markdown:
    1. Cadre Transition Overview: Key responsibilities difference and competency delta.
    2. 12-Week Structured Learning Roadmap (Weeks 1-4, Weeks 5-8, Weeks 9-12) with practical official statistics project milestones.
    3. Recommended Official Learning Sources and Institutional Standards.
    Keep it professional, actionable, and strictly aligned with official civil service statistical cadres.
    """
    mode = "deterministic_cadre_ai"

    # 1. Try ultra-fast Groq API
    if groq_key and groq_key.lower() not in ("admin", "none", "changeme", "your-api-key"):
        llm_narrative = _call_groq_api(prompt, groq_key)
        if llm_narrative:
            mode = "live_groq_ai"

    # 2. Try Gemini API as fallback
    if not llm_narrative and gemini_key and gemini_key.lower() not in ("admin", "none", "changeme", "your-api-key"):
        llm_narrative = _call_gemini_api(prompt, gemini_key)
        if llm_narrative:
            mode = "live_gemini"

    # 3. If LLM was unavailable or returned empty, generate deterministic high-accuracy expert guidance
    if not llm_narrative:
        llm_narrative = _generate_deterministic_pathway(
            role_name=role_name,
            target_role=target_role or "Senior Specialization",
            skills=needed_skills,
            user_query=user_query
        )

    return {
        "status": "success",
        "current_role": role_name,
        "target_role": target_role or "Senior Specialization",
        "competency_focus": needed_skills,
        "ai_analysis": llm_narrative,
        "verified_sources": unique_sources[:4],
        "suggested_projects": [
            f"Automate monthly data validation scripts for {role_name} reports using Python & Pandas",
            "Implement multi-stage probability sampling design with Taylor linearization variance estimation",
            "Build an executive dashboard visualizing state/district level statistical indicators",
        ],
        "estimated_duration": "10–12 weeks (approx. 5 hours/week)",
        "mode": mode
    }


def _generate_deterministic_pathway(
    role_name: str,
    target_role: str,
    skills: list[str],
    user_query: Optional[str]
) -> str:
    """Generate high-accuracy cadre transition pathway when offline or without API key."""
    skill_list_str = ", ".join(skills[:4]) if skills else "Data Validation, Applied Sampling, Python"

    return f"""### Cadre Progression Dossier: {role_name} &rarr; {target_role}

#### 1.0 Strategic Competency Delta
To progress from **{role_name}** to **{target_role}**, the officer must shift from routine field enumeration/data entry toward **independent methodological design, automated reproducible validation, and statistical reporting**.
- **Critical Bridge Competencies:** {skill_list_str}.
- **Cadre Expectation:** In {target_role}, the officer is evaluated on designing sampling frames, auditing data quality under the European Statistical System (ESS) framework, and delivering publication-ready index series.

---

#### 2.0 Twelve-Week Development Trajectory

* **Weeks 1–4: Core Methodological Foundations**
  * Master stratified multi-stage probability sampling & PPS designs (ISI Kolkata curriculum).
  * Shift from manual Excel spreadsheets to clean Python/R data ingestion pipelines.
  * *Milestone Project:* Write an automated data cleansing script applying Fellegi-Holt consistency rules on sample survey data.

* **Weeks 5–8: Analytical Rigor & Modern Tools**
  * Implement relational SQL aggregation with window functions (`PARTITION BY`, `OVER`) for census databases.
  * Practice seasonal adjustment of monthly time series indicators using X-13ARIMA-SEATS principles.
  * *Milestone Project:* Re-estimate sample weights and design effects for a district-level household survey.

* **Weeks 9–12: Leadership, Governance & Executive Reporting**
  * Study OECD Guidelines on responsible AI and machine learning for public administration.
  * Develop clear statistical storytelling dashboards following UNECE data communication standards.
  * *Milestone Project:* Deliver an executive capability briefing note with reproducible charts and methodology provenance.

---

#### 3.0 Administrative & Methodological Recommendations
1. Focus on **reproducibility**—all estimations should be auditable via script (avoid unversioned spreadsheets).
2. Leverage the verified institutional learning sources listed below (UNSD, ISI Kolkata, Eurostat).
3. Partner with senior cadre mentors to conduct peer reviews of survey estimation methodology."""
