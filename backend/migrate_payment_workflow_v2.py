import sys
import os
import logging
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from database import engine, SessionLocal, Base
import models

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def run_migration():
    """
    Safely and additively adds payment workflow and audit columns to subscription_requests,
    and creates the payment_audit_logs table in PostgreSQL.
    100% non-destructive: preserves all existing data and user history.
    """
    logger.info("Starting database migration for Dynamic Admin Subscription & Payment Workflow...")

    with engine.begin() as conn:
        dialect_name = engine.dialect.name
        logger.info(f"Connected database dialect: {dialect_name}")

        # 1. Inspect existing columns on subscription_requests
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'subscription_requests'
        """))
        existing_cols = {row[0] for row in result.fetchall()}
        logger.info(f"Existing columns in subscription_requests: {len(existing_cols)}")

        # Add phone_number if not present
        if "phone_number" not in existing_cols:
            conn.execute(text("ALTER TABLE subscription_requests ADD COLUMN phone_number VARCHAR(20) NULL;"))
            logger.info("Added column: phone_number")

        # Add payment_verified_at if not present
        if "payment_verified_at" not in existing_cols:
            conn.execute(text("ALTER TABLE subscription_requests ADD COLUMN payment_verified_at TIMESTAMP WITHOUT TIME ZONE NULL;"))
            logger.info("Added column: payment_verified_at")

        # Add activated_at if not present
        if "activated_at" not in existing_cols:
            conn.execute(text("ALTER TABLE subscription_requests ADD COLUMN activated_at TIMESTAMP WITHOUT TIME ZONE NULL;"))
            logger.info("Added column: activated_at")

        # Add created_at if not present
        if "created_at" not in existing_cols:
            conn.execute(text("ALTER TABLE subscription_requests ADD COLUMN created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc');"))
            conn.execute(text("UPDATE subscription_requests SET created_at = requested_at WHERE created_at IS NULL AND requested_at IS NOT NULL;"))
            logger.info("Added column: created_at")

        # Backfill activated_at for already active records
        conn.execute(text("""
            UPDATE subscription_requests 
            SET activated_at = starts_at 
            WHERE is_active = TRUE AND starts_at IS NOT NULL AND activated_at IS NULL;
        """))

        # Backfill payment_verified_at for verified records
        conn.execute(text("""
            UPDATE subscription_requests 
            SET payment_verified_at = reviewed_at 
            WHERE payment_verification_status = 'verified' AND reviewed_at IS NOT NULL AND payment_verified_at IS NULL;
        """))

        # 2. Create payment_audit_logs table if not exists
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS payment_audit_logs (
                id SERIAL PRIMARY KEY,
                subscription_request_id INTEGER REFERENCES subscription_requests(id) ON DELETE CASCADE,
                previous_status VARCHAR(50),
                new_status VARCHAR(50),
                actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                actor_role VARCHAR(50) DEFAULT 'system',
                action VARCHAR(100) NOT NULL,
                reason TEXT,
                details JSONB,
                timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
            );
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_audit_req_id ON payment_audit_logs(subscription_request_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_audit_timestamp ON payment_audit_logs(timestamp);"))
        logger.info("Table payment_audit_logs and indexes verified.")

    db = SessionLocal()
    try:
        count = db.query(models.SubscriptionRequest).count()
        logger.info(f"Migration finished cleanly. Found {count} subscription records in PostgreSQL.")
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
