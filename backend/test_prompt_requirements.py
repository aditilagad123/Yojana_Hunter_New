import sys
import os

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database import SessionLocal
from models import Scheme, Profile, User
from services.portal_health_service import PortalHealthService
from services.eligibility_service import SchemeEligibilityService

def test_url_verification():
    print("=== TEST: URL Verification ===")
    valid_urls = [
        "https://pmkisan.gov.in",
        "https://pmvidyalaxmi.co.in",
        "https://pmsuryaghar.gov.in",
        "https://jeevandayee.gov.in",
        "https://jansamarth.in",
        "https://scholarships.gov.in",
        "https://upagriculture.com",
        "https://maandhan.in"
    ]
    invalid_urls = [
        "https://fake-schemes-blog.com/apply",
        "https://random-news-portal.in/pm-kisan-apply",
        "https://privateportal.org",
        "http://insecure-portal.com",
        "",
        None
    ]

    for u in valid_urls:
        assert PortalHealthService.is_official_government_url(u) is True, f"Expected valid URL to pass: {u}"
        print(f"  [PASS] Valid official portal accepted: {u}")

    for u in invalid_urls:
        assert PortalHealthService.is_official_government_url(u) is False, f"Expected invalid URL to fail: {u}"
        print(f"  [PASS] Unofficial/fake URL rejected: {u}")
    print("URL verification tests passed successfully.\n")


def test_dynamic_occupations():
    print("=== TEST: Dynamic Occupation Eligibility ===")
    
    # 1. Clerk Profile
    clerk_profile = {
        "relationship": "Self",
        "occupation": "Clerk",
        "state": "Maharashtra",
        "district": "Pune",
        "age": 30,
        "gender": "Male",
        "annual_income": "2.5 – 5 Lakh",
        "income_numeric": 350000,
        "education": "Graduate (B.A. / B.Com / B.Sc)",
        "category": "General",
        "land_holding_acres": 0.0,
        "is_farmer": False,
        "is_student": False,
        "is_govt_employee": False
    }

    clerk_schemes = SchemeEligibilityService.get_ranked_schemes_for_profile(clerk_profile)
    clerk_eligible = [s for s in clerk_schemes if s.get("eligibility_status") in ("eligible", "possibly_eligible")]
    clerk_slugs = [s["slug"] for s in clerk_eligible]
    print(f"Clerk eligible scheme count: {len(clerk_eligible)}")
    print(f"Clerk eligible schemes: {clerk_slugs}")

    # Clerk must NOT get PM-KISAN or PM Vidyalaxmi
    assert "pm-kisan" not in clerk_slugs, "Clerk must NOT be eligible for PM-KISAN"
    assert "pm-vidyalakshmi" not in clerk_slugs, "Clerk must NOT be eligible for PM Vidyalaxmi"
    # Clerk SHOULD get broad social/citizen schemes like MJP Jan Arogya or PM Surya Ghar
    assert any("jan-arogya" in s or "surya-ghar" in s for s in clerk_slugs), "Clerk must match universal citizen schemes"
    print("  [PASS] Clerk correctly matched universal citizen schemes and disqualified from farmer/student schemes.")

    # 2. Farmer Profile
    farmer_profile = {
        "relationship": "Self",
        "occupation": "Farmer",
        "state": "Maharashtra",
        "district": "Solapur",
        "age": 42,
        "gender": "Male",
        "annual_income": "1 – 2.5 Lakh",
        "income_numeric": 150000,
        "education": "10th Pass (Matriculation)",
        "category": "OBC",
        "land_holding_acres": 3.0,
        "is_farmer": True,
        "is_student": False,
        "is_govt_employee": False
    }

    farmer_schemes = SchemeEligibilityService.get_ranked_schemes_for_profile(farmer_profile)
    farmer_eligible = [s for s in farmer_schemes if s.get("eligibility_status") in ("eligible", "possibly_eligible")]
    farmer_slugs = [s["slug"] for s in farmer_eligible]
    print(f"Farmer eligible schemes: {farmer_slugs}")
    assert "pm-kisan" in farmer_slugs, "Farmer must be eligible for PM-KISAN"
    assert "pm-vidyalakshmi" not in farmer_slugs, "Farmer must NOT be eligible for PM Vidyalaxmi"
    print("  [PASS] Farmer correctly matched agricultural schemes and disqualified from student schemes.")

    # 3. Student Profile
    student_profile = {
        "relationship": "Self",
        "occupation": "Student",
        "state": "Maharashtra",
        "district": "Mumbai",
        "age": 19,
        "gender": "Female",
        "annual_income": "1 – 2.5 Lakh",
        "income_numeric": 180000,
        "education": "12th Pass (Higher Secondary)",
        "category": "SC",
        "land_holding_acres": 0.0,
        "is_farmer": False,
        "is_student": True,
        "is_govt_employee": False
    }

    student_schemes = SchemeEligibilityService.get_ranked_schemes_for_profile(student_profile)
    student_eligible = [s for s in student_schemes if s.get("eligibility_status") in ("eligible", "possibly_eligible")]
    student_slugs = [s["slug"] for s in student_eligible]
    print(f"Student eligible schemes: {student_slugs}")
    assert any("vidyalakshmi" in s or "scholarship" in s for s in student_slugs), "Student must match education schemes"
    assert "pm-kisan" not in student_slugs, "Student must NOT be eligible for PM-KISAN"
    print("  [PASS] Student correctly matched education schemes and disqualified from farmer schemes.")

    # 4. Government Employee Profile
    govt_profile = {
        "relationship": "Self",
        "occupation": "Government Employee",
        "state": "Delhi",
        "age": 45,
        "gender": "Male",
        "annual_income": "> 8 Lakh",
        "income_numeric": 900000,
        "education": "Postgraduate (M.A. / M.Sc / M.Tech / MBA)",
        "category": "General",
        "land_holding_acres": 0.0,
        "is_farmer": False,
        "is_student": False,
        "is_govt_employee": True
    }

    govt_schemes = SchemeEligibilityService.get_ranked_schemes_for_profile(govt_profile)
    govt_eligible = [s for s in govt_schemes if s.get("eligibility_status") in ("eligible", "possibly_eligible")]
    govt_slugs = [s["slug"] for s in govt_eligible]
    print(f"Govt employee eligible schemes: {govt_slugs}")
    assert "pm-kisan" not in govt_slugs, "Govt employee must be disqualified from PM-KISAN"
    print("  [PASS] Government employee correctly evaluated with disqualification flags.\n")


def test_scheme_destination_urls():
    print("=== TEST: Scheme Destination URLs ===")
    db = SessionLocal()
    try:
        schemes = db.query(Scheme).filter(Scheme.is_active == True).all()
        for s in schemes:
            valid, dest_url = PortalHealthService.verify_scheme_official_destination(s)
            assert valid is True, f"Scheme {s.slug} lacks a verified official government destination URL"
            assert dest_url is not None and dest_url.startswith("http"), f"Scheme {s.slug} has malformed destination URL: {dest_url}"
            assert PortalHealthService.is_official_government_url(dest_url) is True, f"Destination URL for {s.slug} is not an official government URL: {dest_url}"
            print(f"  [PASS] Scheme {s.slug}: Verified URL -> {dest_url}")
        print("All active schemes have verified official government URLs.\n")
    finally:
        db.close()


def test_family_member_isolation():
    print("=== TEST: Family Member Isolation ===")
    # Verify that evaluating a family member's profile does not affect another profile
    self_prof = {
        "id": 1,
        "relationship": "Self",
        "name": "Ramesh",
        "occupation": "Clerk",
        "state": "Maharashtra",
        "age": 32,
        "gender": "Male",
        "annual_income": "2.5 – 5 Lakh",
        "income_numeric": 350000,
        "land_holding_acres": 0.0,
        "is_farmer": False,
        "is_student": False
    }

    father_prof = {
        "id": 2,
        "relationship": "Father",
        "name": "Ramlal",
        "occupation": "Farmer",
        "state": "Maharashtra",
        "age": 62,
        "gender": "Male",
        "annual_income": "1 – 2.5 Lakh",
        "income_numeric": 150000,
        "land_holding_acres": 4.0,
        "is_farmer": True,
        "is_student": False
    }

    self_schemes = SchemeEligibilityService.get_ranked_schemes_for_profile(self_prof)
    father_schemes = SchemeEligibilityService.get_ranked_schemes_for_profile(father_prof)

    self_slugs = [s["slug"] for s in self_schemes if s.get("eligibility_status") in ("eligible", "possibly_eligible")]
    father_slugs = [s["slug"] for s in father_schemes if s.get("eligibility_status") in ("eligible", "possibly_eligible")]

    assert "pm-kisan" not in self_slugs, "Self (Clerk) must not get PM-KISAN"
    assert "pm-kisan" in father_slugs, "Father (Farmer) must get PM-KISAN"
    print("  [PASS] Self (Clerk) and Father (Farmer) recommendations are strictly isolated.")
    print("Family member isolation test passed successfully.\n")


if __name__ == "__main__":
    test_url_verification()
    test_dynamic_occupations()
    test_scheme_destination_urls()
    test_family_member_isolation()
    print(">>> ALL VERIFICATION TESTS PASSED SUCCESSFULLY! <<<")
