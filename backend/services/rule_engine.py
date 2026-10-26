import re
from typing import Dict, Any, List, Tuple

class RuleEngine:
    """
    Deterministic Eligibility Rule Engine.
    Evaluates citizen profile attributes against structured scheme rules.
    The LLM NEVER determines eligibility alone.
    """

    OPERATORS = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
        "==": lambda a, b: a == b,
        "eq": lambda a, b: str(a).strip().lower() == str(b).strip().lower(),
        "neq": lambda a, b: str(a).strip().lower() != str(b).strip().lower(),
        "in": lambda a, b: (
            any(str(x).strip().lower() in str(a).strip().lower() or str(a).strip().lower() in str(x).strip().lower() for x in b)
            if isinstance(b, list)
            else (str(b).strip().lower() in str(a).strip().lower() or str(a).strip().lower() in str(b).strip().lower())
        ),
        "not_in": lambda a, b: (
            not any(str(x).strip().lower() in str(a).strip().lower() for x in b)
            if isinstance(b, list)
            else str(b).strip().lower() not in str(a).strip().lower()
        ),
    }

    @staticmethod
    def parse_numeric_income(income_val: Any) -> float:
        """Helper to convert income strings like '< 1 Lakh' or '2.5 Lakh' into numbers."""
        if isinstance(income_val, (int, float)):
            return float(income_val)
        if not income_val:
            return 0.0

        val_str = str(income_val).lower().replace(",", "")
        
        # Check for Lakh
        if "lakh" in val_str:
            numbers = re.findall(r"[-+]?\d*\.\d+|\d+", val_str)
            if numbers:
                # If range like '1 - 3 Lakh', take upper or lower appropriately
                return float(numbers[-1]) * 100000.0
        
        numbers = re.findall(r"\d+", val_str)
        if numbers:
            return float(numbers[0])
            
        return 0.0

    @classmethod
    def evaluate_condition(cls, condition: Dict[str, Any], profile: Dict[str, Any]) -> Tuple[bool, str, Any]:
        """
        Evaluates a single condition dictionary against user profile.
        Returns (passed, explanation, user_value).
        """
        field = condition.get("field")
        op = condition.get("op")
        target_val = condition.get("value")

        user_val = profile.get(field)

        # Normalize special fields
        if field in ("annual_income", "annualIncome", "incomeNumeric", "income_numeric"):
            actual_numeric = profile.get("income_numeric") or profile.get("incomeNumeric")
            if actual_numeric is None:
                actual_numeric = cls.parse_numeric_income(profile.get("annual_income") or profile.get("annualIncome"))
            
            target_numeric = cls.parse_numeric_income(target_val)
            eval_fn = cls.OPERATORS.get(op)
            if eval_fn:
                try:
                    passed = eval_fn(actual_numeric, target_numeric)
                    reason = f"Annual Income ₹{actual_numeric:,.0f} {op} ₹{target_numeric:,.0f}"
                    return passed, reason, profile.get("annualIncome") or profile.get("annual_income") or f"₹{actual_numeric:,.0f}"
                except Exception as e:
                    return False, f"Income eval error: {e}", actual_numeric

        # Normalize gender
        if field in ("gender", "target_gender"):
            from services.eligibility_service import SchemeEligibilityService
            user_gender = str(profile.get("gender") or "").strip()
            target_gender = str(target_val or "All").strip()
            passed = SchemeEligibilityService.genders_match(user_gender, target_gender)
            user_disp = user_gender or "Unspecified"
            reason = f"Gender ({user_disp}) satisfies criteria ({target_gender})" if passed else f"Scheme is exclusively for {target_gender} beneficiaries (You are {user_disp})"
            return passed, reason, user_disp

        # Normalize state
        if field == "state":
            target_state = str(target_val).strip().lower()
            actual_state = str(user_val or "").strip().lower()
            if target_state in ("all india", "national", "all", "any"):
                return True, "Scheme applicable across All India", user_val or "All India"
            passed = target_state == actual_state
            return passed, f"State: {user_val} (Required: {target_val})", user_val

        # Normalize farmer status
        if field in ("is_farmer", "isFarmer"):
            user_farmer = profile.get("is_farmer") if profile.get("is_farmer") is not None else profile.get("isFarmer")
            occ = str(profile.get("occupation") or "").lower()
            actual_farmer = bool(user_farmer is True or "farmer" in occ or "agri" in occ or "kisan" in occ)
            expected = bool(target_val)
            passed = (actual_farmer == expected) if op in ("eq", "==") else actual_farmer
            reason = "Agricultural Farmer Status Verified" if passed else "Must be an active agricultural farmer"
            return passed, reason, "Farmer" if actual_farmer else (profile.get("occupation") or "Non-Farmer")

        # Normalize student status
        if field in ("is_student", "isStudent"):
            user_student = profile.get("is_student") if profile.get("is_student") is not None else profile.get("isStudent")
            occ = str(profile.get("occupation") or "").lower()
            actual_student = bool(user_student is True or "student" in occ)
            expected = bool(target_val)
            passed = (actual_student == expected) if op in ("eq", "==") else actual_student
            reason = "Student Enrollment Verified" if passed else "Requires active student enrollment"
            return passed, reason, "Student" if actual_student else (profile.get("occupation") or "Non-Student")

        # Normalize tax payer
        if field in ("is_tax_payer", "isTaxPayer"):
            actual_tax = bool(profile.get("is_tax_payer") or profile.get("isTaxPayer"))
            expected = bool(target_val)
            passed = (actual_tax == expected) if op in ("eq", "==") else not actual_tax
            reason = "Non-Taxpayer Status Verified" if passed else "Income tax payers are excluded"
            return passed, reason, "Taxpayer" if actual_tax else "Non-Taxpayer"

        # Normalize landholding
        if field in ("land_holding_acres", "landholdingAcres", "landHoldingAcres"):
            raw_land = profile.get("land_holding_acres") or profile.get("landholdingAcres") or profile.get("landHoldingAcres")
            if raw_land is None or raw_land == "":
                return False, "Landholding information required", None
            try:
                actual_acres = float(raw_land)
                target_acres = float(target_val)
                eval_fn = cls.OPERATORS.get(op)
                passed = eval_fn(actual_acres, target_acres) if eval_fn else (actual_acres <= target_acres)
                reason = f"Landholding {actual_acres} acres {op} {target_acres} acres"
                return passed, reason, f"{actual_acres} acres"
            except Exception:
                return False, "Invalid landholding number", raw_land

        # Normalize category
        if field in ("category", "social_category", "socialCategory"):
            user_cat = str(profile.get("category") or profile.get("social_category") or profile.get("socialCategory") or "General").strip().lower()
            user_gender = str(profile.get("gender") or "").strip().lower()
            occ_str = str(profile.get("occupation") or "").strip().lower()
            is_woman = (user_gender == "female" or "woman" in occ_str)

            if isinstance(target_val, list):
                target_cats = [str(x).strip().lower() for x in target_val]
            else:
                target_cats = [str(target_val).strip().lower()]

            if any(t in ("all", "any", "general, obc, sc, st") for t in target_cats):
                return True, "Open to all social categories", profile.get("category") or "General"

            passed = False
            for t in target_cats:
                if t in user_cat or user_cat in t:
                    passed = True
                    break
                if t in ("woman", "female") and is_woman:
                    passed = True
                    break

            if any(b in str(target_cats).lower() for b in ["bpl", "antyodaya", "ration"]):
                # If target mentions ration card or BPL, and citizen has low/moderate income
                actual_inc = profile.get("income_numeric") or profile.get("incomeNumeric")
                if actual_inc is None:
                    actual_inc = cls.parse_numeric_income(profile.get("annual_income") or profile.get("annualIncome"))
                if actual_inc is not None and actual_inc <= 800000:
                    passed = True
                    reason = f"Eligible under state health ration card income provisions (₹{actual_inc:,.0f} <= ₹8,00,000)"
                    user_disp = profile.get("category") or "General"
                    return passed, reason, user_disp

            reason = f"Category / Beneficiary matches {target_val}" if passed else f"Requires {target_val} category"
            user_disp = profile.get("category") or ("Female / Woman Entrepreneur" if is_woman else "General")
            return passed, reason, user_disp

        # Normalize education / qualification
        if field in ("education", "qualification"):
            user_edu = str(profile.get("education") or "").strip()
            if not user_edu:
                return False, "Education qualification required", None

            user_edu_lower = user_edu.lower()
            edu_rank = {
                "illiterate": 0, "none": 0,
                "primary": 1, "8th": 1,
                "10th": 2, "matric": 2, "ssc": 2,
                "12th": 3, "higher secondary": 3, "hsc": 3, "intermediate": 3,
                "diploma": 3.5, "d.ed": 3.5, "ded": 3.5, "iti": 3.5, "polytechnic": 3.5, "vocational": 3.5,
                "graduate": 4, "b.ed": 4, "bed": 4, "b.e": 4, "b.tech": 4, "degree": 4, "b.sc": 4, "b.com": 4, "ba": 4, "bachelor": 4,
                "postgraduate": 5, "pg": 5, "master": 5, "m.tech": 5, "mba": 5, "m.sc": 5, "doctorate": 6, "phd": 6
            }

            user_lvl = 2.0
            for k, v in edu_rank.items():
                if k in user_edu_lower:
                    user_lvl = max(user_lvl, v)

            if isinstance(target_val, list):
                min_req_lvl = 10.0
                has_any_match = False
                for t in target_val:
                    t_str = str(t).lower()
                    if t_str in user_edu_lower or user_edu_lower in t_str:
                        has_any_match = True
                        break
                    for k, v in edu_rank.items():
                        if k in t_str:
                            min_req_lvl = min(min_req_lvl, v)

                if has_any_match or user_lvl >= min_req_lvl:
                    return True, f"Educational qualification ({user_edu}) meets condition", user_edu
                else:
                    return False, f"Requires {target_val} qualification", user_edu
            else:
                target_str = str(target_val).lower()
                if target_str in user_edu_lower or user_edu_lower in target_str:
                    return True, f"Educational qualification ({user_edu}) meets condition", user_edu

                # Split composite alternative requirements like '12th Pass / D.Ed / B.Ed / Graduate' or '10th, 12th or Graduate'
                parts = [p.strip() for p in re.split(r"[/,]|(?:\s+or\s+)", target_str) if p.strip()]
                if not parts:
                    parts = [target_str]

                min_req_lvl = 10.0
                has_any_match = False
                for p in parts:
                    if p in user_edu_lower or user_edu_lower in p:
                        has_any_match = True
                        break
                    for k, v in edu_rank.items():
                        if k in p:
                            min_req_lvl = min(min_req_lvl, v)

                if has_any_match or (min_req_lvl < 10.0 and user_lvl >= min_req_lvl):
                    return True, f"Educational qualification ({user_edu}) satisfies minimum condition ({target_val})", user_edu
                else:
                    return False, f"Requires {target_val} qualification", user_edu

        # Normalize occupation & target occupations dynamically
        if field in ("occupation", "target_occupations", "targetOccupations"):
            user_occ = str(profile.get("occupation") or "").strip()
            if not user_occ:
                return False, "Occupation required", None

            user_occ_lower = user_occ.lower()
            target_list = target_val if isinstance(target_val, list) else [str(target_val)]
            target_clean = [str(x).strip().lower() for x in target_list]

            # Universal schemes
            if any(t in ("all", "any", "open to all", "citizens", "all citizens", "general", "") for t in target_clean):
                return True, "Open to all citizen occupations", user_occ

            passed = False
            # 1. Direct or substring match
            for t in target_clean:
                if t in user_occ_lower or user_occ_lower in t:
                    passed = True
                    break

            # 2. Farmers / Agriculture
            if not passed and any(t in ("farmer", "kisan", "cultivator", "agriculture") for t in target_clean):
                if any(k in user_occ_lower for k in ["farmer", "kisan", "agri", "cultivat", "krishi", "shetkari"]):
                    passed = True

            # 3. Students / Education
            if not passed and any(t in ("student", "scholar", "higher education") for t in target_clean):
                if "student" in user_occ_lower:
                    passed = True

            # 4. Salaried / Professionals
            if not passed and any(t in ("salaried employee", "salaried", "employee", "professional", "teacher", "worker") for t in target_clean):
                if any(s in user_occ_lower for s in ["teacher", "professor", "lecturer", "educator", "doctor", "nurse", "engineer", "clerk", "accountant", "employee", "salaried", "worker", "corporate", "staff"]):
                    passed = True

            # 5. Business / MSME / Trader / Retailer / Self-Employed
            if not passed and any(t in ("self-employed", "business", "entrepreneur", "msme", "artisan", "craftsperson", "shopkeeper", "trader") for t in target_clean):
                if any(b in user_occ_lower for b in ["shopkeeper", "trader", "merchant", "retailer", "vendor", "storekeeper", "business", "self-employed", "artisan", "craftsperson", "entrepreneur"]):
                    passed = True

            # 6. Homemaker / Women
            if not passed and any(t in ("homemaker", "housewife", "women", "female") for t in target_clean):
                user_gender = str(profile.get("gender") or "").strip().lower()
                if any(h in user_occ_lower for h in ["housewife", "homemaker", "home maker", "woman", "women"]) or user_gender == "female":
                    passed = True

            target_display = ", ".join(target_list) if isinstance(target_val, list) else str(target_val)
            if passed:
                return True, f"Occupation ({user_occ}) matches target beneficiary ({target_display})", user_occ
            else:
                return False, f"Requires {target_display} (Your occupation: {user_occ})", user_occ

        # Normalize age with DOB fallback
        if field == "age":
            actual_age = profile.get("age")
            if actual_age is None or actual_age == "" or actual_age == 0:
                dob = profile.get("date_of_birth") or profile.get("dateOfBirth") or profile.get("dob")
                if dob:
                    from services.eligibility_service import SchemeEligibilityService
                    computed_age = SchemeEligibilityService.parse_dob_to_age(dob)
                    if computed_age:
                        actual_age = computed_age
            if actual_age is not None:
                try:
                    actual_num = int(actual_age)
                    target_num = int(target_val)
                    eval_fn = cls.OPERATORS.get(op)
                    passed = eval_fn(actual_num, target_num) if eval_fn else (actual_num <= target_num)
                    return passed, f"Age {actual_num} {op} {target_num}", f"{actual_num} years"
                except Exception:
                    pass
            return False, f"Missing parameter: {field}", None

        if field not in profile or profile[field] is None:
            return False, f"Missing parameter: {field}", None

        actual_val = profile[field]

        eval_fn = cls.OPERATORS.get(op)
        if not eval_fn:
            return False, f"Unsupported operator: {op}", actual_val

        try:
            passed = eval_fn(actual_val, target_val)
            reason = f"{field} ({actual_val}) {op} {target_val}"
            return passed, reason, str(actual_val)
        except Exception as e:
            return False, f"Evaluation error for {field}: {str(e)}", str(actual_val)

    @classmethod
    def evaluate_scheme(cls, rules: List[Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates all rules for a scheme against user profile.
        Returns status, match_score, breakdown, and reason.
        """
        if isinstance(rules, dict):
            rule_items = rules.get("conditions", [])
        else:
            rule_items = list(rules) if rules else []

        if not rule_items:
            return {
                "status": "needs_info",
                "match_score": 50,
                "passed_count": 0,
                "total_count": 0,
                "ineligible_reason": "Eligibility criteria details pending official verification",
                "missing_fields": [],
                "criteria": []
            }

        breakdown = []
        passed_count = 0
        mandatory_failed = False
        missing_count = 0
        missing_fields = []
        first_failure_reason = None

        for idx, rule in enumerate(rule_items):
            # Rule can be a SchemeRule model object or dict
            rule_id = getattr(rule, "id", idx + 1)
            rule_name = getattr(rule, "rule_name", None) or (rule.get("name") if isinstance(rule, dict) else f"Criterion {idx + 1}")
            rule_desc = getattr(rule, "rule_description", "") or (rule.get("description", "") if isinstance(rule, dict) else "")
            
            if isinstance(rule, dict) and "op" in rule and "field" in rule:
                rule_logic = rule
                if not rule_desc:
                    rule_desc = f"{rule.get('field')} {rule.get('op')} {rule.get('value')}"
                is_mandatory = rule.get("is_mandatory", True)
            else:
                rule_logic = getattr(rule, "rule_logic", rule if isinstance(rule, dict) else {})
                is_mandatory = getattr(rule, "is_mandatory", rule.get("is_mandatory", True) if isinstance(rule, dict) else True)

            passed, reason, user_value = cls.evaluate_condition(rule_logic, profile)

            if user_value is None:
                missing_count += 1
                f_name = rule_logic.get("field")
                if f_name:
                    missing_fields.append(f_name)

            if not passed:
                if is_mandatory:
                    mandatory_failed = True
                    if not first_failure_reason:
                        first_failure_reason = f"{rule_name} condition not met: {rule_desc}"
            else:
                passed_count += 1

            breakdown.append({
                "id": f"c{rule_id}",
                "name": rule_name,
                "condition": rule_desc,
                "userValue": str(user_value) if user_value is not None else "Not Provided",
                "passed": passed
            })

        total = len(rule_items)

        if missing_fields and (passed_count + len(missing_fields) == total) and passed_count == 0:
            status = "needs_info"
            match_score = 50
        elif missing_count > 0 and (passed_count + missing_count == total):
            status = "almost"
            match_score = max(50, int((passed_count / total) * 100))
        elif mandatory_failed:
            status = "ineligible"
            match_score = min(45, int((passed_count / total) * 100)) if total > 0 else 0
        elif passed_count == total:
            status = "eligible"
            match_score = 100
        else:
            status = "almost"
            match_score = int((passed_count / total) * 100)

        return {
            "status": status,
            "match_score": match_score,
            "passed_count": passed_count,
            "total_count": total,
            "ineligible_reason": first_failure_reason,
            "missing_fields": missing_fields,
            "criteria": breakdown
        }
