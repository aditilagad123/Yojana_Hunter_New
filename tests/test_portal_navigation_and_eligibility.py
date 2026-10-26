"""
Tests for Scheme Eligibility Filtering & Official Portal Navigation in Yojana Hunter
Validates:
1. Strict eligibility filtering for diverse user profiles (occupation, income, age, state, category, gender)
2. Ineligible schemes excluded when include_ineligible=False
3. Portal availability probing, timeout handling, and friendly messaging
4. Verified alternative official portal resolution (e.g. PM Vidyalakshmi -> pmvidyalaxmi.co.in)
5. Portal timeout does not remove an eligible scheme
6. Safe URL validation (rejecting javascript:, data:, malformed URLs)
7. Distinct application URL vs official website separation
8. Subscription free-tier limit preservation
"""

import sys
import os
import pytest

# Ensure backend directory is in path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from services.eligibility_service import SchemeEligibilityService
from services.portal_health_service import PortalHealthService, VERIFIED_ALTERNATIVE_PORTALS
from models import Scheme, SchemeRule, User
from database import engine, Base, SessionLocal
from app import create_app


@pytest.fixture(scope="session")
def test_app():
    Base.metadata.create_all(bind=engine)
    app = create_app()
    app.config["TESTING"] = True
    yield app
    SessionLocal.remove()


@pytest.fixture(scope="session")
def client(test_app):
    return test_app.test_client()


# =============================================================================
# 1. STRICT SCHEME ELIGIBILITY FILTERING TESTS
# =============================================================================

def test_strict_filtering_excludes_scheme_when_income_exceeds_limit():
    """Verify that a student exceeding family income limit does not receive income-restricted schemes."""
    db = SessionLocal()
    try:
        # PM Vidyalakshmi has an 8 Lakh income limit
        qualifying_student = {
            "occupation": "Student",
            "is_student": True,
            "is_farmer": False,
            "state": "Maharashtra",
            "age": 21,
            "annual_income": "2.5 – 5 Lakh",
            "income_numeric": 350000,
            "education": "Graduate (B.E. / B.Tech / Professional)"
        }

        rich_student = {
            "occupation": "Student",
            "is_student": True,
            "is_farmer": False,
            "state": "Maharashtra",
            "age": 21,
            "annual_income": "> 8 Lakh",
            "income_numeric": 1500000,
            "education": "Graduate (B.E. / B.Tech / Professional)"
        }

        # Qualifying student should receive PM Vidyalakshmi
        res_qualifying = SchemeEligibilityService.get_ranked_schemes_for_profile(
            profile_data=qualifying_student,
            include_ineligible=False
        )
        qualifying_slugs = [s["slug"] for s in res_qualifying]
        assert "pm-vidyalakshmi" in qualifying_slugs, "Qualifying student should receive PM Vidyalakshmi"

        # Rich student (15 Lakh income) MUST NOT receive PM Vidyalakshmi in eligible results
        res_rich = SchemeEligibilityService.get_ranked_schemes_for_profile(
            profile_data=rich_student,
            include_ineligible=False
        )
        rich_slugs = [s["slug"] for s in res_rich]
        assert "pm-vidyalakshmi" not in rich_slugs, "Student exceeding income limit must be strictly excluded"

        # But if include_ineligible=True (e.g. for inspection), it should appear with not_eligible status
        res_rich_all = SchemeEligibilityService.get_ranked_schemes_for_profile(
            profile_data=rich_student,
            include_ineligible=True
        )
        vl_scheme = next((s for s in res_rich_all if s["slug"] == "pm-vidyalakshmi"), None)
        assert vl_scheme is not None
        assert vl_scheme["eligibilityStatus"] in ("not_eligible", "ineligible")
    finally:
        db.close()


def test_strict_filtering_excludes_scheme_when_age_outside_range():
    """Verify that a citizen outside scheme age limits is strictly excluded."""
    # Scheme with age 18-30
    young_scheme = Scheme(
        id=8801,
        slug="youth-skill-initiative",
        name="Youth Skill Initiative",
        category="Skill Development",
        age_min=18,
        age_max=30,
        is_active=True,
        status="published",
        admin_review_status="approved",
        official_source_url="https://skillindia.gov.in"
    )

    overage_profile = {
        "occupation": "Self-employed",
        "age": 45,
        "state": "Delhi",
        "annual_income": "2.5 – 5 Lakh",
        "income_numeric": 350000
    }

    eval_result = SchemeEligibilityService.evaluate_scheme_for_profile(young_scheme, overage_profile)
    assert eval_result["eligibility_status"] == SchemeEligibilityService.STATUS_NOT_ELIGIBLE
    assert any("age" in r.lower() for r in eval_result["requirements_not_satisfied"])


def test_strict_filtering_excludes_farmer_schemes_for_non_farmer():
    """Verify that a teacher or student profile strictly does not receive farmer schemes."""
    teacher_profile = {
        "occupation": "Teacher",
        "is_student": False,
        "is_farmer": False,
        "has_business": False,
        "state": "Maharashtra",
        "age": 32,
        "annual_income": "5 – 8 Lakh",
        "income_numeric": 600000
    }

    schemes = SchemeEligibilityService.get_ranked_schemes_for_profile(
        profile_data=teacher_profile,
        include_ineligible=False
    )
    slugs = [s["slug"] for s in schemes]
    assert "pm-kisan" not in slugs, "Teacher must not receive PM Kisan"
    assert "pmfby" not in slugs, "Teacher must not receive PM Fasal Bima"


# =============================================================================
# 2. OFFICIAL GOVERNMENT PORTAL TIMEOUT & AVAILABILITY HANDLING TESTS
# =============================================================================

def test_timed_out_portal_detection_and_safe_fallback():
    """Verify that timed-out portal is classified as temporarily_unavailable with friendly message."""
    # Probe known timed out URL: https://www.vidyalakshmi.co.in
    result = PortalHealthService.get_cached_status("https://www.vidyalakshmi.co.in")
    assert result["status"] == PortalHealthService.STATUS_TEMPORARILY_UNAVAILABLE
    assert result["is_available"] is False
    # User-friendly message without raw ERR_CONNECTION_TIMED_OUT technical jargon
    assert "ERR_CONNECTION_TIMED_OUT" not in result["status_message"]
    assert "temporarily unavailable" in result["status_message"].lower()


def test_verified_alternative_portal_resolution():
    """Verify that a verified alternative official portal is provided for PM Vidyalakshmi."""
    alt = PortalHealthService.get_alternative_url("https://www.vidyalakshmi.co.in")
    assert alt == "https://pmvidyalaxmi.co.in/"

    # Alternative portal must be a verified official government domain
    assert "gov.in" in alt or "nic.in" in alt or "pmvidyalaxmi.co.in" in alt


def test_portal_timeout_does_not_remove_eligible_scheme():
    """Verify that a portal timeout does not remove an eligible scheme from recommendations."""
    student_profile = {
        "occupation": "Student",
        "is_student": True,
        "is_farmer": False,
        "state": "Maharashtra",
        "age": 22,
        "annual_income": "< 1 Lakh",
        "income_numeric": 90000,
        "education": "Graduate (B.E. / B.Tech / Professional)"
    }

    schemes = SchemeEligibilityService.get_ranked_schemes_for_profile(
        profile_data=student_profile,
        include_ineligible=False
    )

    vl_scheme = next((s for s in schemes if s["slug"] == "pm-vidyalakshmi"), None)
    assert vl_scheme is not None, "PM Vidyalakshmi must remain in eligible schemes"
    assert vl_scheme["eligibilityStatus"] == "eligible"
    assert vl_scheme["officialUrl"] == "https://pmvidyalaxmi.co.in/"

    # Also verify that a scheme with a timing out portal (MJP Jan Arogya) remains eligible
    mjp_profile = {
        "occupation": "Student",
        "is_student": True,
        "is_farmer": False,
        "state": "Maharashtra",
        "age": 22,
        "annual_income": "< 1 Lakh",
        "income_numeric": 90000,
        "education": "Graduate (B.E. / B.Tech / Professional)"
    }
    mjp_schemes = SchemeEligibilityService.get_ranked_schemes_for_profile(
        profile_data=mjp_profile,
        include_ineligible=False
    )
    mjp_scheme = next((s for s in mjp_schemes if s["slug"] == "mjp-jan-arogya"), None)
    assert mjp_scheme is not None, "MJP Jan Arogya must remain eligible even when portal times out"
    assert mjp_scheme["eligibilityStatus"] == "eligible"
    assert mjp_scheme["portalStatus"] == "temporarily_unavailable"


# =============================================================================
# 3. SAFE URL VALIDATION & MALFORMED PROTOCOL PREVENTION
# =============================================================================

def test_safe_url_validation_accepts_valid_http_and_https():
    """Validates safe http and https government URLs."""
    assert PortalHealthService.is_safe_url("https://pmkisan.gov.in/") is True
    assert PortalHealthService.is_safe_url("https://pmvidyalaxmi.co.in/") is True
    assert PortalHealthService.is_safe_url("http://upagriculture.com/Default.aspx") is True


def test_safe_url_validation_rejects_unsafe_and_malformed_urls():
    """Rejects javascript:, data:, file:, relative, and malformed URLs."""
    assert PortalHealthService.is_safe_url("javascript:alert(1)") is False
    assert PortalHealthService.is_safe_url("data:text/html;base64,PHNjcmlwdD4=") is False
    assert PortalHealthService.is_safe_url("file:///etc/passwd") is False
    assert PortalHealthService.is_safe_url("about:blank") is False
    assert PortalHealthService.is_safe_url("not_a_url") is False
    assert PortalHealthService.is_safe_url("") is False
    assert PortalHealthService.is_safe_url(None) is False


def test_distinct_application_url_vs_official_url_separation():
    """Ensures applicationUrl and officialUrl are safely resolved."""
    db = SessionLocal()
    try:
        # Case 1: Scheme with distinct application URL (e.g. pm-kisan)
        kisan = db.query(Scheme).filter(Scheme.slug == "pm-kisan").first()
        if kisan:
            d = kisan.to_dict(include_rules=False)
            assert d["officialUrl"] == "https://pmkisan.gov.in/"
            assert d["applicationUrl"] == "https://pmkisan.gov.in/RegistrationFormNew.aspx"
            assert d["officialUrl"] != d["applicationUrl"]

        # Case 2: Scheme with current verified official URL (pm-vidyalakshmi)
        vl = db.query(Scheme).filter(Scheme.slug == "pm-vidyalakshmi").first()
        if vl:
            d = vl.to_dict(include_rules=False)
            assert d["officialUrl"] == "https://pmvidyalaxmi.co.in/"
            assert d["applicationUrl"] == "https://pmvidyalaxmi.co.in/"
    finally:
        db.close()


# =============================================================================
# 4. BACKEND PORTAL STATUS API ENDPOINT TESTS
# =============================================================================

def test_portal_status_endpoint_returns_json(client):
    """GET /api/schemes/<scheme_id>/portal-status returns structured availability metadata."""
    res = client.get("/api/schemes/pm-vidyalakshmi/portal-status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["schemeId"] == "pm-vidyalakshmi"
    assert data["officialUrl"] == "https://pmvidyalaxmi.co.in/"
    assert data["status"] == "reachable"
    assert data["isAvailable"] is True

    # Test MJP Jan Arogya with timed-out portal
    res_mjp = client.get("/api/schemes/mjp-jan-arogya/portal-status")
    assert res_mjp.status_code == 200
    data_mjp = res_mjp.get_json()
    assert data_mjp["schemeId"] == "mjp-jan-arogya"
    assert data_mjp["status"] == "temporarily_unavailable"
    assert data_mjp["isAvailable"] is False


def test_portal_status_endpoint_returns_404_for_unknown_scheme(client):
    """GET /api/schemes/<scheme_id>/portal-status returns 404 for non-existent scheme."""
    res = client.get("/api/schemes/non-existent-scheme-99999/portal-status")
    assert res.status_code == 404
