import os
import sys
import pytest

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure test environment
os.environ["ADMIN_USERNAME"] = "test_admin"
os.environ["ADMIN_PASSWORD"] = "TestAdminPass-123!"
os.environ["ADMIN_ELEVATION_KEY"] = "ChangeMe-Now-123!"

from app.database import Base, get_db
from app.models import User, Officer, Skill, Role, DepartmentSkillWeight
from app.security import hash_password, create_token
from app.main import app, seed
from app.succession import seed_department_skill_weights_if_empty

# In-memory SQLite test database shared across single thread
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        seed(db)
        seed_department_skill_weights_if_empty(db)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_token(db_session):
    admin = db_session.query(User).filter(User.username == "test_admin").first()
    if not admin:
        admin = User(
            username="test_admin",
            password_hash=hash_password("TestAdminPass-123!"),
            role="admin",
            full_name="Test Administrator"
        )
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)
    return create_token(admin)


@pytest.fixture
def viewer_token(db_session):
    viewer = db_session.query(User).filter(User.username == "test_viewer").first()
    if not viewer:
        viewer = User(
            username="test_viewer",
            password_hash=hash_password("ViewerPass123!"),
            role="viewer",
            full_name="Test Viewer"
        )
        db_session.add(viewer)
        db_session.commit()
        db_session.refresh(viewer)
    return create_token(viewer)


@pytest.fixture
def officer_user(db_session):
    off = db_session.query(Officer).filter(Officer.name == "Priya Sharma").first()
    officer_user = db_session.query(User).filter(User.username == "priya.sharma").first()
    if not officer_user:
        officer_user = User(
            username="priya.sharma",
            password_hash=hash_password("OfficerPass123!"),
            role="officer",
            full_name="Priya Sharma",
            email="priya.sharma@mospi.gov.in",
            officer_id=off.id if off else None
        )
        db_session.add(officer_user)
        db_session.commit()
        db_session.refresh(officer_user)
    token = create_token(officer_user)
    return {"user": officer_user, "token": token, "officer": off}
