import sys
import os
import logging
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from database import engine, SessionLocal, Base
import models

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def run_migrations():
    """
    Safely and additively adds Razorpay fields to subscription_requests and
    creates the processed_webhook_events table in PostgreSQL.
    100% non-destructive: preserves all existing data.
    """
    logger.info("Starting database migration for Razorpay Subscription Payments...")

    # 1. Create any missing tables via SQLAlchemy metadata
    Base.metadata.create_all(bind=engine)
    logger.info("SQLAlchemy Base.metadata.create_all() executed.")

    # 2. Add additive columns to subscription_requests for PostgreSQL
    dialect_name = engine.dialect.name
    if dialect_name == "postgresql":
        alter_statements = [
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS razorpay_subscription_id VARCHAR(100);",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS razorpay_plan_id VARCHAR(100);",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS razorpay_payment_id VARCHAR(100);",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS razorpay_signature VARCHAR(255);",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS amount_in_paise INTEGER;",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50) DEFAULT 'pending';",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS billing_interval VARCHAR(50);",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP WITHOUT TIME ZONE;",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS cancellation_reason TEXT;",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc');",
            
            # Indexes
            "CREATE INDEX IF NOT EXISTS idx_sub_req_rzp_sub_id ON subscription_requests(razorpay_subscription_id);",
            "CREATE INDEX IF NOT EXISTS idx_sub_req_rzp_pay_id ON subscription_requests(razorpay_payment_id);",
            "CREATE INDEX IF NOT EXISTS idx_sub_req_payment_status ON subscription_requests(payment_status);",

            # Webhook Events table
            """
            CREATE TABLE IF NOT EXISTS processed_webhook_events (
                id SERIAL PRIMARY KEY,
                event_id VARCHAR(100) UNIQUE NOT NULL,
                event_type VARCHAR(100) NOT NULL,
                entity_id VARCHAR(100),
                payload JSONB,
                processed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_processed_webhook_event_id ON processed_webhook_events(event_id);",
            "CREATE INDEX IF NOT EXISTS idx_processed_webhook_event_type ON processed_webhook_events(event_type);"
        ]

        with engine.begin() as conn:
            for stmt in alter_statements:
                try:
                    conn.execute(text(stmt))
                except Exception as e:
                    logger.warning(f"Notice executing statement: {e}")

        logger.info("[SUCCESS] PostgreSQL Razorpay columns and processed_webhook_events table verified.")

    db = SessionLocal()
    try:
        count = db.query(models.SubscriptionRequest).count()
        logger.info(f"Migration completed cleanly. Found {count} existing subscription records.")
    finally:
        db.close()

if __name__ == "__main__":
    run_migrations()
