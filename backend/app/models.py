from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def utcnow(): return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="admin")
    full_name: Mapped[str] = mapped_column(String(160), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    officer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("officers.id", ondelete="SET NULL"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    officer: Mapped["Officer | None"] = relationship(foreign_keys=[officer_id])

class Officer(Base):
    __tablename__ = "officers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    department: Mapped[str] = mapped_column(String(180), default="Not specified")
    current_role: Mapped[str] = mapped_column(String(160), default="Not specified")
    target_role: Mapped[str] = mapped_column(String(160), default="Not specified")
    readiness: Mapped[float] = mapped_column(Float, default=0)
    open_gaps: Mapped[int] = mapped_column(Integer, default=0)
    skills: Mapped[str] = mapped_column(Text, default="")
    missing_skills: Mapped[str] = mapped_column(Text, default="")
    assessment_source: Mapped[str] = mapped_column(String(255), default="User-entered; unverified")
    assessment_date: Mapped[str] = mapped_column(String(40), default="")
    years_in_role: Mapped[int] = mapped_column(Integer, default=0)
    qualification: Mapped[str] = mapped_column(String(200), default="")
    assigned_pathway: Mapped[str] = mapped_column(Text, default="")
    assigned_by: Mapped[str] = mapped_column(String(80), default="")
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Skill(Base):
    __tablename__ = "skills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(100), default="General")
    description: Mapped[str] = mapped_column(Text, default="")
    source_reference: Mapped[str] = mapped_column(String(500), default="")
    review_status: Mapped[str] = mapped_column(String(40), default="Pending review")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)

class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    grade: Mapped[str] = mapped_column(String(100), default="Not specified")
    description: Mapped[str] = mapped_column(Text, default="")
    source_reference: Mapped[str] = mapped_column(String(500), default="")
    review_status: Mapped[str] = mapped_column(String(40), default="Pending review")
    requirements: Mapped[list["RoleSkill"]] = relationship(back_populates="role", cascade="all, delete-orphan")

class RoleSkill(Base):
    __tablename__ = "role_skills"
    __table_args__ = (UniqueConstraint("role_id", "skill_id", name="uq_role_skill"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), index=True)
    required_level: Mapped[int] = mapped_column(Integer, default=3)
    role: Mapped[Role] = relationship(back_populates="requirements")
    skill: Mapped[Skill] = relationship()

class Course(Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(220), index=True)
    provider: Mapped[str] = mapped_column(String(180), default="Unverified provider")
    skill_name: Mapped[str] = mapped_column(String(180), default="")
    domain: Mapped[str] = mapped_column(String(100), default="General")
    duration: Mapped[str] = mapped_column(String(80), default="Not specified")
    url: Mapped[str] = mapped_column(String(1000), default="")
    source_reference: Mapped[str] = mapped_column(String(500), default="")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=True)
    username: Mapped[str] = mapped_column(String(80), default="system")
    action: Mapped[str] = mapped_column(String(40))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int] = mapped_column(Integer, nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    officer_id: Mapped[int] = mapped_column(ForeignKey("officers.id", ondelete="CASCADE"), index=True)
    skill_name: Mapped[str] = mapped_column(String(180), index=True)
    cadre_tier: Mapped[str] = mapped_column(String(50), default="operational")
    phase_order: Mapped[int] = mapped_column(Integer, default=1)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    total_questions: Mapped[int] = mapped_column(Integer, default=5)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    officer: Mapped[Officer] = relationship()


class Certificate(Base):
    __tablename__ = "certificates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cert_uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    officer_id: Mapped[int] = mapped_column(ForeignKey("officers.id", ondelete="CASCADE"), index=True)
    officer_name: Mapped[str] = mapped_column(String(160))
    skill_name: Mapped[str] = mapped_column(String(180), index=True)
    cadre_tier: Mapped[str] = mapped_column(String(50), default="operational")
    target_role: Mapped[str] = mapped_column(String(160), default="")
    score: Mapped[float] = mapped_column(Float, default=100.0)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    officer: Mapped[Officer] = relationship()


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    officer_id: Mapped[int] = mapped_column(ForeignKey("officers.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sender: Mapped[str] = mapped_column(String(20))  # "user" or "advisor"
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    officer: Mapped[Officer] = relationship()


