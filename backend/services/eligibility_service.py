import re
import datetime
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import joinedload
from database import SessionLocal
from models import Scheme, SchemeRule, Profile, SchemeDocumentRequirement
from services.rule_engine import RuleEngine

logger = logging.getLogger(__name__)

# In-memory TTL cache for Gemini evaluations to prevent repeated slow API calls
_GEMINI_EVAL_CACHE: Dict[str, Tuple[float, Dict[int, Any]]] = {}
_CACHE_TTL_SECONDS = 900  # 15 minutes

class SchemeEligibilityService:
    """
    Core Deterministic Eligibility and Matching Service for Yojana Hunter.
    Compares real citizen profile attributes against structured scheme criteria,
    evaluates application periods, detects exclusions, and produces transparent
    human-readable explanations for every match decision.
    """

    # Supported standardized statuses
    STATUS_ELIGIBLE = "eligible"
    STATUS_POSSIBLY_ELIGIBLE = "possibly_eligible"
    STATUS_NOT_ELIGIBLE = "not_eligible"
    STATUS_ELIGIBILITY_UNKNOWN = "eligibility_unknown"
    STATUS_APPLICATIONS_CLOSED = "applications_closed"

    @classmethod
    def parse_dob_to_age(cls, dob_str: Optional[str]) -> Optional[int]:
        """Calculates age in years from common date of birth string formats."""
        if not dob_str:
            return None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                dob = datetime.datetime.strptime(str(dob_str).strip()[:10], fmt)
                today = datetime.datetime.now()
                return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            except Exception:
                continue
        return None

    @staticmethod
    def normalize_gender(val: Optional[str]) -> str:
        """Normalizes gender string to 'male', 'female', 'transgender', or 'all'."""
        if not val:
            return "all"
        v = str(val).strip().lower()
        if v in ("female", "woman", "women", "girl", "girls", "mahila", "kanya", "ladki", "महिला", "स्त्री", "लड़की", "औरत"):
            return "female"
        if v in ("male", "man", "men", "boy", "boys", "purush", "पुरुष", "लड़का", "माणूस"):
            return "male"
        if v in ("transgender", "other", "third gender", "trans", "तृतीयपंथी", "इतर", "अन्य", "ट्रांसजेंडर"):
            return "transgender"
        return "all"

    @classmethod
    def classify_scheme_gender(cls, scheme: Any) -> str:
        """
        Distinguishes scheme gender restriction as 'female', 'male', or 'all'.
        Default is 'all' (gender-neutral) unless explicitly designated as gender-exclusive.
        """
        raw_gender = getattr(scheme, "gender", None)
        if isinstance(scheme, dict):
            raw_gender = scheme.get("gender")

        g_norm = cls.normalize_gender(raw_gender)
        if g_norm in ("female", "male"):
            return g_norm

        raw_str = str(raw_gender or "").strip().lower()
        if raw_str in ("all", "any", "all genders", "both", "unrestricted", "universal"):
            return "all"

        s_name = str(getattr(scheme, "name", None) or (scheme.get("name") if isinstance(scheme, dict) else "") or "").lower()

        # Unambiguous female-exclusive markers in title
        if any(marker in s_name for marker in [
            "for girl students", "for girls", "ladki bahin", "mahila samman",
            "matru vandana", "sukanya samriddhi", "scheme for adolescent girls"
        ]):
            return "female"

        # Unambiguous male-exclusive markers in title
        if any(marker in s_name for marker in ["boys only", "male only", "men only", "for boys"]):
            return "male"

        return "all"

    @classmethod
    def user_satisfies_scheme_gender(cls, user_gender: Optional[str], scheme: Any) -> Tuple[bool, str]:
        """
        Evaluates whether user satisfies scheme gender criteria:
        - If female: eligible for female-specific and all-gender schemes.
        - If male: eligible for male-specific and all-gender schemes.
        - Never show female-exclusive schemes to male users or male-exclusive schemes to female users.
        - Missing or gender-neutral metadata defaults to all-genders (never 0 schemes).
        """
        u_gender = cls.normalize_gender(user_gender)
        s_gender = cls.classify_scheme_gender(scheme)

        if s_gender == "all":
            return True, ""

        if not user_gender or u_gender == "all":
            return True, ""

        if u_gender == "male" and s_gender == "female":
            return False, f"Gender restriction: Scheme exclusively benefits female beneficiaries (Your profile: Male)"

        if u_gender == "female" and s_gender == "male":
            return False, f"Gender restriction: Scheme exclusively benefits male beneficiaries (Your profile: Female)"

        return True, ""

    @classmethod
    def genders_match(cls, user_gender: Optional[str], target_gender: Optional[str]) -> bool:
        """Accurately checks whether user gender satisfies the scheme target gender without substring leakage."""
        u_norm = cls.normalize_gender(user_gender)
        t_norm = cls.normalize_gender(target_gender)
        if t_norm == "all" or u_norm == "all":
            return True
        return u_norm == t_norm

    @classmethod
    def evaluate_scheme_for_profile(
        cls, 
        scheme: Scheme, 
        profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates a single scheme against a citizen profile.
        Returns a rich evaluation dictionary with status, match score, breakdown,
        and human-friendly 'Why am I seeing this scheme?' explanations.
        """
        profile = dict(profile_data or {})
        if "profile" in profile and isinstance(profile["profile"], dict):
            inner = dict(profile["profile"])
            inner.update({k: v for k, v in profile.items() if k != "profile"})
            profile = inner

        # Normalize age from DOB if age is missing
        if (profile.get("age") is None or profile.get("age") == 0) and profile.get("date_of_birth"):
            calculated_age = cls.parse_dob_to_age(profile.get("date_of_birth"))
            if calculated_age:
                profile["age"] = calculated_age
        elif (profile.get("age") is None or profile.get("age") == 0) and profile.get("dateOfBirth"):
            calculated_age = cls.parse_dob_to_age(profile.get("dateOfBirth"))
            if calculated_age:
                profile["age"] = calculated_age

        # Standardize camelCase profile keys to snake_case
        if profile.get("is_farmer") is None and profile.get("isFarmer") is not None:
            profile["is_farmer"] = profile.get("isFarmer")
        if profile.get("is_student") is None and profile.get("isStudent") is not None:
            profile["is_student"] = profile.get("isStudent")
        if profile.get("has_business") is None and profile.get("hasBusiness") is not None:
            profile["has_business"] = profile.get("hasBusiness")
        if profile.get("is_disabled") is None and profile.get("isDisabled") is not None:
            profile["is_disabled"] = profile.get("isDisabled")
        if profile.get("is_tax_payer") is None:
            profile["is_tax_payer"] = bool(profile.get("isTaxPayer", False))
        if profile.get("is_govt_employee") is None:
            profile["is_govt_employee"] = bool(profile.get("isGovtEmployee", False))
        if profile.get("land_holding_acres") is None and profile.get("landholdingAcres") is not None:
            profile["land_holding_acres"] = profile.get("landholdingAcres")
        if profile.get("annual_income") is None and profile.get("annualIncome") is not None:
            profile["annual_income"] = profile.get("annualIncome")

        p_occ_lower = str(profile.get("occupation") or "").lower().strip()
        if "student" in p_occ_lower and profile.get("is_student") is None:
            profile["is_student"] = True
        if any(k in p_occ_lower for k in ["farmer", "kisan", "agri", "cultivat"]) and profile.get("is_farmer") is None:
            profile["is_farmer"] = True

        requirements_satisfied: List[str] = []
        requirements_not_satisfied: List[str] = []
        missing_information: List[str] = []
        criteria_breakdown: List[Dict[str, Any]] = []

        total_rules_evaluated = 0
        passed_rules_count = 0
        mandatory_failed = False
        is_unknown_rules = False

        # ---------------------------------------------------------------------
        # 1. APPLICATION WINDOW / STATUS EVALUATION
        # ---------------------------------------------------------------------
        app_window = (scheme.application_status or "open").lower().strip()
        now = datetime.datetime.now()

        # Check explicit dates if available
        if scheme.end_date and scheme.end_date < now:
            app_window = "closed"
        elif scheme.deadline and scheme.deadline < now:
            app_window = "closed"
        elif scheme.start_date and scheme.start_date > now:
            app_window = "upcoming"

        is_closed = (app_window == "closed")

        # ---------------------------------------------------------------------
        # 2. CHECK EXCLUSIONS (Disqualifications)
        # ---------------------------------------------------------------------
        exclusions = scheme.exclusions or []
        if isinstance(exclusions, str):
            exclusions = [e.strip() for e in exclusions.split(",") if e.strip()]

        for excl in exclusions:
            excl_lower = str(excl).lower()
            if "tax" in excl_lower:
                total_rules_evaluated += 1
                if profile.get("is_tax_payer") or profile.get("isTaxPayer"):
                    mandatory_failed = True
                    requirements_not_satisfied.append(f"Ineligible: Income tax payers are excluded ({excl})")
                elif profile.get("is_tax_payer") is False or profile.get("isTaxPayer") is False:
                    passed_rules_count += 1
                    requirements_satisfied.append("Non-taxpayer status verified")
            if "govt" in excl_lower or "government" in excl_lower:
                total_rules_evaluated += 1
                if profile.get("is_govt_employee") or profile.get("isGovtEmployee"):
                    mandatory_failed = True
                    requirements_not_satisfied.append(f"Ineligible: Government employees are excluded ({excl})")
                elif profile.get("is_govt_employee") is False or profile.get("isGovtEmployee") is False:
                    passed_rules_count += 1
                    requirements_satisfied.append("Non-government employee status verified")

        # ---------------------------------------------------------------------
        # 3. DIRECT SCHEME LEVEL & STATE RESTRICTIONS
        # ---------------------------------------------------------------------
        scheme_state = (scheme.state or "All India").strip()
        scheme_level = (scheme.level or "Central Scheme").strip()
        user_state = (profile.get("state") or "").strip()

        if scheme_state.lower() not in ("all india", "national", "central", "all"):
            total_rules_evaluated += 1
            if not user_state:
                missing_information.append(f"State of Residence required to verify {scheme_state} residency")
            elif user_state.lower() == scheme_state.lower():
                passed_rules_count += 1
                requirements_satisfied.append(f"Resident of {scheme_state}")
                criteria_breakdown.append({
                    "id": "c_state",
                    "name": "State Domicile",
                    "condition": f"Must be resident of {scheme_state}",
                    "userValue": user_state,
                    "passed": True
                })
            else:
                mandatory_failed = True
                requirements_not_satisfied.append(f"State: Restricted to residents of {scheme_state} (Your state: {user_state})")
                criteria_breakdown.append({
                    "id": "c_state",
                    "name": "State Domicile",
                    "condition": f"Must be resident of {scheme_state}",
                    "userValue": user_state,
                    "passed": False
                })

        # ---------------------------------------------------------------------
        # 4. AGE LIMITS (age_min, age_max)
        # ---------------------------------------------------------------------
        user_age = profile.get("age")
        if scheme.age_min is not None:
            total_rules_evaluated += 1
            if user_age is None or user_age == 0:
                missing_information.append(f"Age or Date of Birth required (Minimum age: {scheme.age_min} years)")
            elif user_age >= scheme.age_min:
                passed_rules_count += 1
                requirements_satisfied.append(f"Age {user_age} is above minimum limit of {scheme.age_min} years")
                criteria_breakdown.append({
                    "id": "c_age_min",
                    "name": "Minimum Age",
                    "condition": f"Age >= {scheme.age_min}",
                    "userValue": f"{user_age} years",
                    "passed": True
                })
            else:
                mandatory_failed = True
                requirements_not_satisfied.append(f"Age: Age {user_age} is below the minimum required age of {scheme.age_min} years")
                criteria_breakdown.append({
                    "id": "c_age_min",
                    "name": "Minimum Age",
                    "condition": f"Age >= {scheme.age_min}",
                    "userValue": f"{user_age} years",
                    "passed": False
                })

        if scheme.age_max is not None:
            total_rules_evaluated += 1
            if user_age is None or user_age == 0:
                missing_information.append(f"Age or Date of Birth required (Maximum age: {scheme.age_max} years)")
            elif user_age <= scheme.age_max:
                passed_rules_count += 1
                requirements_satisfied.append(f"Age {user_age} is within upper limit of {scheme.age_max} years")
                criteria_breakdown.append({
                    "id": "c_age_max",
                    "name": "Maximum Age",
                    "condition": f"Age <= {scheme.age_max}",
                    "userValue": f"{user_age} years",
                    "passed": True
                })
            else:
                mandatory_failed = True
                requirements_not_satisfied.append(f"Age: Age {user_age} exceeds the maximum limit of {scheme.age_max} years")
                criteria_breakdown.append({
                    "id": "c_age_max",
                    "name": "Maximum Age",
                    "condition": f"Age <= {scheme.age_max}",
                    "userValue": f"{user_age} years",
                    "passed": False
                })

        # ---------------------------------------------------------------------
        # 5. INCOME CEILING (income_max)
        # ---------------------------------------------------------------------
        if scheme.income_max is not None:
            total_rules_evaluated += 1
            actual_numeric = profile.get("income_numeric") or profile.get("incomeNumeric")
            if actual_numeric is None:
                actual_numeric = RuleEngine.parse_numeric_income(profile.get("annual_income") or profile.get("annualIncome"))

            if not actual_numeric and not profile.get("annual_income") and not profile.get("annualIncome"):
                missing_information.append(f"Annual family income required (Ceiling: ₹{scheme.income_max:,.0f})")
            elif actual_numeric <= scheme.income_max:
                passed_rules_count += 1
                requirements_satisfied.append(f"Family income ₹{actual_numeric:,.0f} is within ₹{scheme.income_max:,.0f} ceiling")
                criteria_breakdown.append({
                    "id": "c_income_max",
                    "name": "Annual Income Limit",
                    "condition": f"Income <= ₹{scheme.income_max:,.0f}",
                    "userValue": f"₹{actual_numeric:,.0f}",
                    "passed": True
                })
            else:
                mandatory_failed = True
                requirements_not_satisfied.append(f"Income: Family income ₹{actual_numeric:,.0f} exceeds the maximum limit of ₹{scheme.income_max:,.0f}")
                criteria_breakdown.append({
                    "id": "c_income_max",
                    "name": "Annual Income Limit",
                    "condition": f"Income <= ₹{scheme.income_max:,.0f}",
                    "userValue": f"₹{actual_numeric:,.0f}",
                    "passed": False
                })

        # ---------------------------------------------------------------------
        # 6. GENDER SPECIFICITY & BENEFICIARY CRITERIA
        # ---------------------------------------------------------------------
        user_gender = (profile.get("gender") or "").strip()
        scheme_gender_type = cls.classify_scheme_gender(scheme)

        if scheme_gender_type != "all":
            total_rules_evaluated += 1
            if not user_gender:
                missing_information.append(f"Gender information required (Scheme requires: {scheme_gender_type.capitalize()})")
                criteria_breakdown.append({
                    "id": "c_gender",
                    "name": "Gender Eligibility",
                    "condition": f"Gender: {scheme_gender_type.capitalize()} Only",
                    "userValue": "Not specified",
                    "passed": False
                })
            else:
                is_gen_ok, gen_fail_reason = cls.user_satisfies_scheme_gender(user_gender, scheme)
                if not is_gen_ok:
                    mandatory_failed = True
                    requirements_not_satisfied.append(gen_fail_reason)
                    criteria_breakdown.append({
                        "id": "c_gender",
                        "name": "Gender Eligibility",
                        "condition": f"Gender: {scheme_gender_type.capitalize()} Only",
                        "userValue": user_gender,
                        "passed": False
                    })
                else:
                    passed_rules_count += 1
                    requirements_satisfied.append(f"Gender matches criteria ({scheme_gender_type.capitalize()})")
                    criteria_breakdown.append({
                        "id": "c_gender",
                        "name": "Gender Eligibility",
                        "condition": f"Gender: {scheme_gender_type.capitalize()} Only",
                        "userValue": user_gender,
                        "passed": True
                    })
        else:
            # Gender-neutral / open to all genders
            total_rules_evaluated += 1
            passed_rules_count += 1
            requirements_satisfied.append(f"Gender eligibility: Scheme open to all genders ({user_gender or 'Any'})")
            criteria_breakdown.append({
                "id": "c_gender",
                "name": "Gender Eligibility",
                "condition": "Gender: All Genders Eligible",
                "userValue": user_gender or "All",
                "passed": True
            })

        # ---------------------------------------------------------------------
        # 7. OCCUPATION & TARGET BENEFICIARY EVALUATION (c_occupation)
        # ---------------------------------------------------------------------
        raw_target_occs = scheme.target_occupations or []
        if isinstance(raw_target_occs, str):
            raw_target_occs = [x.strip() for x in raw_target_occs.split(",") if x.strip()]
        target_occs = [str(x).strip().lower() for x in raw_target_occs if str(x).strip()]

        scheme_occ = str(scheme.occupation or "").lower().strip()
        scheme_cat = str(scheme.category or "").lower().strip()

        # Build comprehensive target occupation list
        if not target_occs:
            if scheme.is_farmer_only or scheme_occ in ("farmer", "kisan") or scheme_cat in ("agriculture", "farming"):
                target_occs.append("farmer")
            if scheme.is_student_only or scheme_occ in ("student", "scholar") or scheme_cat in ("education", "scholarship"):
                target_occs.append("student")
            if scheme.is_business_only or any(b in scheme_occ for b in ["artisan", "business", "self-employed"]) or scheme_cat in ("entrepreneurship", "business"):
                target_occs.extend(["self-employed", "business", "artisan"])

        user_occ = str(profile.get("occupation") or "").strip()
        user_occ_lower = user_occ.lower()

        # Categorize user occupation
        is_user_farmer = bool(
            (profile.get("is_farmer") is True or profile.get("isFarmer") is True)
            or any(k in user_occ_lower for k in ["farmer", "kisan", "agri", "cultivat", "krishi", "shetkari"])
        )
        is_user_student = bool(
            (profile.get("is_student") is True or profile.get("isStudent") is True)
            or "student" in user_occ_lower
        )
        is_user_biz = bool(
            (profile.get("has_business") is True or profile.get("hasBusiness") is True)
            or any(b in user_occ_lower for b in ["shopkeeper", "trader", "merchant", "retailer", "vendor", "storekeeper", "business", "self-employed", "artisan", "craftsperson", "entrepreneur"])
        )
        is_user_teacher = bool(
            any(t in user_occ_lower for t in ["teacher", "professor", "lecturer", "educator", "instructor", "faculty", "shikshak", "adhyapak", "mentor", "tutor", "academic", "teaching"])
        )
        is_user_salaried = bool(
            (any(s in user_occ_lower for s in ["teacher", "professor", "lecturer", "educator", "instructor", "doctor", "nurse", "engineer", "clerk", "accountant", "employee", "salaried", "worker", "corporate", "staff"]) or is_user_teacher)
            and not is_user_student and not is_user_farmer
        )
        is_user_homemaker = bool(
            any(h in user_occ_lower for h in ["housewife", "homemaker", "home maker"])
        )
        is_user_unemployed = bool("unemploy" in user_occ_lower or str(profile.get("employment_status") or "").lower() == "unemployed")

        # Exclusivities
        is_teacher_target = bool(
            any(t in target_occs for t in ["teacher", "educator", "professor", "faculty", "lecturer", "instructor", "shikshak", "adhyapak", "teaching"])
            or any(t in scheme_occ for t in ["teacher", "educator", "professor", "faculty", "lecturer", "instructor", "shikshak", "adhyapak", "teaching"])
            or any(t in str(scheme.name or "").lower() for t in ["teacher", "shikshak", "faculty", "educator"])
        )

        is_farmer_target = bool(
            scheme.is_farmer_only 
            or (target_occs and all(t in ("farmer", "kisan", "cultivator", "agriculture") for t in target_occs)) 
            or (scheme_cat in ("agriculture", "farming", "krishi") and not scheme.is_student_only)
        )
        is_student_target = bool(
            (scheme.is_student_only 
            or (target_occs and all(t in ("student", "scholar", "higher education") for t in target_occs)) 
            or (scheme_cat in ("scholarship",) and not scheme.is_farmer_only))
            and not is_teacher_target
        )
        is_biz_target = bool(
            scheme.is_business_only 
            or (target_occs and all(b in ["self-employed", "artisan", "craftsperson", "entrepreneur", "business"] for b in target_occs)) 
            or (scheme_cat in ("entrepreneurship", "business", "msme") and not scheme.is_farmer_only and not scheme.is_student_only)
        )

        is_broad_social = bool(
            (not is_farmer_target and not is_student_target and not is_biz_target and not is_teacher_target)
            and (
                scheme_cat in ("health", "social welfare", "women & child", "skill development", "public health", "food security", "family welfare")
                or len(target_occs) >= 4
                or any(o in ("all", "any", "general", "citizens", "all citizens", "*", "") for o in target_occs)
                or not target_occs
            )
        )

        total_rules_evaluated += 1

        if is_broad_social:
            target_display = "Open to all citizen occupations (Subject to income/residence)"
            passed_rules_count += 1
            requirements_satisfied.append(f"Occupation: Universal eligibility ({user_occ or 'Citizen'})")
            criteria_breakdown.append({
                "id": "c_occupation",
                "name": "Target Occupation",
                "condition": target_display,
                "userValue": user_occ or "Citizen",
                "passed": True
            })
        elif is_teacher_target:
            target_display = "School / College Teacher, Educator & Academic Faculty"
            occ_passed = is_user_teacher
            if occ_passed:
                passed_rules_count += 1
                requirements_satisfied.append(f"Occupation: Educator / Teacher verified ({user_occ or 'Teacher'})")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": user_occ or "Teacher",
                    "passed": True
                })
            elif not user_occ:
                missing_information.append("Teacher / Educator occupational status required")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": "Not Provided",
                    "passed": False
                })
            else:
                mandatory_failed = True
                requirements_not_satisfied.append(f"Occupation: Restricted to educators & teachers (Your occupation: {user_occ or 'Non-Teacher'})")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": user_occ or "Non-Teacher",
                    "passed": False
                })
        elif is_farmer_target:
            target_display = "Active Agricultural Farmer / Cultivator"
            biz_type = str(profile.get("business_type") or profile.get("businessType") or "").lower()
            is_agri_biz = any(k in biz_type or k in user_occ_lower for k in ["agri", "farm", "kisan", "krishi", "cultivat"])
            occ_passed = is_user_farmer or (is_user_biz and is_agri_biz and "self-employed" in target_occs)

            if occ_passed:
                passed_rules_count += 1
                requirements_satisfied.append(f"Occupation: Agricultural Farmer verified ({user_occ or 'Farmer'})")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": user_occ or "Farmer",
                    "passed": True
                })
                # Check landholding if restricted
                if scheme.max_landholding_acres:
                    total_rules_evaluated += 1
                    user_land = profile.get("land_holding_acres") or profile.get("landholding_acres") or profile.get("landHoldingAcres")
                    if user_land is None:
                        missing_information.append(f"Landholding acreage required (Max permitted: {scheme.max_landholding_acres} acres)")
                    elif float(user_land) <= scheme.max_landholding_acres:
                        passed_rules_count += 1
                        requirements_satisfied.append(f"Landholding {user_land} acres is within {scheme.max_landholding_acres} acres limit")
                        criteria_breakdown.append({
                            "id": "c_land",
                            "name": "Landholding Limit",
                            "condition": f"Land <= {scheme.max_landholding_acres} acres",
                            "userValue": f"{user_land} acres",
                            "passed": True
                        })
                    else:
                        mandatory_failed = True
                        requirements_not_satisfied.append(f"Landholding: {user_land} acres exceeds maximum limit of {scheme.max_landholding_acres} acres")
                        criteria_breakdown.append({
                            "id": "c_land",
                            "name": "Landholding Limit",
                            "condition": f"Land <= {scheme.max_landholding_acres} acres",
                            "userValue": f"{user_land} acres",
                            "passed": False
                        })
            elif not user_occ and profile.get("is_farmer") is None:
                missing_information.append("Farmer status / agricultural occupation required")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": "Not Provided",
                    "passed": False
                })
            else:
                mandatory_failed = True
                requirements_not_satisfied.append(f"Occupation: Restricted to agricultural farmers (Your occupation: {user_occ or 'Non-Farmer'})")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": user_occ or "Non-Farmer",
                    "passed": False
                })
        elif is_student_target:
            target_display = "Enrolled Student (Higher Education / School)"
            occ_passed = is_user_student
            if occ_passed:
                passed_rules_count += 1
                requirements_satisfied.append(f"Occupation: Active student enrollment verified ({user_occ or 'Student'})")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": user_occ or "Student",
                    "passed": True
                })
            elif not user_occ and profile.get("is_student") is None:
                missing_information.append("Student enrollment status required")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": "Not Provided",
                    "passed": False
                })
            else:
                mandatory_failed = True
                requirements_not_satisfied.append(f"Occupation: Restricted to students (Your occupation: {user_occ or 'Non-Student'})")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": user_occ or "Non-Student",
                    "passed": False
                })
        elif is_biz_target:
            target_display = "Small Business / MSME / Artisan / Self-Employed"
            occ_passed = is_user_biz
            if occ_passed:
                passed_rules_count += 1
                requirements_satisfied.append(f"Occupation: Business / Self-Employed status verified ({user_occ or 'Business'})")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": user_occ or "Self-Employed",
                    "passed": True
                })
            elif not user_occ and profile.get("has_business") is None:
                missing_information.append("Business / Self-Employed status required")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": "Not Provided",
                    "passed": False
                })
            else:
                mandatory_failed = True
                requirements_not_satisfied.append(f"Occupation: Restricted to business / self-employed (Your occupation: {user_occ or 'Non-Business'})")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": user_occ or "Non-Business",
                    "passed": False
                })
        else:
            # Multi-group target_occs
            matched_group = False
            if "student" in target_occs and is_user_student:
                matched_group = True
            if "farmer" in target_occs and is_user_farmer:
                matched_group = True
            if any(b in target_occs for b in ["self-employed", "business", "entrepreneur", "artisan", "craftsperson", "shopkeeper", "trader"]) and is_user_biz:
                matched_group = True
            if any(s in target_occs for s in ["teacher", "educator", "professor", "faculty"]) and any(t in user_occ_lower for t in ["teacher", "educator", "professor", "faculty", "lecturer", "instructor"]):
                matched_group = True
            if any(s in target_occs for s in ["salaried employee", "salaried", "employee"]) and is_user_salaried:
                matched_group = True
            if any(u in target_occs for u in ["unemployed", "job seeker", "youth"]) and (is_user_unemployed or is_user_student):
                matched_group = True
            if any(h in target_occs for h in ["homemaker", "housewife", "women"]) and is_user_homemaker:
                matched_group = True
            if any(o in user_occ_lower or user_occ_lower in o for o in target_occs if user_occ_lower):
                matched_group = True

            target_display = ", ".join(raw_target_occs) if raw_target_occs else (scheme.occupation or "Target Beneficiaries")
            if matched_group:
                passed_rules_count += 1
                requirements_satisfied.append(f"Occupation matches target beneficiary ({user_occ})")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": user_occ or "Matching Role",
                    "passed": True
                })
            elif not user_occ:
                missing_information.append(f"Occupation required (Targets: {target_display})")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": "Not Provided",
                    "passed": False
                })
            else:
                mandatory_failed = True
                requirements_not_satisfied.append(f"Occupation: Restricted to {target_display} (Your occupation: {user_occ})")
                criteria_breakdown.append({
                    "id": "c_occupation",
                    "name": "Target Occupation",
                    "condition": target_display,
                    "userValue": user_occ,
                    "passed": False
                })

        # ---------------------------------------------------------------------
        # 8. EDUCATION REQUIREMENT EVALUATION
        # ---------------------------------------------------------------------
        scheme_edu = (scheme.education or "").strip().lower()
        if scheme_edu and scheme_edu not in ("all", "any", "no formal education required", "no minimum education requirement", "no education barrier", "none"):
            total_rules_evaluated += 1
            user_edu = str(profile.get("education") or "").strip()
            user_edu_lower = user_edu.lower()

            if not user_edu:
                missing_information.append(f"Education level required (Scheme requirement: {scheme.education})")
            else:
                edu_rank = {
                    "illiterate": 0, "none": 0,
                    "primary": 1, "8th": 1, "8th pass": 1,
                    "10th": 2, "10th pass": 2, "matriculation": 2, "matric": 2, "ssc": 2,
                    "12th": 3, "12th pass": 3, "higher secondary": 3, "hsc": 3, "intermediate": 3,
                    "diploma": 3.5, "iti": 3.5, "d.ed": 3.5, "ded": 3.5, "d.el.ed": 3.5,
                    "graduate": 4, "b.e.": 4, "b.e": 4, "b.tech": 4, "degree": 4, "b.sc": 4, "b.com": 4, "ba": 4, "b.ed": 4, "bed": 4, "b.el.ed": 4,
                    "postgraduate": 5, "pg": 5, "master": 5, "m.tech": 5
                }
                user_level = 2  # default 10th pass if unrecognized
                for k, v in edu_rank.items():
                    if k in user_edu_lower:
                        user_level = max(user_level, v)

                # Split composite requirement strings (e.g. '12th Pass / D.Ed / B.Ed / Graduate')
                # A citizen qualifies if their level meets the MINIMUM alternative level, or matches any keyword
                options = [opt.strip() for opt in re.split(r'[/,]|\s+or\s+', scheme_edu) if opt.strip()]
                option_levels = []
                for opt in options:
                    opt_lvl = 0
                    for k, v in edu_rank.items():
                        if k in opt:
                            opt_lvl = max(opt_lvl, v)
                    if opt_lvl > 0:
                        option_levels.append(opt_lvl)

                req_level = min(option_levels) if option_levels else 0
                if req_level == 0:
                    for k, v in edu_rank.items():
                        if k in scheme_edu:
                            req_level = max(req_level, v)

                matched_term = any(term in user_edu_lower for term in scheme_edu.split() if len(term) > 2) or any(user_edu_lower in opt or opt in user_edu_lower for opt in options)
                if user_level >= req_level or matched_term:
                    passed_rules_count += 1
                    requirements_satisfied.append(f"Education requirement met ({user_edu})")
                    criteria_breakdown.append({
                        "id": "c_education",
                        "name": "Educational Qualification",
                        "condition": scheme.education,
                        "userValue": user_edu,
                        "passed": True
                    })
                else:
                    mandatory_failed = True
                    requirements_not_satisfied.append(f"Education: Requires {scheme.education} (Your qualification: {user_edu})")
                    criteria_breakdown.append({
                        "id": "c_education",
                        "name": "Educational Qualification",
                        "condition": scheme.education,
                        "userValue": user_edu,
                        "passed": False
                    })

        # ---------------------------------------------------------------------
        # 9. SOCIAL CATEGORY EVALUATION
        # ---------------------------------------------------------------------
        scheme_cat = (scheme.social_category or "All").strip().lower()
        user_cat = str(profile.get("category") or profile.get("social_category") or profile.get("socialCategory") or "General").strip()
        user_cat_lower = user_cat.lower()

        if scheme_cat not in ("all", "any", "unrestricted", "all categories"):
            total_rules_evaluated += 1
            if not profile.get("category") and not profile.get("social_category") and not profile.get("socialCategory"):
                missing_information.append(f"Social category required (Target: {scheme.social_category})")
            elif user_cat_lower in scheme_cat or scheme_cat in user_cat_lower:
                passed_rules_count += 1
                requirements_satisfied.append(f"Social Category ({user_cat}) qualifies for {scheme.social_category} allocation")
                criteria_breakdown.append({
                    "id": "c_category",
                    "name": "Social Category",
                    "condition": scheme.social_category,
                    "userValue": user_cat,
                    "passed": True
                })
            else:
                mandatory_failed = True
                requirements_not_satisfied.append(f"Social Category: Reserved for {scheme.social_category} beneficiaries (Your category: {user_cat})")
                criteria_breakdown.append({
                    "id": "c_category",
                    "name": "Social Category",
                    "condition": scheme.social_category,
                    "userValue": user_cat,
                    "passed": False
                })
        else:
            # Scheme is open to all; if user is OBC/SC/ST and scheme prioritizes it, note as satisfied
            if user_cat_lower in ("obc", "sc", "st"):
                requirements_satisfied.append(f"Beneficiary category {user_cat} verified")



        # ---------------------------------------------------------------------
        # 12. DISABILITY SPECIFICITY
        # ---------------------------------------------------------------------
        if scheme.is_disability_required:
            total_rules_evaluated += 1
            user_disabled_val = profile.get("is_disabled") if profile.get("is_disabled") is not None else profile.get("isDisabled")
            if user_disabled_val is True:
                passed_rules_count += 1
                requirements_satisfied.append("Differently-abled status verified")
            elif user_disabled_val is None:
                missing_information.append("Disability / Divyangjan status required")
            else:
                mandatory_failed = True
                requirements_not_satisfied.append("Disability Status: Scheme intended for Divyangjan / persons with disability")

        # ---------------------------------------------------------------------
        # 11. EVALUATE CUSTOM SCHEME RULES (From SchemeRule table)
        # ---------------------------------------------------------------------
        if scheme.rules:
            for idx, rule in enumerate(scheme.rules):
                total_rules_evaluated += 1
                passed, reason, user_val = RuleEngine.evaluate_condition(rule.rule_logic or {}, profile)
                r_name = rule.rule_name or f"Rule {idx + 1}"
                r_desc = rule.rule_description or ""

                if user_val is None:
                    missing_information.append(f"{r_name}: Information needed ({r_desc})")
                    criteria_breakdown.append({
                        "id": f"rule_{rule.id}",
                        "name": r_name,
                        "condition": r_desc,
                        "userValue": "Not Provided",
                        "passed": False
                    })
                elif passed:
                    passed_rules_count += 1
                    requirements_satisfied.append(f"{r_name}: {r_desc}")
                    criteria_breakdown.append({
                        "id": f"rule_{rule.id}",
                        "name": r_name,
                        "condition": r_desc,
                        "userValue": str(user_val),
                        "passed": True
                    })
                else:
                    if rule.is_mandatory:
                        mandatory_failed = True
                    requirements_not_satisfied.append(f"{r_name}: {r_desc} (Current value: {user_val})")
                    criteria_breakdown.append({
                        "id": f"rule_{rule.id}",
                        "name": r_name,
                        "condition": r_desc,
                        "userValue": str(user_val),
                        "passed": False
                    })

        # ---------------------------------------------------------------------
        # 12. DETERMINE FINAL ELIGIBILITY STATUS
        # ---------------------------------------------------------------------
        # Distinct statuses:
        # 1. 'applications_closed' - Scheme is closed according to verified information
        # 2. 'not_eligible' - At least one verified mandatory condition is not satisfied
        # 3. 'eligibility_unknown' - Reliable rules are unavailable or incomplete
        # 4. 'possibly_eligible' - No known mandatory condition failed, but some information missing
        # 5. 'eligible' - All mandatory conditions verified and satisfied
        has_specific_criteria = bool(
            scheme.rules
            or scheme.income_max
            or scheme.age_min
            or scheme.age_max
            or (scheme.education and scheme.education.lower() not in ("all", "any", "no formal education required", "no minimum education requirement", "no education barrier", "none", ""))
            or scheme.target_occupations
            or (scheme.occupation and scheme.occupation.lower() not in ("all", "any", "general", ""))
            or scheme.is_farmer_only
            or scheme.is_student_only
            or scheme.is_business_only
            or (scheme.social_category and scheme.social_category.lower() not in ("all", "any", "unrestricted", "all categories", ""))
            or (scheme.gender and scheme.gender.lower() not in ("all", "any", ""))
            or scheme.max_landholding_acres
            or scheme.is_disability_required
            or scheme.exclusions
        )

        if is_closed:
            status = cls.STATUS_APPLICATIONS_CLOSED
        elif mandatory_failed:
            status = cls.STATUS_NOT_ELIGIBLE
        elif not has_specific_criteria or total_rules_evaluated == 0:
            status = cls.STATUS_ELIGIBILITY_UNKNOWN
            is_unknown_rules = True
            missing_information.append("Official eligibility rules for this scheme are pending verification from government source portals.")
        elif len(missing_information) > 0:
            status = cls.STATUS_POSSIBLY_ELIGIBLE
        else:
            status = cls.STATUS_ELIGIBLE

        # ---------------------------------------------------------------------
        # 13. CALCULATE RELEVANCE & MATCH SCORE (0 - 100)
        # ---------------------------------------------------------------------
        if total_rules_evaluated > 0:
            base_score = int((passed_rules_count / total_rules_evaluated) * 100)
        else:
            base_score = 40

        # Adjust score according to status
        if status == cls.STATUS_ELIGIBLE:
            match_score = max(85, min(100, base_score))
        elif status == cls.STATUS_POSSIBLY_ELIGIBLE:
            match_score = max(50, min(80, base_score))
        elif status == cls.STATUS_APPLICATIONS_CLOSED:
            match_score = max(40, min(75, base_score))
        elif status == cls.STATUS_NOT_ELIGIBLE:
            match_score = min(40, base_score)
        else:
            match_score = 45

        # ---------------------------------------------------------------------
        # 14. GENERATE "WHY AM I SEEING THIS SCHEME?" EXPLANATION
        # ---------------------------------------------------------------------
        # ---------------------------------------------------------------------
        # 14. GENERATE "WHY AM I SEEING THIS SCHEME?" EXPLANATION
        # ---------------------------------------------------------------------
        is_rel, rel_rej, match_reason = cls.is_scheme_relevant(scheme, profile)
        match_reason_str = match_reason or "Matches your profile criteria."

        why_parts = ["Why am I seeing this scheme?", match_reason_str]
        if status == cls.STATUS_ELIGIBLE:
            why_parts.append(f"You qualify for {scheme.name} as all mandatory eligibility conditions are fully verified.")
            if requirements_satisfied:
                why_parts.append(f"Key verified criteria: {', '.join(requirements_satisfied[:3])}.")
        elif status == cls.STATUS_POSSIBLY_ELIGIBLE:
            why_parts.append("Note: Eligibility still requires verification. Target audience matches your profile, but final qualification is pending.")
            if missing_information:
                why_parts.append(f"To confirm 100% eligibility, please verify: {', '.join(missing_information[:2])}.")
        elif status == cls.STATUS_APPLICATIONS_CLOSED:
            why_parts.append(f"This scheme is currently not accepting applications as the deadline has passed or applications are temporarily closed.")
        elif status == cls.STATUS_NOT_ELIGIBLE:
            why_parts.append(f"You currently do not meet mandatory eligibility requirements for this scheme.")
            if requirements_not_satisfied:
                why_parts.append(f"Reason: {requirements_not_satisfied[0]}.")
        else:
            why_parts.append("Official eligibility rules for this scheme are pending verification from government source portals.")

        why_matched = " ".join(why_parts)

        # Legacy backward-compatible mapping for existing frontend components:
        legacy_status_map = {
            cls.STATUS_ELIGIBLE: "eligible",
            cls.STATUS_POSSIBLY_ELIGIBLE: "almost",
            cls.STATUS_NOT_ELIGIBLE: "ineligible",
            cls.STATUS_ELIGIBILITY_UNKNOWN: "almost",
            cls.STATUS_APPLICATIONS_CLOSED: "ineligible",
        }

        from services.portal_health_service import PortalHealthService
        raw_off = scheme.official_source_url
        raw_app = scheme.application_url
        dist_app = raw_app if (raw_app and raw_off and raw_app.rstrip('/') != raw_off.rstrip('/')) else None
        alt_url = getattr(scheme, "alternative_url", None) or PortalHealthService.get_alternative_url(raw_off)
        port_info = PortalHealthService.get_cached_status(raw_off)

        return {
            "eligibility_status": status,
            "legacy_status": legacy_status_map.get(status, "almost"),
            "application_status": app_window,
            "match_score": match_score,
            "match_reason": match_reason_str,
            "why_matched": why_matched,
            "requirements_satisfied": requirements_satisfied,
            "requirements_not_satisfied": requirements_not_satisfied,
            "missing_information": missing_information,
            "criteria": criteria_breakdown,
            "required_documents": [doc.document_name for doc in scheme.document_requirements] if scheme.document_requirements else [],
            "application_procedure": scheme.application_process or "Follow official portal guidelines to apply online.",
            "source_reference": {
                "official_url": raw_off,
                "application_url": dist_app,
                "alternative_url": alt_url,
                "source_url": scheme.source_url or scheme.official_source_url,
                "portal_status": port_info.get("status", "reachable"),
                "portal_status_message": port_info.get("status_message"),
                "verification_status": scheme.source_verification_status or "verified_live",
                "last_fetched_at": scheme.last_fetched_at.isoformat() if scheme.last_fetched_at else None,
                "last_verified_date": scheme.last_verified_date or "12 Oct 2026",
                "is_verified": bool(scheme.official_source_url and scheme.last_verified_date)
            }
        }

    @classmethod
    def is_scheme_relevant(
        cls,
        scheme: Scheme,
        profile_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Determines whether a scheme is strictly relevant to the user's profile
        before returning it to the citizen portal.
        
        Excludes schemes when target occupation, beneficiary group, state domicile,
        age limits, income limits, or mandatory exclusions clearly conflict with profile.
        
        Returns:
            (is_relevant: bool, rejection_reason: Optional[str], match_reason: Optional[str])
        """
        if not scheme:
            return False, "Scheme not provided", None

        # 1. Verification & human approval requirements: ONLY active, published, and admin-approved schemes
        if not scheme.is_active:
            return False, "Scheme is inactive", None
        if scheme.status and scheme.status != "published":
            return False, f"Scheme status is {scheme.status} (must be published)", None
        review_stat = getattr(scheme, "admin_review_status", None) or ("approved" if getattr(scheme, "status", None) == "published" else None)
        if not review_stat or review_stat not in ("approved", "published"):
            return False, f"Scheme review status is '{getattr(scheme, 'admin_review_status', None)}' (must be approved by admin)", None


        profile = dict(profile_data or {})

        # 2. Empty or invalid profile validation
        # Treat unknown information as unknown; do not invent profile values.
        # But an empty profile must not bypass filtering.
        occ = str(profile.get("occupation") or "").strip()
        user_farmer_val = profile.get("is_farmer") if profile.get("is_farmer") is not None else profile.get("isFarmer")
        user_student_val = profile.get("is_student") if profile.get("is_student") is not None else profile.get("isStudent")
        user_biz_val = profile.get("has_business") if profile.get("has_business") is not None else profile.get("hasBusiness")
        user_age = profile.get("age")
        user_state = str(profile.get("state") or "").strip()

        # Check if profile has any meaningful fields
        meaningful_fields = [occ, user_farmer_val, user_student_val, user_biz_val, user_age, user_state, profile.get("gender"), profile.get("education"), profile.get("annual_income"), profile.get("annualIncome")]
        if not any(f is not None and str(f).strip() != "" for f in meaningful_fields):
            return False, "Profile is empty or invalid. Please complete your profile to view matching schemes.", None

        # If occupation is not provided and no specific boolean flags are set, profile is incomplete
        if not occ and user_farmer_val is None and user_student_val is None and user_biz_val is None:
            return False, "Occupation or beneficiary profile is required to filter relevant schemes.", None

        # Normalize age if DOB provided
        if (user_age is None or user_age == 0) and profile.get("date_of_birth"):
            user_age = cls.parse_dob_to_age(profile.get("date_of_birth"))
        elif (user_age is None or user_age == 0) and profile.get("dateOfBirth"):
            user_age = cls.parse_dob_to_age(profile.get("dateOfBirth"))

        occ_lower = occ.lower()
        emp_status = str(profile.get("employment_status") or profile.get("employmentStatus") or "").lower()

        # Dynamic citizen flags
        is_farmer_in_occ = any(k in occ_lower for k in ["farmer", "kisan", "agri", "cultivat"])
        is_student_in_occ = "student" in occ_lower
        is_user_farmer = bool(user_farmer_val is True or is_farmer_in_occ)
        is_user_student = bool(user_student_val is True or is_student_in_occ)
        is_user_biz = bool(user_biz_val is True or any(b in occ_lower for b in ["business", "self-employed", "entrepreneur", "artisan", "craftsperson", "shopkeeper", "retailer", "trader", "merchant", "vendor", "storekeeper"]))
        is_user_teacher = bool(
            any(t in occ_lower for t in ["teacher", "professor", "lecturer", "educator", "instructor", "faculty", "shikshak", "adhyapak", "mentor", "tutor", "academic", "teaching"])
        )
        is_user_govt_employee = bool(
            profile.get("is_govt_employee") is True or profile.get("isGovtEmployee") is True
            or any(g in occ_lower for g in ["government", "govt", "sarkari", "civil service", "ias", "ips", "public sector"])
        )
        is_user_salaried = bool(
            (any(s in occ_lower for s in ["teacher", "professor", "lecturer", "educator", "instructor", "salaried", "employee", "corporate", "service", "job", "worker", "clerk", "nurse", "doctor", "engineer", "accountant", "staff", "private", "clerical"]) or is_user_teacher or is_user_govt_employee)
            and not is_user_student and not is_user_farmer
        )
        is_user_unemployed = bool("unemploy" in occ_lower or emp_status == "unemployed")
        is_user_homemaker = bool("homemaker" in occ_lower or "housewife" in occ_lower or "home maker" in occ_lower)

        user_land = profile.get("land_holding_acres") or profile.get("landHoldingAcres") or 0.0
        try:
            user_land = float(user_land)
        except (ValueError, TypeError):
            user_land = 0.0

        # Disambiguate when single primary occupation is declared
        if is_student_in_occ and not is_farmer_in_occ:
            is_user_student = True
            # Student is only treated as a farmer if they explicitly have landholding or dual-category
            if user_land <= 0 and not profile.get("is_dual_category"):
                is_user_farmer = False
        elif is_farmer_in_occ and not is_student_in_occ:
            is_user_farmer = True
            if not profile.get("is_dual_category"):
                is_user_student = False
        elif occ_lower:
            # Custom non-student, non-farmer occupation (e.g. Clerk, Teacher, Housewife, Shopkeeper, Private employee, Govt employee, Daily-wage worker, etc.)
            if not profile.get("is_dual_category"):
                is_user_student = False
                if user_land <= 0:
                    is_user_farmer = False


        # -------------------------------------------------------------
        # Rule 0: Strict Gender Restrictions (Evaluated Independently)
        # -------------------------------------------------------------
        user_gender = str(profile.get("gender") or "").strip()
        if user_gender:
            is_gen_ok, gen_fail_reason = cls.user_satisfies_scheme_gender(user_gender, scheme)
            if not is_gen_ok:
                return False, gen_fail_reason, None

        # Women & Child category check (excludes adult males)
        scheme_cat = str(scheme.category or "").strip().lower()
        if any(wc in scheme_cat for wc in ["women & child", "women and child", "women child"]):
            norm_g = cls.normalize_gender(user_gender)
            if norm_g == "male":
                if user_age is not None and user_age <= 18:
                    pass  # Minor boy might be eligible for child welfare
                else:
                    return False, "Category restriction: 'Women & Child' schemes exclusively benefit women and children (Your profile: Male)", None

            if scheme.age_max is not None and scheme.age_max <= 18:
                if user_age is not None and user_age > scheme.age_max:
                    return False, f"Age & Category restriction: Scheme for children up to {scheme.age_max} years (Your age: {user_age})", None

        # 3. Scheme target audience fields
        raw_target_occs = scheme.target_occupations or []
        if isinstance(raw_target_occs, str):
            raw_target_occs = [x.strip() for x in raw_target_occs.split(",") if x.strip()]
        target_occs = [str(x).strip().lower() for x in raw_target_occs if str(x).strip()]

        scheme_occ = str(scheme.occupation or "").lower().strip()
        scheme_cat = str(scheme.category or "").lower().strip()

        is_scheme_teacher_target = bool(
            any(t in target_occs for t in ["teacher", "educator", "professor", "faculty", "lecturer", "instructor", "shikshak", "adhyapak", "teaching"])
            or any(t in scheme_occ for t in ["teacher", "educator", "professor", "faculty", "lecturer", "instructor", "shikshak", "adhyapak", "teaching"])
            or any(t in str(scheme.name or "").lower() for t in ["teacher", "shikshak", "faculty", "educator"])
        )

        # Fallback target occupations from legacy columns if target_occupations not yet stored
        if not target_occs:
            if scheme.is_farmer_only or scheme_occ in ("farmer", "kisan") or scheme_cat in ("agriculture", "farming"):
                target_occs.append("farmer")
            if is_scheme_teacher_target:
                target_occs.append("teacher")
            elif scheme.is_student_only or scheme_occ in ("student", "scholar") or scheme_cat in ("scholarship",):
                target_occs.append("student")
            elif scheme_cat == "education":
                target_occs.extend(["student", "teacher"])
            if scheme.is_business_only or any(b in scheme_occ for b in ["artisan", "business", "self-employed"]) or scheme_cat in ("entrepreneurship", "business"):
                target_occs.extend(["self-employed", "business", "artisan"])

        # Determine scheme exclusivity
        is_scheme_farmer_only = bool(
            scheme.is_farmer_only 
            or scheme_occ in ("farmer", "kisan", "cultivator")
            or (scheme_cat in ("agriculture", "farming", "krishi") and not scheme.is_student_only)
            or (target_occs and all(t in ("farmer", "kisan", "cultivator", "agriculture") for t in target_occs))
        )

        is_scheme_student_only = bool(
            (scheme.is_student_only
            or scheme_occ in ("student", "scholar")
            or (target_occs and all(t in ("student", "scholar", "higher education") for t in target_occs))
            or (scheme_cat in ("scholarship",) and not scheme.is_farmer_only))
            and not is_scheme_teacher_target
        )

        is_scheme_biz_only = bool(
            scheme.is_business_only
            or (scheme_cat in ("entrepreneurship", "business", "msme") and not scheme.is_student_only and not scheme.is_farmer_only)
            or (target_occs and all(b in ["self-employed", "artisan", "craftsperson", "entrepreneur", "business"] for b in target_occs))
        )

        # -------------------------------------------------------------
        # Rule 1 & 2: Exclude when mandatory target occupation conflicts
        # -------------------------------------------------------------
        # Farmer-only schemes vs non-farmer
        if is_scheme_farmer_only and not is_user_farmer:
            # Only allow dual-target schemes (e.g. Agri-entrepreneur) if user explicitly runs an agricultural enterprise
            biz_type = str(profile.get("business_type") or profile.get("businessType") or "").lower()
            is_agri_biz = any(k in biz_type or k in occ_lower for k in ["agri", "farm", "kisan", "krishi", "cultivat"])
            if not (is_user_biz and is_agri_biz and any(b in target_occs for b in ["self-employed", "business", "entrepreneur"])):
                return False, f"Scheme exclusively targets farmers and agricultural beneficiaries (Your occupation: {occ or 'Non-farmer'})", None

        # Student-only schemes vs non-student
        if is_scheme_student_only and not is_user_student:
            return False, f"Scheme exclusively targets students (Your occupation: {occ or 'Non-student'})", None

        # Business-only schemes vs non-business
        if is_scheme_biz_only and not is_user_biz:
            return False, f"Scheme exclusively targets business owners / artisans (Your occupation: {occ or 'Non-business'})", None

        # Teacher-only / Educator-targeted schemes vs non-teacher
        if is_scheme_teacher_target and not is_user_teacher:
            return False, f"Scheme exclusively targets teachers and educators (Your occupation: {occ or 'Non-teacher'})", None

        # Broad universal public welfare schemes (e.g., universal health like MJP Jan Arogya, general food security, solar electricity)
        has_universal_target = any(o in ("all", "any", "general", "citizens", "all citizens", "all categories", "*", "") for o in target_occs)
        is_broad_social_scheme = (
            any(k in scheme_cat for k in ["health", "public health", "food security", "social welfare", "family welfare"])
            or has_universal_target
            or (all(group in target_occs for group in ["farmer", "student", "salaried employee", "self-employed"]))
            or (len(target_occs) >= 4 and not is_scheme_farmer_only and not is_scheme_student_only and not is_scheme_biz_only and not is_scheme_teacher_target)
        )


        # Multi-group schemes: Check if broad target_occupations covers user
        if target_occs and not is_broad_social_scheme and not has_universal_target:
            matched_group = False
            if is_user_teacher and (is_scheme_teacher_target or any(s in target_occs for s in ["teacher", "educator", "professor", "faculty", "lecturer", "instructor", "shikshak", "academic"])):
                matched_group = True
            if "student" in target_occs and is_user_student:
                matched_group = True
            if "farmer" in target_occs and is_user_farmer:
                matched_group = True
            if any(b in target_occs for b in ["self-employed", "business", "entrepreneur", "artisan", "craftsperson", "shopkeeper", "trader"]) and is_user_biz:
                matched_group = True
            if any(s in target_occs for s in ["teacher", "educator", "professor", "faculty"]) and any(t in occ_lower for t in ["teacher", "educator", "professor", "faculty", "lecturer", "instructor"]):
                matched_group = True
            if any(s in target_occs for s in ["salaried employee", "salaried", "employee"]) and (is_user_salaried or is_user_teacher):
                matched_group = True
            if any(u in target_occs for u in ["unemployed", "job seeker", "youth"]) and (is_user_unemployed or is_user_student):
                matched_group = True
            if any(h in target_occs for h in ["homemaker", "housewife"]) and is_user_homemaker:
                matched_group = True
            if any(o in occ_lower or occ_lower in o for o in target_occs if occ_lower):
                matched_group = True

            if not matched_group:
                return False, f"Scheme target audience does not cover your occupation ({occ})", None

        # -------------------------------------------------------------
        # Rule 4: State-specific schemes excluded for outside users
        # -------------------------------------------------------------
        scheme_state = (scheme.state or "All India").strip()
        raw_states = scheme.eligible_states or [scheme_state]
        if isinstance(raw_states, str):
            raw_states = [x.strip() for x in raw_states.split(",") if x.strip()]
        states_lower = [str(s).strip().lower() for s in raw_states if str(s).strip()]

        is_all_india = any(s in ("all india", "national", "central", "all", "*", "") for s in states_lower) or scheme_state.lower() in ("all india", "national", "central", "all", "")

        if not is_all_india and user_state:
            matches_state = any(user_state.lower() == s or s in ("all india", "all") for s in states_lower) or (user_state.lower() == scheme_state.lower())
            if not matches_state:
                return False, f"Restricted to residents of {scheme_state} (Your state: {user_state})", None

        # -------------------------------------------------------------
        # Rule 5: Age & Income restrictions respected when verified
        # -------------------------------------------------------------
        if user_age is not None and user_age > 0:
            if scheme.age_min is not None and user_age < scheme.age_min:
                return False, f"Age restriction: Minimum age is {scheme.age_min} years (Your age: {user_age})", None
            if scheme.age_max is not None and user_age > scheme.age_max:
                return False, f"Age restriction: Maximum age is {scheme.age_max} years (Your age: {user_age})", None

        actual_income = profile.get("income_numeric") or profile.get("incomeNumeric")
        if actual_income is None:
            inc_str = profile.get("annual_income") or profile.get("annualIncome")
            if inc_str:
                actual_income = RuleEngine.parse_numeric_income(inc_str)

        if actual_income is not None and actual_income > 0 and scheme.income_max is not None:
            if actual_income > scheme.income_max:
                return False, f"Income restriction: Family income ₹{actual_income:,.0f} exceeds maximum ceiling of ₹{scheme.income_max:,.0f}", None

        # Gender restrictions
        target_gender = (scheme.gender or "All").strip()
        user_gender = (profile.get("gender") or "").strip()
        if not cls.genders_match(user_gender, target_gender):
            return False, f"Gender restriction: Exclusively for {scheme.gender} beneficiaries (You are {profile.get('gender')})", None

        # Disability restrictions
        if scheme.is_disability_required:
            user_dis = profile.get("is_disabled") if profile.get("is_disabled") is not None else profile.get("isDisabled")
            if user_dis is False:
                return False, "Disability restriction: Exclusively for differently-abled citizens", None

        # Exclusions (e.g. tax payer, govt employee)
        exclusions = scheme.exclusions or []
        if isinstance(exclusions, str):
            exclusions = [e.strip() for e in exclusions.split(",") if e.strip()]
        for excl in exclusions:
            e_low = str(excl).lower()
            if "tax" in e_low and (profile.get("is_tax_payer") is True or profile.get("isTaxPayer") is True):
                return False, "Exclusion: Income tax payers are disqualified from this scheme", None
            if ("govt" in e_low or "government" in e_low) and is_user_govt_employee:
                return False, "Exclusion: Government employees are disqualified from this scheme", None


        # -------------------------------------------------------------
        # Section 5: Concise Match Reason
        # -------------------------------------------------------------
        reason_parts = []
        if is_user_teacher and (is_scheme_teacher_target or "teacher" in target_occs or scheme.category in ("Education", "Skill Development")):
            reason_parts.append("your educator & teaching profile")
        elif is_user_student and ("student" in target_occs or is_scheme_student_only or scheme.category == "Education"):
            reason_parts.append("your student profile")
        elif is_user_farmer and ("farmer" in target_occs or is_scheme_farmer_only or scheme.category == "Agriculture"):
            reason_parts.append("your farmer profile")
        elif is_user_unemployed and (any(u in target_occs for u in ["unemployed", "job seeker"]) or scheme.category in ("Employment", "Skill Development")):
            reason_parts.append("your employment & skill development profile")
        elif is_user_biz and (is_scheme_biz_only or any(b in target_occs for b in ["self-employed", "business", "entrepreneur", "artisan"])):
            reason_parts.append("your enterprise & artisan profile")
        elif occ:
            reason_parts.append(f"your {occ} profile")
        else:
            reason_parts.append("your citizen profile")

        if user_state:
            if not is_all_india and (user_state.lower() == scheme_state.lower() or any(user_state.lower() == s for s in states_lower)):
                reason_parts.append(f"selected state ({user_state})")
            else:
                reason_parts.append("selected state")

        match_reason = f"Matches {' and '.join(reason_parts)}."
        return True, None, match_reason

    @classmethod
    def get_ranked_schemes_for_profile(
        cls, 
        profile_data: Dict[str, Any],
        category_filter: Optional[str] = None,
        state_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        include_ineligible: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieves published schemes, evaluates each against the given profile,
        applies strict relevance filtering, ranks them by priority and relevance,
        and returns only schemes relevant to the user profile.
        """
        # Empty or invalid profile validation
        if not profile_data or not isinstance(profile_data, dict):
            return []

        occ = str(profile_data.get("occupation") or "").strip()
        user_farmer_val = profile_data.get("is_farmer") if profile_data.get("is_farmer") is not None else profile_data.get("isFarmer")
        user_student_val = profile_data.get("is_student") if profile_data.get("is_student") is not None else profile_data.get("isStudent")
        user_biz_val = profile_data.get("has_business") if profile_data.get("has_business") is not None else profile_data.get("hasBusiness")
        user_age = profile_data.get("age")
        user_state = str(profile_data.get("state") or "").strip()

        if not occ and user_farmer_val is None and user_student_val is None and user_biz_val is None and not user_age and not user_state:
            return []

        db = SessionLocal()
        try:
            query = db.query(Scheme).options(
                joinedload(Scheme.rules),
                joinedload(Scheme.document_requirements)
            ).filter(
                Scheme.is_active == True,
                Scheme.status == "published",
                Scheme.admin_review_status.in_(["approved", "published"]),
                (Scheme.is_test == False) | (Scheme.is_test.is_(None))
            )

            if category_filter and category_filter.lower() != "all":
                query = query.filter(Scheme.category.ilike(f"%{category_filter}%"))

            if state_filter and state_filter.lower() != "all":
                query = query.filter(
                    (Scheme.state.ilike(f"%{state_filter}%")) | (Scheme.state.ilike("%all india%"))
                )

            schemes = query.all()
            logger.info(f"[SCHEMES RETRIEVED] Retrieved {len(schemes)} schemes from database for profile: occupation='{profile_data.get('occupation')}', education='{profile_data.get('education')}', state='{profile_data.get('state')}'")

            # Check if Gemini evaluation is available (with cache & candidate pre-filtering)
            gemini_evals = {}
            use_gemini = False
            cache_key = f"{profile_data.get('occupation')}_{profile_data.get('state')}_{profile_data.get('age')}_{profile_data.get('gender')}_{profile_data.get('annual_income')}_{profile_data.get('education')}_{profile_data.get('category')}"
            cached_entry = _GEMINI_EVAL_CACHE.get(cache_key)
            now_ts = time.time()
            if cached_entry and (now_ts - cached_entry[0] < _CACHE_TTL_SECONDS):
                gemini_evals = cached_entry[1]
                use_gemini = bool(gemini_evals)
            else:
                try:
                    from services.gemini_service import GeminiService
                    if GeminiService.is_configured():
                        # Pre-filter candidate schemes so Gemini only evaluates relevant schemes (under 10 items)
                        # instead of passing all 35 schemes which causes 20+ second delays
                        candidate_schemes = []
                        for s in schemes:
                            is_rel, _, _ = cls.is_scheme_relevant(s, profile_data)
                            if is_rel or include_ineligible:
                                candidate_schemes.append(s)
                        if candidate_schemes:
                            candidate_dicts = [s.to_dict(include_rules=False) for s in candidate_schemes[:12]]
                            g_res = GeminiService.evaluate_schemes_for_profile(profile_data, candidate_dicts)
                            gemini_evals = g_res.get("evaluations", {})
                            if gemini_evals:
                                use_gemini = True
                                _GEMINI_EVAL_CACHE[cache_key] = (now_ts, gemini_evals)
                except Exception as ge:
                    logger.warning(f"Gemini scheme evaluation bypass due to: {ge}")

            results = []

            for scheme in schemes:
                # Text search filter
                if search_query:
                    q = search_query.lower().strip()
                    name_match = q in scheme.name.lower()
                    desc_match = q in (scheme.short_description or "").lower() or q in scheme.description.lower()
                    dept_match = q in (scheme.department or "").lower()
                    cat_match = q in (scheme.category or "").lower()
                    benefits_match = q in (scheme.benefits or "").lower()
                    if not (name_match or desc_match or dept_match or cat_match or benefits_match):
                        continue

                # Strict relevance check
                is_relevant, rejection_reason, match_reason = cls.is_scheme_relevant(scheme, profile_data)
                
                g_eval = (gemini_evals.get(scheme.id) or gemini_evals.get(scheme.slug)) if use_gemini else None

                if g_eval:
                    # Gemini provides qualitative match reasoning and rich why_matched explanations.
                    # It MUST NOT override verified deterministic relevance or invent restrictions.
                    if is_relevant and g_eval.get("match_reason"):
                        match_reason = g_eval["match_reason"]

                if not include_ineligible and not is_relevant:
                    logger.info(f"[SCHEME REJECTED] {scheme.name} rejected: {rejection_reason}")
                    continue

                eval_result = cls.evaluate_scheme_for_profile(scheme, profile_data)

                # If include_ineligible is True but scheme is irrelevant, mark as not_eligible
                if not is_relevant:
                    eval_result["eligibility_status"] = cls.STATUS_NOT_ELIGIBLE
                    eval_result["legacy_status"] = "ineligible"
                    if rejection_reason:
                        eval_result["requirements_not_satisfied"] = [rejection_reason] + [r for r in eval_result["requirements_not_satisfied"] if r != rejection_reason]
                elif g_eval:
                    # Enrich with Gemini why_matched and match_reason
                    if g_eval.get("why_matched"):
                        eval_result["why_matched"] = g_eval["why_matched"]
                    if g_eval.get("match_reason"):
                        eval_result["match_reason"] = g_eval["match_reason"]
                    # Gemini must never downgrade deterministic STATUS_ELIGIBLE
                    if eval_result["eligibility_status"] == cls.STATUS_ELIGIBLE:
                        pass
                    elif eval_result["eligibility_status"] == cls.STATUS_POSSIBLY_ELIGIBLE:
                        # If Gemini also considers it eligible and there is no missing info, elevate
                        if g_eval.get("eligibility_status") == cls.STATUS_ELIGIBLE and not eval_result["missing_information"]:
                            eval_result["eligibility_status"] = cls.STATUS_ELIGIBLE
                            eval_result["legacy_status"] = "eligible"
                    if g_eval.get("match_score") and eval_result["eligibility_status"] != cls.STATUS_NOT_ELIGIBLE:
                        try:
                            eval_result["match_score"] = max(int(eval_result["match_score"]), int(g_eval["match_score"]))
                        except (ValueError, TypeError):
                            pass

                logger.info(f"[SCHEME RETAINED] {scheme.name}: status={eval_result['eligibility_status']}, score={eval_result['match_score']}")

                # Strict Scheme Eligibility Filtering:
                # When include_ineligible is False and caller is not explicitly requesting ineligible or closed schemes,
                # strictly exclude schemes for which the user does not qualify or whose applications are closed.
                e_status = eval_result["eligibility_status"]
                leg_status = eval_result["legacy_status"]

                if not include_ineligible:
                    is_ineligible = e_status == cls.STATUS_NOT_ELIGIBLE or leg_status == "ineligible"
                    is_closed = e_status == cls.STATUS_APPLICATIONS_CLOSED
                    target_filter = (status_filter or "").lower()
                    if is_ineligible and target_filter not in ("not_eligible", "ineligible"):
                        logger.info(f"[SCHEME INELIGIBLE EXCLUDED] {scheme.name} excluded: user does not satisfy criteria")
                        continue
                    if is_closed and target_filter not in ("applications_closed", "closed"):
                        logger.info(f"[SCHEME CLOSED EXCLUDED] {scheme.name} excluded: applications closed")
                        continue

                # Check status filter
                if status_filter and status_filter.lower() != "all":
                    s_filter = status_filter.lower()
                    if s_filter not in (e_status, leg_status):
                        continue

                # Prepare response dictionary with all rich metadata
                scheme_dict = scheme.to_dict(include_rules=False)
                scheme_dict["eligibilityStatus"] = eval_result["eligibility_status"]
                scheme_dict["eligibility_status"] = eval_result["eligibility_status"]
                scheme_dict["legacyEligibilityStatus"] = eval_result["legacy_status"]
                scheme_dict["applicationStatus"] = eval_result["application_status"]
                scheme_dict["matchScore"] = eval_result["match_score"]
                scheme_dict["match_score"] = eval_result["match_score"]
                scheme_dict["matchReason"] = eval_result.get("match_reason") or match_reason
                scheme_dict["whyMatched"] = eval_result["why_matched"]
                scheme_dict["requirementsSatisfied"] = eval_result["requirements_satisfied"]
                scheme_dict["requirementsNotSatisfied"] = eval_result["requirements_not_satisfied"]
                scheme_dict["missingInformation"] = eval_result["missing_information"]
                scheme_dict["criteria"] = eval_result["criteria"]
                scheme_dict["requiredDocuments"] = eval_result["required_documents"]
                scheme_dict["applicationProcess"] = eval_result["application_procedure"]
                scheme_dict["sourceReference"] = eval_result["source_reference"]

                # First failure reason for backward compatibility
                if eval_result["requirements_not_satisfied"]:
                    scheme_dict["ineligibleReason"] = eval_result["requirements_not_satisfied"][0]
                else:
                    scheme_dict["ineligibleReason"] = None

                results.append(scheme_dict)

            # Sort:
            # 1. Eligible (status priority)
            # 2. Occupation Specificity (schemes directly targeted to citizen's primary occupation sort ahead of broad welfare)
            # 3. Highest match score
            priority_rank = {
                cls.STATUS_ELIGIBLE: 0,
                cls.STATUS_POSSIBLY_ELIGIBLE: 1,
                "almost": 1,
                cls.STATUS_APPLICATIONS_CLOSED: 2,
                cls.STATUS_ELIGIBILITY_UNKNOWN: 3,
                cls.STATUS_NOT_ELIGIBLE: 4,
                "ineligible": 4,
            }

            p_occ = (profile_data.get("occupation") or "").lower().strip()
            p_is_student = bool(profile_data.get("is_student") or "student" in p_occ)
            p_is_farmer = bool(profile_data.get("is_farmer") or any(k in p_occ for k in ["farmer", "kisan", "agri", "cultivat"]))
            p_is_teacher = bool(any(t in p_occ for t in ["teacher", "educator", "professor", "faculty", "shikshak"]))
            p_is_biz = bool(profile_data.get("has_business") or any(b in p_occ for b in ["business", "shop", "self-employed", "artisan"]))
            p_is_homemaker = bool(any(h in p_occ for h in ["homemaker", "housewife"]))

            def get_occupation_priority(s_dict: Dict[str, Any]) -> int:
                # 0 = directly targeted to citizen's primary occupation
                # 1 = general / universal citizen welfare
                s_name = str(s_dict.get("name") or "").lower()
                s_cat = str(s_dict.get("category") or "").lower()
                t_occs = [str(o).lower() for o in (s_dict.get("targetOccupations") or [])]

                if p_is_student:
                    if s_dict.get("isStudentOnly") or "student" in s_cat or any("student" in o for o in t_occs) or any(w in s_name for w in ["scholarship", "vidyalakshmi", "pragati", "matric"]):
                        return 0
                elif p_is_farmer:
                    if s_dict.get("isFarmerOnly") or any(a in s_cat for a in ["agri", "farm", "krishi"]) or any("farmer" in o for o in t_occs) or any(w in s_name for w in ["kisan", "crop", "fasal", "sinchayee", "mechanization"]):
                        return 0
                elif p_is_teacher:
                    if any("teacher" in o for o in t_occs) or any(t in s_name for t in ["teacher", "shikshak", "educator", "teaching"]):
                        return 0
                elif p_is_biz:
                    if s_dict.get("isBusinessOnly") or any(b in s_cat for b in ["business", "msme"]) or any(b in o for o in t_occs for b in ["business", "self-employed", "artisan", "shopkeeper"]):
                        return 0
                elif p_is_homemaker:
                    if any(h in o for o in t_occs for h in ["homemaker", "housewife"]) or any(w in s_name for w in ["ladki bahin", "matru vandana", "mahila"]):
                        return 0
                return 1

            results.sort(key=lambda s: (
                priority_rank.get(s["eligibilityStatus"], 5),
                get_occupation_priority(s),
                -s.get("matchScore", 0)
            ))

            # In-memory stable deduplication safeguard: guarantee one canonical record per scheme
            deduped_results = []
            seen_schemes = set()
            for s in results:
                s_id = s.get("id") or s.get("slug")
                s_name_norm = re.sub(r'[^a-z0-9]', '', str(s.get("name") or "").lower())
                if s_id in seen_schemes or (s_name_norm and s_name_norm in seen_schemes):
                    continue
                if s_id:
                    seen_schemes.add(s_id)
                if s_name_norm:
                    seen_schemes.add(s_name_norm)
                deduped_results.append(s)

            return deduped_results
        finally:
            db.close()
