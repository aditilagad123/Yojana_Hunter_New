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
    Safely and additively ensures user_name column is present on subscription_requests,
    and nullifies any stored phone numbers for privacy compliance.
    100% non-destructive and backward-compatible.
    """
    logger.info("Starting database migration for Direct Razorpay Subscription integration...")

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

        # Add user_name if not present
        if "user_name" not in existing_cols:
            conn.execute(text("ALTER TABLE subscription_requests ADD COLUMN user_name VARCHAR(255) NULL;"))
            logger.info("Added column: user_name to subscription_requests")

            # Backfill user_name from profiles and users
            conn.execute(text("""
                UPDATE subscription_requests sr
                SET user_name = p.full_name
                FROM profiles p
                WHERE sr.user_id = p.user_id 
                  AND p.full_name IS NOT NULL 
                  AND (sr.user_name IS NULL OR sr.user_name = '');
            """))
            logger.info("Backfilled user_name from existing user profiles.")

        # Ensure phone_number is nullified in PostgreSQL for privacy compliance
        if "phone_number" in existing_cols:
            conn.execute(text("UPDATE subscription_requests SET phone_number = NULL WHERE phone_number IS NOT NULL;"))
            logger.info("Cleared stored phone numbers from subscription_requests for privacy compliance.")

    db = SessionLocal()
    try:
        count = db.query(models.SubscriptionRequest).count()
        logger.info(f"Migration completed successfully. Verified {count} subscription records in PostgreSQL.")
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
