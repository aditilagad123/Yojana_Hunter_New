import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from config import config

logger = logging.getLogger(__name__)

# Normalize database URL for SQLAlchemy
db_url = config.DATABASE_URL
if db_url.startswith("postgres://"):
    # Render PostgreSQL URLs often use postgres://; convert to postgresql+psycopg://
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://"):
    # Standardize to postgresql+psycopg if dialect not specified
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine_kwargs = {"echo": False}
if "sqlite" not in db_url:
    engine_kwargs.update({"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20})

try:
    engine = create_engine(db_url, **engine_kwargs)
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    # Fallback attempt with psycopg2 if psycopg 3 throws dialect error
    if "psycopg" in db_url and not "psycopg2" in db_url:
        fallback_url = db_url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
        engine = create_engine(fallback_url, **engine_kwargs)
    else:
        raise

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()

def get_db():
    """Provides a transactional database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Create all tables defined in models if they do not exist."""
    import models  # Ensure all model classes are imported
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully.")
