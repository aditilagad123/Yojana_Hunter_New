import os
import re
import uuid
import time
import json
import logging
import threading
import datetime
from typing import Dict, Any, List, Optional

from database import SessionLocal
from models import (
    Scheme, SchemeCitation, SchemeChangeLog, SchemeRule,
    DiscoveryJob, DiscoveryJobLog, User
)
from services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

# Standard Indian Government Target Queries with category keywords
STANDARD_DISCOVERY_CATEGORIES = [
    {
        "category": "Agriculture",
        "keywords": ["agri", "farm", "kisan", "crop", "irrigation"],
        "label": "Farmers & Agricultural Welfare",
        "queries": [
            "Pradhan Mantri farmer welfare schemes subsidy 2026 official portal",
            "Maharashtra kisan crop insurance agricultural mechanization subsidy portal",
            "Kisan credit card agriculture input subsidy official portal"
        ]
    },
    {
        "category": "Education",
        "keywords": ["edu", "scholar", "student", "fellowship", "school", "college"],
        "label": "Scholarships & Higher Education",
        "queries": [
            "Ministry of Education scholarship fellowship scheme official gov.in",
            "Maharashtra higher education post matric scholarship mahadbt portal",
            "National scholarship portal central sector merit scholarship official"
        ]
    },
    {
        "category": "Women & Child",
        "keywords": ["women", "child", "girl", "matru", "mahila", "kanya", "sukanya"],
        "label": "Women Empowerment & Maternal Welfare",
        "queries": [
            "central government schemes for women empowerment entrepreneurship gov.in",
            "Maharashtra majhi ladki bahin yojana women welfare portal",
            "Pradhan Mantri Matru Vandana Yojana official guidelines portal"
        ]
    },
    {
        "category": "Employment & Skills",
        "keywords": ["employ", "skill", "job", "intern", "artisan", "rozkari", "rozgar", "vishwakarma"],
        "label": "Skill Development & Employment",
        "queries": [
            "National Apprenticeship PM Internship scheme official portal eligibility",
            "PM Vishwakarma artisan loan subsidy official site",
            "Pradhan Mantri Kaushal Vikas Yojana training and placement official"
        ]
    },
    {
        "category": "Health & Housing",
        "keywords": ["health", "house", "awas", "ayushman", "arogya", "bima", "medical", "swasthya"],
        "label": "Healthcare & Social Housing",
        "queries": [
            "Ayushman Bharat PMJAY health insurance eligibility official portal",
            "Pradhan Mantri Awas Yojana urban rural subsidy portal",
            "PM Jan Arogya Yojana free healthcare benefits portal"
        ]
    },
    {
        "category": "Social Welfare",
        "keywords": ["social", "welfare", "pension", "divyang", "disab", "senior", "minority"],
        "label": "Social Welfare & Empowerment",
        "queries": [
            "National Social Assistance Programme old age disability pension portal gov.in",
            "Social welfare empowerment financial support schemes official"
        ]
    }
]


def normalize_scheme_name(name: str) -> str:
    """Normalizes scheme name by stripping punctuation and common prefixes for duplicate detection."""
    if not name:
        return ""
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    stop_words = {"pradhan", "mantri", "yojana", "scheme", "shasan", "kisan", "pm", "national", "state", "central"}
    tokens = [w for w in s.split() if w not in stop_words and len(w) > 1]
    return " ".join(tokens)


class DiscoveryService:
    """
    Orchestrates Google Search grounded scheme discovery, evidence extraction,
    multi-level deduplication, validation, and admin review queue population.
    """

    _job_lock = threading.Lock()
    _active_job_id: Optional[str] = None
    _cancel_requested: bool = False

    @classmethod
    def is_job_running(cls) -> bool:
        return cls._active_job_id is not None

    @classmethod
    def get_active_job_id(cls) -> Optional[str]:
        return cls._active_job_id

    @classmethod
    def request_cancel(cls, job_id: str) -> bool:
        """Flags an active discovery job to halt gracefully."""
        if cls._active_job_id == job_id:
            cls._cancel_requested = True
            logger.info(f"Cancellation requested for discovery job {job_id}")
            return True
        return False

    @classmethod
    def cleanup_stale_jobs(cls):
        """Cleans up uncompleted jobs from previous server sessions so they don't linger in queued/running status."""
        try:
            db = SessionLocal()
            stale = db.query(DiscoveryJob).filter(DiscoveryJob.status.in_(["queued", "running"])).all()
            if stale:
                for j in stale:
                    j.status = "cancelled"
                    j.completed_at = datetime.datetime.utcnow()
                db.commit()
                logger.info(f"Cleaned up {len(stale)} stale discovery jobs from prior sessions.")
            db.close()
        except Exception as e:
            logger.warning(f"Could not clean up stale discovery jobs: {e}")

    @staticmethod
    def generate_slug(name: str) -> str:
        """Generates a stable kebab-case slug from scheme name."""
        s = name.lower().strip()
        s = re.sub(r'[^a-z0-9\s-]', '', s)
        s = re.sub(r'[\s-]+', '-', s).strip('-')
        return s[:250] or f"scheme-{uuid.uuid4().hex[:8]}"

    @classmethod
    def log_job(cls, db, job_id: int, level: str, message: str, details: Optional[Dict] = None):
        """Appends a structured log entry to the discovery job log."""
        try:
            log_entry = DiscoveryJobLog(
                job_id=job_id,
                level=level,
                message=message,
                details=details or {},
                timestamp=datetime.datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to record discovery job log: {e}")

    @classmethod
    def start_discovery_job(
        cls,
        parameters: Optional[Dict[str, Any]] = None,
        admin_user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Initializes a new discovery job record in PostgreSQL and launches background execution.
        Enforces singleton concurrency to prevent overlapping executions.
        """
        with cls._job_lock:
            if cls.is_job_running():
                return {
                    "success": False,
                    "error": f"Another discovery job ({cls._active_job_id}) is currently in progress. Please wait for it to complete.",
                    "jobId": cls._active_job_id
                }

            params = parameters or {}
            job_uuid = f"disc_{uuid.uuid4().hex[:12]}"
            cls._active_job_id = job_uuid
            cls._cancel_requested = False

        db = SessionLocal()
        try:
            job = DiscoveryJob(
                job_id=job_uuid,
                status="queued",
                parameters=params,
                created_by_admin_id=admin_user_id,
                created_at=datetime.datetime.utcnow()
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            # Spawn background worker thread
            worker = threading.Thread(
                target=cls._run_discovery_worker,
                args=(job.id, job_uuid, params),
                daemon=True,
                name=f"DiscoveryWorker-{job_uuid}"
            )
            worker.start()

            return {
                "success": True,
                "jobId": job_uuid,
                "numericId": job.id,
                "status": "queued",
                "message": "Discovery job queued and started in background worker."
            }

        except Exception as e:
            with cls._job_lock:
                cls._active_job_id = None
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    @classmethod
    def _run_discovery_worker(cls, numeric_job_id: int, job_uuid: str, params: Dict[str, Any]):
        """Background thread executing the grounded discovery pipeline."""
        db = SessionLocal()
        start_time = datetime.datetime.utcnow()

        try:
            job = db.query(DiscoveryJob).filter(DiscoveryJob.id == numeric_job_id).first()
            if not job:
                return

            job.status = "running"
            job.started_at = start_time
            db.commit()

            cls.log_job(db, job.id, "INFO", f"Discovery job {job_uuid} started with parameters: {json.dumps(params)}")

            # 1. Check Gemini API configuration
            if not GeminiService.is_configured():
                err_msg = "GEMINI_API_KEY is not configured in backend/.env. Cannot perform grounded search."
                job.status = "failed"
                job.error_summary = err_msg
                job.finished_at = datetime.datetime.utcnow()
                db.commit()
                cls.log_job(db, job.id, "ERROR", err_msg)
                return

            # 2. Determine target query plan with flexible category matching
            target_state = params.get("state") or "All India"
            target_category = params.get("category") or "All"
            target_department = params.get("department") or None
            custom_query = params.get("query")
            max_requests = int(params.get("max_queries", 4))

            query_targets = []
            if custom_query:
                query_targets.append({
                    "category": target_category,
                    "query": custom_query,
                    "department": target_department
                })
            else:
                cat_lower = target_category.lower()
                is_all_cat = cat_lower in ("all", "all beneficiary categories", "")

                for cat in STANDARD_DISCOVERY_CATEGORIES:
                    # Match if All, or if category name matches, or if any keyword matches
                    matches = is_all_cat or (cat["category"].lower() in cat_lower) or any(kw in cat_lower for kw in cat.get("keywords", []))
                    if not matches:
                        continue

                    for q in cat["queries"]:
                        full_q = f"{q} {target_state}" if target_state.lower() not in ("all india", "all", "") else q
                        query_targets.append({
                            "category": cat["category"],
                            "query": full_q,
                            "department": target_department
                        })
                        if len(query_targets) >= max_requests:
                            break
                    if len(query_targets) >= max_requests:
                        break

                # If still empty (e.g. custom category name without keyword match), synthesize query
                if not query_targets:
                    synth_q = f"government welfare schemes for {target_category} in {target_state} eligibility official portal gov.in"
                    query_targets.append({
                        "category": target_category,
                        "query": synth_q,
                        "department": target_department
                    })

            job.query_count = len(query_targets)
            job.category_count = len(set(q["category"] for q in query_targets))
            db.commit()

            cls.log_job(db, job.id, "INFO", f"Planned {len(query_targets)} grounded discovery search requests.")

            # 3. Execute searches incrementally
            total_discovered = 0
            total_created = 0
            total_updated = 0
            total_duplicates = 0
            total_skipped = 0
            total_rejected = 0
            total_failed = 0

            for idx, target in enumerate(query_targets, 1):
                if cls._cancel_requested:
                    cls.log_job(db, job.id, "WARNING", "Job execution halted due to admin cancellation request.")
                    job.status = "cancelled"
                    break

                cls.log_job(db, job.id, "INFO", f"[{idx}/{len(query_targets)}] Discovering schemes: '{target['query'][:80]}'")

                discovery_result = GeminiService.discover_schemes_grounded(
                    search_query=target["query"],
                    state=target_state,
                    category=target["category"],
                    department=target["department"],
                    max_schemes=4
                )

                if not discovery_result.get("success"):
                    err = discovery_result.get("error", "Unknown error")
                    total_failed += 1
                    cls.log_job(db, job.id, "ERROR", f"Search error for '{target['query'][:40]}': {err}")
                    if discovery_result.get("quota_exhausted"):
                        cls.log_job(db, job.id, "WARNING", "Gemini API quota reached. Pausing remaining query plan.")
                        break
                    continue

                raw_schemes = discovery_result.get("schemes", [])
                citations = discovery_result.get("citations", [])
                grounding_queries = discovery_result.get("grounding_queries", [])
                mode = discovery_result.get("grounding_mode", "direct")

                cls.log_job(
                    db, job.id, "INFO",
                    f"Retrieved {len(raw_schemes)} candidate schemes ({mode}) and {len(citations)} source citations."
                )

                for raw_scheme in raw_schemes:
                    total_discovered += 1
                    process_outcome = cls._process_discovered_scheme(
                        db=db,
                        job=job,
                        raw=raw_scheme,
                        citations=citations,
                        grounding_queries=grounding_queries
                    )
                    if process_outcome == "created":
                        total_created += 1
                    elif process_outcome == "updated":
                        total_updated += 1
                        total_duplicates += 1
                    elif process_outcome == "duplicate":
                        total_duplicates += 1
                    elif process_outcome == "rejected":
                        total_rejected += 1
                    elif process_outcome == "skipped":
                        total_skipped += 1
                    elif process_outcome == "failed":
                        total_failed += 1

                # Update live counts on the job record
                job.discovered_count = total_discovered
                job.created_count = total_created
                job.updated_count = total_updated
                job.duplicate_count = total_duplicates
                job.skipped_count = total_skipped
                job.rejected_count = total_rejected
                job.failed_count = total_failed
                db.commit()

                # Polite delay between searches
                time.sleep(0.5)

            # 4. Finalize job status
            if job.status not in ("cancelled", "failed"):
                if total_created == 0 and total_discovered == 0 and total_failed > 0:
                    job.status = "failed"
                elif total_failed > 0:
                    job.status = "completed_with_errors"
                else:
                    job.status = "completed"

            job.finished_at = datetime.datetime.utcnow()
            db.commit()

            cls.log_job(
                db, job.id, "SUCCESS",
                f"Discovery completed: {total_discovered} evaluated, {total_created} new schemes for review, "
                f"{total_updated} updated, {total_duplicates} duplicates, {total_rejected} rejected."
            )

        except Exception as e:
            logger.exception(f"Unhandled error in discovery worker: {e}")
            try:
                job = db.query(DiscoveryJob).filter(DiscoveryJob.id == numeric_job_id).first()
                if job:
                    job.status = "failed"
                    job.error_summary = str(e)
                    job.finished_at = datetime.datetime.utcnow()
                    db.commit()
                    cls.log_job(db, job.id, "ERROR", f"Unhandled worker exception: {e}")
            except Exception:
                pass
        finally:
            with cls._job_lock:
                cls._active_job_id = None
                cls._cancel_requested = False
            db.close()

    @classmethod
    def _process_discovered_scheme(
        cls,
        db,
        job: DiscoveryJob,
        raw: Dict[str, Any],
        citations: List[Dict[str, Any]],
        grounding_queries: List[str]
    ) -> str:
        """
        Normalizes, validates, deduplicates, and persists a single discovered scheme safely.
        Returns: 'created', 'updated', 'duplicate', 'rejected', 'skipped', or 'failed'.
        """
        name = str(raw.get("name") or "").strip()
        if not name or len(name) < 4:
            return "skipped"

        # Validate minimum essential fields
        benefits = str(raw.get("benefits") or "").strip()
        short_desc = str(raw.get("short_description") or (raw.get("description", "")[:150])).strip()
        desc = str(raw.get("description") or short_desc).strip()

        # Reject malformed or empty records
        if not desc or len(desc) < 15 or not benefits or len(benefits) < 5:
            cls.log_job(db, job.id, "WARNING", f"Rejected candidate '{name[:40]}': Missing description or benefits.")
            return "rejected"

        official_url = str(raw.get("official_source_url") or raw.get("officialUrl") or "").strip()
        has_adequate_evidence = False

        if official_url and official_url.startswith("http"):
            if ".gov.in" in official_url or ".nic.in" in official_url or "myscheme.gov.in" in official_url:
                has_adequate_evidence = True
        else:
            # Check citations for official government portal
            gov_citation = next((c for c in citations if ".gov.in" in c.get("url", "") or ".nic.in" in c.get("url", "")), None)
            if gov_citation:
                official_url = gov_citation["url"]
                has_adequate_evidence = True
            else:
                official_url = "https://myscheme.gov.in/"
                has_adequate_evidence = False

        slug = raw.get("slug") or cls.generate_slug(name)
        department = str(raw.get("department") or "Government of India").strip()
        level = str(raw.get("level") or "Central Scheme").strip()
        state = str(raw.get("state") or "All India").strip()
        category = str(raw.get("category") or "General").strip()

        # Application availability parsing
        raw_app_status = str(raw.get("application_status") or "unknown").lower()
        if "open" in raw_app_status:
            application_status = "open"
        elif "close" in raw_app_status:
            application_status = "closed"
        elif "upcoming" in raw_app_status:
            application_status = "upcoming"
        else:
            application_status = "unknown"

        deadline = None
        raw_deadline = raw.get("application_deadline")
        if raw_deadline and isinstance(raw_deadline, str) and re.match(r'^\d{4}-\d{2}-\d{2}', raw_deadline):
            try:
                deadline = datetime.datetime.strptime(raw_deadline[:10], "%Y-%m-%d")
            except Exception:
                deadline = None

        age_min = int(raw["age_min"]) if raw.get("age_min") is not None and str(raw.get("age_min")).isdigit() else None
        age_max = int(raw["age_max"]) if raw.get("age_max") is not None and str(raw.get("age_max")).isdigit() else None
        income_max = float(raw["income_max"]) if raw.get("income_max") not in (None, "") else None
        occupation = str(raw.get("occupation") or "").strip() or None
        education = str(raw.get("education") or "").strip() or None
        gender = str(raw.get("gender") or "All").strip()
        social_cat = str(raw.get("social_category") or "All").strip()
        is_farmer = bool(raw.get("is_farmer_only"))
        is_student = bool(raw.get("is_student_only"))
        is_biz = bool(raw.get("is_business_only"))
        is_disability = bool(raw.get("is_disability_required"))
        exclusions = raw.get("exclusions") if isinstance(raw.get("exclusions"), list) else []

        grounding_meta = {
            "web_search_queries": grounding_queries,
            "verification_evidence": raw.get("verification_evidence", ""),
            "extracted_at": datetime.datetime.utcnow().isoformat(),
            "has_gov_domain": has_adequate_evidence,
        }

        # Multi-factor Deduplication Check
        norm_name = normalize_scheme_name(name)
        existing = db.query(Scheme).filter(
            (Scheme.slug == slug) |
            (Scheme.name.ilike(name))
        ).first()

        # If not matched by exact name or slug, try matching normalized name within same state/central scope
        if not existing and norm_name and len(norm_name) > 5:
            candidates = db.query(Scheme).all()
            for cand in candidates:
                cand_norm = normalize_scheme_name(cand.name)
                if cand_norm and (norm_name in cand_norm or cand_norm in norm_name):
                    # Check geographic scope compatibility
                    if cand.state == state or cand.state in ("All India", "") or state in ("All India", ""):
                        existing = cand
                        break

        # Also match if same official source URL
        if not existing and official_url and "myscheme.gov.in" not in official_url:
            existing = db.query(Scheme).filter(Scheme.official_source_url == official_url).first()

        if existing:
            # Duplicate detected! Prevent duplicate insertion and preserve approved information
            is_approved = (existing.admin_review_status == "approved" or existing.status == "published")
            has_changes = False
            changes = []

            # Preserve admin-reviewed descriptions and benefits for approved schemes
            if not is_approved:
                if existing.benefits != benefits and len(benefits) > 10:
                    changes.append("Benefits refreshed from official source")
                    existing.benefits = benefits
                    has_changes = True

            if existing.application_status != application_status and application_status != "unknown":
                changes.append(f"Application status changed to '{application_status}'")
                existing.application_status = application_status
                has_changes = True

            if deadline and existing.deadline != deadline:
                changes.append(f"Deadline updated to {deadline.strftime('%Y-%m-%d')}")
                existing.deadline = deadline
                has_changes = True

            existing.last_fetched_at = datetime.datetime.utcnow()
            existing.grounding_metadata = grounding_meta

            if has_changes:
                change_log = SchemeChangeLog(
                    scheme_id=existing.id,
                    change_summary=f"[AI Discovery Job {job.job_id}] " + "; ".join(changes),
                    detected_at=datetime.datetime.utcnow()
                )
                db.add(change_log)
                db.commit()
                cls.log_job(db, job.id, "INFO", f"Duplicate detected & updated '{existing.name}': {'; '.join(changes)}")
                return "updated"
            else:
                db.commit()
                cls.log_job(db, job.id, "INFO", f"Duplicate detected: '{existing.name}' is already up-to-date.")
                return "duplicate"

        # Determine Review and Evidence Status
        review_status = "pending_review"
        verif_notes = raw.get("verification_evidence") or ""
        if not has_adequate_evidence:
            verif_notes = f"[Flagged: Inadequate official .gov.in evidence] {verif_notes}".strip()

        # Create New Scheme safely using savepoint
        savepoint = db.begin_nested()
        try:
            new_scheme = Scheme(
                slug=slug,
                name=name,
                short_description=short_desc,
                description=desc,
                benefits=benefits,
                category=category,
                department=department,
                level=level,
                state=state,
                official_source_url=official_url,
                application_url=raw.get("application_url") or official_url,
                application_process=raw.get("application_process") or "Visit official portal to apply.",
                status="draft",  # draft until admin approves
                application_status=application_status,
                admin_review_status=review_status,  # Visible in admin discovery review queue
                is_active=False,  # Inactive until approved by admin
                age_min=age_min,
                age_max=age_max,
                income_max=income_max,
                occupation=occupation,
                education=education,
                gender=gender,
                social_category=social_cat,
                is_farmer_only=is_farmer,
                is_student_only=is_student,
                is_business_only=is_biz,
                is_disability_required=is_disability,
                exclusions=exclusions,
                deadline=deadline,
                verification_notes=verif_notes,
                grounding_metadata=grounding_meta,
                discovery_job_id=job.id,
                source_verification_status="verified_grounded_search" if has_adequate_evidence else "unverified_insufficient_evidence",
                last_fetched_at=datetime.datetime.utcnow(),
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
            db.add(new_scheme)
            db.flush()

            # Attach Citations
            for cit in citations:
                c_record = SchemeCitation(
                    scheme_id=new_scheme.id,
                    source_title=cit.get("title") or "Official Portal Reference",
                    source_url=cit.get("url") or official_url,
                    excerpt=cit.get("excerpt") or verif_notes,
                    verified_at=datetime.datetime.utcnow()
                )
                db.add(c_record)

            savepoint.commit()
            db.commit()
            cls.log_job(db, job.id, "SUCCESS", f"Created candidate scheme '{name}' (Status: {review_status}).")
            return "created"

        except Exception as e:
            savepoint.rollback()
            # If slug collision or concurrent insert occurred, attempt idempotent fetch and update
            existing_retry = db.query(Scheme).filter(
                (Scheme.slug == slug) | (Scheme.name.ilike(name))
            ).first()
            if existing_retry:
                existing_retry.last_fetched_at = datetime.datetime.utcnow()
                existing_retry.grounding_metadata = grounding_meta
                db.commit()
                cls.log_job(db, job.id, "INFO", f"Concurrent collision resolved idempotently for '{name}'.")
                return "duplicate"
            db.rollback()
            cls.log_job(db, job.id, "ERROR", f"Failed to persist scheme '{name}': {e}")
            return "failed"
