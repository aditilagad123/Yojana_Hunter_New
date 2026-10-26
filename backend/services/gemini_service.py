import os
import re
import json
import time
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Official Google Gen AI SDK
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    APIError = Exception
    GENAI_AVAILABLE = False
    logger.warning("google-genai SDK not installed. Gemini features will run in mock/fallback mode.")


class GeminiService:
    """
    Secure server-side gateway to the Gemini API using the official Google Gen AI Python SDK.
    Supports Google Search grounding, structured scheme extraction, robust retries,
    multi-model fallback resilience, and quota handling with zero secret leakage.
    """

    _client = None
    _cached_api_key = None
    _QUOTA_COOLDOWN_UNTIL: float = 0.0

    @classmethod
    def is_quota_cooling_down(cls) -> bool:
        return time.time() < cls._QUOTA_COOLDOWN_UNTIL

    @classmethod
    def set_quota_cooldown(cls, seconds: float = 300.0) -> None:
        cls._QUOTA_COOLDOWN_UNTIL = time.time() + seconds

    @classmethod
    def get_api_key(cls) -> str:
        key = os.getenv("GEMINI_API_KEY", "")
        if not key or key == "your_gemini_api_key_here":
            try:
                from dotenv import dotenv_values
                env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
                env_vals = dotenv_values(env_path)
                key = env_vals.get("GEMINI_API_KEY", "") or ""
            except Exception:
                pass
        return key.strip()

    @classmethod
    def get_model_name(cls) -> str:
        model = os.getenv("GEMINI_MODEL", "")
        if not model:
            try:
                from dotenv import dotenv_values
                env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
                env_vals = dotenv_values(env_path)
                model = env_vals.get("GEMINI_MODEL", "") or ""
            except Exception:
                pass
        model = (model or "gemini-3.5-flash-lite").strip()
        # Automatically upgrade deprecated 2.5-flash / 2.0-flash / 1.5-flash
        if model in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash-lite"):
            model = "gemini-3.5-flash-lite"
        return model

    @classmethod
    def get_candidate_models(cls) -> List[str]:
        """Returns prioritized candidate models for graceful fallback if one model encounters 503/404/429."""
        preferred = cls.get_model_name()
        candidates = [
            preferred,
            "gemini-3.5-flash-lite",
            "gemini-3.6-flash",
            "gemini-flash-lite-latest",
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.8-flash",
            "gemini-flash-latest"
        ]
        # Deduplicate while preserving order
        seen = set()
        result = []
        for m in candidates:
            if m not in seen:
                seen.add(m)
                result.append(m)
        return result

    @classmethod
    def is_configured(cls) -> bool:
        key = cls.get_api_key()
        return bool(key and key != "your_gemini_api_key_here")

    @classmethod
    def get_client(cls):
        """
        Returns or initializes the singleton official GenAI client.
        Never logs or exposes the API key.
        """
        if not GENAI_AVAILABLE:
            raise RuntimeError("The official 'google-genai' SDK is not installed.")

        current_key = cls.get_api_key()
        if not current_key or current_key == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY is not configured in backend/.env.")

        if cls._client is None or cls._cached_api_key != current_key:
            http_opts = types.HttpOptions(timeout=15000) if types and hasattr(types, "HttpOptions") else None
            if http_opts:
                cls._client = genai.Client(api_key=current_key, http_options=http_opts)
            else:
                cls._client = genai.Client(api_key=current_key)
            cls._cached_api_key = current_key

        return cls._client

    @classmethod
    def sanitize_error_message(cls, error_msg: str) -> str:
        """Removes potential API keys or sensitive query string tokens from error strings."""
        if not error_msg:
            return ""
        key = cls.get_api_key()
        if key and len(key) > 6:
            error_msg = error_msg.replace(key, "[REDACTED_API_KEY]")
        # Redact generic alphanumeric secrets
        error_msg = re.sub(r'(AIza[0-9A-Za-z-_]{15,45})', '[REDACTED_API_KEY]', error_msg)
        error_msg = re.sub(r'(AQ\.[0-9A-Za-z-_]{20,60})', '[REDACTED_API_KEY]', error_msg)
        return error_msg

    @classmethod
    def extract_text_from_response(cls, response) -> str:
        """Safely extracts text content from GenAI response handling candidate parts and thought traces."""
        if not response:
            return ""
        if getattr(response, "text", None):
            return response.text
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                texts = [p.text for p in candidate.content.parts if getattr(p, "text", None)]
                if texts:
                    return "".join(texts)
        return ""

    @classmethod
    def test_connection(cls) -> Dict[str, Any]:
        """
        Validates API key, model connectivity, and Google Search grounding availability
        with real API calls and detailed diagnostics.
        """
        if not cls.is_configured():
            return {
                "configured": False,
                "connected": False,
                "model": cls.get_model_name(),
                "groundingSupported": False,
                "message": "GEMINI_API_KEY is not configured in backend/.env. Please configure it to enable live AI scheme discovery.",
                "quotaExhausted": False,
            }

        if not GENAI_AVAILABLE:
            return {
                "configured": True,
                "connected": False,
                "model": cls.get_model_name(),
                "groundingSupported": False,
                "message": "google-genai SDK package is missing from Python environment.",
                "quotaExhausted": False,
            }

        start_time = time.time()
        try:
            client = cls.get_client()
        except Exception as e:
            err_str = cls.sanitize_error_message(str(e))
            is_quota = "RESOURCE_EXHAUSTED" in err_str or "429" in err_str or "quota" in err_str.lower()
            return {
                "configured": True,
                "connected": False,
                "model": cls.get_model_name(),
                "groundingSupported": False,
                "message": f"Connection initialization failed: {err_str}",
                "quotaExhausted": is_quota,
            }

        candidate_models = cls.get_candidate_models()
        active_model = candidate_models[0]
        connected = False
        connect_error = None
        latency_ms = 0

        # Step 1: Real API call to test connection and model response
        for model in candidate_models:
            try:
                t0 = time.time()
                res = client.models.generate_content(
                    model=model,
                    contents="Confirm connection by replying with 'OK'.",
                )
                txt = cls.extract_text_from_response(res).strip()
                latency_ms = int((time.time() - t0) * 1000)
                active_model = model
                connected = True
                break
            except Exception as e:
                connect_error = e
                logger.warning(f"Connection test attempt with model '{model}' failed: {e}")

        if not connected:
            err_str = cls.sanitize_error_message(str(connect_error))
            is_quota = "RESOURCE_EXHAUSTED" in err_str or "429" in err_str
            return {
                "configured": True,
                "connected": False,
                "model": active_model,
                "groundingSupported": False,
                "message": f"Gemini connection error: {err_str}",
                "quotaExhausted": is_quota,
            }

        # Step 2: Test Google Search Grounding with official tool configuration
        has_grounding = False
        grounding_chunks_count = 0
        grounding_status_note = ""

        try:
            config = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1,
            )
            g_res = client.models.generate_content(
                model=active_model,
                contents="What is the official domain of the National Portal of India?",
                config=config,
            )
            if g_res.candidates and len(g_res.candidates) > 0:
                gm = getattr(g_res.candidates[0], "grounding_metadata", None)
                if gm:
                    has_grounding = True
                    chunks = getattr(gm, "grounding_chunks", []) or []
                    grounding_chunks_count = len(chunks)
                    grounding_status_note = f"Google Search Grounding active ({grounding_chunks_count} verification chunks returned)."
        except Exception as ge:
            g_err = cls.sanitize_error_message(str(ge))
            if "RESOURCE_EXHAUSTED" in g_err or "429" in g_err:
                grounding_status_note = (
                    "Google Search Grounding returned 429 RESOURCE_EXHAUSTED. "
                    "Note: Search grounding requires a billing-enabled Google Cloud/AI Studio project. "
                    "Direct Gemini model extraction targeting official government portals (.gov.in) will be used."
                )
            else:
                grounding_status_note = f"Grounding tool note: {g_err[:120]}"

        status_msg = f"Successfully connected to Gemini API using model '{active_model}' ({latency_ms}ms). "
        if has_grounding:
            status_msg += "Google Search Grounding is active and verifying live portals."
        else:
            status_msg += grounding_status_note

        return {
            "configured": True,
            "connected": True,
            "model": active_model,
            "groundingSupported": has_grounding,
            "groundingChunksCount": grounding_chunks_count,
            "groundingStatus": grounding_status_note,
            "message": status_msg,
            "latencyMs": latency_ms,
            "quotaExhausted": False,
        }

    @classmethod
    def call_with_retry(cls, fn, max_retries: int = 3, initial_delay: float = 1.5):
        """Executes a Gemini API call with bounded retries and exponential backoff."""
        if cls.is_quota_cooling_down():
            remaining = int(cls._QUOTA_COOLDOWN_UNTIL - time.time())
            raise RuntimeError(f"RESOURCE_EXHAUSTED: Gemini API quota cooling down ({remaining}s remaining). Serving verified schemes directly from database.")

        delay = initial_delay
        last_exception = None

        for attempt in range(1, max_retries + 1):
            try:
                return fn()
            except Exception as e:
                last_exception = e
                err_str = cls.sanitize_error_message(str(e))
                is_quota = any(code in err_str for code in ["429", "RESOURCE_EXHAUSTED"])
                if is_quota:
                    if attempt < max_retries:
                        logger.warning(f"Transient quota error calling Gemini (attempt {attempt}/{max_retries}). Retrying in {delay:.2f}s: {err_str}")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    cls.set_quota_cooldown(300.0)
                    logger.warning(f"Gemini quota exhausted (429 RESOURCE_EXHAUSTED). Activated 300s cooldown. Existing database schemes are unaffected: {err_str}")
                    raise RuntimeError("RESOURCE_EXHAUSTED: Daily Gemini quota reached. Existing verified database schemes are displayed.") from e

                is_transient = any(code in err_str for code in ["503", "UNAVAILABLE", "timeout", "timed out"])

                if attempt == max_retries or not is_transient:
                    logger.error(f"Gemini API call failed permanently on attempt {attempt}/{max_retries}: {err_str}")
                    raise RuntimeError(err_str) from e

                logger.warning(f"Transient error calling Gemini (attempt {attempt}/{max_retries}). Retrying in {delay:.1f}s: {err_str}")
                time.sleep(delay)
                delay *= 2

        raise last_exception

    @classmethod
    def discover_schemes_grounded(
        cls,
        search_query: str,
        state: str = "All India",
        category: str = "All",
        department: Optional[str] = None,
        max_schemes: int = 5
    ) -> Dict[str, Any]:
        """
        Executes scheme discovery via Gemini with Google Search Grounding.
        If Google Search grounding encounters quota limits (429), seamlessly falls back
        to direct model knowledge extraction targeting verified official government portals (.gov.in, .nic.in).
        """
        if not cls.is_configured():
            return {
                "success": False,
                "schemes": [],
                "citations": [],
                "grounding_queries": [],
                "error": "GEMINI_API_KEY is not configured in backend/.env",
                "quota_exhausted": False,
            }

        if cls.is_quota_cooling_down():
            remaining = int(cls._QUOTA_COOLDOWN_UNTIL - time.time())
            return {
                "success": False,
                "schemes": [],
                "citations": [],
                "grounding_queries": [],
                "error": f"Gemini API quota cooling down ({remaining}s remaining). Existing database schemes are active.",
                "quota_exhausted": True,
            }

        client = cls.get_client()
        candidate_models = cls.get_candidate_models()

        prompt = f"""
You are an expert government welfare intelligence officer researching official Indian government schemes.
Identify genuine, verified Indian government welfare schemes matching the target parameters.

RESEARCH TARGET:
- Query: "{search_query}"
- Target Geographic Level / State: "{state}"
- Target Category: "{category}"
- Target Department: "{department or 'Any relevant Ministry / Department'}"

INSTRUCTIONS:
1. Identify up to {max_schemes} genuine, officially verified government welfare schemes matching the target.
2. For each scheme, retrieve REAL official information from official portals (e.g. *.gov.in, *.nic.in, myscheme.gov.in, state portals).
3. Provide the REAL official website URL for the scheme (e.g. ending in .gov.in or .nic.in).
4. You MUST distinguish between:
   - "scheme_status": "active" (scheme is recognized and operating), "discontinued" (scheme ended), or "unknown".
   - "application_status": "open" (current active window), "closed" (window ended), "upcoming" (not yet open), or "unknown" (if no deadline or window is explicitly verified).
5. Output your response as a valid JSON object matching the schema below.

JSON SCHEMA:
{{
  "discovered_schemes": [
    {{
      "name": "Full official name of the scheme",
      "short_name": "Official acronym e.g. PM-KISAN (or null)",
      "slug": "kebab-case-stable-slug-e.g-pm-kisan-samman-nidhi",
      "department": "Administering Ministry or Department",
      "level": "Central Scheme" or "State Scheme",
      "state": "Name of State (e.g. Maharashtra) or 'All India'",
      "category": "Agriculture / Education / Health / Women & Child / etc.",
      "benefits": "Precise financial or in-kind benefit details",
      "short_description": "1-2 sentence concise summary",
      "description": "Comprehensive explanation of objectives and provisions",
      "official_source_url": "Real official URL (e.g. https://pmkisan.gov.in/)",
      "application_url": "Direct application or portal URL (or null)",
      "application_process": "Step-by-step application instructions (or null)",
      "scheme_status": "active" | "discontinued" | "unknown",
      "application_status": "open" | "closed" | "upcoming" | "unknown",
      "application_deadline": "YYYY-MM-DD" (or null if open indefinitely),
      "age_min": integer or null,
      "age_max": integer or null,
      "income_max": float ceiling or null,
      "occupation": "Eligible occupations (e.g. Farmer, Student, Artisan) or null",
      "education": "Required education qualification or null",
      "gender": "All" | "Female" | "Male" | "Transgender",
      "social_category": "All" | "SC" | "ST" | "OBC" | "General" | "Minority",
      "is_farmer_only": boolean,
      "max_landholding_acres": float or null,
      "is_student_only": boolean,
      "is_business_only": boolean,
      "is_disability_required": boolean,
      "exclusions": ["List of excluded beneficiary types if any"],
      "required_documents": ["List of mandatory documents e.g. Aadhaar, 7/12 Land Record"],
      "verification_evidence": "Exact excerpt from the official source confirming existence, eligibility, and status"
    }}
  ]
}}

Return ONLY valid JSON.
"""

        response = None
        has_grounding = False
        citations = []
        grounding_queries = []
        last_error = None
        used_model = candidate_models[0]

        # Phase A: Try with Google Search Grounding across candidate models
        for model in candidate_models:
            try:
                config_grounded = types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.1,
                    response_modalities=["TEXT"],
                )
                logger.info(f"Attempting grounded scheme discovery with model '{model}'...")
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config_grounded,
                )
                used_model = model
                has_grounding = True
                break
            except Exception as e:
                err_str = cls.sanitize_error_message(str(e))
                last_error = e
                logger.warning(f"Grounded search with model '{model}' failed: {err_str[:120]}")
                # If search tool quota exhausted or model 503, try next or switch to direct model
                if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str or "quota" in err_str.lower():
                    logger.info("Search tool quota exhausted; falling back to direct model knowledge generation.")
                    break

        # Phase B: Fallback to direct Gemini generation without search tool if Phase A failed
        if response is None:
            for model in candidate_models:
                for attempt in range(2):
                    try:
                        logger.info(f"Attempting direct scheme extraction with model '{model}' (attempt {attempt+1})...")
                        config_direct = types.GenerateContentConfig(
                            temperature=0.1,
                            response_modalities=["TEXT"],
                        )
                        response = client.models.generate_content(
                            model=model,
                            contents=prompt,
                            config=config_direct,
                        )
                        used_model = model
                        break
                    except Exception as e:
                        last_error = e
                        err_text = str(e)
                        logger.warning(f"Direct extraction attempt with model '{model}' failed: {err_text[:120]}")
                        if ("503" in err_text or "UNAVAILABLE" in err_text) and attempt == 0:
                            time.sleep(1.5)
                            continue
                        break
                if response is not None:
                    break

        if response is None:
            err_str = cls.sanitize_error_message(str(last_error))
            is_quota = "RESOURCE_EXHAUSTED" in err_str or "429" in err_str
            if is_quota:
                cls.set_quota_cooldown(300.0)
            return {
                "success": False,
                "schemes": [],
                "citations": [],
                "grounding_queries": [],
                "error": err_str,
                "quota_exhausted": is_quota,
            }

        # Extract raw text
        raw_text = cls.extract_text_from_response(response)

        # Extract citations from Grounding Metadata if present
        if response.candidates and len(response.candidates) > 0:
            gm = getattr(response.candidates[0], "grounding_metadata", None)
            if gm:
                queries = getattr(gm, "web_search_queries", []) or []
                grounding_queries = [str(q) for q in queries]
                chunks = getattr(gm, "grounding_chunks", []) or []
                for chunk in chunks:
                    web = getattr(chunk, "web", None)
                    if web:
                        citations.append({
                            "title": getattr(web, "title", "Official Portal"),
                            "url": getattr(web, "uri", ""),
                            "excerpt": getattr(chunk, "title", "")
                        })

        # Parse JSON from model output
        clean_json_str = raw_text.strip()
        if "```json" in clean_json_str:
            clean_json_str = clean_json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json_str:
            clean_json_str = clean_json_str.split("```")[1].split("```")[0].strip()

        parsed = {}
        try:
            parsed = json.loads(clean_json_str)
        except json.JSONDecodeError as jde:
            logger.warning(f"Failed to parse JSON directly from Gemini: {jde}. Attempting regex extraction.")
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except Exception:
                    pass

        schemes = parsed.get("discovered_schemes", [])

        # If search citations were empty (e.g. in direct fallback mode), synthesize citations from official URLs
        if not citations and schemes:
            for s in schemes:
                u = s.get("official_source_url") or s.get("officialUrl")
                if u and u.startswith("http"):
                    citations.append({
                        "title": s.get("department") or s.get("name") or "Official Government Portal",
                        "url": u,
                        "excerpt": s.get("verification_evidence") or s.get("short_description") or ""
                    })

        return {
            "success": True,
            "schemes": schemes,
            "citations": citations,
            "grounding_queries": grounding_queries,
            "grounding_mode": "google_search" if has_grounding else "official_direct",
            "model": used_model,
            "model_used": used_model,
            "raw_text": raw_text[:500],
            "error": None,
            "quota_exhausted": False,
        }

    @classmethod
    def evaluate_schemes_for_profile(
        cls,
        profile_data: Dict[str, Any],
        candidate_schemes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Dynamically analyzes and evaluates database candidate schemes against the citizen's actual profile,
        including custom occupations (e.g. Teacher, Housewife, Shopkeeper, or any custom role) and educations.
        
        Strict Rules:
        - Receives actual values (never 'Other').
        - Does NOT hardcode responses for individual occupations.
        - Excludes schemes that conflict with citizen's occupation or eligibility (e.g. farmer schemes for non-farmers).
        - Distinguishes 'eligible', 'possibly_eligible', 'not_eligible'.
        - Provides transparent human-readable explanations.
        - Returns structured dictionary keyed by scheme_id for easy integration.
        """
        if not candidate_schemes:
            return {"evaluations": {}}

        if not cls.is_configured() or not GENAI_AVAILABLE:
            return {"evaluations": {}, "source": "gemini_unconfigured"}

        client = cls.get_client()
        candidate_models = cls.get_candidate_models()

        actual_occ = profile_data.get("occupation") or "Citizen"
        actual_edu = profile_data.get("education") or "Not specified"
        actual_state = profile_data.get("state") or "All India"
        actual_age = profile_data.get("age") or "Not specified"
        actual_income = profile_data.get("annualIncome") or profile_data.get("annual_income") or "Not specified"
        actual_cat = profile_data.get("category") or profile_data.get("social_category") or "General"
        actual_gender = profile_data.get("gender") or "Not specified"

        # Safe debug logging for Gemini Prompt profile (Requirement 7)
        logger.info(f"[GEMINI PROMPT INPUT] Occupation: '{actual_occ}', Education: '{actual_edu}', State: '{actual_state}', Age: '{actual_age}', Income: '{actual_income}'")

        # Format candidates concisely to keep tokens compact and inference fast
        condensed_candidates = []
        for s in candidate_schemes:
            condensed_candidates.append({
                "id": s.get("id"),
                "name": s.get("name"),
                "category": s.get("category"),
                "target_occupations": s.get("target_occupations") or s.get("targetOccupations"),
                "state": s.get("state"),
                "age_min": s.get("age_min") or s.get("ageMin"),
                "age_max": s.get("age_max") or s.get("ageMax"),
                "income_max": s.get("income_max") or s.get("incomeMax"),
                "is_farmer_only": s.get("is_farmer_only") or s.get("isFarmerOnly") or False,
                "is_student_only": s.get("is_student_only") or s.get("isStudentOnly") or False,
                "is_business_only": s.get("is_business_only") or s.get("isBusinessOnly") or False,
                "gender": s.get("gender") or "All",
                "department": s.get("department"),
            })

        prompt = f"""
You are an expert Government Welfare Eligibility & Scheme Matching Officer in India.
Your mission is to evaluate candidate government welfare schemes from our official database against this citizen's real profile.

CITIZEN PROFILE:
- Actual Occupation: {actual_occ}
- Actual Education / Qualification: {actual_edu}
- State of Residence: {actual_state}
- Age: {actual_age}
- Annual Family Income: {actual_income}
- Social Category: {actual_cat}
- Gender: {actual_gender}

MATCHING & ELIGIBILITY EVALUATION RULES:
1. Gender Eligibility Rules:
   - Occupations like Student, Farmer, Teacher, Shopkeeper, etc., can be either male or female. Do NOT classify these occupations as belonging to only one gender.
   - For a Male citizen: show male-specific schemes and schemes open to all genders. NEVER show female-exclusive schemes to male citizens.
   - For a Female citizen: show female-specific schemes and schemes open to all genders. NEVER show male-exclusive schemes to female citizens.
   - Schemes open to all genders (gender="All" or "Any" or unspecified) MUST remain eligible for both male and female citizens. Do NOT invent gender restrictions or exclude schemes based on missing or neutral gender metadata.
2. Dynamic Occupation Relevance:
   - Identify schemes that are genuinely relevant to the citizen's actual occupation ("{actual_occ}") or universal citizen welfare categories (e.g. general public health, family welfare, skilling).
   - If citizen is a Student ("{actual_occ}"), they ARE eligible for student scholarships, fellowships, and student education financing schemes (such as PM Vidyalakshmi, Post Matric Scholarship) regardless of qualification level.
   - If citizen is a Farmer ("{actual_occ}"), they ARE eligible for farmer support, crop insurance, and agri schemes.
   - STRICTLY EXCLUDE schemes for unrelated occupational domains:
     * Non-farmers (e.g. pure Student, Teacher, Housewife, Shopkeeper) MUST NOT receive farmer-only schemes unless they explicitly operate an agricultural business.
     * Non-students (e.g. Teacher, Farmer, Housewife, Shopkeeper) MUST NOT receive student-only scholarships or student stipends.
     * Non-business owners (e.g. pure students or salaried workers with no commercial business) MUST NOT receive enterprise-only business loan schemes.
   - For custom occupations (e.g. Teacher, Housewife, Shopkeeper, Nurse, Driver):
     * Reason dynamically about their role and beneficiary group:
       - Teacher / Academic: salaried/employee/professional; eligible for teacher training, public welfare, state health coverage, adult skilling, but NOT farmer subsidies or school student scholarships.
       - Housewife / Homemaker: women & family welfare, health insurance, livelihood training; NOT farmer-only or student scholarships.
       - Shopkeeper: small business, MSME, trade, self-employed credit/skilling schemes, health schemes; NOT student scholarships.
3. Official Eligibility Verification:
   - Verify if the citizen satisfies the available criteria (age limits, income limits, state domicile, gender, target group).
   - Distinguish between 3 distinct statuses:
     * "eligible": Citizen appears fully eligible based on available information and meets all mandatory conditions.
     * "possibly_eligible": Citizen is a matching beneficiary and no mandatory condition is failed, but some conditions or documents require additional verification.
     * "not_eligible": Citizen does NOT meet mandatory eligibility (wrong occupation, age/income disqualified, or outside eligible state).
4. Be strictly factual. Do NOT invent gender restrictions or override verified scheme eligibility.

CANDIDATE SCHEMES:
{json.dumps(condensed_candidates, indent=2)}

OUTPUT REQUIREMENT:
Output a single valid JSON object with the "evaluations" array matching this exact schema:
{{
  "evaluations": [
    {{
      "scheme_id": <int>,
      "is_relevant": <true or false>,
      "eligibility_status": "eligible" | "possibly_eligible" | "not_eligible",
      "match_score": <integer 0 to 100>,
      "match_reason": "<1 concise sentence explaining relevance to citizen's actual occupation and profile>",
      "why_matched": "<2-3 sentences explaining why citizen is seeing this scheme and how profile details map to criteria>",
      "rejection_reason": "<Clear reason if is_relevant is false or status is not_eligible, else null>"
    }}
  ]
}}
"""

        evaluations_dict = {}
        for model in candidate_models:
            try:
                config = types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                )
                logger.info(f"Calling Gemini ({model}) for dynamic scheme evaluation against occupation '{actual_occ}'...")
                res = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config
                )
                txt = cls.extract_text_from_response(res).strip()
                if txt:
                    data = json.loads(txt)
                    raw_evals = data.get("evaluations", [])
                    for ev in raw_evals:
                        s_id = ev.get("scheme_id")
                        if s_id is not None:
                            evaluations_dict[s_id] = ev
                    logger.info(f"Gemini dynamic scheme evaluation succeeded: {len(evaluations_dict)} evaluations parsed.")
                    return {
                        "evaluations": evaluations_dict,
                        "source": "gemini_dynamic_evaluation",
                        "model": model
                    }
            except Exception as e:
                err_str = cls.sanitize_error_message(str(e))
                logger.warning(f"Gemini evaluation with model '{model}' failed: {err_str[:120]}")

        return {"evaluations": {}, "source": "gemini_failed_fallback"}

    @classmethod
    def generate_grounded_explanation(
        cls,
        scheme_data: Dict[str, Any],
        profile_data: Optional[Dict[str, Any]] = None,
        eval_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Translates deterministic eligibility outcomes into a user-friendly citizen explanation.
        Strict rule: Does NOT invent benefits or override the deterministic engine decision.
        """
        profile_data = profile_data or {}
        eval_result = eval_result or {}
        status = eval_result.get("eligibility_status") or eval_result.get("status") or "unknown"
        match_score = eval_result.get("match_score", 100)
        satisfied = eval_result.get("requirements_satisfied", [])
        not_satisfied = eval_result.get("requirements_not_satisfied", [])
        missing_info = eval_result.get("missing_information", [])
        official_url = scheme_data.get("officialUrl") or scheme_data.get("official_source_url") or "https://myscheme.gov.in"

        if not cls.is_configured() or not GENAI_AVAILABLE:
            fallback_text = (
                f"**Eligibility Result: {status.replace('_', ' ').title()} ({match_score}%)**\n\n"
                f"- **Verified Scheme:** {scheme_data.get('name', 'Government Scheme')}\n"
                f"- **Key Benefits:** {scheme_data.get('benefits', 'Financial or educational welfare support.')}\n"
                f"- **Department:** {scheme_data.get('department', 'Government of India')}\n"
            )
            if satisfied:
                fallback_text += f"- **Satisfied Conditions:** {'; '.join(satisfied[:3])}\n"
            if not_satisfied:
                fallback_text += f"- **Unmet Requirements:** {'; '.join(not_satisfied[:2])}\n"
            if missing_info:
                fallback_text += f"- **Missing Information to Confirm:** {'; '.join(missing_info[:2])}\n"
            fallback_text += f"\n*Please verify your application details on the [Official Portal]({official_url}).*"

            return {
                "explanation": fallback_text,
                "source": "deterministic_engine_fallback",
                "citations": [{"title": "Official Portal", "url": official_url}]
            }

        client = cls.get_client()
        candidate_models = cls.get_candidate_models()

        prompt = f"""
You are an empathetic, highly accurate Citizen Welfare Assistant for Yojana Hunter in India.
Explain the eligibility matching result for this citizen in simple, encouraging, respectful language.

STRICT ACCURACY RULES:
1. You MUST uphold the Deterministic Match Decision: "{status.upper()}". Do NOT override or change this decision.
2. Only reference facts provided in the SCHEME DATA. Never invent deadlines, grants, or criteria.
3. If criteria were not satisfied or information was missing, explain what the citizen needs to complete.
4. Keep the explanation concise (2 short paragraphs max).

SCHEME DATA:
- Name: {scheme_data.get('name')}
- Benefits: {scheme_data.get('benefits')}
- Department: {scheme_data.get('department')}
- Official URL: {official_url}
- Application Status: {scheme_data.get('applicationStatus') or scheme_data.get('application_status')}

CITIZEN PROFILE:
- Occupation: {profile_data.get('occupation')}
- Education: {profile_data.get('education')}
- State: {profile_data.get('state')}
- Age: {profile_data.get('age')}
- Income: {profile_data.get('annualIncome') or profile_data.get('annual_income')}
- Category: {profile_data.get('category')}
- Gender: {profile_data.get('gender')}

DETERMINISTIC EVALUATION:
- Status: {status}
- Match Score: {match_score}%
- Satisfied Criteria: {satisfied}
- Unsatisfied Criteria: {not_satisfied}
- Missing Information: {missing_info}
"""

        for model in candidate_models:
            try:
                config = types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=300,
                )
                res = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                txt = cls.extract_text_from_response(res).strip()
                if txt:
                    return {
                        "explanation": txt,
                        "source": "gemini_grounded",
                        "citations": [{"title": "Official Scheme Portal", "url": official_url}] if official_url else []
                    }
            except Exception as e:
                logger.warning(f"Failed to generate Gemini explanation with model '{model}': {e}")

        # Deterministic fallback if all model calls fail
        fallback_text = (
            f"**Eligibility Status: {status.replace('_', ' ').title()} ({match_score}%)**\n\n"
            f"Based on the official criteria for **{scheme_data.get('name')}**, your profile matches "
            f"{len(satisfied)} mandatory conditions. "
        )
        if not_satisfied:
            fallback_text += f"The following requirement is not currently met: {not_satisfied[0]}. "
        if missing_info:
            fallback_text += f"To verify full qualification, please complete: {', '.join(missing_info)}. "

        return {
            "explanation": fallback_text,
            "source": "deterministic_fallback_on_error",
            "citations": [{"title": "Official Portal", "url": official_url}]
        }
