import sys
import os
import uuid
import datetime
import pytest
import concurrent.futures

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from database import engine, Base, SessionLocal
from models import Scheme, SchemeReviewHistory, DiscoveryJob, User
from utils.auth import hash_password, create_admin_token
from app import create_app
from services.discovery_service import DiscoveryService
from services.eligibility_service import SchemeEligibilityService

@pytest.fixture(scope="module")
def test_app():
    Base.metadata.create_all(bind=engine)
    app = create_app()
    app.config["TESTING"] = True
    yield app
    SessionLocal.remove()

@pytest.fixture(scope="module")
def client(test_app):
    return test_app.test_client()

@pytest.fixture(scope="module")
def admin_token(test_app):
    db = SessionLocal()
    admin = db.query(User).filter(User.role == "admin").first()
    if not admin:
        admin = User(
            email=f"admin_{uuid.uuid4().hex[:6]}@yojanahunter.gov.in",
            mobile="98" + str(uuid.uuid4().int)[:8],
            password_hash=hash_password("Admin@123456"),
            role="admin",
            is_active=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
    token = create_admin_token(admin.id, admin.email)
    db.close()
    return token


def test_repeated_discovery_creates_only_one_canonical_record():
    """Requirement: Discovering the same scheme five times creates only one canonical record."""
    db = SessionLocal()
    test_slug = "canonical-dedup-verification-scheme"
    test_job_id = f"test_dedup_{uuid.uuid4().hex[:8]}"
    job = None
    try:
        # Clean up any existing fixture
        existing = db.query(Scheme).filter(Scheme.slug == test_slug).first()
        if existing:
            db.delete(existing)
            db.commit()

        # Create real discovery job in DB for foreign key constraint
        job = DiscoveryJob(
            job_id=test_job_id,
            status="running",
            created_at=datetime.datetime.utcnow()
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        raw_candidate = {
            "name": "National Canonical Verification Scheme 2026",
            "slug": test_slug,
            "description": "Comprehensive welfare program for verification of idempotency and deduplication.",
            "short_description": "Short description of canonical verification scheme.",
            "benefits": "₹15,000 annual direct benefit transfer",
            "official_source_url": "https://pib.gov.in/canonical-test-scheme",
            "category": "Social Welfare",
            "department": "Ministry of Social Justice",
            "level": "Central Scheme",
            "state": "All India",
            "application_status": "open",
            "is_farmer_only": False,
            "is_student_only": False,
            "verification_evidence": "Official Press Information Bureau notification pib.gov.in/canonical-test-scheme"
        }

        # Discover / process 5 times repeatedly
        outcomes = []
        for i in range(5):
            outcome = DiscoveryService._process_discovered_scheme(
                db=db,
                job=job,
                raw=raw_candidate,
                citations=[{"title": "PIB Notification", "url": "https://pib.gov.in/canonical-test-scheme"}],
                grounding_queries=["National Canonical Verification Scheme 2026"]
            )
            outcomes.append(outcome)

        assert outcomes[0] == "created", f"First run should create scheme, got: {outcomes[0]}"
        for idx, outcome in enumerate(outcomes[1:], 2):
            assert outcome in ("duplicate", "updated"), f"Run {idx} should be duplicate/updated, got: {outcome}"

        # Verify exactly 1 canonical record in the database
        matching_count = db.query(Scheme).filter(Scheme.slug == test_slug).count()
        assert matching_count == 1, f"Expected exactly 1 canonical scheme in DB, found {matching_count}"

        # Verify initial status is draft & pending_review
        record = db.query(Scheme).filter(Scheme.slug == test_slug).first()
        assert record.status == "draft"
        assert record.admin_review_status == "pending_review"
        assert record.is_active is False

    finally:
        # Cleanup
        to_del = db.query(Scheme).filter(Scheme.slug == test_slug).all()
        for d in to_del:
            db.delete(d)
        if job:
            db_job = db.query(DiscoveryJob).filter(DiscoveryJob.id == job.id).first()
            if db_job:
                db.delete(db_job)
        db.commit()
        db.close()


def test_concurrent_discovery_creates_no_duplicates():
    """Requirement: Concurrent requests cannot create duplicate schemes."""
    db = SessionLocal()
    test_slug = "concurrent-race-test-scheme"
    test_job_id = f"test_concurrent_{uuid.uuid4().hex[:8]}"
    job = None
    try:
        existing = db.query(Scheme).filter(Scheme.slug == test_slug).first()
        if existing:
            db.delete(existing)
            db.commit()

        # Create real discovery job in DB
        job = DiscoveryJob(
            job_id=test_job_id,
            status="running",
            created_at=datetime.datetime.utcnow()
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        raw_candidate = {
            "name": "Concurrent Race Condition Safety Scheme",
            "slug": test_slug,
            "description": "Multi-threaded concurrency safety validation scheme.",
            "benefits": "₹10,000 safety grant",
            "official_source_url": "https://digitalindia.gov.in/concurrency-test",
            "category": "Employment & Skills",
            "department": "MeitY",
            "state": "All India",
            "verification_evidence": "https://digitalindia.gov.in/concurrency-test"
        }

        job_db_id = job.id

        def worker_task():
            thread_db = SessionLocal()
            try:
                # Reload job in thread session
                thread_job = thread_db.query(DiscoveryJob).filter(DiscoveryJob.id == job_db_id).first()
                res = DiscoveryService._process_discovered_scheme(
                    db=thread_db,
                    job=thread_job,
                    raw=raw_candidate,
                    citations=[{"title": "Digital India", "url": "https://digitalindia.gov.in/concurrency-test"}],
                    grounding_queries=["Concurrent Race Condition Safety Scheme"]
                )
                return res
            finally:
                thread_db.close()

        # Run 5 concurrent threads attempting to insert the exact same scheme simultaneously
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_task) for _ in range(5)]
            results = [f.result() for f in futures]

        assert "created" in results
        # Verify exactly 1 canonical record in DB
        matching_count = db.query(Scheme).filter(Scheme.slug == test_slug).count()
        assert matching_count == 1, f"Expected 1 record under concurrent insert, found {matching_count}!"

    finally:
        to_del = db.query(Scheme).filter(Scheme.slug == test_slug).all()
        for d in to_del:
            db.delete(d)
        if job:
            db_job = db.query(DiscoveryJob).filter(DiscoveryJob.id == job.id).first()
            if db_job:
                db.delete(db_job)
        db.commit()
        db.close()


def test_similar_distinct_schemes_remain_separate():
    """Requirement: Do not merge two distinct schemes solely because their names are similar."""
    db = SessionLocal()
    try:
        s1 = db.query(Scheme).filter(Scheme.slug == "post-matric-scholarship").first()
        s2 = db.query(Scheme).filter(Scheme.slug == "post-matric-scholarship-to-obc-students").first()
        assert s1 is not None and s2 is not None
        assert s1.id != s2.id
        assert s1.slug != s2.slug
        # Both distinct schemes coexist legitimately
    finally:
        db.close()


def test_admin_approval_gate_lifecycle(client, admin_token):
    """Requirement: Pending review -> Admin approves -> published to citizen; Reject -> hidden."""
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    db = SessionLocal()
    slug = "lifecycle-approval-gate-test"
    try:
        # Create as draft (pending_review)
        create_payload = {
            "name": "Lifecycle Approval Gate Verification Scheme",
            "shortDescription": "Testing admin review approval gating.",
            "description": "Thorough description of review approval workflow test scheme.",
            "category": "Education",
            "benefits": "₹12,000 stipend",
            "officialUrl": "https://education.gov.in/gate-test",
            "status": "draft",
            "isStudentOnly": True
        }
        res_create = client.post("/api/admin/schemes", headers=headers, json=create_payload)
        assert res_create.status_code == 201
        scheme_id = res_create.get_json()["scheme"]["numericId"]
        created_slug = res_create.get_json()["scheme"]["slug"]

        # 1. Citizen cannot view pending scheme (404)
        res_citizen = client.get(f"/api/schemes/{created_slug}")
        assert res_citizen.status_code == 404, "Pending scheme should be hidden from citizens!"

        # 2. Scheme appears in admin pending review list
        res_pending = client.get("/api/admin/schemes/pending-review", headers=headers)
        assert res_pending.status_code == 200
        pending_ids = [s["numericId"] for s in res_pending.get_json().get("schemes", [])]
        assert scheme_id in pending_ids, "Newly created draft scheme must appear in admin pending review queue!"

        # 3. Admin approves scheme
        res_approve = client.post(f"/api/admin/schemes/{scheme_id}/approve", headers=headers, json={"notes": "Verified official guidelines"})
        assert res_approve.status_code == 200
        assert res_approve.get_json()["scheme"]["adminReviewStatus"] == "approved"

        # 4. Citizen CAN view approved scheme
        res_citizen_approved = client.get(f"/api/schemes/{created_slug}")
        assert res_citizen_approved.status_code == 200, "Approved scheme must be accessible to citizens!"

        # 5. Admin rejects scheme
        res_reject = client.post(f"/api/admin/schemes/{scheme_id}/reject", headers=headers, json={"reason": "Scheme closed for current financial year"})
        assert res_reject.status_code == 200

        # 6. Citizen CANNOT view rejected scheme (404)
        res_citizen_rejected = client.get(f"/api/schemes/{created_slug}")
        assert res_citizen_rejected.status_code == 404, "Rejected scheme must be hidden from citizens!"

    finally:
        # Cleanup
        to_del = db.query(Scheme).filter(Scheme.name == "Lifecycle Approval Gate Verification Scheme").all()
        for d in to_del:
            db.delete(d)
        db.commit()
        db.close()
