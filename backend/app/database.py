from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings
import os

# Prepare database URL
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    # SQLAlchemy 1.4+ requires postgresql://
    db_url = db_url.replace("postgres://", "postgresql://", 1)
if db_url.startswith("postgresql://"):
    # SQLAlchemy 2.1 defaults plain PostgreSQL URLs to psycopg v3. The
    # application ships psycopg2-binary, so select that driver explicitly.
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

connect_args = {}
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    engine = create_engine(db_url, connect_args=connect_args)
else:
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initializes tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
