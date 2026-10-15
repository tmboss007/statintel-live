import csv, io, json, os, statistics
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from .database import Base, engine, get_db, SessionLocal
from .models import User, Officer, Skill, Role, RoleSkill, Course, AuditLog, AssessmentAttempt, Certificate, ConversationMessage
from .schemas import (
    LoginInput, RegisterInput, UserUpdate, OfficerInput, SkillInput, RoleInput,
    CourseInput, CopilotInput, PathwayGenerateInput, PathwayConverseInput, PathwayPdfInput,
    PathwayAccessGrantInput, QuizRequest, QuizSubmission, ChatSendMessageInput
)

from .security import hash_password, verify_password, create_token, current_user, require_admin
from .analytics import (
    compute_workforce_analytics, compute_gap_severity, compute_competency_heatmap,
    compute_officer_readiness_profile, compute_descriptive_stats, build_histogram,
    _profile_mentions_skill, _normalize, SKILL_ALIASES,
)
from .llm import generate_career_pathway
from .pathway import (
    generate_structured_roadmap, execute_grounded_conversation, generate_pathway_pdf_dossier
)
from .assessment import (
    get_quiz_questions, evaluate_quiz_submission, generate_certificate_pdf
)


FRONTEND_DIR = os.getenv("FRONTEND_DIR")
if not FRONTEND_DIR or not os.path.isdir(FRONTEND_DIR):
    _candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend")),
        os.path.abspath(os.path.join(os.getcwd(), "frontend")),
        "/frontend",
    ]
    FRONTEND_DIR = next((p for p in _candidates if os.path.isdir(p)), _candidates[0])


def _audit(db: Session, user: User | None, action: str, entity_type: str, entity_id: int | None = None, detail: str = ""):
    db.add(AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else "system",
        action=action, entity_type=entity_type, entity_id=entity_id, detail=detail,
    ))


def ensure_admin(db: Session):
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "ChangeMe-Now-123!")
    if not db.scalar(select(User).where(User.username == username)):
        db.add(User(username=username, password_hash=hash_password(password), role="admin", full_name="System Administrator"))
        db.commit()


def seed(db: Session):
    ensure_admin(db)
    if db.scalar(select(Officer.id).limit(1)) is None:
        demo = [
            ("Priya Sharma","National Sample Survey Office","Junior Statistical Officer","Senior Statistical Officer",58,4,"Survey methodology;Data validation;Statistical reporting","Python;Applied sampling;Data visualisation",3,"M.Sc. Statistics"),
            ("Arjun Menon","Directorate of Economics & Statistics","Statistical Investigator","Junior Statistical Officer",76,2,"Data collection;Survey operations;Quality assurance","SQL;Reproducible analysis",5,"B.Sc. Mathematics"),
            ("Farah Khan","National Statistical Office","Senior Statistical Officer","Assistant Director",69,3,"Survey design;Estimation;Team coordination","Python automation;Machine learning;Data storytelling",7,"M.A. Economics"),
            ("Rohan Das","National Sample Survey Office","Junior Statistical Officer","Senior Statistical Officer",47,6,"Field operations;Data entry","Sampling methods;SQL;Python;Data quality;Visualisation;Metadata",2,"B.Sc. Statistics"),
            ("Meera Iyer","National Statistical Office","Assistant Director","Deputy Director",84,1,"Statistical systems;Quality assurance;Leadership","Data governance",12,"Ph.D. Statistics"),
            ("Kabir Rao","Directorate of Economics & Statistics","Statistical Investigator","Junior Statistical Officer",63,3,"Data collection;Field protocols","SQL;Data visualisation;Python",4,"M.Sc. Applied Statistics"),
            ("Ananya Gupta","Central Statistics Office","Junior Statistical Officer","Senior Statistical Officer",72,2,"Index computation;Price statistics;Data cleaning","R programming;Advanced Excel",3,"M.Sc. Statistics"),
            ("Vikram Patel","Ministry of Statistics","Senior Statistical Officer","Assistant Director",55,5,"National accounts;GDP estimation;Quarterly reporting","Python;Econometric modelling;Time series",8,"M.A. Economics"),
            ("Deepa Nair","Labour Bureau","Statistical Investigator","Junior Statistical Officer",41,7,"Labour statistics;Survey execution","SQL;Sampling design;Data quality;Python;Stata",1,"B.A. Statistics"),
            ("Rajesh Kumar","Registrar General of India","Junior Statistical Officer","Senior Statistical Officer",88,1,"Census operations;Demographic analysis;Vital statistics","Machine learning",6,"M.Phil. Population Studies"),
            ("Sunita Devi","National Statistical Office","Deputy Director","Director",91,0,"Strategic planning;Policy analysis;Statistical coordination;International liaison","Cloud infrastructure",15,"Ph.D. Econometrics"),
            ("Amit Singh","Directorate of Economics & Statistics","Statistical Investigator","Junior Statistical Officer",34,8,"Basic data entry;Field enumeration","Python;SQL;Sampling;Data quality;Visualisation;Statistical testing;R;SAS",1,"B.Sc. Mathematics"),
        ]
        for name,dept,role,target,ready,gaps,skills,missing,years,qual in demo:
            db.add(Officer(name=name,department=dept,current_role=role,target_role=target,readiness=ready,open_gaps=gaps,
                           skills=skills,missing_skills=missing,assessment_source="Synthetic demonstration seed",
                           assessment_date="",years_in_role=years,qualification=qual,is_demo=True))
    if db.scalar(select(Skill.id).limit(1)) is None:
        skills_data = [
            ("Python & reproducible analysis","Data & programming","Ability to use Python for data processing, statistical computation, and reproducible analytical workflows."),
            ("Applied sampling methodology","Survey methodology","Knowledge of probability sampling designs, estimation theory, and practical survey implementation."),
            ("Data quality & validation","Statistical operations","Skills in data cleaning, validation rules, consistency checks, and quality assurance frameworks."),
            ("SQL & data management","Data & programming","Proficiency in SQL for querying, managing, and transforming statistical databases."),
            ("AI / machine learning foundations","Emerging technology","Understanding of supervised/unsupervised learning, model evaluation, and responsible AI in official statistics."),
            ("Data visualisation","Communication","Ability to create clear, accurate statistical graphics and dashboards for varied audiences."),
            ("Time series analysis","Analytical methods","Methods for analysing temporal data including decomposition, ARIMA, and seasonal adjustment."),
            ("Econometric modelling","Analytical methods","Regression analysis, panel data methods, and causal inference techniques for economic data."),
            ("R programming","Data & programming","Statistical computing using R for analysis, visualisation, and reproducible research."),
            ("Survey design & questionnaire","Survey methodology","Designing survey instruments, cognitive testing, and minimising measurement error."),
        ]
        for name,domain,desc in skills_data:
            db.add(Skill(name=name,domain=domain,description=desc,source_reference="",review_status="Pending official validation",is_demo=True))
    if db.scalar(select(Role.id).limit(1)) is None:
        for name,grade in [("Junior Statistical Officer","Entry / Group B"),("Senior Statistical Officer","Mid-career / Group B"),("Statistical Investigator","Entry / Group C"),("Assistant Director","Senior / Group A"),("Deputy Director","Senior / Group A"),("ISS Officer","Group A"),("Director","Senior / Group A")]:
            db.add(Role(name=name,grade=grade,source_reference="",review_status="Pending official validation"))
    if db.scalar(select(RoleSkill.id).limit(1)) is None:
        db.flush()
        role_skill_map = {
            "Junior Statistical Officer": ["Python & reproducible analysis", "Applied sampling methodology", "Data quality & validation"],
            "Senior Statistical Officer": ["Python & reproducible analysis", "Applied sampling methodology", "Data quality & validation", "SQL & data management", "Data visualisation"],
            "Statistical Investigator": ["Applied sampling methodology", "Data quality & validation", "SQL & data management"],
            "Assistant Director": ["Data quality & validation", "SQL & data management", "AI / machine learning foundations", "Data visualisation", "Time series analysis"],
            "Deputy Director": ["Data quality & validation", "SQL & data management", "AI / machine learning foundations", "Data visualisation", "Econometric modelling"],
            "ISS Officer": ["Python & reproducible analysis", "SQL & data management", "AI / machine learning foundations", "Data visualisation"],
            "Director": ["AI / machine learning foundations", "Data visualisation", "Econometric modelling", "Time series analysis"],
        }
        for role_name, skill_names in role_skill_map.items():
            role = db.scalar(select(Role).where(Role.name == role_name))
            if not role: continue
            for skill_name in skill_names:
                skill = db.scalar(select(Skill).where(Skill.name == skill_name))
                if skill and not db.scalar(select(RoleSkill.id).where(RoleSkill.role_id == role.id, RoleSkill.skill_id == skill.id)):
                    db.add(RoleSkill(role_id=role.id, skill_id=skill.id, required_level=3))
    if db.scalar(select(Course.id).limit(1)) is None:
        courses_data = [
            ("Python for Official Statistics","iOSS / UNSD","Python & reproducible analysis","Data & programming","2 weeks"),
            ("Applied Sampling & Estimation","ISI Kolkata","Applied sampling methodology","Survey methodology","2 weeks"),
            ("SQL for Statistical Data","DataCamp","SQL & data management","Data & programming","10 hours"),
            ("Responsible AI for Public Data","OECD","AI / machine learning foundations","Emerging technology","1 week"),
            ("Data Visualisation with Python","Coursera","Data visualisation","Communication","4 weeks"),
            ("Time Series for Official Statistics","Eurostat","Time series analysis","Analytical methods","3 weeks"),
            ("Introduction to R","RStudio Education","R programming","Data & programming","2 weeks"),
            ("Survey Design Fundamentals","University of Michigan","Survey design & questionnaire","Survey methodology","6 weeks"),
        ]
        for name,provider,skill,domain,duration in courses_data:
            db.add(Course(name=name,provider=provider,skill_name=skill,domain=domain,duration=duration,verified=False))
    db.commit()


def ensure_schema_migrations(eng):
    """Ensure newly added columns exist in existing database tables."""
    from sqlalchemy import text
    with eng.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN officer_id INTEGER"))
            conn.commit()
        except Exception:
            pass
        for col, col_type in [
            ("assigned_pathway", "TEXT"),
            ("assigned_by", "VARCHAR(80)"),
            ("assigned_at", "TIMESTAMP WITH TIME ZONE")
        ]:
            try:
                conn.execute(text(f"ALTER TABLE officers ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_migrations(engine)
    with SessionLocal() as db:
        ensure_admin(db)
        if os.getenv("SEED_DEMO_DATA", "true").lower() == "true":
            seed(db)
    yield


app = FastAPI(
    title="StatIntel Workforce Intelligence API",
    version="2.0.0",
    description="Workforce intelligence platform for statistical organisations. Provides role-competency mapping, "
                "gap analysis with weighted severity scoring, descriptive statistics, competency heatmaps, and "
                "individual officer readiness profiling. Seed records are illustrative, not official statistics.",
    lifespan=lifespan,
)
cors_env = os.getenv("CORS_ORIGINS", "*").strip()
if cors_env == "*":
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    origins = [x.strip() for x in cors_env.split(",") if x.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(select(1))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    officer_count = db.scalar(select(func.count(Officer.id)))
    skill_count = db.scalar(select(func.count(Skill.id)))
    return {
        "status": "ok",
        "database": "connected",
        "records": {"officers": officer_count, "skills": skill_count},
        "data_mode": "demo_seeded" if os.getenv("SEED_DEMO_DATA","true").lower()=="true" else "user_data",
        "official_data_connected": False,
        "model_inference_enabled": False,
        "version": "2.0.0",
    }


# ── Authentication ──────────────────────────────────────────────────────────

@app.post("/api/auth/login")
def login(payload: LoginInput, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not user.active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    return {
        "access_token": create_token(user), "token_type": "bearer",
        "username": user.username, "role": user.role, "full_name": user.full_name,
        "officer_id": user.officer_id, "email": user.email
    }


@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterInput, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status_code=409, detail="Username already taken")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        email=payload.email,
        role="viewer",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "access_token": create_token(user), "token_type": "bearer",
        "username": user.username, "role": user.role, "full_name": user.full_name,
        "officer_id": user.officer_id, "email": user.email
    }


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {
        "id": user.id, "username": user.username, "role": user.role,
        "full_name": user.full_name, "email": user.email, "officer_id": user.officer_id
    }



@app.patch("/api/auth/me")
def update_profile(payload: UserUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.email is not None:
        user.email = payload.email
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    db.commit()
    return {"ok": True, "username": user.username}


# ── Dashboard (enhanced) ───────────────────────────────────────────────────

@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    people = db.scalars(select(Officer)).all()
    count = len(people)
    average = round(statistics.mean([p.readiness for p in people]), 1) if people else 0
    total_gaps = sum(p.open_gaps for p in people)
    demo_count = sum(1 for p in people if p.is_demo)
    skill_rows = db.scalars(select(Skill)).all()
    priority = [
        {
            "skill": skill.name,
            "profile_mentions": sum(1 for p in people if _profile_mentions_skill(p, skill.name)),
            "severity": compute_gap_severity(
                sum(1 for p in people if _profile_mentions_skill(p, skill.name)), count
            ),
        }
        for skill in skill_rows
    ]
    priority.sort(key=lambda x: (-x["severity"]["score"], x["skill"]))

    # Department summary
    dept_counts = {}
    for p in people:
        dept = p.department or "Unassigned"
        if dept not in dept_counts:
            dept_counts[dept] = {"count": 0, "readiness_sum": 0}
        dept_counts[dept]["count"] += 1
        dept_counts[dept]["readiness_sum"] += p.readiness
    dept_summary = [
        {"name": d, "count": v["count"], "avg_readiness": round(v["readiness_sum"]/v["count"],1)}
        for d, v in sorted(dept_counts.items())
    ]

    return {
        "profile_count": count,
        "average_readiness": average,
        "reported_gaps": total_gaps,
        "demo_profiles": demo_count,
        "user_entered_profiles": count - demo_count,
        "training_completion": None,
        "priority_skills": priority,
        "departments": dept_summary,
        "readiness_median": round(statistics.median([p.readiness for p in people]), 1) if people else 0,
        "readiness_std_dev": round(statistics.pstdev([p.readiness for p in people]), 1) if people else 0,
        "data_note": "Metrics are computed from database records. Readiness and gap values are user-entered or synthetic until backed by validated assessment evidence.",
        "official_statistics": False,
    }


# ── Analytics Endpoints ────────────────────────────────────────────────────

@app.get("/api/analytics/workforce")
def workforce_analytics(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return compute_workforce_analytics(db)


@app.get("/api/analytics/heatmap")
def heatmap(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return compute_competency_heatmap(db)


@app.get("/api/analytics/officer/{officer_id}")
def officer_analysis(officer_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    officer = db.get(Officer, officer_id)
    if not officer:
        raise HTTPException(404, detail="Officer not found")
    return compute_officer_readiness_profile(officer, db)


# ── Officers ───────────────────────────────────────────────────────────────

@app.get("/api/officers")
def list_officers(q: str = "", department: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(Officer).order_by(Officer.name)
    if q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            (Officer.name.ilike(pattern)) | (Officer.current_role.ilike(pattern)) |
            (Officer.target_role.ilike(pattern)) | (Officer.department.ilike(pattern))
        )
    if department:
        stmt = stmt.where(Officer.department == department)
    return [
        {k: getattr(p, k) for k in [
            "id","name","department","current_role","target_role","readiness","open_gaps",
            "skills","missing_skills","assessment_source","assessment_date","years_in_role",
            "qualification","is_demo"
        ]}
        for p in db.scalars(stmt).all()
    ]


@app.post("/api/officers", status_code=201)
def create_officer(payload: OfficerInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    if db.scalar(select(Officer.id).where(func.lower(Officer.name)==payload.name.strip().lower())):
        raise HTTPException(409, detail="An officer with this name already exists")
    p = Officer(
        name=payload.name.strip(), department=payload.department,
        current_role=payload.current_role, target_role=payload.target_role,
        readiness=payload.readiness, open_gaps=payload.open_gaps,
        skills=";".join(payload.skills), missing_skills=";".join(payload.missing_skills),
        assessment_source=payload.assessment_source, assessment_date=payload.assessment_date,
        years_in_role=payload.years_in_role, qualification=payload.qualification,
        is_demo=payload.is_demo,
    )
    db.add(p)
    _audit(db, user, "create", "officer", detail=p.name)
    db.commit()
    db.refresh(p)
    return {"id": p.id, "name": p.name}


@app.put("/api/officers/{officer_id}")
def update_officer(officer_id: int, payload: OfficerInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    p = db.get(Officer, officer_id)
    if not p:
        raise HTTPException(404, detail="Officer not found")
    for key in ["name","department","current_role","target_role","readiness","open_gaps",
                "assessment_source","assessment_date","years_in_role","qualification","is_demo"]:
        setattr(p, key, getattr(payload, key))
    p.skills = ";".join(payload.skills)
    p.missing_skills = ";".join(payload.missing_skills)
    _audit(db, user, "update", "officer", entity_id=p.id, detail=p.name)
    db.commit()
    return {"ok": True, "id": p.id}


@app.delete("/api/officers/{officer_id}", status_code=204)
def delete_officer(officer_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    p = db.get(Officer, officer_id)
    if not p:
        raise HTTPException(404, detail="Officer not found")
    _audit(db, user, "delete", "officer", entity_id=p.id, detail=p.name)
    db.delete(p)
    db.commit()
    return None


@app.post("/api/officers/import-csv")
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_admin)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, detail="Upload a .csv file")
    raw = await file.read()
    if len(raw) > 5_000_000:
        raise HTTPException(413, detail="CSV file exceeds 5 MB")
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
    except Exception:
        raise HTTPException(400, detail="Could not read CSV as UTF-8")
    if not reader.fieldnames:
        raise HTTPException(400, detail="CSV header row is missing")
    normalize = lambda x: (x or "").strip().lower().replace(" ","").replace("_","").replace("-","")
    headers = {normalize(h): h for h in reader.fieldnames}
    if not any(k in headers for k in ["name","officer","officername"]):
        raise HTTPException(400, detail="CSV requires a name column")
    def val(row, *keys, default=""):
        for k in keys:
            if k in headers and row.get(headers[k]) is not None:
                return row.get(headers[k]).strip()
        return default
    added = updated = skipped = 0
    for row in reader:
        name = val(row, "name", "officer", "officername")
        if not name:
            skipped += 1
            continue
        try:
            readiness = float(val(row, "readiness", "readinesspercent", "score", default="0").replace("%",""))
            gaps = int(float(val(row, "gaps", "gapcount", "opengaps", default="0")))
            if not 0 <= readiness <= 100 or gaps < 0:
                raise ValueError()
        except ValueError:
            skipped += 1
            continue
        p = db.scalar(select(Officer).where(func.lower(Officer.name) == name.lower()))
        values = {
            "department": val(row, "department", "dept", default="Not specified"),
            "current_role": val(row, "role", "currentrole", default="Not specified"),
            "target_role": val(row, "target", "targetrole", default="Not specified"),
            "readiness": readiness, "open_gaps": gaps,
            "skills": val(row, "skills", "evidencedskills").replace("|", ";"),
            "missing_skills": val(row, "missing", "missingskills", "skillgaps").replace("|", ";"),
            "assessment_source": val(row, "assessmentsource", "source", default="Imported CSV; unverified"),
            "assessment_date": val(row, "assessmentdate", "date"),
            "years_in_role": int(float(val(row, "yearsinrole", "years", default="0"))),
            "qualification": val(row, "qualification", "qual", default=""),
            "is_demo": False,
        }
        if p:
            for k, v in values.items():
                setattr(p, k, v)
            updated += 1
        else:
            db.add(Officer(name=name, **values))
            added += 1
    _audit(db, user, "import", "officer", detail=f"CSV: +{added} ~{updated} skip={skipped}")
    db.commit()
    return {
        "added": added, "updated": updated, "skipped": skipped,
        "note": "CSV values are stored but not independently verified. Include source and assessment date for traceability.",
    }


# ── Skills ─────────────────────────────────────────────────────────────────

@app.get("/api/skills")
def list_skills(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [
        {"id": s.id, "name": s.name, "domain": s.domain, "description": s.description,
         "source_reference": s.source_reference, "review_status": s.review_status, "is_demo": s.is_demo}
        for s in db.scalars(select(Skill).order_by(Skill.domain, Skill.name)).all()
    ]


@app.post("/api/skills", status_code=201)
def create_skill(payload: SkillInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    s = Skill(**payload.model_dump())
    db.add(s)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail="Skill already exists")
    db.refresh(s)
    _audit(db, user, "create", "skill", entity_id=s.id, detail=s.name)
    db.commit()
    return {"id": s.id, "name": s.name, "review_status": s.review_status}


# ── Roles ──────────────────────────────────────────────────────────────────

@app.get("/api/roles")
def list_roles(db: Session = Depends(get_db), user: User = Depends(current_user)):
    roles = db.scalars(
        select(Role).options(joinedload(Role.requirements).joinedload(RoleSkill.skill)).order_by(Role.name)
    ).unique().all()
    return [
        {
            "id": r.id, "name": r.name, "grade": r.grade, "description": r.description,
            "source_reference": r.source_reference, "review_status": r.review_status,
            "required_skills": [
                {"skill_id": x.skill_id, "skill": x.skill.name, "required_level": x.required_level}
                for x in r.requirements
            ],
        }
        for r in roles
    ]


@app.post("/api/roles", status_code=201)
def create_role(payload: RoleInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    r = Role(
        name=payload.name, grade=payload.grade, description=payload.description,
        source_reference=payload.source_reference, review_status=payload.review_status,
    )
    db.add(r)
    try:
        db.flush()
        for skill_name in payload.required_skills:
            s = db.scalar(select(Skill).where(func.lower(Skill.name) == skill_name.lower()))
            if not s:
                s = Skill(name=skill_name, domain="General", review_status="Pending review", is_demo=False)
                db.add(s)
                db.flush()
            db.add(RoleSkill(role_id=r.id, skill_id=s.id, required_level=3))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail="Role already exists")
    _audit(db, user, "create", "role", entity_id=r.id, detail=r.name)
    db.commit()
    return {"id": r.id, "name": r.name}


# ── Courses ────────────────────────────────────────────────────────────────

@app.get("/api/courses")
def list_courses(q: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(Course).order_by(Course.name)
    if q.strip():
        stmt = stmt.where(
            (Course.name.ilike(f"%{q}%")) | (Course.skill_name.ilike(f"%{q}%")) | (Course.domain.ilike(f"%{q}%"))
        )
    return [
        {"id": c.id, "name": c.name, "provider": c.provider, "skill_name": c.skill_name,
         "domain": c.domain, "duration": c.duration, "url": c.url,
         "source_reference": c.source_reference, "verified": c.verified}
        for c in db.scalars(stmt).all()
    ]


@app.post("/api/courses", status_code=201)
def create_course(payload: CourseInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    c = Course(**payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    _audit(db, user, "create", "course", entity_id=c.id, detail=c.name)
    db.commit()
    return {"id": c.id, "name": c.name}


# ── Gap Analysis ───────────────────────────────────────────────────────────

@app.get("/api/gap-analysis")
def gap_analysis(db: Session = Depends(get_db), user: User = Depends(current_user)):
    people = db.scalars(select(Officer)).all()
    skill_rows = db.scalars(select(Skill)).all()
    total = len(people)
    result = []
    for s in skill_rows:
        matching = [p for p in people if _profile_mentions_skill(p, s.name)]
        severity = compute_gap_severity(len(matching), total)
        result.append({
            "skill_id": s.id, "skill": s.name, "domain": s.domain,
            "profile_mentions": len(matching),
            "severity_score": severity["score"],
            "severity_level": severity["level"],
            "mention_ratio": severity["ratio"],
            "profiles": [p.name for p in matching],
            "source_status": s.review_status,
        })
    result.sort(key=lambda x: (-x["severity_score"], x["skill"]))
    return {
        "items": result,
        "total_profiles": total,
        "method": "Weighted composite severity scoring: 60% mention-ratio + 40% log-scaled absolute impact. "
                  "This is a rule-based count of skill-name mentions in each profile's missing_skills field; not an AI prediction.",
        "data_quality_warning": "Accuracy depends on imported records and skill naming consistency. "
                                "Standardise skills and validate assessment sources for reliable results.",
    }


# ── Knowledge Graph ────────────────────────────────────────────────────────

@app.get("/api/graph")
def knowledge_graph(db: Session = Depends(get_db), user: User = Depends(current_user)):
    roles = db.scalars(
        select(Role).options(joinedload(Role.requirements).joinedload(RoleSkill.skill)).order_by(Role.name)
    ).unique().all()
    skills = db.scalars(select(Skill).order_by(Skill.name)).all()
    courses = db.scalars(select(Course).order_by(Course.name)).all()
    nodes, edges = [], []
    for r in roles:
        nodes.append({"id": f"role-{r.id}", "type": "role", "label": r.name,
                       "source_status": r.review_status, "source_reference": r.source_reference})
        for rs in r.requirements:
            edges.append({"from": f"role-{r.id}", "to": f"skill-{rs.skill_id}",
                          "type": "requires", "required_level": rs.required_level})
    for s in skills:
        nodes.append({"id": f"skill-{s.id}", "type": "skill", "label": s.name,
                       "source_status": s.review_status, "source_reference": s.source_reference})
    for c in courses:
        nodes.append({"id": f"course-{c.id}", "type": "course", "label": c.name,
                       "source_status": "Verified" if c.verified else "Unverified",
                       "source_reference": c.source_reference or c.url})
        target = next(
            (s for s in skills
             if _normalize(s.name) == _normalize(c.skill_name)
             or _normalize(c.skill_name) in {_normalize(a) for a in SKILL_ALIASES.get(s.name.lower(), [])}),
            None,
        )
        if target:
            edges.append({"from": f"course-{c.id}", "to": f"skill-{target.id}", "type": "teaches"})
    return {
        "nodes": nodes, "edges": edges,
        "note": "Edges come from stored role-skill mappings and course skill labels. Review status and source references are included.",
    }


# ── Audit Log ──────────────────────────────────────────────────────────────

@app.get("/api/audit-log")
def get_audit_log(limit: int = 50, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    logs = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 200))).all()
    return [
        {"id": l.id, "username": l.username, "action": l.action, "entity_type": l.entity_type,
         "entity_id": l.entity_id, "detail": l.detail, "created_at": l.created_at.isoformat()}
        for l in logs
    ]


# ── Export ─────────────────────────────────────────────────────────────────

@app.get("/api/export/officers.csv")
def export_officers(db: Session = Depends(get_db), user: User = Depends(current_user)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name","department","current_role","target_role","readiness","open_gaps",
                      "skills","missing_skills","years_in_role","qualification","assessment_source","assessment_date","is_demo"])
    for p in db.scalars(select(Officer).order_by(Officer.name)).all():
        writer.writerow([p.name,p.department,p.current_role,p.target_role,p.readiness,p.open_gaps,
                          p.skills,p.missing_skills,p.years_in_role,p.qualification,p.assessment_source,p.assessment_date,p.is_demo])
    return Response(content=output.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":"attachment; filename=statintel-officers.csv"})


@app.get("/api/export/pitch-dossier.pdf")
def export_pitch_dossier():
    pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "StatIntel_Executive_Pitch_and_Technical_Dossier.pdf"))
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Pitch dossier PDF not found")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="StatIntel_Executive_Pitch_and_Technical_Dossier.pdf"
    )


# ── AI Copilot ─────────────────────────────────────────────────────────────

@app.post("/api/ai/career-copilot")
def career_copilot(payload: CopilotInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return generate_career_pathway(
        role_name=payload.current_role,
        target_role=payload.target_role,
        skill_focus=payload.skill_focus,
        user_query=payload.message,
        db=db
    )


# ── Pathway Planner & Grounded Analyst ─────────────────────────────────────

@app.post("/api/pathway/generate")
def pathway_generate(payload: PathwayGenerateInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return generate_structured_roadmap(
        officer_id=payload.officer_id,
        target_role=payload.target_role,
        weekly_hours=payload.weekly_hours,
        preferred_style=payload.preferred_style,
        content_level=payload.content_level,
        db=db
    )


@app.post("/api/pathway/converse")
def pathway_converse(payload: PathwayConverseInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return execute_grounded_conversation(
        current_roadmap=payload.roadmap,
        user_message=payload.message,
        db=db
    )


@app.post("/api/pathway/export-pdf")
def pathway_export_pdf(payload: PathwayPdfInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    pdf_bytes = generate_pathway_pdf_dossier(payload.roadmap)
    officer_id = payload.roadmap.get("officer_id", "dossier")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=statintel-pathway-checklist-officer-{officer_id}.pdf"}
    )


@app.post("/api/pathway/grant-access")
def pathway_grant_access(payload: PathwayAccessGrantInput, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    email = payload.email.strip().lower()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="A valid institutional email address is required.")

    # Check or auto-provision user account
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    username_created = None
    default_pwd = None
    if not user:
        # Username from email prefix
        prefix = email.split("@")[0].replace(".", "_")
        candidate = prefix
        counter = 1
        while db.scalar(select(User.id).where(User.username == candidate)):
            candidate = f"{prefix}_{counter}"
            counter += 1
        default_pwd = f"Cadre@{datetime.now(timezone.utc).year}!"
        user = User(
            username=candidate,
            email=email,
            password_hash=hash_password(default_pwd),
            role="officer",
            full_name=email.split("@")[0].replace(".", " ").title(),
            active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        username_created = candidate

    # Link officer record to user account
    if payload.officer_id:
        user.officer_id = payload.officer_id
        user.role = "officer"

    # Detail logging & pathway sealing
    officer_name = "Cadre Development Profile"
    target_role_name = payload.target_role or "Senior Cadre Progression"
    off = None
    if payload.officer_id:
        off = db.get(Officer, payload.officer_id)
        if off:
            officer_name = off.name
            target_role_name = payload.target_role or off.target_role
            if payload.attach_current_roadmap and payload.roadmap:
                off.assigned_pathway = json.dumps(payload.roadmap)
                off.assigned_by = admin.username
                off.assigned_at = datetime.now(timezone.utc)
            elif payload.attach_current_roadmap and not off.assigned_pathway:
                generated = generate_structured_roadmap(
                    officer_id=off.id,
                    target_role=target_role_name,
                    weekly_hours=payload.weekly_hours,
                    preferred_style=payload.preferred_style,
                    content_level="operational",
                    db=db
                )
                off.assigned_pathway = json.dumps(generated)
                off.assigned_by = admin.username
                off.assigned_at = datetime.now(timezone.utc)

    detail_msg = f"Granted pathway access to {email}. Linked officer: {officer_name} (ID: {payload.officer_id}). Target role: {target_role_name}."
    if username_created:
        detail_msg += f" Created account: {username_created}."

    _audit(db, admin, "grant_access", "pathway", user.id, detail_msg)
    db.commit()

    # Generate one-click direct access token
    direct_token = create_token(user)
    direct_login_url = f"/#autologin={direct_token}&page=pathway"

    invitation_note = (
        f"🏛️ OFFICIAL STATINTEL CADRE PATHWAY INVITATION\n"
        f"---------------------------------------------------\n"
        f"Officer: {officer_name}\n"
        f"Email: {email}\n"
        f"Target Cadre: {target_role_name}\n"
        f"Authority Approved By: System Administrator ({admin.username})\n\n"
        f"ACCOUNT CREDENTIALS:\n"
        f"Username: {user.username}\n"
        f"Password: {default_pwd or '[Existing Password]'}\n\n"
        f"ONE-CLICK DIRECT ACCESS:\n"
        f"{direct_login_url}\n"
        f"---------------------------------------------------\n"
        f"You have been granted official access to your personalized cadre progression pathway, "
        f"verified curriculum lectures, competency verification examinations, and interactive cadre AI mentoring."
    )

    return {
        "status": "success",
        "message": f"Pathway planning access successfully granted to {email}.",
        "email": email,
        "user_id": user.id,
        "username": user.username,
        "officer_id": user.officer_id,
        "officer_name": officer_name,
        "target_role": target_role_name,
        "new_account_created": bool(username_created),
        "temporary_credentials": {
            "username": user.username,
            "temporary_password": default_pwd
        } if default_pwd else None,
        "direct_access_url": direct_login_url,
        "invitation_note": invitation_note,
        "assigned_pathway_attached": bool(off and off.assigned_pathway),
        "access_scope": "Full access to Plan My Pathway learning curriculum, YouTube video catalog, progress tracking, and progression chat.",
        "granted_at": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/pathway/my-pathway")
def pathway_my_pathway(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Retrieve the logged in officer's assigned pathway."""
    if not user.officer_id and user.email:
        # Auto-match by email or full name if not explicitly set
        candidate_off = db.scalar(select(Officer).where(func.lower(Officer.name) == func.lower(user.full_name)))
        if candidate_off:
            user.officer_id = candidate_off.id
            db.commit()

    if not user.officer_id:
        return {"has_assigned": False, "officer": None, "roadmap": None}

    off = db.get(Officer, user.officer_id)
    if not off:
        return {"has_assigned": False, "officer": None, "roadmap": None}

    roadmap = None
    if off.assigned_pathway:
        try:
            roadmap = json.loads(off.assigned_pathway)
        except Exception:
            roadmap = None

    if not roadmap:
        # Generate baseline roadmap on the fly
        roadmap = generate_structured_roadmap(
            officer_id=off.id,
            target_role=off.target_role or "Senior Statistical Officer",
            weekly_hours=4,
            preferred_style="applied",
            content_level="operational",
            db=db
        )
        off.assigned_pathway = json.dumps(roadmap)
        off.assigned_by = "System Auto-Provisioning"
        off.assigned_at = datetime.now(timezone.utc)
        db.commit()

    return {
        "has_assigned": True,
        "officer": {
            "id": off.id,
            "name": off.name,
            "department": off.department,
            "current_role": off.current_role,
            "target_role": off.target_role,
            "readiness": off.readiness,
            "open_gaps": off.open_gaps
        },
        "assigned_by": off.assigned_by or "Cadre Administration",
        "assigned_at": off.assigned_at.isoformat() if off.assigned_at else None,
        "roadmap": roadmap
    }


@app.get("/api/pathway/chat/history/{officer_id}")
def pathway_get_chat_history(officer_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Retrieve past persistent conversational messages for an officer."""
    messages = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.officer_id == officer_id)
        .order_by(ConversationMessage.created_at.asc())
        .limit(50)
    ).all()
    return [
        {
            "id": m.id,
            "sender": m.sender,
            "message": m.message,
            "created_at": m.created_at.isoformat() if m.created_at else None
        }
        for m in messages
    ]


@app.post("/api/pathway/chat/send")
def pathway_chat_send(payload: ChatSendMessageInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Persistent grounded conversational advisory."""
    # 1. Save user message
    user_msg = ConversationMessage(
        officer_id=payload.officer_id,
        user_id=user.id,
        sender="user",
        message=payload.message,
        created_at=datetime.now(timezone.utc)
    )
    db.add(user_msg)
    db.commit()

    # 2. Execute conversation with advisor
    advisor_res = execute_grounded_conversation(
        current_roadmap=payload.roadmap or {},
        user_message=payload.message,
        db=db
    )
    reply_text = advisor_res.get("reply", "")

    # 3. Save advisor response
    advisor_msg = ConversationMessage(
        officer_id=payload.officer_id,
        user_id=None,
        sender="advisor",
        message=reply_text,
        created_at=datetime.now(timezone.utc)
    )
    db.add(advisor_msg)
    db.commit()

    return {
        "status": "success",
        "reply": reply_text,
        "mode": advisor_res.get("mode", "grounded_catalog"),
        "created_at": advisor_msg.created_at.isoformat()
    }


@app.delete("/api/pathway/chat/clear/{officer_id}")
def pathway_chat_clear(officer_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Clear conversation history for this officer."""
    messages = db.scalars(select(ConversationMessage).where(ConversationMessage.officer_id == officer_id)).all()
    for m in messages:
        db.delete(m)
    db.commit()
    return {"status": "cleared", "deleted_count": len(messages)}



@app.get("/api/pathway/grants")
def pathway_list_grants(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.action == "grant_access", AuditLog.entity_type == "pathway")
        .order_by(AuditLog.created_at.desc())
        .limit(25)
    ).all()
    return [
        {
            "id": log.id,
            "granted_by": log.username,
            "detail": log.detail,
            "created_at": log.created_at.isoformat() if log.created_at else None
        }
        for log in logs
    ]


# ── Competency Assessment & Certification Engine ───────────────────────────

@app.get("/api/assessment/quiz")
def assessment_get_quiz(
    skill: str,
    tier: str = "operational",
    phase: int = 1,
    officer_id: int = 1,
    db: Session = Depends(get_db),
    user: User = Depends(current_user)
):
    return get_quiz_questions(skill_name=skill, cadre_tier=tier, phase_order=phase)


@app.post("/api/assessment/submit")
def assessment_submit(
    payload: QuizSubmission,
    db: Session = Depends(get_db),
    user: User = Depends(current_user)
):
    try:
        result = evaluate_quiz_submission(
            officer_id=payload.officer_id,
            skill_name=payload.skill_name,
            cadre_tier=payload.cadre_tier,
            phase_order=payload.phase_order,
            target_role=payload.target_role or "",
            answers=payload.answers,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assessment evaluation failed: {e}")


@app.get("/api/assessment/certificate/{cert_uuid}/verify")
def certificate_verify(cert_uuid: str, db: Session = Depends(get_db)):
    cert = db.scalar(select(Certificate).where(Certificate.cert_uuid == cert_uuid.strip()))
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found or invalid identifier")
    return {
        "status": "valid",
        "certificate_id": cert.cert_uuid,
        "officer_name": cert.officer_name,
        "skill_name": cert.skill_name,
        "cadre_tier": cert.cadre_tier,
        "target_role": cert.target_role,
        "examination_score": cert.score,
        "issued_at": cert.issued_at.isoformat() if cert.issued_at else None,
        "authenticity": "Verified by StatIntel National Cadre Registry"
    }


@app.get("/api/assessment/certificate/{cert_uuid}/pdf")
def certificate_download_pdf(cert_uuid: str, db: Session = Depends(get_db)):
    cert = db.scalar(select(Certificate).where(Certificate.cert_uuid == cert_uuid.strip()))
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found or invalid identifier")
    officer = db.get(Officer, cert.officer_id)
    if not officer:
        raise HTTPException(status_code=404, detail="Officer record missing")
    pdf_bytes = generate_certificate_pdf(cert, officer)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=StatIntel-Certificate-{cert.cert_uuid}.pdf"}
    )


@app.get("/api/assessment/certificates/officer/{officer_id}")
def officer_certificates(officer_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    certs = db.scalars(
        select(Certificate)
        .where(Certificate.officer_id == officer_id)
        .order_by(Certificate.issued_at.desc())
    ).all()
    return [
        {
            "id": c.id,
            "cert_uuid": c.cert_uuid,
            "skill_name": c.skill_name,
            "cadre_tier": c.cadre_tier,
            "target_role": c.target_role,
            "score": c.score,
            "issued_at": c.issued_at.isoformat() if c.issued_at else None
        }
        for c in certs
    ]


# ── Static files & SPA fallback ────────────────────────────────────────────


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
