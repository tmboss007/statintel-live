from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)

class RegisterInput(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=256)
    full_name: str = Field(default="", max_length=160)
    email: str = Field(default="", max_length=255)

class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=160)
    email: Optional[str] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, min_length=8, max_length=256)

class ElevateInput(BaseModel):
    admin_password: str = Field(min_length=1, max_length=256)

class ProgressToggleInput(BaseModel):
    officer_id: int
    item_type: str = Field(default="video_lecture")  # video_lecture, phase_task, practical_exercise
    item_key: str
    item_title: Optional[str] = ""
    completed: bool = True
    notes: Optional[str] = ""

class ProgressNoteInput(BaseModel):
    officer_id: int
    item_key: str
    notes: str

class OfficerInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    department: str = Field(default="Not specified", max_length=180)
    current_role: str = Field(default="Not specified", max_length=160)
    target_role: str = Field(default="Not specified", max_length=160)
    readiness: float = Field(default=0, ge=0, le=100)
    open_gaps: int = Field(default=0, ge=0, le=1000)
    skills: list[str] = []
    missing_skills: list[str] = []
    assessment_source: str = Field(default="User-entered; unverified", max_length=255)
    assessment_date: str = Field(default="", max_length=40)
    years_in_role: int = Field(default=0, ge=0, le=50)
    qualification: str = Field(default="", max_length=200)
    is_demo: bool = True

class OfficerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    department: str
    current_role: str
    target_role: str
    readiness: float
    open_gaps: int
    skills: str
    missing_skills: str
    assessment_source: str
    assessment_date: str
    years_in_role: int
    qualification: str
    is_demo: bool

class SkillInput(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    domain: str = Field(default="General", max_length=100)
    description: str = ""
    source_reference: str = Field(default="", max_length=500)
    review_status: str = Field(default="Pending review", max_length=40)

class RoleInput(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    grade: str = Field(default="Not specified", max_length=100)
    description: str = ""
    source_reference: str = Field(default="", max_length=500)
    review_status: str = Field(default="Pending review", max_length=40)
    required_skills: list[str] = []

class CourseInput(BaseModel):
    name: str = Field(min_length=1, max_length=220)
    provider: str = Field(default="Unverified provider", max_length=180)
    skill_name: str = Field(default="", max_length=180)
    domain: str = Field(default="General", max_length=100)
    duration: str = Field(default="Not specified", max_length=80)
    url: str = Field(default="", max_length=1000)
    source_reference: str = Field(default="", max_length=500)
    verified: bool = False

class CopilotInput(BaseModel):
    current_role: str = Field(default="Junior Statistical Officer", max_length=180)
    target_role: Optional[str] = Field(default="Senior Statistical Officer", max_length=180)
    skill_focus: Optional[str] = None
    message: Optional[str] = None


class PathwayGenerateInput(BaseModel):
    officer_id: int = Field(default=1)
    target_role: Optional[str] = None
    weekly_hours: int = Field(default=4, ge=1, le=40)
    preferred_style: str = Field(default="applied")
    content_level: str = Field(default="operational")


class PathwayConverseInput(BaseModel):
    roadmap: dict
    message: str = Field(min_length=1)


class PathwayPdfInput(BaseModel):
    roadmap: dict


class PathwayAccessGrantInput(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    officer_id: Optional[int] = None
    target_role: Optional[str] = None
    weekly_hours: int = Field(default=4, ge=1, le=40)
    preferred_style: str = Field(default="applied")
    attach_current_roadmap: bool = Field(default=True)
    roadmap: Optional[dict] = None
    notes: Optional[str] = None


class ChatSendMessageInput(BaseModel):
    officer_id: int
    message: str = Field(min_length=1)
    roadmap: Optional[dict] = None



class QuizRequest(BaseModel):
    officer_id: int = Field(default=1)
    skill_name: str = Field(min_length=1, max_length=180)
    cadre_tier: str = Field(default="operational", max_length=50)
    phase_order: int = Field(default=1, ge=1, le=10)


class QuizSubmission(BaseModel):
    officer_id: int
    skill_name: str
    cadre_tier: str = "operational"
    phase_order: int = 1
    target_role: Optional[str] = ""
    answers: dict[str, int] = {}  # question_id (as str) -> selected_option_index


