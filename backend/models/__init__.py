import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship, relationship as sa_relationship
from database import Base

# Gracefully handle pgvector if available, fallback to JSON for standard PostgreSQL
try:
    from pgvector.sqlalchemy import Vector  # type: ignore
    VectorColumnType = Vector(384)
except Exception:
    VectorColumnType = JSON

# ==========================================
# 1. USERS & TRUST DOMAIN
# ==========================================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    mobile = Column(String(20), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="citizen")  # citizen, helper, curator, reviewer, admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    profiles = relationship("Profile", back_populates="user", cascade="all, delete-orphan", foreign_keys="Profile.user_id", order_by="Profile.id.asc()")
    profile = relationship("Profile", primaryjoin="and_(User.id == Profile.user_id, or_(Profile.relationship == 'Self', Profile.relationship == None))", uselist=False, viewonly=True)
    consents = relationship("ConsentRecord", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")
    documents = relationship("UserDocument", back_populates="user")
    applications = relationship("Application", back_populates="user")
    interview_sessions = relationship("InterviewSession", back_populates="user")
    saved_schemes = relationship("SavedScheme", back_populates="user", cascade="all, delete-orphan")
    password_resets = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    subscription_requests = relationship("SubscriptionRequest", back_populates="user", cascade="all, delete-orphan", foreign_keys="SubscriptionRequest.user_id", order_by="SubscriptionRequest.requested_at.desc()")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "mobile": self.mobile,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    relationship = Column(String(50), default="Self")  # Self, Father, Mother, Child, Spouse, Other
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(50), nullable=True)
    occupation = Column(String(100), nullable=True)
    annual_income = Column(String(100), nullable=True)  # Formatted text e.g. "< 1 Lakh"
    income_numeric = Column(Float, nullable=True)      # Numeric value for rule evaluation
    education = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True)      # General, OBC, SC, ST, EWS
    father_name = Column(String(255), nullable=True)
    date_of_birth = Column(String(50), nullable=True)
    land_holding_acres = Column(Float, default=0.0)
    is_disabled = Column(Boolean, default=False)
    is_farmer = Column(Boolean, default=False)
    is_student = Column(Boolean, default=False)
    course = Column(String(150), nullable=True)
    institution = Column(String(255), nullable=True)
    has_business = Column(Boolean, default=False)
    business_type = Column(String(150), nullable=True)
    disability_type = Column(String(150), nullable=True)
    is_tax_payer = Column(Boolean, default=False)
    is_govt_employee = Column(Boolean, default=False)
    employment_status = Column(String(100), nullable=True)
    preferred_language = Column(String(20), default="en")
    completeness_percent = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = sa_relationship("User", back_populates="profiles")

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "user_id": self.user_id,
            "relationship": self.relationship or "Self",
            "name": self.full_name or "",
            "fullName": self.full_name or "",
            "full_name": self.full_name or "",
            "avatarUrl": self.avatar_url,
            "avatar_url": self.avatar_url,
            "age": self.age or 0,
            "gender": self.gender or "",
            "occupation": self.occupation or "",
            "employmentStatus": self.employment_status or "",
            "employment_status": self.employment_status or "",
            "annualIncome": self.annual_income or "",
            "annual_income": self.annual_income or "",
            "incomeNumeric": self.income_numeric,
            "income_numeric": self.income_numeric,
            "education": self.education or "",
            "state": self.state or "",
            "district": self.district or "",
            "category": self.category or "",
            "fatherName": self.father_name or "",
            "father_name": self.father_name or "",
            "dateOfBirth": self.date_of_birth or "",
            "date_of_birth": self.date_of_birth or "",
            "landHoldingAcres": self.land_holding_acres,
            "land_holding_acres": self.land_holding_acres,
            "isDisabled": self.is_disabled,
            "is_disabled": self.is_disabled,
            "isFarmer": self.is_farmer or False,
            "is_farmer": self.is_farmer or False,
            "isStudent": self.is_student or False,
            "is_student": self.is_student or False,
            "course": self.course or "",
            "institution": self.institution or "",
            "hasBusiness": self.has_business or False,
            "has_business": self.has_business or False,
            "businessType": self.business_type or "",
            "business_type": self.business_type or "",
            "disabilityType": self.disability_type or "",
            "disability_type": self.disability_type or "",
            "isTaxPayer": self.is_tax_payer or False,
            "is_tax_payer": self.is_tax_payer or False,
            "isGovtEmployee": self.is_govt_employee or False,
            "is_govt_employee": self.is_govt_employee or False,
            "language": self.preferred_language or "en",
            "preferred_language": self.preferred_language or "en",
            "completenessPercent": self.completeness_percent or 0,
            "completeness_percent": self.completeness_percent or 0,
            "isProfileSaved": bool(self.occupation and self.state and (self.age is not None and self.age > 0) and (self.completeness_percent or 0) > 0),
            "is_profile_saved": bool(self.occupation and self.state and (self.age is not None and self.age > 0) and (self.completeness_percent or 0) > 0),
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class ConsentRecord(Base):
    __tablename__ = "consent_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    consent_type = Column(String(100), nullable=False)  # ai_processing, data_storage, profiling
    granted = Column(Boolean, default=False)
    granted_at = Column(DateTime, default=datetime.datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="consents")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="notifications")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(100), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")

# ==========================================
# 2. SCHEMES & KNOWLEDGE DOMAIN
# ==========================================

class DiscoveryJob(Base):
    __tablename__ = "discovery_jobs"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(String(50), default="queued", index=True)  # queued, running, completed, completed_with_errors, failed, cancelled
    query_count = Column(Integer, default=0)
    category_count = Column(Integer, default=0)
    discovered_count = Column(Integer, default=0)
    created_count = Column(Integer, default=0)
    updated_count = Column(Integer, default=0)
    duplicate_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    rejected_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    parameters = Column(JSON, nullable=True)
    error_summary = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    created_by_admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    creator = relationship("User", foreign_keys=[created_by_admin_id])
    logs = relationship("DiscoveryJobLog", back_populates="job", cascade="all, delete-orphan", order_by="DiscoveryJobLog.timestamp.desc()")
    discovered_schemes = relationship("Scheme", back_populates="discovery_job", foreign_keys="Scheme.discovery_job_id")

    def to_dict(self, include_logs: bool = False):
        data = {
            "id": self.id,
            "jobId": self.job_id,
            "status": self.status,
            "queryCount": self.query_count or 0,
            "categoryCount": self.category_count or 0,
            "discoveredCount": self.discovered_count or 0,
            "createdCount": self.created_count or 0,
            "insertedCount": self.created_count or 0,
            "updatedCount": self.updated_count or 0,
            "duplicateCount": self.duplicate_count or 0,
            "skippedCount": self.skipped_count or 0,
            "rejectedCount": self.rejected_count or 0,
            "failedCount": self.failed_count or 0,
            "parameters": self.parameters or {},
            "errorSummary": self.error_summary,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "finishedAt": self.finished_at.isoformat() if self.finished_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "createdByAdminId": self.created_by_admin_id,
        }
        if include_logs and self.logs:
            data["logs"] = [l.to_dict() for l in self.logs]
        return data

class DiscoverySchedule(Base):
    __tablename__ = "discovery_schedules"
    id = Column(Integer, primary_key=True, index=True)
    is_enabled = Column(Boolean, default=False)
    frequency_hours = Column(Integer, default=24)
    parameters = Column(JSON, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    last_job_id = Column(String(64), nullable=True)
    last_status = Column(String(50), nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "isEnabled": bool(self.is_enabled),
            "frequencyHours": self.frequency_hours or 24,
            "parameters": self.parameters or {},
            "lastRunAt": self.last_run_at.isoformat() if self.last_run_at else None,
            "nextRunAt": self.next_run_at.isoformat() if self.next_run_at else None,
            "lastJobId": self.last_job_id,
            "lastStatus": self.last_status,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }

class Scheme(Base):
    __tablename__ = "schemes"
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), index=True, nullable=False)
    short_description = Column(Text, nullable=True)
    description = Column(Text, nullable=False)
    benefits = Column(Text, nullable=False)
    category = Column(String(100), index=True, nullable=True)
    department = Column(String(255), nullable=True)
    level = Column(String(100), default="Central Scheme")  # Central Scheme / State Scheme
    state = Column(String(100), index=True, default="All India")
    official_source_url = Column(String(500), nullable=False)
    last_verified_date = Column(String(100), default="12 Oct 2026")
    priority = Column(String(50), default="High Priority")  # High Priority, Medium Priority, Low Priority
    deadline = Column(DateTime, nullable=True)
    status = Column(String(50), default="draft", index=True)  # draft, published, archived
    application_status = Column(String(50), default="open", index=True)  # open, closing_soon, closed, upcoming
    application_url = Column(String(500), nullable=True)
    source_url = Column(String(500), nullable=True)
    alternative_url = Column(String(500), nullable=True)
    application_process = Column(Text, nullable=True)
    age_min = Column(Integer, nullable=True)
    age_max = Column(Integer, nullable=True)
    income_max = Column(Float, nullable=True)
    occupation = Column(String(200), nullable=True)
    education = Column(String(200), nullable=True)
    gender = Column(String(50), default="All")  # All, Female, Male, Transgender
    social_category = Column(String(100), default="All")  # All, SC, ST, OBC, General, Minority
    is_farmer_only = Column(Boolean, default=False)
    max_landholding_acres = Column(Float, nullable=True)
    is_student_only = Column(Boolean, default=False)
    is_business_only = Column(Boolean, default=False)
    is_disability_required = Column(Boolean, default=False)
    exclusions = Column(JSON, nullable=True)  # List of strings e.g. ["Income tax payer"]
    target_occupations = Column(JSON, nullable=True)  # List of strings e.g. ["Student", "Farmer"]
    target_beneficiary_groups = Column(JSON, nullable=True)  # List of strings e.g. ["Students", "Youth"]
    eligible_states = Column(JSON, nullable=True)  # List of strings e.g. ["All India"] or ["Maharashtra"]
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    source_verification_status = Column(String(100), default="verified_live")
    last_fetched_at = Column(DateTime, default=datetime.datetime.utcnow)
    verification_notes = Column(Text, nullable=True)
    grounding_metadata = Column(JSON, nullable=True)
    discovery_job_id = Column(Integer, ForeignKey("discovery_jobs.id"), nullable=True)
    admin_review_status = Column(String(50), default="pending_review", index=True)  # pending_review, approved, rejected, needs_verification
    rejection_reason = Column(Text, nullable=True)
    is_test = Column(Boolean, default=False, index=True)
    created_by_admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by_admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    rules = relationship("SchemeRule", back_populates="scheme", cascade="all, delete-orphan")
    document_requirements = relationship("SchemeDocumentRequirement", back_populates="scheme", cascade="all, delete-orphan")
    source_documents = relationship("SourceDocument", back_populates="scheme", cascade="all, delete-orphan")
    change_logs = relationship("SchemeChangeLog", back_populates="scheme", cascade="all, delete-orphan")
    eligibility_results = relationship("EligibilityResult", back_populates="scheme")
    discovery_job = relationship("DiscoveryJob", back_populates="discovered_schemes", foreign_keys=[discovery_job_id])
    citations = relationship("SchemeCitation", back_populates="scheme", cascade="all, delete-orphan")
    review_history = relationship("SchemeReviewHistory", back_populates="scheme", cascade="all, delete-orphan", order_by="SchemeReviewHistory.timestamp.desc()")

    def to_dict(self, include_rules: bool = True):
        # Resolve URLs with safety checks
        from services.portal_health_service import PortalHealthService

        raw_official = (self.official_source_url or "").strip()
        official_url = raw_official if raw_official and PortalHealthService.is_official_government_url(raw_official) else None

        raw_app = (self.application_url or "").strip()
        if raw_app and PortalHealthService.is_official_government_url(raw_app):
            application_url = raw_app
        else:
            application_url = official_url

        if not official_url and application_url:
            official_url = application_url


        alt_url = getattr(self, "alternative_url", None)
        if not alt_url and raw_official:
            alt_url = PortalHealthService.get_alternative_url(raw_official)

        portal_info = PortalHealthService.get_cached_status(raw_official)

        data = {
            "id": self.slug,
            "numericId": self.id,
            "slug": self.slug,
            "name": self.name,
            "shortDescription": self.short_description or (self.description[:120] + "..."),
            "description": self.description,
            "category": self.category or "General",
            "department": self.department or "Government of India",
            "level": self.level or "Central Scheme",
            "state": self.state or "All India",
            "eligibleStates": self.eligible_states or ([self.state] if self.state else ["All India"]),
            "benefit": self.benefits,
            "benefits": self.benefits,
            "officialUrl": official_url,
            "applicationUrl": application_url,
            "alternativeUrl": alt_url,
            "portalStatus": portal_info.get("status", "reachable"),
            "portalStatusMessage": portal_info.get("status_message"),
            "sourceUrl": self.source_url or self.official_source_url,
            "sourceVerificationStatus": self.source_verification_status or "verified_live",
            "lastFetchedAt": self.last_fetched_at.isoformat() if self.last_fetched_at else None,
            "applicationProcess": self.application_process or "",
            "lastVerifiedDate": self.last_verified_date or "12 Oct 2026",
            "priority": self.priority or "High Priority",
            "status": self.status or ("published" if self.is_active else "draft"),
            "applicationStatus": self.application_status or "open",
            "isActive": self.is_active,
            "ageMin": self.age_min,
            "ageMax": self.age_max,
            "incomeMax": self.income_max,
            "occupation": self.occupation,
            "targetOccupations": self.target_occupations or ([self.occupation] if self.occupation else []),
            "targetBeneficiaryGroups": self.target_beneficiary_groups or [],
            "education": self.education,
            "gender": self.gender or "All",
            "socialCategory": self.social_category or "All",
            "isFarmerOnly": bool(self.is_farmer_only),
            "maxLandholdingAcres": self.max_landholding_acres,
            "isStudentOnly": bool(self.is_student_only),
            "isBusinessOnly": bool(self.is_business_only),
            "isDisabilityRequired": bool(self.is_disability_required),
            "exclusions": self.exclusions or [],
            "verificationNotes": self.verification_notes or "",
            "groundingMetadata": self.grounding_metadata or {},
            "discoveryJobId": self.discovery_job_id,
            "adminReviewStatus": self.admin_review_status or "pending_review",
            "rejectionReason": self.rejection_reason,
            "isTest": bool(self.is_test),
            "is_test": bool(self.is_test),
            "citations": [c.to_dict() for c in self.citations] if self.citations else [],
            "createdByAdminId": self.created_by_admin_id,
            "updatedByAdminId": self.updated_by_admin_id,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "endDate": self.end_date.isoformat() if self.end_date else (self.deadline.isoformat() if self.deadline else None),
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "requiredDocuments": [doc.document_name for doc in self.document_requirements] if self.document_requirements else [],
            "eligibilityStatus": "eligible",
            "matchScore": 100,
            "criteria": [],
        }

        if include_rules and self.rules:
            data["criteria"] = [
                {
                    "id": f"c{rule.id}",
                    "name": rule.rule_name or "Eligibility Rule",
                    "condition": rule.rule_description,
                    "passed": True,
                    "userValue": ""
                }
                for rule in self.rules
            ]

        return data

class SchemeRule(Base):
    __tablename__ = "scheme_rules"
    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    rule_name = Column(String(200), nullable=True)
    rule_description = Column(Text, nullable=False)
    rule_logic = Column(JSON, nullable=False)  # Declarative JSON: {"field": "age", "op": "<=", "value": 30}
    is_mandatory = Column(Boolean, default=True)

    scheme = relationship("Scheme", back_populates="rules")

class SchemeDocumentRequirement(Base):
    __tablename__ = "scheme_document_requirements"
    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    document_name = Column(String(150), nullable=False)
    is_mandatory = Column(Boolean, default=True)
    description = Column(Text, nullable=True)

    scheme = relationship("Scheme", back_populates="document_requirements")

class SourceDocument(Base):
    __tablename__ = "source_documents"
    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    title = Column(String(255), nullable=False)
    source_url = Column(String(500), nullable=False)
    document_hash = Column(String(128), nullable=True)
    fetched_at = Column(DateTime, default=datetime.datetime.utcnow)

    scheme = relationship("Scheme", back_populates="source_documents")
    chunks = relationship("SchemeChunk", back_populates="source_document", cascade="all, delete-orphan")

class SchemeChunk(Base):
    __tablename__ = "scheme_chunks"
    id = Column(Integer, primary_key=True, index=True)
    source_document_id = Column(Integer, ForeignKey("source_documents.id"), nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(VectorColumnType, nullable=True)

    source_document = relationship("SourceDocument", back_populates="chunks")

class SchemeChangeLog(Base):
    __tablename__ = "scheme_change_logs"
    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    change_summary = Column(Text, nullable=False)
    detected_at = Column(DateTime, default=datetime.datetime.utcnow)

    scheme = relationship("Scheme", back_populates="change_logs")

class DiscoveryJobLog(Base):
    __tablename__ = "discovery_job_logs"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("discovery_jobs.id"), nullable=False, index=True)
    level = Column(String(20), default="INFO")  # INFO, WARNING, ERROR, SUCCESS
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    job = relationship("DiscoveryJob", back_populates="logs")

    def to_dict(self):
        return {
            "id": self.id,
            "jobId": self.job_id,
            "level": self.level,
            "message": self.message,
            "details": self.details or {},
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

class SchemeCitation(Base):
    __tablename__ = "scheme_citations"
    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False, index=True)
    source_title = Column(String(500), nullable=True)
    source_url = Column(String(1000), nullable=False)
    excerpt = Column(Text, nullable=True)
    confidence_score = Column(Float, default=1.0)
    verified_at = Column(DateTime, default=datetime.datetime.utcnow)

    scheme = relationship("Scheme", back_populates="citations")

    def to_dict(self):
        return {
            "id": self.id,
            "schemeId": self.scheme_id,
            "sourceTitle": self.source_title or "",
            "sourceUrl": self.source_url,
            "excerpt": self.excerpt or "",
            "confidenceScore": self.confidence_score or 1.0,
            "verifiedAt": self.verified_at.isoformat() if self.verified_at else None,
        }

class SchemeReviewHistory(Base):
    __tablename__ = "scheme_review_histories"
    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)  # approve, reject, reverify, edit
    reason = Column(Text, nullable=True)
    previous_data = Column(JSON, nullable=True)
    new_data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    scheme = relationship("Scheme", back_populates="review_history")
    admin = relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "schemeId": self.scheme_id,
            "adminId": self.admin_id,
            "adminEmail": self.admin.email if self.admin else None,
            "action": self.action,
            "reason": self.reason,
            "previousData": self.previous_data or {},
            "newData": self.new_data or {},
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

# ==========================================
# 3. CITIZEN JOURNEY DOMAIN
# ==========================================

class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    language = Column(String(20), default="en")
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    messages = relationship("InterviewMessage", back_populates="session", cascade="all, delete-orphan")
    user = relationship("User", back_populates="interview_sessions")

class InterviewMessage(Base):
    __tablename__ = "interview_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False)
    sender = Column(String(20), nullable=False)  # "user" or "bot"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("InterviewSession", back_populates="messages")

class EligibilityResult(Base):
    __tablename__ = "eligibility_results"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    status = Column(String(50), nullable=False)  # eligible, almost, ineligible, needs_info
    match_score = Column(Integer, default=0)
    criteria_breakdown = Column(JSON, nullable=True)
    reasoning_text = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, default=datetime.datetime.utcnow)

    scheme = relationship("Scheme", back_populates="eligibility_results")

class SavedScheme(Base):
    __tablename__ = "saved_schemes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    saved_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="saved_schemes")
    scheme = relationship("Scheme")

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "schemeId": self.scheme_id,
            "savedAt": self.saved_at.isoformat() if self.saved_at else None,
        }

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="password_resets")

    def is_valid(self):
        return (not self.used) and (self.expires_at > datetime.datetime.utcnow())

# ==========================================
# 3.5 SUBSCRIPTIONS & CITIZEN ACCESS TIERS
# ==========================================

class SubscriptionRequest(Base):
    __tablename__ = "subscription_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user_name = Column(String(255), nullable=True)
    plan_id = Column(String(50), nullable=False)          # monthly, two_months, yearly
    plan_name = Column(String(100), nullable=False)        # Monthly Access, 2 Months Standard, Yearly Premium Pass
    amount = Column(Float, nullable=False)                # 50.0, 100.0, 500.0
    currency = Column(String(10), default="INR")
    duration_days = Column(Integer, nullable=False)       # 30, 60, 365
    status = Column(String(50), default="pending", index=True)  # pending, approved, rejected, cancelled
    rejection_reason = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)
    requested_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by_admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    starts_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    is_active = Column(Boolean, default=False, index=True)

    # Razorpay Payment Gateway & Admin Approval integration fields
    admin_approval_status = Column(String(50), default="pending", index=True) # pending, approved, rejected
    mandate_status = Column(String(50), default="MANDATE_PENDING", index=True) # MANDATE_PENDING, MANDATE_ACTIVE, MANDATE_FAILED
    payment_method = Column(String(50), nullable=True) # netbanking, card, upi, emandate
    bank_name = Column(String(100), nullable=True) # e.g. HDFC Bank
    bank_account_type = Column(String(50), nullable=True) # e.g. Savings Account
    failure_reason = Column(Text, nullable=True)
    phone_number = Column(String(20), nullable=True)
    payment_verified_at = Column(DateTime, nullable=True)
    activated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    razorpay_order_id = Column(String(100), nullable=True, index=True)
    razorpay_subscription_id = Column(String(100), nullable=True, index=True)
    razorpay_plan_id = Column(String(100), nullable=True, index=True)
    razorpay_payment_id = Column(String(100), nullable=True, index=True)
    razorpay_signature = Column(String(255), nullable=True)
    amount_in_paise = Column(Integer, nullable=True)
    payment_verification_status = Column(String(50), default="pending", index=True) # pending, verified, failed
    payment_status = Column(String(50), default="PAYMENT_PENDING", index=True)  # PAYMENT_PENDING, PAYMENT_SUCCESS, PAYMENT_FAILED, refunded
    admin_decision = Column(String(50), nullable=True)
    billing_interval = Column(String(50), nullable=True)               # monthly, two_months, yearly
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="subscription_requests", foreign_keys=[user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_admin_id])
    audit_logs = relationship("PaymentAuditLog", back_populates="subscription_request", cascade="all, delete-orphan", order_by="PaymentAuditLog.timestamp.desc()")

    def to_dict(self, include_user=True):
        now = datetime.datetime.utcnow()
        is_currently_active = bool(
            (self.status in ("approved", "Approved", "active", "Active")) 
            and self.is_active 
            and self.expires_at 
            and self.expires_at > now
        )
        data = {
            "id": self.id,
            "userId": self.user_id,
            "planId": self.plan_id,
            "planName": self.plan_name,
            "amount": self.amount,
            "amountInPaise": self.amount_in_paise or int(self.amount * 100),
            "currency": self.currency,
            "durationDays": self.duration_days,
            "status": self.status.capitalize() if self.status else "Pending",
            "adminApprovalStatus": self.admin_approval_status or "pending",
            "mandateStatus": self.mandate_status or "MANDATE_PENDING",
            "paymentMethod": self.payment_method,
            "bankName": self.bank_name,
            "bankAccountType": self.bank_account_type,
            "failureReason": self.failure_reason,
            "phoneNumber": self.phone_number,
            "paymentVerificationStatus": self.payment_verification_status or "pending",
            "paymentStatus": self.payment_status or "PAYMENT_PENDING",
            "paymentVerifiedAt": self.payment_verified_at.isoformat() if self.payment_verified_at else None,
            "activatedAt": self.activated_at.isoformat() if self.activated_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "razorpayOrderId": self.razorpay_order_id,
            "razorpaySubscriptionId": self.razorpay_subscription_id,
            "razorpayPlanId": self.razorpay_plan_id,
            "razorpayPaymentId": self.razorpay_payment_id,
            "adminDecision": self.admin_decision,
            "billingInterval": self.billing_interval,
            "rejectionReason": self.rejection_reason,
            "adminNotes": self.admin_notes,
            "requestedAt": self.requested_at.isoformat() if self.requested_at else None,
            "reviewedAt": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewedByAdminId": self.reviewed_by_admin_id,
            "startsAt": self.starts_at.isoformat() if self.starts_at else None,
            "expiresAt": self.expires_at.isoformat() if self.expires_at else None,
            "cancelledAt": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "cancellationReason": self.cancellation_reason,
            "isActive": is_currently_active,
            # snake_case aliases for backend/tests compatibility
            "user_id": self.user_id,
            "plan_id": self.plan_id,
            "plan_name": self.plan_name,
            "duration_days": self.duration_days,
            "admin_approval_status": self.admin_approval_status or "pending",
            "mandate_status": self.mandate_status or "MANDATE_PENDING",
            "payment_method": self.payment_method,
            "bank_name": self.bank_name,
            "bank_account_type": self.bank_account_type,
            "failure_reason": self.failure_reason,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "starts_at": self.starts_at.isoformat() if self.starts_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": is_currently_active,
            "payment_verification_status": self.payment_verification_status or "pending",
            "payment_status": self.payment_status or "PAYMENT_PENDING",
            "payment_verified_at": self.payment_verified_at.isoformat() if self.payment_verified_at else None,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "razorpay_order_id": self.razorpay_order_id,
            "razorpay_subscription_id": self.razorpay_subscription_id,
            "razorpay_payment_id": self.razorpay_payment_id,
            "razorpay_plan_id": self.razorpay_plan_id,
            "admin_decision": self.admin_decision,
            "rejection_reason": self.rejection_reason,
        }
        u_name = self.user_name
        if not u_name:
            try:
                profile = self.user.profile if self.user else None
                u_name = profile.full_name if profile and profile.full_name else (self.user.email.split("@")[0].capitalize() if self.user and self.user.email else f"Citizen #{self.user_id}")
            except Exception:
                u_name = f"Citizen #{self.user_id}"
        data["userName"] = u_name
        data["user_name"] = u_name
        if include_user:
            try:
                if self.user:
                    u_email = self.user.email or ""
                    data["userEmail"] = u_email
                    data["user_email"] = u_email
                    data["user"] = {
                        "id": self.user.id,
                        "email": u_email,
                        "name": u_name
                    }
            except Exception:
                pass
        return data


class ProcessedWebhookEvent(Base):
    __tablename__ = "processed_webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(100), unique=True, index=True, nullable=False)
    event_type = Column(String(100), index=True, nullable=False)
    entity_id = Column(String(100), index=True, nullable=True)
    payload = Column(JSON, nullable=True)
    processed_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "eventId": self.event_id,
            "eventType": self.event_type,
            "entityId": self.entity_id,
            "processedAt": self.processed_at.isoformat() if self.processed_at else None
        }


class PaymentAuditLog(Base):
    __tablename__ = "payment_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    subscription_request_id = Column(Integer, ForeignKey("subscription_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_role = Column(String(50), default="system")
    action = Column(String(100), nullable=False)
    reason = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)

    subscription_request = relationship("SubscriptionRequest", back_populates="audit_logs")
    actor = relationship("User", foreign_keys=[actor_id])

    def to_dict(self):
        return {
            "id": self.id,
            "subscriptionRequestId": self.subscription_request_id,
            "previousStatus": self.previous_status,
            "newStatus": self.new_status,
            "actorId": self.actor_id,
            "actorRole": self.actor_role,
            "action": self.action,
            "reason": self.reason,
            "details": self.details or {},
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


# ==========================================
# 4. DOCUMENTS & APPLICATION DOMAIN
# ==========================================

class UserDocument(Base):
    __tablename__ = "user_documents"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    doc_key = Column(String(100), nullable=True)      # doc-1, doc-aadhaar, etc.
    name = Column(String(200), nullable=False)        # Aadhaar Card, Income Certificate
    document_type = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=True)
    file_path = Column(String(500), nullable=True)
    file_size = Column(String(50), nullable=True)
    status = Column(String(50), default="missing")   # uploaded, missing, pending
    is_verified = Column(Boolean, default=False)
    required_for = Column(JSON, nullable=True)       # List of scheme names / slugs
    uploaded_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="documents")
    extracted_fields = relationship("ExtractedField", back_populates="document", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.doc_key or f"doc-{self.id}",
            "numericId": self.id,
            "name": self.name,
            "type": self.document_type,
            "status": self.status,
            "fileName": self.file_name,
            "fileSize": self.file_size,
            "uploadedAt": self.uploaded_at.strftime("%d %b %Y, %I:%M %p") if self.uploaded_at else None,
            "isRequiredFor": self.required_for or [],
            "isVerified": self.is_verified,
        }

class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("user_documents.id"), nullable=False)
    field_name = Column(String(100), nullable=False)
    field_value = Column(String(255), nullable=False)
    confidence = Column(Float, default=1.0)

    document = relationship("UserDocument", back_populates="extracted_fields")

class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    application_number = Column(String(100), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    scheme_name = Column(String(255), nullable=False)
    status = Column(String(50), default="draft")  # draft, submitted, approved, rejected
    applicant_name = Column(String(255), nullable=True)
    father_name = Column(String(255), nullable=True)
    date_of_birth = Column(String(50), nullable=True)
    education = Column(String(100), nullable=True)
    family_income = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="applications")
    fields = relationship("ApplicationField", back_populates="application", cascade="all, delete-orphan")
    affidavit = relationship("Affidavit", back_populates="application", uselist=False, cascade="all, delete-orphan")
    verification_reports = relationship("VerificationReport", back_populates="application", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.application_number,
            "numericId": self.id,
            "schemeId": str(self.scheme_id),
            "scheme_id": self.scheme_id,
            "schemeName": self.scheme_name,
            "scheme_name": self.scheme_name,
            "applicantName": self.applicant_name or "",
            "applicant_name": self.applicant_name or "",
            "fatherName": self.father_name or "",
            "father_name": self.father_name or "",
            "dateOfBirth": self.date_of_birth or "",
            "date_of_birth": self.date_of_birth or "",
            "education": self.education or "",
            "familyIncome": self.family_income or "",
            "family_income": self.family_income or "",
            "state": self.state or "",
            "district": self.district or "",
            "status": self.status,
            "description": self.description,
            "createdAt": self.created_at.strftime("%d %b %Y") if self.created_at else "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }

class ApplicationField(Base):
    __tablename__ = "application_fields"
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    field_key = Column(String(100), nullable=False)
    field_value = Column(Text, nullable=False)

    application = relationship("Application", back_populates="fields")

class Affidavit(Base):
    __tablename__ = "affidavits"
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), unique=True, nullable=False)
    affidavit_pdf_path = Column(String(500), nullable=False)
    is_confirmed_by_user = Column(Boolean, default=False)
    confirmed_at = Column(DateTime, nullable=True)

    application = relationship("Application", back_populates="affidavit")

# ==========================================
# 5. AI INSIGHTS & TELEMETRY
# ==========================================

class VerificationReport(Base):
    __tablename__ = "verification_reports"
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    source_verified = Column(Boolean, default=True)
    hallucination_detected = Column(Boolean, default=False)
    confidence_score = Column(Float, default=1.0)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    application = relationship("Application", back_populates="verification_reports")

class AgentRun(Base):
    __tablename__ = "agent_runs"
    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String(100), nullable=False)
    task_id = Column(String(100), nullable=True)
    latency_ms = Column(Float, nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class RetrievalLog(Base):
    __tablename__ = "retrieval_logs"
    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(Text, nullable=False)
    retrieved_chunk_ids = Column(JSON, nullable=False)
    top_score = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
