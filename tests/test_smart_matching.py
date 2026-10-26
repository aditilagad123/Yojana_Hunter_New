import sys
import os
import pytest
import datetime

# Setup backend in path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from services.eligibility_service import SchemeEligibilityService
from models import Scheme, SchemeRule, SchemeDocumentRequirement, User, Profile
from utils.auth import hash_password, create_admin_token
from app import create_app
from database import engine, Base, SessionLocal

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

@pytest.fixture(scope="session")
def admin_token(test_app):
    db = SessionLocal()
    admin = db.query(User).filter(User.role == "admin").first()
    if not admin:
        import uuid
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

@pytest.fixture(scope="session")
def citizen_token(test_app):
    db = SessionLocal()
    citizen = db.query(User).filter(User.role == "citizen").first()
    if not citizen:
        import uuid
        citizen = User(
            email=f"citizen_{uuid.uuid4().hex[:6]}@example.com",
            mobile="97" + str(uuid.uuid4().int)[:8],
            password_hash=hash_password("Citizen@123456"),
            role="citizen",
            is_active=True
        )
        db.add(citizen)
        db.commit()
        db.refresh(citizen)
    token = create_admin_token(citizen.id, citizen.email, role="citizen")
    db.close()
    return token


# =========================================================================
# UNIT TESTS: SchemeEligibilityService
# =========================================================================

def test_1_eligible_user_satisfies_all_conditions():
    """Eligible user satisfies all conditions -> status == 'eligible'"""
    scheme = Scheme(
        id=101,
        slug="pm-kisan-test",
        name="PM Kisan Samman Nidhi",
        category="Agriculture",
        state="All India",
        age_min=18,
        age_max=75,
        income_max=300000,
        is_farmer_only=True,
        max_landholding_acres=5.0,
        application_status="open",
        is_active=True,
        status="published"
    )

    profile = {
        "age": 35,
        "state": "Maharashtra",
        "annual_income": 180000,
        "is_farmer": True,
        "landholding_acres": 2.5,
        "is_tax_payer": False,
        "is_govt_employee": False
    }

    result = SchemeEligibilityService.evaluate_scheme_for_profile(scheme, profile)
    assert result["eligibility_status"] == "eligible"
    assert result["legacy_status"] == "eligible"
    assert result["match_score"] >= 80
    assert len(result["requirements_satisfied"]) > 0
    assert len(result["requirements_not_satisfied"]) == 0
    assert "Why am I seeing this scheme?" in result["why_matched"]


def test_2_user_under_minimum_age():
    """User under minimum age -> status == 'not_eligible' with age reason"""
    scheme = Scheme(
        id=102,
        slug="youth-skill-test",
        name="Pradhan Mantri Kaushal Vikas Yojana",
        age_min=18,
        age_max=35,
        application_status="open",
        is_active=True,
        status="published"
    )

    profile = {
        "age": 16,
        "state": "Delhi"
    }

    result = SchemeEligibilityService.evaluate_scheme_for_profile(scheme, profile)
    assert result["eligibility_status"] == "not_eligible"
    assert any("Age 16 is below the minimum required age of 18" in r for r in result["requirements_not_satisfied"])


def test_3_user_above_income_ceiling():
    """User above income ceiling -> status == 'not_eligible' with income reason"""
    scheme = Scheme(
        id=103,
        slug="housing-subsidy-test",
        name="PMAY Urban",
        income_max=300000,
        application_status="open",
        is_active=True,
        status="published"
    )

    profile = {
        "age": 28,
        "annual_income": 600000
    }

    result = SchemeEligibilityService.evaluate_scheme_for_profile(scheme, profile)
    assert result["eligibility_status"] == "not_eligible"
    assert any("exceeds the maximum limit" in r for r in result["requirements_not_satisfied"])


def test_4_user_in_wrong_state_for_state_scheme():
    """User in wrong state -> status == 'not_eligible'"""
    scheme = Scheme(
        id=104,
        slug="maharashtra-farm-test",
        name="Maharashtra Krishi Sanman",
        state="Maharashtra",
        application_status="open",
        is_active=True,
        status="published"
    )

    profile = {
        "age": 30,
        "state": "Gujarat"
    }

    result = SchemeEligibilityService.evaluate_scheme_for_profile(scheme, profile)
    assert result["eligibility_status"] == "not_eligible"
    assert any("Restricted to residents of Maharashtra" in r for r in result["requirements_not_satisfied"])


def test_5_user_with_missing_info_is_possibly_eligible():
    """User with missing info -> status == 'possibly_eligible' with missingInformation listed"""
    scheme = Scheme(
        id=105,
        slug="higher-ed-scholarship-test",
        name="Post Matric Scholarship",
        is_student_only=True,
        income_max=250000,
        application_status="open",
        is_active=True,
        status="published"
    )

    # Empty profile - no student status or income specified
    profile = {
        "state": "Karnataka"
    }

    result = SchemeEligibilityService.evaluate_scheme_for_profile(scheme, profile)
    assert result["eligibility_status"] == "possibly_eligible"
    assert result["legacy_status"] == "almost"
    assert len(result["missing_information"]) > 0
    assert any("Annual family income" in m for m in result["missing_information"])
    assert any("Student enrollment" in m for m in result["missing_information"])


def test_6_scheme_with_unspecified_rules():
    """Scheme with no restrictive criteria -> status == 'eligibility_unknown' or open match"""
    scheme = Scheme(
        id=106,
        slug="generic-awareness-test",
        name="National Awareness Mission",
        state="All India",
        application_status="open",
        is_active=True,
        status="published"
    )

    result = SchemeEligibilityService.evaluate_scheme_for_profile(scheme, {})
    assert result["eligibility_status"] in ("eligibility_unknown", "eligible")


def test_7_closed_application_window():
    """Scheme with application_status == 'closed' -> status == 'applications_closed'"""
    scheme = Scheme(
        id=107,
        slug="closed-scheme-test",
        name="Closed Fellowship Scheme",
        application_status="closed",
        is_active=True,
        status="published"
    )

    profile = {
        "age": 25,
        "annual_income": 100000
    }

    result = SchemeEligibilityService.evaluate_scheme_for_profile(scheme, profile)
    assert result["eligibility_status"] == "applications_closed"


def test_8_scheme_exclusions():
    """Scheme excluding income tax payers -> tax payer user gets 'not_eligible'"""
    scheme = Scheme(
        id=108,
        slug="antodaya-ration-test",
        name="Antyodaya Anna Yojana",
        exclusions=["tax_payer", "govt_employee"],
        application_status="open",
        is_active=True,
        status="published"
    )

    profile = {
        "age": 30,
        "is_tax_payer": True
    }

    result = SchemeEligibilityService.evaluate_scheme_for_profile(scheme, profile)
    assert result["eligibility_status"] == "not_eligible"
    assert any("Income tax payers are excluded" in r for r in result["requirements_not_satisfied"])


# =========================================================================
# INTEGRATION TESTS: Admin Lifecycle & Matching Routes
# =========================================================================

def test_9_admin_scheme_lifecycle(client, admin_token):
    """Admin creates, edits, deactivates, and toggles a scheme"""
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

    # 1. Create scheme as Published
    create_payload = {
        "name": "Integration Test Welfare Scheme",
        "shortDescription": "Test scheme short summary for automated verification.",
        "description": "Comprehensive description of integration testing scheme.",
        "category": "Education",
        "department": "Ministry of Education",
        "level": "Central Scheme",
        "state": "All India",
        "benefits": "₹20,000 yearly stipend",
        "officialUrl": "https://education.gov.in/test-scheme",
        "ageMin": 18,
        "ageMax": 28,
        "incomeMax": 350000,
        "isStudentOnly": True,
        "status": "published",
        "applicationStatus": "open",
        "requiredDocuments": ["Aadhaar Card", "Income Certificate"]
    }

    res_create = client.post("/api/admin/schemes", headers=headers, json=create_payload)
    assert res_create.status_code == 201
    created_data = res_create.get_json()
    scheme_id = created_data["scheme"]["id"]
    slug = created_data["scheme"]["slug"]

    # 2. Citizen sees the published scheme
    res_citizen_get = client.get(f"/api/schemes/{slug}")
    assert res_citizen_get.status_code == 200

    # 3. Admin updates scheme
    update_payload = {
        "benefits": "₹25,000 yearly stipend + laptop subsidy",
        "applicationStatus": "closing_soon"
    }
    res_update = client.put(f"/api/admin/schemes/{scheme_id}", headers=headers, json=update_payload)
    assert res_update.status_code == 200

    # 4. Admin toggles active to False (Deactivate)
    res_toggle = client.patch(f"/api/admin/schemes/{scheme_id}/toggle-active", headers=headers, json={"isActive": False})
    assert res_toggle.status_code == 200
    assert res_toggle.get_json()["isActive"] is False

    # 5. Citizen accessing deactivated scheme receives 404
    res_citizen_deactivated = client.get(f"/api/schemes/{slug}")
    assert res_citizen_deactivated.status_code == 404

    # 6. Admin toggles active back to True
    res_toggle_back = client.patch(f"/api/admin/schemes/{scheme_id}/toggle-active", headers=headers, json={"isActive": True})
    assert res_toggle_back.status_code == 200
    assert res_toggle_back.get_json()["isActive"] is True

    # 7. Cleanup: Delete test scheme to prevent persistence in production database
    res_cleanup = client.delete(f"/api/admin/schemes/{scheme_id}", headers=headers)
    assert res_cleanup.status_code == 200


def test_10_unauthorized_user_rejected_on_admin_routes(client, citizen_token):
    """Citizen or unauthenticated user is strictly forbidden from admin routes"""
    # Without token -> 401
    res_no_auth = client.get("/api/admin/schemes")
    assert res_no_auth.status_code == 401

    # With Citizen token -> 403 Forbidden
    headers = {"Authorization": f"Bearer {citizen_token}"}
    res_citizen = client.get("/api/admin/schemes", headers=headers)
    assert res_citizen.status_code == 403

    # Citizen POST to admin -> 403
    res_citizen_post = client.post("/api/admin/schemes", headers=headers, json={"name": "Illegal Scheme"})
    assert res_citizen_post.status_code == 403
