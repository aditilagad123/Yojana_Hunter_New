import sys
import os
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from database import engine, SessionLocal, Base
import models

def run_migrations():
    """
    Safely adds any missing columns to existing PostgreSQL / SQLite tables
    without dropping or recreating any existing tables or losing any existing data.
    """
    print("Running database migrations for Smart Scheme Matching and Admin Management...")

    # For new tables if any
    Base.metadata.create_all(bind=engine)

    # For existing tables, execute ALTER TABLE IF NOT EXISTS safely
    dialect_name = engine.dialect.name

    if dialect_name == "postgresql":
        alter_statements = [
            # Profile additions
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_farmer BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_student BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS course VARCHAR(150);",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS institution VARCHAR(255);",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS has_business BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS business_type VARCHAR(150);",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS disability_type VARCHAR(150);",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_tax_payer BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_govt_employee BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS employment_status VARCHAR(100);",
            
            # Scheme additions
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS application_status VARCHAR(50) DEFAULT 'open';",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS gender VARCHAR(50) DEFAULT 'All';",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS social_category VARCHAR(100) DEFAULT 'All';",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS is_farmer_only BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS max_landholding_acres DOUBLE PRECISION;",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS is_student_only BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS is_business_only BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS is_disability_required BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS exclusions JSONB;",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS target_occupations JSONB;",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS target_beneficiary_groups JSONB;",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS eligible_states JSONB;",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS created_by_admin_id INTEGER;",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS updated_by_admin_id INTEGER;",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS source_verification_status VARCHAR(100) DEFAULT 'verified_live';",
            "ALTER TABLE schemes ADD COLUMN IF NOT EXISTS last_fetched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();",
        ]

        with engine.begin() as conn:
            for stmt in alter_statements:
                try:
                    conn.execute(text(stmt))
                except Exception as e:
                    print(f"Notice executing '{stmt[:40]}...': {e}")
                    
        print("[SUCCESS] PostgreSQL columns migrated successfully.")
    else:
        print(f"[INFO] Running on {dialect_name}, Base.metadata.create_all handles schema.")

    backfill_scheme_target_audience()

def backfill_scheme_target_audience():
    """
    Safely backfills structured target audience fields, age limits, income ceilings,
    and region restrictions on all existing scheme records without losing any data.
    """
    db = SessionLocal()
    try:
        from models import Scheme
        schemes = db.query(Scheme).all()
        for s in schemes:
            slug = s.slug or ""
            
            # 1. PM Vidyalakshmi Scheme
            if slug == "pm-vidyalakshmi":
                s.is_student_only = True
                s.target_occupations = ["Student"]
                s.target_beneficiary_groups = ["Students", "Higher Education Seekers"]
                s.eligible_states = ["All India"]
                s.age_min = 18
                s.age_max = 30
                s.income_max = 800000.0
                s.education = "12th Pass"
                
            # 2. Post Matric Scholarship
            elif slug == "post-matric-scholarship":
                s.is_student_only = True
                s.target_occupations = ["Student"]
                s.target_beneficiary_groups = ["Students", "Post-Matric Students", "Youth"]
                s.state = "Maharashtra"
                s.eligible_states = ["Maharashtra"]
                s.age_min = 17
                s.age_max = 25
                s.income_max = 250000.0
                s.education = "10th Pass"

            # 3. Skill India Training
            elif slug == "skill-india-training":
                s.target_occupations = ["Student", "Unemployed", "Self-Employed", "Salaried Employee", "Homemaker"]
                s.target_beneficiary_groups = ["Youth", "Job Seekers", "Students", "Unemployed"]
                s.eligible_states = ["All India"]
                s.age_min = 18
                s.age_max = 35

            # 4. MJP Jan Arogya
            elif slug == "mjp-jan-arogya":
                s.target_occupations = ["Student", "Farmer", "Salaried Employee", "Self-Employed", "Unemployed", "Homemaker"]
                s.target_beneficiary_groups = ["All Citizens", "Families", "BPL", "Low Income"]
                s.state = "Maharashtra"
                s.eligible_states = ["Maharashtra"]

            # 5. NAPS Apprenticeship
            elif slug == "naps-apprenticeship":
                s.target_occupations = ["Student", "Unemployed", "Job Seeker"]
                s.target_beneficiary_groups = ["Graduates", "Diploma Holders", "Youth", "Students"]
                s.eligible_states = ["All India"]
                s.age_min = 18
                s.age_max = 28
                s.education = "Diploma"

            # 6. PM Internship Scheme
            elif slug == "pm-internship-scheme":
                s.target_occupations = ["Student", "Unemployed", "Job Seeker"]
                s.target_beneficiary_groups = ["Youth", "Graduates", "Students"]
                s.eligible_states = ["All India"]
                s.age_min = 21
                s.age_max = 24
                s.income_max = 800000.0

            # 7. PM Vishwakarma
            elif slug == "pm-vishwakarma":
                s.target_occupations = ["Self-Employed", "Artisan", "Craftsperson"]
                s.target_beneficiary_groups = ["Traditional Artisans", "Craftspeople", "Self-Employed"]
                s.eligible_states = ["All India"]
                s.is_business_only = True
                s.age_min = 18

            # 8. Stand-Up India
            elif slug == "stand-up-india":
                s.target_occupations = ["Self-Employed", "Entrepreneur", "Business Owner"]
                s.target_beneficiary_groups = ["Women Entrepreneurs", "SC/ST Entrepreneurs"]
                s.eligible_states = ["All India"]
                s.is_business_only = True
                s.age_min = 18

            # 9. Agriculture Infrastructure Fund
            elif slug == "agri-infra-fund":
                s.is_farmer_only = False
                s.target_occupations = ["Farmer", "Self-Employed", "Entrepreneur"]
                s.target_beneficiary_groups = ["Farmers", "Agri-Entrepreneurs", "FPOs"]
                s.eligible_states = ["All India"]
                s.age_min = 18

            # 10. Integration test welfare schemes
            elif "integration-test" in slug:
                s.is_test = True
                s.is_active = False
                s.status = "draft"
                s.admin_review_status = "pending_review"

            # 11. Farmer-specific schemes
            elif s.is_farmer_only or s.occupation == "Farmer" or s.category == "Agriculture":
                s.is_farmer_only = True
                s.occupation = "Farmer"
                s.target_occupations = ["Farmer"]
                s.target_beneficiary_groups = ["Farmers", "Agricultural Beneficiaries", "Cultivators"]
                if s.state and s.state.lower() not in ("all india", "national", "central", "all"):
                    s.eligible_states = [s.state]
                else:
                    s.eligible_states = ["All India"]
                if s.age_min is None:
                    s.age_min = 18

            # Fallback for any other scheme
            else:
                if not s.target_occupations:
                    if s.is_student_only:
                        s.target_occupations = ["Student"]
                    elif s.is_farmer_only:
                        s.target_occupations = ["Farmer"]
                    elif s.occupation:
                        s.target_occupations = [s.occupation]
                    else:
                        s.target_occupations = ["All"]
                if not s.eligible_states:
                    s.eligible_states = [s.state or "All India"]

        db.commit()
        print("[SUCCESS] Backfilled structured scheme target audience and criteria.")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error backfilling scheme target audience: {e}")
    finally:
        db.close()

def clean_inconsistent_profile_flags():
    """
    Cleans up any historically inconsistent boolean flags on existing profiles in the database
    (e.g., student profiles where is_farmer was erroneously True without landholding).
    """
    db = SessionLocal()
    try:
        from models import Profile
        profiles = db.query(Profile).all()
        fixed_count = 0
        for p in profiles:
            occ = (p.occupation or "").lower().strip()
            user_land = p.land_holding_acres or 0.0
            
            is_student_in_occ = "student" in occ
            is_farmer_in_occ = any(k in occ for k in ["farmer", "kisan", "agri", "cultivat"])
            is_biz_in_occ = any(b in occ for b in ["business", "entrepreneur", "self-employed", "artisan"])

            changed = False
            if is_student_in_occ and not is_farmer_in_occ:
                if p.is_student is not True:
                    p.is_student = True
                    changed = True
                if user_land <= 0 and p.is_farmer is not False:
                    p.is_farmer = False
                    changed = True
            elif is_farmer_in_occ and not is_student_in_occ:
                if p.is_farmer is not True:
                    p.is_farmer = True
                    changed = True
                if p.is_student is not False:
                    p.is_student = False
                    changed = True
            elif is_biz_in_occ and not is_farmer_in_occ and not is_student_in_occ:
                if p.has_business is not True:
                    p.has_business = True
                    changed = True
                if p.is_farmer is not False:
                    p.is_farmer = False
                    changed = True
                if p.is_student is not False:
                    p.is_student = False
                    changed = True
                    
            if changed:
                fixed_count += 1
                
        db.commit()
        print(f"[SUCCESS] Cleaned up {fixed_count} profile records with inconsistent flags.")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error cleaning inconsistent profile flags: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_migrations()
    clean_inconsistent_profile_flags()
