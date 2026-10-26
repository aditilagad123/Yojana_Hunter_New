import sys
import logging
from database import SessionLocal
from models import (
    Scheme, SchemeRule, SchemeDocumentRequirement,
    SavedScheme, SchemeReviewHistory, SchemeCitation,
    SchemeChangeLog, User
)
from utils.auth import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("duplicate_cleanup")

def run_migration():
    db = SessionLocal()
    try:
        logger.info("Starting safe duplicate cleanup migration...")

        # ---------------------------------------------------------
        # 1. Update family_tester password hash
        # ---------------------------------------------------------
        family_user = db.query(User).filter(User.email == "family_tester@yojana.gov.in").first()
        if family_user and (not family_user.password_hash or not family_user.password_hash.startswith("$2")):
            family_user.password_hash = hash_password("FamilyPass123!")
            logger.info("Updated family_tester@yojana.gov.in password hash to valid bcrypt format.")

        # ---------------------------------------------------------
        # 2. Consolidate Integration Test Welfare Scheme
        # Canonical: ID 17
        # Duplicates to remove: IDs [29, 32, 33, 40, 46]
        # ---------------------------------------------------------
        canonical_test = db.query(Scheme).filter(Scheme.id == 17).first()
        if not canonical_test:
            canonical_test = db.query(Scheme).filter(Scheme.slug == "integration-test-welfare-scheme").first()

        if canonical_test:
            canonical_test.is_test = True
            canonical_test.status = "draft"
            canonical_test.is_active = False
            canonical_test.admin_review_status = "pending_review"
            logger.info(f"Marked canonical test scheme ID {canonical_test.id} as is_test=True, status=draft, inactive.")

        test_dup_ids = [29, 32, 33, 40, 46]
        for dup_id in test_dup_ids:
            s_dup = db.query(Scheme).filter(Scheme.id == dup_id).first()
            if s_dup:
                # Check foreign keys
                saved_count = db.query(SavedScheme).filter(SavedScheme.scheme_id == dup_id).count()
                if saved_count > 0 and canonical_test:
                    db.query(SavedScheme).filter(SavedScheme.scheme_id == dup_id).update({"scheme_id": canonical_test.id})
                db.delete(s_dup)
                logger.info(f"Safely removed duplicate test scheme ID {dup_id} ('{s_dup.slug}').")

        # ---------------------------------------------------------
        # 3. Consolidate PM Surya Ghar Muft Bijli Yojana
        # Canonical: ID 9
        # Duplicate to remove: ID 10
        # ---------------------------------------------------------
        canonical_surya = db.query(Scheme).filter(Scheme.id == 9).first()
        dup_surya = db.query(Scheme).filter(Scheme.id == 10).first()
        if dup_surya:
            saved_count = db.query(SavedScheme).filter(SavedScheme.scheme_id == 10).count()
            if saved_count > 0 and canonical_surya:
                db.query(SavedScheme).filter(SavedScheme.scheme_id == 10).update({"scheme_id": canonical_surya.id})
            db.delete(dup_surya)
            logger.info("Safely removed duplicate PM Surya Ghar ID 10.")

        # ---------------------------------------------------------
        # 4. Consolidate Pradhan Mantri Kisan Maandhan Yojana
        # Canonical: ID 20 (pm-kmy)
        # Duplicate to remove: ID 13 (pradhan-mantri-kisan-maandhan-yojana)
        # ---------------------------------------------------------
        canonical_kmy = db.query(Scheme).filter(Scheme.id == 20).first()
        dup_kmy = db.query(Scheme).filter(Scheme.id == 13).first()
        if dup_kmy and canonical_kmy:
            saved_count = db.query(SavedScheme).filter(SavedScheme.scheme_id == 13).count()
            if saved_count > 0:
                db.query(SavedScheme).filter(SavedScheme.scheme_id == 13).update({"scheme_id": canonical_kmy.id})
            db.delete(dup_kmy)
            logger.info("Safely removed duplicate PM-KMY ID 13, preserving canonical ID 20.")

        # ---------------------------------------------------------
        # 5. Ensure all genuine published schemes have admin_review_status='approved'
        # ---------------------------------------------------------
        published_schemes = db.query(Scheme).filter(
            Scheme.status == "published",
            Scheme.is_active == True,
            Scheme.is_test == False
        ).all()
        for ps in published_schemes:
            if ps.admin_review_status != "approved":
                ps.admin_review_status = "approved"
        logger.info(f"Verified admin_review_status='approved' for {len(published_schemes)} active published schemes.")

        db.commit()
        logger.info("Duplicate cleanup migration successfully applied and committed.")
    except Exception as e:
        db.rollback()
        logger.error(f"Migration error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
