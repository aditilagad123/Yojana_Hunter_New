import re
import logging
from flask import Blueprint, request, jsonify, g
from sqlalchemy.orm import joinedload
from database import SessionLocal
from models import Scheme, SchemeRule, Profile
from services.eligibility_service import SchemeEligibilityService
from services.subscription_service import SubscriptionService, FREE_SCHEMES_LIMIT
from utils.auth import optional_auth
from utils.activity import record_activity

logger = logging.getLogger(__name__)

schemes_bp = Blueprint("schemes", __name__)

def get_current_profile_dict(db) -> dict:
    """Helper to fetch stored citizen profile for authenticated user or overlay profile query parameters."""
    # Check if empty or cleared profile is requested
    if request.args.get("empty_profile") == "true" or request.args.get("profile_empty") == "true":
        return {}

    base_profile = None
    current_user = getattr(g, "current_user", None)
    profile_id = request.args.get("profile_id")
    user_profile = None

    if current_user:
        if profile_id:
            try:
                user_profile = db.query(Profile).filter(Profile.id == int(profile_id), Profile.user_id == current_user.id).first()
            except (ValueError, TypeError):
                user_profile = None
        if not user_profile:
            user_profile = db.query(Profile).filter(Profile.user_id == current_user.id, Profile.relationship == "Self").first()
            if not user_profile:
                user_profile = db.query(Profile).filter(Profile.user_id == current_user.id).order_by(Profile.id.asc()).first()
        if user_profile:
            base_profile = user_profile.to_dict()
    elif profile_id:
        try:
            user_profile = db.query(Profile).filter(Profile.id == int(profile_id)).first()
            if user_profile:
                base_profile = user_profile.to_dict()
        except (ValueError, TypeError):
            user_profile = None

    if not base_profile:
        # Check if caller supplied explicit meaningful profile parameters in request.args
        has_meaningful_params = any(
            request.args.get(k) is not None and str(request.args.get(k)).strip() != ""
            for k in (
                "profile_occupation", "occupation",
                "profile_state", "state", "profile_state_domicile", "state_domicile",
                "profile_age", "age",
                "profile_income", "annual_income", "annualIncome",
                "profile_gender", "gender",
                "profile_education", "education",
                "profile_category", "category_caste", "caste"
            )
        )
        if has_meaningful_params:
            base_profile = {}
        else:
            # If no authenticated profile, no profile_id found, and no meaningful query parameters supplied,
            # return {} to trigger public catalog mode cleanly.
            return {}

    profile_dict = dict(base_profile)

    # Overlay profile parameters from request.args
    occ = request.args.get("profile_occupation") or request.args.get("occupation")
    if occ is not None:
        profile_dict["occupation"] = occ
        occ_lower = occ.lower()
        if "student" in occ_lower:
            profile_dict["is_student"] = True
            if "profile_is_farmer" not in request.args and "is_farmer" not in request.args:
                profile_dict["is_farmer"] = False
        elif any(k in occ_lower for k in ["farmer", "kisan", "agri", "cultivat"]):
            profile_dict["is_farmer"] = True
            if "profile_is_student" not in request.args and "is_student" not in request.args:
                profile_dict["is_student"] = False

    st = request.args.get("profile_state") or request.args.get("state_domicile") or request.args.get("state")
    if st is not None:
        profile_dict["state"] = st

    age = request.args.get("profile_age") or request.args.get("age")
    if age is not None:
        try:
            profile_dict["age"] = int(age)
        except (ValueError, TypeError):
            pass

    income = request.args.get("profile_income") or request.args.get("annual_income") or request.args.get("annualIncome") or request.args.get("income")
    if income is not None:
        profile_dict["annual_income"] = income
        try:
            profile_dict["income_numeric"] = float(income)
        except (ValueError, TypeError):
            pass

    gender = request.args.get("profile_gender") or request.args.get("gender")
    if gender is not None:
        profile_dict["gender"] = SchemeEligibilityService.normalize_gender(gender).capitalize()
    elif profile_dict.get("gender"):
        profile_dict["gender"] = SchemeEligibilityService.normalize_gender(profile_dict["gender"]).capitalize()

    edu = request.args.get("profile_education") or request.args.get("education")
    if edu is not None:
        profile_dict["education"] = edu

    cat = request.args.get("profile_category") or request.args.get("category_caste") or request.args.get("caste") or request.args.get("social_category") or request.args.get("socialCategory") or request.args.get("category")
    if cat is not None:
        profile_dict["category"] = cat
        profile_dict["social_category"] = cat
        profile_dict["socialCategory"] = cat

    emp = request.args.get("profile_employment_status") or request.args.get("employment_status") or request.args.get("employmentStatus")
    if emp is not None:
        profile_dict["employment_status"] = emp

    land = request.args.get("profile_land_holding_acres") or request.args.get("land_holding_acres") or request.args.get("landholding_acres") or request.args.get("landHoldingAcres")
    if land is not None:
        try:
            val_land = float(land)
            profile_dict["land_holding_acres"] = val_land
            profile_dict["landholding_acres"] = val_land
            profile_dict["landHoldingAcres"] = val_land
        except (ValueError, TypeError):
            pass

    if any(k in request.args for k in ("profile_is_farmer", "is_farmer", "isFarmer")):
        val = request.args.get("profile_is_farmer") or request.args.get("is_farmer") or request.args.get("isFarmer")
        profile_dict["is_farmer"] = val.lower() in ("true", "1", "yes")

    if any(k in request.args for k in ("profile_is_student", "is_student", "isStudent")):
        val = request.args.get("profile_is_student") or request.args.get("is_student") or request.args.get("isStudent")
        profile_dict["is_student"] = val.lower() in ("true", "1", "yes")

    if any(k in request.args for k in ("profile_has_business", "has_business", "hasBusiness")):
        val = request.args.get("profile_has_business") or request.args.get("has_business") or request.args.get("hasBusiness")
        profile_dict["has_business"] = val.lower() in ("true", "1", "yes")

    if any(k in request.args for k in ("profile_is_disabled", "is_disabled", "isDisabled")):
        val = request.args.get("profile_is_disabled") or request.args.get("is_disabled") or request.args.get("isDisabled")
        profile_dict["is_disabled"] = val.lower() in ("true", "1", "yes")

    if any(k in request.args for k in ("profile_is_tax_payer", "is_tax_payer", "isTaxPayer")):
        val = request.args.get("profile_is_tax_payer") or request.args.get("is_tax_payer") or request.args.get("isTaxPayer")
        profile_dict["is_tax_payer"] = val.lower() in ("true", "1", "yes")

    if any(k in request.args for k in ("profile_is_govt_employee", "is_govt_employee", "isGovtEmployee")):
        val = request.args.get("profile_is_govt_employee") or request.args.get("is_govt_employee") or request.args.get("isGovtEmployee")
        profile_dict["is_govt_employee"] = val.lower() in ("true", "1", "yes")

    if "is_dual_category" in request.args or "profile_is_dual_category" in request.args:
        val = request.args.get("is_dual_category") or request.args.get("profile_is_dual_category")
        profile_dict["is_dual_category"] = val.lower() in ("true", "1", "yes")

    # Consistent occupation disambiguation
    final_occ = (profile_dict.get("occupation") or "").lower().strip()
    user_land = profile_dict.get("land_holding_acres") or profile_dict.get("landHoldingAcres") or 0.0
    try:
        user_land = float(user_land)
    except (ValueError, TypeError):
        user_land = 0.0

    if "student" in final_occ and not any(k in final_occ for k in ["farmer", "kisan", "agri"]):
        profile_dict["is_student"] = True
        if user_land <= 0 and ("profile_is_farmer" not in request.args and "is_farmer" not in request.args and not profile_dict.get("is_dual_category")):
            profile_dict["is_farmer"] = False
    elif any(k in final_occ for k in ["farmer", "kisan", "agri", "cultivat"]) and "student" not in final_occ:
        profile_dict["is_farmer"] = True
        if "profile_is_student" not in request.args and "is_student" not in request.args and not profile_dict.get("is_dual_category"):
            profile_dict["is_student"] = False
    elif final_occ:
        # Custom non-student non-farmer occupation (e.g. Clerk, Teacher, Housewife, Shopkeeper, Private employee, Govt employee, Daily-wage worker, etc.)
        if not profile_dict.get("is_dual_category"):
            profile_dict["is_student"] = False
            if user_land <= 0:
                profile_dict["is_farmer"] = False
        if any(b in final_occ for b in ["business", "self-employed", "entrepreneur", "shopkeeper", "artisan", "trader"]):
            profile_dict["has_business"] = True
        if any(g in final_occ for g in ["government", "govt", "sarkari", "civil service", "ias", "ips", "public sector"]):
            if "profile_is_govt_employee" not in request.args and "is_govt_employee" not in request.args:
                profile_dict["is_govt_employee"] = True


    # Normalize key variants for downstream eligibility evaluation
    if profile_dict.get("annual_income") and not profile_dict.get("annualIncome"):
        profile_dict["annualIncome"] = profile_dict["annual_income"]
    elif profile_dict.get("annualIncome") and not profile_dict.get("annual_income"):
        profile_dict["annual_income"] = profile_dict["annualIncome"]

    if profile_dict.get("date_of_birth") and not profile_dict.get("dateOfBirth"):
        profile_dict["dateOfBirth"] = profile_dict["date_of_birth"]
    elif profile_dict.get("dateOfBirth") and not profile_dict.get("date_of_birth"):
        profile_dict["date_of_birth"] = profile_dict["dateOfBirth"]

    if (profile_dict.get("age") is None or profile_dict.get("age") == 0) and profile_dict.get("date_of_birth"):
        computed_age = SchemeEligibilityService.parse_dob_to_age(profile_dict["date_of_birth"])
        if computed_age:
            profile_dict["age"] = computed_age

    resolved_cat = profile_dict.get("category") or profile_dict.get("social_category") or profile_dict.get("socialCategory")
    if resolved_cat:
        profile_dict["category"] = resolved_cat
        profile_dict["social_category"] = resolved_cat
        profile_dict["socialCategory"] = resolved_cat

    return profile_dict

@schemes_bp.route("", methods=["GET"])
@schemes_bp.route("/", methods=["GET"])
@optional_auth
def list_schemes():
    """
    GET /api/schemes
    Returns verified, published schemes evaluated against the citizen profile,
    ranked with transparent eligibility explanations.
    """
    db = SessionLocal()
    try:
        category_filter = request.args.get("category")
        state_filter = request.args.get("state")
        query_filter = request.args.get("q")
        status_filter = request.args.get("filter")  # eligible | possibly_eligible | not_eligible | applications_closed | all
        include_ineligible = request.args.get("include_ineligible", "").lower() in ("true", "1")
        if status_filter and status_filter.lower() in ("not_eligible", "ineligible", "applications_closed", "closed"):
            include_ineligible = True

        profile_dict = get_current_profile_dict(db)
        logger.info(f"[FLASK /api/schemes INPUT] Profile occupation: '{profile_dict.get('occupation')}', education: '{profile_dict.get('education')}', state: '{profile_dict.get('state')}'")

        current_user = getattr(g, "current_user", None)
        is_admin = bool(current_user and getattr(current_user, "role", None) == "admin")
        is_premium = is_admin or (bool(current_user) and SubscriptionService.is_user_premium(db, current_user.id))
        active_sub = SubscriptionService.get_active_subscription(db, current_user.id) if current_user else None

        if not profile_dict:
            if request.args.get("empty_profile") == "true" or request.args.get("profile_empty") == "true":
                if request.args.get("raw_list") == "true":
                    return jsonify([])
                return jsonify({
                    "schemes": [],
                    "total_count": 0,
                    "total_matching_count": 0,
                    "accessible_count": 0,
                    "is_premium": is_premium,
                    "free_limit": FREE_SCHEMES_LIMIT,
                    "subscription": None,
                    "has_more": False
                })

            # Public catalog browsing mode for unauthenticated / anonymous visitors
            query = db.query(Scheme).filter(
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
            if query_filter:
                q = query_filter.lower().strip()
                query = query.filter(
                    (Scheme.name.ilike(f"%{q}%")) |
                    (Scheme.short_description.ilike(f"%{q}%")) |
                    (Scheme.department.ilike(f"%{q}%"))
                )
            schemes_records = query.all()
            results = []
            seen_catalog = set()
            for s in schemes_records:
                key = s.slug or str(s.id)
                norm = re.sub(r'[^a-z0-9]', '', (s.name or '').lower())
                if key in seen_catalog or (norm and norm in seen_catalog):
                    continue
                seen_catalog.add(key)
                if norm:
                    seen_catalog.add(norm)
                sd = s.to_dict(include_rules=False)
                sd["eligibilityStatus"] = "possibly_eligible"
                sd["legacyEligibilityStatus"] = "almost"
                sd["whyMatched"] = "Explore public government scheme catalog. Log in or complete profile for personalized eligibility."
                sd["matchScore"] = 50
                results.append(sd)
            logger.info(f"[FLASK /api/schemes RESPONSE] Public catalog returned {len(results)} schemes")

            total_count = len(results)
            accessible_results = results if is_premium else results[:FREE_SCHEMES_LIMIT]
            counts_breakdown = {
                "total_in_db": total_count,
                "all": total_count,
                "eligible": 0,
                "possibly_eligible": total_count,
                "not_eligible": 0,
                "applications_closed": 0
            }

            if request.args.get("raw_list") == "true":
                return jsonify(accessible_results)

            return jsonify({
                "schemes": accessible_results,
                "total_count": total_count,
                "total_matching_count": total_count,
                "accessible_count": len(accessible_results),
                "counts": counts_breakdown,
                "is_premium": is_premium,
                "free_limit": FREE_SCHEMES_LIMIT,
                "subscription": active_sub.to_dict(include_user=False) if active_sub else None,
                "has_more": total_count > len(accessible_results)
            })

        # Evaluate complete scheme dataset to provide accurate counters and filter subsets
        all_evals = SchemeEligibilityService.get_ranked_schemes_for_profile(
            profile_data=profile_dict,
            category_filter=category_filter,
            state_filter=state_filter,
            status_filter=None,
            search_query=query_filter,
            include_ineligible=True
        )

        total_in_db = db.query(Scheme).filter(
            Scheme.is_active == True,
            Scheme.status == "published",
            Scheme.admin_review_status.in_(["approved", "published"]),
            (Scheme.is_test == False) | (Scheme.is_test.is_(None))
        ).count()

        eligible_count = sum(1 for s in all_evals if s.get("eligibilityStatus") == "eligible")
        possibly_eligible_count = sum(1 for s in all_evals if s.get("eligibilityStatus") in ("possibly_eligible", "almost"))
        not_eligible_count = sum(1 for s in all_evals if s.get("eligibilityStatus") in ("not_eligible", "ineligible"))
        closed_count = sum(1 for s in all_evals if s.get("eligibilityStatus") == "applications_closed")
        relevant_count = eligible_count + possibly_eligible_count

        counts_breakdown = {
            "total_in_db": total_in_db,
            "all": relevant_count,
            "eligible": eligible_count,
            "possibly_eligible": possibly_eligible_count,
            "not_eligible": not_eligible_count,
            "applications_closed": closed_count
        }

        # Filter schemes according to status_filter
        s_filter = (status_filter or "").lower()
        if s_filter in ("eligible",):
            schemes = [s for s in all_evals if s.get("eligibilityStatus") == "eligible"]
        elif s_filter in ("possibly_eligible", "almost"):
            schemes = [s for s in all_evals if s.get("eligibilityStatus") in ("possibly_eligible", "almost")]
        elif s_filter in ("not_eligible", "ineligible"):
            schemes = [s for s in all_evals if s.get("eligibilityStatus") in ("not_eligible", "ineligible")]
        elif s_filter in ("applications_closed", "closed"):
            schemes = [s for s in all_evals if s.get("eligibilityStatus") == "applications_closed"]
        elif include_ineligible:
            schemes = all_evals
        else:
            # Default / "all": All relevant schemes (eligible + possibly eligible)
            schemes = [s for s in all_evals if s.get("eligibilityStatus") in ("eligible", "possibly_eligible", "almost")]

        total_count = len(schemes)
        accessible_schemes = schemes if is_premium else schemes[:FREE_SCHEMES_LIMIT]

        # Record scheme search activity for authenticated user
        if getattr(g, "current_user", None) and query_filter and query_filter.strip():
            record_activity(
                db,
                g.current_user.id,
                "scheme_search",
                {
                    "query": query_filter.strip(),
                    "category": category_filter,
                    "state": state_filter,
                    "title": f"Searched schemes for '{query_filter.strip()}'",
                    "results_count": total_count
                }
            )

        logger.info(f"[FLASK /api/schemes RESPONSE] Returning {len(accessible_schemes)}/{total_count} schemes to citizen (is_premium={is_premium}, eligible={eligible_count}, relevant={relevant_count})")

        if request.args.get("raw_list") == "true":
            return jsonify(accessible_schemes)

        return jsonify({
            "schemes": accessible_schemes,
            "total_count": total_count,
            "total_matching_count": total_count,
            "accessible_count": len(accessible_schemes),
            "counts": counts_breakdown,
            "is_premium": is_premium,
            "free_limit": FREE_SCHEMES_LIMIT,
            "subscription": active_sub.to_dict(include_user=False) if active_sub else None,
            "has_more": total_count > len(accessible_schemes)
        })
    except Exception as e:
        return jsonify({"error": str(e), "schemes": []}), 500
    finally:
        db.close()

@schemes_bp.route("/<string:scheme_id>", methods=["GET"])
@optional_auth
def get_scheme(scheme_id):
    """
    GET /api/schemes/<scheme_id>
    Fetches full scheme details with transparent eligibility reasons and requirements breakdown.
    Free users can only view complete details of the first 5 matching schemes.
    """
    db = SessionLocal()
    try:
        scheme = None
        if scheme_id.isdigit():
            scheme = db.query(Scheme).options(
                joinedload(Scheme.rules),
                joinedload(Scheme.document_requirements)
            ).filter(Scheme.id == int(scheme_id)).first()

        if not scheme:
            scheme = db.query(Scheme).options(
                joinedload(Scheme.rules),
                joinedload(Scheme.document_requirements)
            ).filter(Scheme.slug == scheme_id).first()

        # Reject if scheme is not found, not active, not published, or not admin-approved
        if (
            not scheme 
            or not scheme.is_active 
            or scheme.status != "published" 
            or not scheme.admin_review_status 
            or scheme.admin_review_status not in ("approved", "published")
        ):
            return jsonify({"error": f"Scheme '{scheme_id}' not found"}), 404

        current_user = getattr(g, "current_user", None)
        is_admin = bool(current_user and getattr(current_user, "role", None) == "admin")
        is_premium = is_admin or (bool(current_user) and SubscriptionService.is_user_premium(db, current_user.id))

        profile_dict = get_current_profile_dict(db)

        # Check access limit for free users when evaluating against a profile with declared occupation
        if not is_premium and profile_dict and (profile_dict.get("occupation") or profile_dict.get("is_student") or profile_dict.get("is_farmer")):
            ranked_matches = SchemeEligibilityService.get_ranked_schemes_for_profile(
                profile_data=profile_dict,
                include_ineligible=False
            )
            scheme_rank = None
            for idx, s in enumerate(ranked_matches):
                s_id = s.get("id")
                s_num_id = s.get("numericId")
                s_slug = s.get("slug")
                if (scheme.slug and s_slug == scheme.slug) or (s_id in (scheme.slug, str(scheme.id), scheme.id)) or (s_num_id == scheme.id):
                    scheme_rank = idx
                    break

            if scheme_rank is not None and scheme_rank >= FREE_SCHEMES_LIMIT:
                return jsonify({
                    "error": "Subscription required",
                    "is_locked": True,
                    "message": f"Free accounts can view complete details of only the first {FREE_SCHEMES_LIMIT} matching schemes. Please upgrade to a Premium plan to unlock this scheme.",
                    "scheme_name": scheme.name,
                    "scheme_slug": scheme.slug,
                    "total_matching_count": len(ranked_matches),
                    "free_limit": FREE_SCHEMES_LIMIT,
                    "rank": scheme_rank + 1
                }), 403

        eval_result = SchemeEligibilityService.evaluate_scheme_for_profile(scheme, profile_dict)

        data = scheme.to_dict(include_rules=False)
        data["eligibilityStatus"] = eval_result["eligibility_status"]
        data["legacyEligibilityStatus"] = eval_result["legacy_status"]
        data["applicationStatus"] = eval_result["application_status"]
        data["matchScore"] = eval_result["match_score"]
        data["whyMatched"] = eval_result["why_matched"]
        data["requirementsSatisfied"] = eval_result["requirements_satisfied"]
        data["requirementsNotSatisfied"] = eval_result["requirements_not_satisfied"]
        data["missingInformation"] = eval_result["missing_information"]
        data["criteria"] = eval_result["criteria"]
        data["requiredDocuments"] = eval_result["required_documents"]
        data["applicationProcess"] = eval_result["application_procedure"]
        data["sourceReference"] = eval_result["source_reference"]

        if eval_result["requirements_not_satisfied"]:
            data["ineligibleReason"] = eval_result["requirements_not_satisfied"][0]
        else:
            data["ineligibleReason"] = None

        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@schemes_bp.route("/match", methods=["POST"])
@optional_auth
def match_schemes():
    """
    POST /api/schemes/match
    Dynamically evaluate and rank all published schemes against a custom citizen profile payload.
    Used for instant smart questionnaire matching.
    """
    try:
        payload = request.get_json() or {}
        profile_data = payload.get("profile") if isinstance(payload.get("profile"), dict) else payload
        logger.info(f"[FLASK /api/schemes/match INPUT] Occupation: '{profile_data.get('occupation')}', Education: '{profile_data.get('education')}', State: '{profile_data.get('state')}'")
        category = request.args.get("category") or payload.get("category_filter")
        state_filter = request.args.get("state") or payload.get("state_filter")
        search_query = request.args.get("q") or payload.get("q")
        include_ineligible = request.args.get("include_ineligible", "").lower() in ("true", "1") or bool(payload.get("include_ineligible", True))

        matched = SchemeEligibilityService.get_ranked_schemes_for_profile(
            profile_data=profile_data,
            category_filter=category,
            state_filter=state_filter,
            search_query=search_query,
            include_ineligible=include_ineligible
        )

        eligible_list = [x for x in matched if x["eligibilityStatus"] == "eligible"]
        possibly_eligible_list = [x for x in matched if x["eligibilityStatus"] == "possibly_eligible"]
        not_eligible_list = [x for x in matched if x["eligibilityStatus"] == "not_eligible"]
        closed_list = [x for x in matched if x["eligibilityStatus"] == "applications_closed"]

        logger.info(f"[FLASK /api/schemes/match RESPONSE] Evaluated: {len(matched)}, Eligible: {len(eligible_list)}, Possibly: {len(possibly_eligible_list)}, Ineligible: {len(not_eligible_list)}")

        user = getattr(g, "current_user", None)
        is_admin = bool(user and getattr(user, "role", None) == "admin")
        db = SessionLocal()
        is_premium = is_admin
        try:
            if user and not is_admin:
                is_premium = SubscriptionService.is_user_premium(db, user.id)
        finally:
            db.close()

        total_matching_count = len(matched)
        accessible_matched = matched if is_premium else matched[:FREE_SCHEMES_LIMIT]
        accessible_eligible = eligible_list if is_premium else eligible_list[:FREE_SCHEMES_LIMIT]

        return jsonify({
            "total_evaluated": len(matched),
            "total_matching_count": total_matching_count,
            "eligible_count": len(eligible_list),
            "possibly_eligible_count": len(possibly_eligible_list),
            "not_eligible_count": len(not_eligible_list),
            "applications_closed_count": len(closed_list),
            "accessible_count": len(accessible_matched),
            "is_premium": is_premium,
            "free_limit": FREE_SCHEMES_LIMIT,
            "has_more": total_matching_count > len(accessible_matched),
            "eligible": accessible_eligible,
            "possibly_eligible": possibly_eligible_list,
            "not_eligible": not_eligible_list,
            "applications_closed": closed_list,
            "schemes": accessible_matched
        })
    except Exception as e:
        return jsonify({"error": str(e), "schemes": []}), 500

@schemes_bp.route("/sync", methods=["POST"])
def sync_schemes():
    """
    POST /api/schemes/sync
    Actively fetches, probes official sources, and updates all 10 verified real schemes in the database.
    Recalculates eligibility recommendations against the user profile.
    """
    try:
        from services.scheme_sync_service import SchemeSyncService
        payload = request.get_json() or {}
        profile_data = payload.get("profile")
        result = SchemeSyncService.sync_all_schemes(profile_override=profile_data)
        status_code = 200 if result.get("success") else 500
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@schemes_bp.route("/sync-status", methods=["GET"])
def get_sync_status():
    """
    GET /api/schemes/sync-status
    Returns the latest synchronization status, total verified schemes count, and last sync timestamp.
    """
    db = SessionLocal()
    try:
        total_schemes = db.query(Scheme).count()
        verified_live = db.query(Scheme).filter(Scheme.source_verification_status.ilike("%verified%")).count()
        latest_scheme = db.query(Scheme).order_by(Scheme.last_fetched_at.desc()).first()

        return jsonify({
            "total_schemes": total_schemes,
            "verified_schemes": verified_live,
            "last_sync_time": latest_scheme.last_fetched_at.isoformat() if latest_scheme and latest_scheme.last_fetched_at else None,
            "last_verified_date": latest_scheme.last_verified_date if latest_scheme else "12 Oct 2026",
            "status": "ready"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@schemes_bp.route("/recommendations", methods=["GET"])
@optional_auth
def get_recommendations():
    """
    GET /api/schemes/recommendations
    Returns up to 10 top recommendations matching the current profile, ranked by relevance and eligibility.
    """
    db = SessionLocal()
    try:
        limit = int(request.args.get("limit", 10))
        profile_dict = get_current_profile_dict(db)

        ranked = SchemeEligibilityService.get_ranked_schemes_for_profile(profile_data=profile_dict)

        # Recommendations strictly return schemes that are eligible or possibly eligible
        eligible = [s for s in ranked if s["eligibilityStatus"] in ("eligible", "possibly_eligible")]
        recommendations = eligible[:limit]

        return jsonify({
            "profile_evaluated": {
                "occupation": profile_dict.get("occupation"),
                "annual_income": profile_dict.get("annual_income") or profile_dict.get("annualIncome"),
                "age": profile_dict.get("age"),
                "state": profile_dict.get("state"),
                "education": profile_dict.get("education"),
                "category": profile_dict.get("category"),
            },
            "total_evaluated": len(ranked),
            "recommendations_count": len(recommendations),
            "recommendations": recommendations
        })
    except Exception as e:
        return jsonify({"error": str(e), "recommendations": []}), 500
    finally:
        db.close()


@schemes_bp.route("/categories", methods=["GET"])
def get_categories():
    """
    GET /api/schemes/categories
    Returns distinct scheme categories for discovery and filter interfaces.
    """
    db = SessionLocal()
    try:
        results = db.query(Scheme.category).filter(Scheme.category != None).distinct().all()
        categories = sorted([r[0] for r in results if r[0] and r[0].strip()])
        if "Agriculture" not in categories:
            categories.append("Agriculture")
        if "Education" not in categories:
            categories.append("Education")
        return jsonify({"categories": sorted(list(set(categories)))}), 200
    except Exception as e:
        return jsonify({"categories": ["Agriculture", "Education", "Healthcare", "Women & Child", "Social Welfare"]}), 200
    finally:
        db.close()


@schemes_bp.route("/states", methods=["GET"])
def get_states():
    """
    GET /api/schemes/states
    Returns distinct supported states for filter interfaces.
    """
    db = SessionLocal()
    try:
        results = db.query(Scheme.state).filter(Scheme.state != None).distinct().all()
        states = sorted([r[0] for r in results if r[0] and r[0].strip() and r[0] != "All India"])
        return jsonify({"states": ["All India"] + states}), 200
    except Exception as e:
        return jsonify({"states": ["All India", "Maharashtra", "Uttar Pradesh", "Delhi", "Karnataka"]}), 200
    finally:
        db.close()


@schemes_bp.route("/<string:scheme_id>/explain", methods=["POST"])
@optional_auth
def explain_scheme_eligibility(scheme_id: str):
    """
    POST /api/schemes/<scheme_id>/explain
    Generates a Gemini AI-assisted transparent explanation of scheme eligibility,
    grounded in official source facts without overriding the deterministic engine decision.
    """
    db = SessionLocal()
    try:
        from services.ai_service import AIService

        payload = request.get_json() or {}
        profile_override = payload.get("profile")
        consent_granted = bool(payload.get("consent", True))

        scheme = None
        if scheme_id.isdigit():
            scheme = db.query(Scheme).filter(Scheme.id == int(scheme_id)).first()
        if not scheme:
            scheme = db.query(Scheme).filter(Scheme.slug == scheme_id).first()

        if not scheme:
            return jsonify({"error": f"Scheme '{scheme_id}' was not found"}), 404

        # Use profile from request payload or logged-in citizen
        profile_data = profile_override or get_current_profile_dict(db)

        # 1. Deterministic evaluation first
        eval_result = SchemeEligibilityService.evaluate_scheme_for_profile(scheme, profile_data)

        # 2. Grounded explanation
        ai_res = AIService.generate_explanation(
            scheme_data=scheme.to_dict(include_rules=False),
            profile_data=profile_data,
            rule_results=eval_result,
            consent_granted=consent_granted
        )

        return jsonify({
            "schemeId": scheme.slug,
            "schemeName": scheme.name,
            "eligibilityStatus": eval_result["eligibility_status"],
            "matchScore": eval_result["match_score"],
            "explanation": ai_res.get("explanation"),
            "source": ai_res.get("source"),
            "citations": ai_res.get("citations", []),
            "requirementsSatisfied": eval_result["requirements_satisfied"],
            "requirementsNotSatisfied": eval_result["requirements_not_satisfied"],
            "missingInformation": eval_result["missing_information"],
            "officialUrl": scheme.official_source_url
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@schemes_bp.route("/<string:scheme_id>/portal-status", methods=["GET"])
def get_scheme_portal_status(scheme_id):
    """
    Checks or returns cached health status of official government portal.
    Supports ?refresh=true for user retry action without relying on frontend CORS.
    """
    db = SessionLocal()
    try:
        force_refresh = request.args.get("refresh", "").lower() in ("true", "1")

        # Look up scheme by numeric ID or slug
        scheme = None
        if str(scheme_id).isdigit():
            scheme = db.query(Scheme).filter(Scheme.id == int(scheme_id)).first()
        if not scheme:
            scheme = db.query(Scheme).filter(Scheme.slug == str(scheme_id)).first()

        if not scheme:
            return jsonify({"error": f"Scheme '{scheme_id}' was not found"}), 404

        official_url = scheme.official_source_url
        if not official_url:
            return jsonify({
                "schemeId": scheme.slug,
                "status": "unverified",
                "isAvailable": False,
                "statusMessage": "No official portal link is registered for this scheme.",
                "officialUrl": None,
                "alternativeUrl": None
            }), 200

        from services.portal_health_service import PortalHealthService

        alt_url = getattr(scheme, "alternative_url", None) or PortalHealthService.get_alternative_url(official_url)

        if force_refresh:
            probe_res = PortalHealthService.probe_url(official_url, force_refresh=True)
        else:
            probe_res = PortalHealthService.get_cached_status(official_url, check_if_missing=True)

        return jsonify({
            "schemeId": scheme.slug,
            "officialUrl": official_url,
            "alternativeUrl": alt_url or probe_res.get("alternative_url"),
            "status": probe_res.get("status", "reachable"),
            "isAvailable": probe_res.get("is_available", True),
            "statusCode": probe_res.get("status_code"),
            "statusMessage": probe_res.get("status_message"),
            "checkedAt": probe_res.get("checked_at")
        }), 200

    except Exception as e:
        logger.error(f"Error checking portal status for {scheme_id}: {e}")
        return jsonify({
            "schemeId": scheme_id,
            "status": "temporarily_unavailable",
            "isAvailable": False,
            "statusMessage": "The official portal could not be reached. It may be temporarily unavailable. You can review the scheme details and try again later.",
            "error": str(e)
        }), 200
    finally:
        db.close()

