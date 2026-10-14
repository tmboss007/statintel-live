import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

raw_url = os.getenv("DATABASE_URL", "").strip()

# Guard against accidental HTTP/HTTPS web links or empty values
if not raw_url or raw_url.startswith(("http://", "https://")):
    if raw_url.startswith(("http://", "https://")):
        logging.warning("DATABASE_URL was set to an HTTP/HTTPS URL instead of a database connection string. Falling back to SQLite.")
    DATABASE_URL = "sqlite:///./statintel_dev.db"
elif raw_url.startswith("postgres://"):
    DATABASE_URL = raw_url.replace("postgres://", "postgresql+psycopg://", 1)
elif raw_url.startswith("postgresql://") and "+psycopg" not in raw_url:
    DATABASE_URL = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
else:
    DATABASE_URL = raw_url

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
