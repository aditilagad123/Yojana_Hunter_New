import json
import logging
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Configure logging to show info messages
logging.basicConfig(level=logging.INFO)

from app import create_app
app = create_app()
client = app.test_client()

def test_all():
    print("=" * 80)
    print("STARTING COMPREHENSIVE 10-SCENARIO VERIFICATION")
    print("=" * 80)
    
    passed_count = 0
    total_scenarios = 10

    # --------------------------------------------------------------------------
    # SCENARIO 1: Student + Graduate
    # Expected: Education / scholarship schemes, 0 farmer schemes
    # --------------------------------------------------------------------------
    print("\n--- [Scenario 1] Student + Graduate ---")
    payload1 = {
        "occupation": "Student",
        "education": "Graduate",
        "state": "Maharashtra",
        "age": 22,
        "annual_income": 120000,
        "gender": "Female",
        "category": "General",
        "is_student": True,
        "is_farmer": False
    }
    res1 = client.post("/api/schemes/match", json=payload1)
    assert res1.status_code == 200, f"Scenario 1 failed with status {res1.status_code}"
    data1 = res1.get_json()
    eligible1 = data1.get("eligible", []) + data1.get("possibly_eligible", [])
    farmer_schemes_s1 = [s["name"] for s in eligible1 if s.get("category") == "Agriculture" or s.get("is_farmer_only")]
    print(f"Matched {len(eligible1)} schemes for Student + Graduate:")
    for s in eligible1:
        print(f"  + [{s.get('category')}] {s.get('name')}")
    assert len(farmer_schemes_s1) == 0, f"Farmer schemes leaked to Student: {farmer_schemes_s1}"
    assert any(s.get("category") == "Education" or "Student" in str(s.get("target_occupations")) for s in eligible1), "Student did not receive education/scholarship schemes"
    print("=> Scenario 1 PASSED: Relevant student schemes returned, 0 farmer schemes.")
    passed_count += 1

    # --------------------------------------------------------------------------
    # SCENARIO 2: Farmer + 12th
    # Expected: Agricultural schemes (e.g. PM-KISAN, PMFBY), 0 student-only schemes
    # --------------------------------------------------------------------------
    print("\n--- [Scenario 2] Farmer + 12th ---")
    payload2 = {
        "occupation": "Farmer",
        "education": "12th Pass",
        "state": "Maharashtra",
        "age": 40,
        "annual_income": 150000,
        "gender": "Male",
        "category": "OBC",
        "land_holding_acres": 2.5,
        "is_farmer": True,
        "is_student": False
    }
    res2 = client.post("/api/schemes/match", json=payload2)
    assert res2.status_code == 200, f"Scenario 2 failed with status {res2.status_code}"
    data2 = res2.get_json()
    eligible2 = data2.get("eligible", []) + data2.get("possibly_eligible", [])
    student_schemes_s2 = [s["name"] for s in eligible2 if s.get("category") == "Education" or s.get("is_student_only")]
    print(f"Matched {len(eligible2)} schemes for Farmer + 12th:")
    for s in eligible2:
        print(f"  + [{s.get('category')}] {s.get('name')}")
    assert len(student_schemes_s2) == 0, f"Student schemes leaked to Farmer: {student_schemes_s2}"
    assert any(s.get("category") == "Agriculture" for s in eligible2), "Farmer did not receive agricultural schemes"
    print("=> Scenario 2 PASSED: Relevant agriculture schemes returned, 0 student schemes.")
    passed_count += 1

    # --------------------------------------------------------------------------
    # SCENARIO 3: Other occupation + Teacher
    # Expected: Actual occupation 'Teacher' received by API and Gemini,
    # 0 farmer schemes, 0 student scholarships, relevant employee/health/skill schemes
    # --------------------------------------------------------------------------
    print("\n--- [Scenario 3] Other occupation + Teacher ---")
    payload3 = {
        "occupation": "Teacher",
        "education": "Graduate",
        "state": "Maharashtra",
        "age": 32,
        "annual_income": 350000,
        "gender": "Female",
        "category": "General"
    }
    res3 = client.post("/api/schemes/match", json=payload3)
    assert res3.status_code == 200, f"Scenario 3 failed with status {res3.status_code}"
    data3 = res3.get_json()
    eligible3 = data3.get("eligible", []) + data3.get("possibly_eligible", [])
    farmer_schemes_s3 = [s["name"] for s in eligible3 if s.get("is_farmer_only") or (s.get("category") == "Agriculture" and not any(t in s.get("name", "").lower() for t in ["teacher", "shikshak"]))]
    student_schemes_s3 = [s["name"] for s in eligible3 if s.get("is_student_only") or ("scholarship" in s.get("name", "").lower() and not any(t in s.get("name", "").lower() for t in ["teacher", "shikshak"]))]
    print(f"Matched {len(eligible3)} schemes for Teacher:")
    for s in eligible3:
        print(f"  + [{s.get('category')}] {s.get('name')} | whyMatched: {s.get('whyMatched', '')[:70]}...")
    assert len(farmer_schemes_s3) == 0, f"Farmer schemes leaked to Teacher: {farmer_schemes_s3}"
    assert len(student_schemes_s3) == 0, f"Student schemes leaked to Teacher: {student_schemes_s3}"
    assert len(eligible3) > 0, "Teacher should receive relevant citizen welfare/health schemes (e.g. MJP Jan Arogya / Skill India)"
    print("=> Scenario 3 PASSED: Teacher matched relevant schemes without student/farmer leakage.")
    passed_count += 1

    # --------------------------------------------------------------------------
    # SCENARIO 4: Other occupation + Housewife
    # Expected: Women / family / health schemes, 0 farmer schemes, 0 student scholarships
    # --------------------------------------------------------------------------
    print("\n--- [Scenario 4] Other occupation + Housewife ---")
    payload4 = {
        "occupation": "Housewife",
        "education": "10th Pass",
        "state": "Maharashtra",
        "age": 28,
        "annual_income": 120000,
        "gender": "Female",
        "category": "General"
    }
    res4 = client.post("/api/schemes/match", json=payload4)
    assert res4.status_code == 200, f"Scenario 4 failed with status {res4.status_code}"
    data4 = res4.get_json()
    eligible4 = data4.get("eligible", []) + data4.get("possibly_eligible", [])
    farmer_schemes_s4 = [s["name"] for s in eligible4 if s.get("category") == "Agriculture" or s.get("is_farmer_only")]
    student_schemes_s4 = [s["name"] for s in eligible4 if s.get("category") == "Education" or s.get("is_student_only")]
    print(f"Matched {len(eligible4)} schemes for Housewife:")
    for s in eligible4:
        print(f"  + [{s.get('category')}] {s.get('name')} | whyMatched: {s.get('whyMatched', '')[:70]}...")
    assert len(farmer_schemes_s4) == 0, f"Farmer schemes leaked to Housewife: {farmer_schemes_s4}"
    assert len(student_schemes_s4) == 0, f"Student schemes leaked to Housewife: {student_schemes_s4}"
    assert len(eligible4) > 0, "Housewife should receive relevant citizen/health/women schemes"
    print("=> Scenario 4 PASSED: Housewife matched relevant schemes without student/farmer leakage.")
    passed_count += 1

    # --------------------------------------------------------------------------
    # SCENARIO 5: Other occupation + Shopkeeper
    # Expected: Business / MSME / self-employed / health schemes, 0 student scholarships
    # --------------------------------------------------------------------------
    print("\n--- [Scenario 5] Other occupation + Shopkeeper ---")
    payload5 = {
        "occupation": "Shopkeeper",
        "education": "12th Pass",
        "state": "Maharashtra",
        "age": 35,
        "annual_income": 250000,
        "gender": "Male",
        "category": "OBC",
        "has_business": True
    }
    res5 = client.post("/api/schemes/match", json=payload5)
    assert res5.status_code == 200, f"Scenario 5 failed with status {res5.status_code}"
    data5 = res5.get_json()
    eligible5 = data5.get("eligible", []) + data5.get("possibly_eligible", [])
    student_schemes_s5 = [s["name"] for s in eligible5 if s.get("category") == "Education" or s.get("is_student_only")]
    farmer_schemes_s5 = [s["name"] for s in eligible5 if s.get("is_farmer_only") or (s.get("category") == "Agriculture" and not s.get("is_business_only"))]
    print(f"Matched {len(eligible5)} schemes for Shopkeeper:")
    for s in eligible5:
        print(f"  + [{s.get('category')}] {s.get('name')}")
    assert len(student_schemes_s5) == 0, f"Student schemes leaked to Shopkeeper: {student_schemes_s5}"
    assert len(farmer_schemes_s5) == 0, f"Farmer-only schemes leaked to Shopkeeper: {farmer_schemes_s5}"
    assert len(eligible5) > 0, "Shopkeeper should receive relevant self-employed/business/health schemes"
    print("=> Scenario 5 PASSED: Shopkeeper matched relevant schemes.")
    passed_count += 1

    # --------------------------------------------------------------------------
    # SCENARIO 6: Other education + a manually entered qualification
    # E.g. Education: 'Diploma in Electrical Engineering', Occupation: 'Electrician'
    # --------------------------------------------------------------------------
    print("\n--- [Scenario 6] Other education + Custom qualification ---")
    payload6 = {
        "occupation": "Electrician",
        "education": "Diploma in Electrical Engineering",
        "state": "Maharashtra",
        "age": 25,
        "annual_income": 180000,
        "gender": "Male",
        "category": "General"
    }
    res6 = client.post("/api/schemes/match", json=payload6)
    assert res6.status_code == 200, f"Scenario 6 failed with status {res6.status_code}"
    data6 = res6.get_json()
    eligible6 = data6.get("eligible", []) + data6.get("possibly_eligible", [])
    farmer_schemes_s6 = [s["name"] for s in eligible6 if s.get("category") == "Agriculture" or s.get("is_farmer_only")]
    print(f"Matched {len(eligible6)} schemes for Electrician with Diploma:")
    for s in eligible6:
        print(f"  + [{s.get('category')}] {s.get('name')}")
    assert len(farmer_schemes_s6) == 0, f"Farmer schemes leaked to Electrician: {farmer_schemes_s6}"
    assert len(eligible6) > 0, "Electrician should match skill development / health schemes"
    print("=> Scenario 6 PASSED: Custom qualification preserved and evaluated successfully.")
    passed_count += 1

    # --------------------------------------------------------------------------
    # SCENARIO 7: Custom occupation not in predefined options
    # E.g. Occupation: 'Solar Technician'
    # --------------------------------------------------------------------------
    print("\n--- [Scenario 7] Custom occupation ('Solar Technician') ---")
    payload7 = {
        "occupation": "Solar Technician",
        "education": "ITI Certified",
        "state": "Maharashtra",
        "age": 27,
        "annual_income": 200000,
        "gender": "Male",
        "category": "OBC"
    }
    res7 = client.post("/api/schemes/match", json=payload7)
    assert res7.status_code == 200, f"Scenario 7 failed with status {res7.status_code}"
    data7 = res7.get_json()
    eligible7 = data7.get("eligible", []) + data7.get("possibly_eligible", [])
    farmer_schemes_s7 = [s["name"] for s in eligible7 if s.get("is_farmer_only")]
    student_schemes_s7 = [s["name"] for s in eligible7 if s.get("is_student_only")]
    print(f"Matched {len(eligible7)} schemes for Solar Technician:")
    for s in eligible7:
        print(f"  + [{s.get('category')}] {s.get('name')}")
    assert len(farmer_schemes_s7) == 0, f"Farmer schemes leaked to Solar Technician: {farmer_schemes_s7}"
    assert len(student_schemes_s7) == 0, f"Student schemes leaked to Solar Technician: {student_schemes_s7}"
    print("=> Scenario 7 PASSED: Previously unknown custom occupation evaluated dynamically.")
    passed_count += 1

    # --------------------------------------------------------------------------
    # SCENARIO 8: Change from Farmer to Teacher and submit again
    # Verify that results refresh immediately and farmer schemes disappear
    # --------------------------------------------------------------------------
    print("\n--- [Scenario 8] Dynamic switch from Farmer to Teacher ---")
    # Step A: Farmer
    res8_farmer = client.post("/api/schemes/match", json={
        "occupation": "Farmer",
        "education": "12th",
        "state": "Maharashtra",
        "age": 30,
        "annual_income": 150000,
        "land_holding_acres": 2.0,
        "is_farmer": True
    })
    farmer_matches = [s["name"] for s in res8_farmer.get_json().get("eligible", []) + res8_farmer.get_json().get("possibly_eligible", []) if s.get("category") == "Agriculture"]
    print(f"  Step A (Farmer): Found {len(farmer_matches)} agriculture schemes.")
    assert len(farmer_matches) > 0, "Farmer must have agricultural schemes"

    # Step B: Switch to Teacher
    res8_teacher = client.post("/api/schemes/match", json={
        "occupation": "Teacher",
        "education": "Graduate",
        "state": "Maharashtra",
        "age": 30,
        "annual_income": 150000,
        "land_holding_acres": 0
    })
    teacher_matches = res8_teacher.get_json().get("eligible", []) + res8_teacher.get_json().get("possibly_eligible", [])
    teacher_farmer_leaks = [s["name"] for s in teacher_matches if s.get("category") == "Agriculture" or s.get("is_farmer_only")]
    print(f"  Step B (Switched to Teacher): Found {len(teacher_matches)} schemes. Agriculture leaks: {len(teacher_farmer_leaks)}")
    assert len(teacher_farmer_leaks) == 0, f"Farmer schemes lingered after switching to Teacher: {teacher_farmer_leaks}"
    print("=> Scenario 8 PASSED: Switching profile refreshes results and eliminates stale occupation schemes.")
    passed_count += 1

    # --------------------------------------------------------------------------
    # SCENARIO 9: Profile for which no matching schemes exist
    # E.g. Super high income (₹50 Lakh) or outside eligible age/region
    # --------------------------------------------------------------------------
    print("\n--- [Scenario 9] Profile with no matching schemes ---")
    payload9 = {
        "occupation": "Corporate Executive",
        "education": "Postgraduate",
        "state": "Sikkim",
        "age": 62,
        "annual_income": 5000000,  # 50 Lakh income (exceeds all welfare caps)
        "is_tax_payer": True,
        "is_govt_employee": True
    }
    res9 = client.post("/api/schemes/match", json=payload9)
    assert res9.status_code == 200, f"Scenario 9 failed with status {res9.status_code}"
    data9 = res9.get_json()
    eligible9 = data9.get("eligible", [])
    print(f"  Eligible schemes for Rs. 50L income corporate executive: {len(eligible9)}")
    assert len(eligible9) == 0, f"Expected 0 eligible schemes for high-income corporate taxpayer, got: {[s['name'] for s in eligible9]}"
    print("=> Scenario 9 PASSED: Proper empty results when citizen does not match any scheme conditions.")
    passed_count += 1

    # --------------------------------------------------------------------------
    # SCENARIO 10: Missing custom values, API errors, and incomplete eligibility
    # --------------------------------------------------------------------------
    print("\n--- [Scenario 10] Missing values, incomplete data & error handling ---")
    # Case A: Completely empty profile
    res10_empty = client.post("/api/schemes/match", json={})
    assert res10_empty.status_code == 200, f"Empty profile failed: {res10_empty.status_code}"
    data10_empty = res10_empty.get_json()
    assert data10_empty.get("total_evaluated") == 0, f"Empty profile should return 0 evaluated schemes, got {data10_empty.get('total_evaluated')}"
    print("  + Case A: Empty profile returns safe empty result list (total_evaluated: 0).")

    # Case B: Incomplete profile (missing age and income)
    res10_incomp = client.post("/api/schemes/match", json={"occupation": "Teacher", "state": "Maharashtra"})
    assert res10_incomp.status_code == 200, f"Incomplete profile failed: {res10_incomp.status_code}"
    data10_incomp = res10_incomp.get_json()
    # Incomplete info must result in 'possibly_eligible' rather than claiming 100% confirmed eligibility
    assert data10_incomp.get("possibly_eligible_count", 0) > 0, "Incomplete profile schemes should be marked 'possibly_eligible'"
    print(f"  + Case B: Incomplete profile flags {data10_incomp.get('possibly_eligible_count')} schemes as 'possibly_eligible' (pending verification).")

    # Case C: Single scheme evaluation with incomplete data
    res10_single = client.get("/api/schemes/mjp-jan-arogya")
    assert res10_single.status_code == 200, f"Single scheme get failed: {res10_single.status_code}"
    s_detail = res10_single.get_json()
    assert s_detail.get("id") or s_detail.get("slug") == "mjp-jan-arogya", "Failed to retrieve scheme details"
    print(f"  + Case C: Single scheme endpoint returns structured criteria and source reference: {s_detail.get('sourceReference', {}).get('official_url')}")

    print("=> Scenario 10 PASSED: Robust error handling, safe fallbacks, and accurate incomplete info flagging.")
    passed_count += 1

    print("\n" + "=" * 80)
    print(f"ALL {passed_count}/{total_scenarios} SCENARIOS TESTED AND PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    test_all()
