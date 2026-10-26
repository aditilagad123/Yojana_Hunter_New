import sys
import logging
from sqlalchemy import create_engine, text
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_database_if_not_exists():
    """Connect to default 'postgres' database and create target database if missing."""
    import urllib.parse
    db_url = config.DATABASE_URL
    if "sqlite" in db_url:
        logger.info("SQLite database detected; skipping PostgreSQL maintenance check.")
        return

    parsed = urllib.parse.urlparse(db_url)
    target_db = parsed.path.lstrip("/") or "yojna_hunter"

    # Create connection URL pointing to default 'postgres' maintenance DB
    postgres_maintenance_url = db_url.replace(f"/{target_db}", "/postgres")

    try:
        # Use AUTOCOMMIT isolation level for CREATE DATABASE
        engine_maintenance = create_engine(postgres_maintenance_url, isolation_level="AUTOCOMMIT")
        with engine_maintenance.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": target_db}
            )
            exists = result.scalar() is not None
            if not exists:
                logger.info(f"Database '{target_db}' does not exist. Creating...")
                conn.execute(text(f'CREATE DATABASE "{target_db}"'))
                logger.info(f"Database '{target_db}' created successfully.")
            else:
                logger.info(f"Database '{target_db}' already exists.")
        engine_maintenance.dispose()
    except Exception as e:
        logger.warning(f"Could not check/create database via maintenance connection: {e}")
        logger.info("Will attempt connecting directly to target DATABASE_URL...")

def setup_schema_and_seed():
    """Create all tables and seed with verified schemes data."""
    from database import engine, Base
    import models  # Import models so Base has metadata
    from services.seed_data import seed_database

    logger.info("Creating tables in PostgreSQL...")
    Base.metadata.create_all(bind=engine)
    logger.info("All tables created successfully.")

    logger.info("Seeding initial government schemes and profile data...")
    seed_database()
    logger.info("Database setup and seeding completed successfully!")

if __name__ == "__main__":
    try:
        create_database_if_not_exists()
        setup_schema_and_seed()
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        sys.exit(1)
