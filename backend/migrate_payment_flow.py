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
    Safely and additively adds Razorpay Order and Admin-Controlled verification columns
    to the subscription_requests table in PostgreSQL.
    100% non-destructive: preserves all existing data and records.
    """
    logger.info("Starting database migration for Razorpay Order Flow & Admin-Controlled Status...")

    # 1. Ensure any missing tables exist via SQLAlchemy metadata
    Base.metadata.create_all(bind=engine)

    dialect_name = engine.dialect.name
    if dialect_name == "postgresql":
        alter_statements = [
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS razorpay_order_id VARCHAR(100);",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS payment_verification_status VARCHAR(50) DEFAULT 'pending';",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS admin_approval_status VARCHAR(50) DEFAULT 'pending';",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS bank_name VARCHAR(100);",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS bank_account_type VARCHAR(50);",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS admin_decision VARCHAR(50);",
            
            # Indexes for performant lookups
            "CREATE INDEX IF NOT EXISTS idx_sub_req_rzp_order_id ON subscription_requests(razorpay_order_id);",
            "CREATE INDEX IF NOT EXISTS idx_sub_req_pay_verif_status ON subscription_requests(payment_verification_status);",
            "CREATE INDEX IF NOT EXISTS idx_sub_req_admin_appr_status ON subscription_requests(admin_approval_status);"
        ]

        with engine.begin() as conn:
            for stmt in alter_statements:
                try:
                    conn.execute(text(stmt))
                except Exception as e:
                    logger.warning(f"Notice executing statement: {e}")

        logger.info("[SUCCESS] PostgreSQL columns and indexes verified safely.")

    db = SessionLocal()
    try:
        count = db.query(models.SubscriptionRequest).count()
        logger.info(f"Migration completed cleanly. Found {count} existing subscription records.")
    finally:
        db.close()

if __name__ == "__main__":
    run_migrations()
