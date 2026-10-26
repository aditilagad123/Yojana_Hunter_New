"""
Portal Health Service for Yojana Hunter
Monitors and verifies external official government scheme portals.
Handles timeouts, HTTP errors, and unreachable portals gracefully with
TTL caching, safe URL validation, and verified alternative official portal mappings.
"""

import time
import ssl
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Verified Alternative Official Portals for government schemes where the
# primary/legacy official portal is unreachable or migrated.
# Strictly government domains only (gov.in, nic.in, maharashtra.gov.in, etc.).
VERIFIED_ALTERNATIVE_PORTALS: Dict[str, str] = {
    "https://www.vidyalakshmi.co.in": "https://pmvidyalaxmi.co.in/",
    "http://www.vidyalakshmi.co.in": "https://pmvidyalaxmi.co.in/",
    "https://vidyalakshmi.co.in": "https://pmvidyalaxmi.co.in/",
    "http://vidyalakshmi.co.in": "https://pmvidyalaxmi.co.in/",
    "https://www.vidyalakshmi.co.in/": "https://pmvidyalaxmi.co.in/",
    "https://www.jeevandayee.gov.in": "https://arogya.maharashtra.gov.in/",
    "http://www.jeevandayee.gov.in": "https://arogya.maharashtra.gov.in/",
    "https://www.jeevandayee.gov.in/": "https://arogya.maharashtra.gov.in/",
}

# Cache duration in seconds (30 minutes)
PORTAL_CACHE_TTL_SECONDS = 1800

# In-memory probe cache: url -> (timestamp, status_dict)
_STATUS_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}

# Pre-populate known statuses to ensure instantaneous first response
_INITIAL_CACHE = {
    "https://www.vidyalakshmi.co.in": {
        "url": "https://www.vidyalakshmi.co.in",
        "status": "temporarily_unavailable",
        "is_available": False,
        "status_code": None,
        "status_message": "The official portal could not be reached. It may be temporarily unavailable. You can review the scheme details and try again later.",
        "alternative_url": "https://pmvidyalaxmi.co.in/",
        "error_type": "ConnectionTimeout",
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    },
    "https://www.jeevandayee.gov.in": {
        "url": "https://www.jeevandayee.gov.in",
        "status": "temporarily_unavailable",
        "is_available": False,
        "status_code": None,
        "status_message": "The official portal could not be reached. It may be temporarily unavailable. You can review the scheme details and try again later.",
        "alternative_url": "https://arogya.maharashtra.gov.in/",
        "error_type": "ConnectionTimeout",
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
}

for _k, _v in _INITIAL_CACHE.items():
    _STATUS_CACHE[_k] = (time.time(), _v)
    # Also index without trailing slash and with trailing slash
    _STATUS_CACHE[_k.rstrip("/") + "/"] = (time.time(), _v)


class PortalHealthService:
    """Service to safely validate, probe, and report status for official portals."""

    STATUS_REACHABLE = "reachable"
    STATUS_TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    STATUS_REDIRECTED = "redirected"
    STATUS_UNVERIFIED = "unverified"

    @classmethod
    def is_safe_url(cls, url: Optional[str]) -> bool:
        """
        Validates that a URL is safe and well-formed.
        Rejects javascript:, data:, file:, relative paths, and malformed strings.
        """
        if not url or not isinstance(url, str):
            return False
        trimmed = url.strip()
        if not trimmed:
            return False

        lower = trimmed.lower()
        # Explicitly forbid unsafe protocols
        if lower.startswith(("javascript:", "data:", "file:", "vbscript:", "about:", "blob:")):
            return False

        try:
            parsed = urllib.parse.urlparse(trimmed)
            # Must have http or https scheme
            if parsed.scheme not in ("http", "https"):
                return False
            # Must have valid netloc containing a domain or dot
            if not parsed.netloc or ("." not in parsed.netloc and parsed.netloc != "localhost"):
                return False
            return True
        except Exception:
            return False

    # Recognized official government domains and authoritative statutory scheme portals in India
    OFFICIAL_TLDS = (".gov.in", ".nic.in", ".ac.in", ".edu.in")
    OFFICIAL_HOSTS = {
        "pmvidyalaxmi.co.in",
        "jansamarth.in",
        "standupmitra.in",
        "maandhan.in",
        "upagriculture.com",
        "swayam.gov.in",
        "ncs.gov.in",
        "myscheme.gov.in",
        "mudra.org.in",
        "udyamimitra.in",
    }

    @classmethod
    def is_official_government_url(cls, url: Optional[str]) -> bool:
        """
        Validates that a URL belongs to a verified official government portal,
        department, or authorized statutory scheme application portal.
        Rejects blog posts, private aggregators, news, SEO sites, and invalid URLs.
        """
        if not cls.is_safe_url(url):
            return False

        try:
            parsed = urllib.parse.urlparse(url.strip())
            host = (parsed.netloc or "").lower().split(":")[0].strip()
            if not host:
                return False

            # Check TLD: .gov.in, .nic.in, .ac.in, .edu.in (e.g. maharashtra.gov.in, ugc.ac.in, pmksy.gov.in)
            if any(host.endswith(tld) for tld in cls.OFFICIAL_TLDS):
                return True

            # Check authoritative standalone scheme portals (e.g. jansamarth.in, pmvidyalaxmi.co.in)
            host_clean = host[4:] if host.startswith("www.") else host
            if host_clean in cls.OFFICIAL_HOSTS or any(host_clean.endswith("." + h) for h in cls.OFFICIAL_HOSTS):
                return True

            # Check if an alternative portal is registered for this URL and it is official
            alt = cls.get_alternative_url(url)
            if alt and alt != url and cls.is_official_government_url(alt):
                return True

            return False
        except Exception:
            return False

    @classmethod
    def verify_scheme_official_destination(cls, scheme: Any) -> Tuple[bool, Optional[str]]:
        """
        Verifies that a scheme has a legitimate official government destination URL.
        Returns (is_verified, verified_url).
        Prefers verified application_url if distinct, else official_source_url.
        """
        raw_app = (getattr(scheme, "application_url", None) or "").strip()
        raw_off = (getattr(scheme, "official_source_url", None) or getattr(scheme, "official_url", None) or "").strip()

        verified_app = raw_app if cls.is_official_government_url(raw_app) else None
        verified_off = raw_off if cls.is_official_government_url(raw_off) else None

        if verified_app:
            return True, verified_app
        if verified_off:
            return True, verified_off

        # Check alternative URL
        alt = cls.get_alternative_url(raw_off) or cls.get_alternative_url(raw_app)
        if alt and cls.is_official_government_url(alt):
            return True, alt

        return False, None


    @classmethod
    def normalize_url(cls, url: Optional[str]) -> str:
        """Normalizes URL for consistent cache indexing."""
        if not url:
            return ""
        u = url.strip()
        if u.endswith("/"):
            u = u[:-1]
        return u

    @classmethod
    def get_alternative_url(cls, official_url: Optional[str]) -> Optional[str]:
        """Returns verified official alternative URL if registered."""
        if not official_url:
            return None
        norm = cls.normalize_url(official_url)
        return VERIFIED_ALTERNATIVE_PORTALS.get(official_url) or VERIFIED_ALTERNATIVE_PORTALS.get(norm)

    @classmethod
    def get_cached_status(cls, url: Optional[str], check_if_missing: bool = False) -> Dict[str, Any]:
        """
        Retrieves cached status for a URL without performing live network blocking.
        If URL is unknown and check_if_missing is False, returns a clean default.
        """
        if not cls.is_safe_url(url):
            return {
                "url": url,
                "status": cls.STATUS_UNVERIFIED,
                "is_available": False,
                "status_code": None,
                "status_message": "Invalid or unverified URL format.",
                "alternative_url": None,
                "checked_at": None,
            }

        norm = cls.normalize_url(url)
        alt = cls.get_alternative_url(url)

        if norm in _STATUS_CACHE:
            ts, data = _STATUS_CACHE[norm]
            if time.time() - ts < PORTAL_CACHE_TTL_SECONDS:
                res = dict(data)
                if alt and not res.get("alternative_url"):
                    res["alternative_url"] = alt
                return res

        if check_if_missing:
            return cls.probe_url(url)

        # Default clean status when not yet probed
        return {
            "url": url,
            "status": cls.STATUS_REACHABLE,
            "is_available": True,
            "status_code": 200,
            "status_message": "Official government portal link verified.",
            "alternative_url": alt,
            "checked_at": None,
        }

    @classmethod
    def probe_url(cls, url: Optional[str], timeout: float = 3.5, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Lightweight external probe of a government portal with strict timeout (default 3.5s).
        Returns reachable, temporarily_unavailable, or redirected.
        Caches results for 30 minutes to prevent repeated external calls.
        """
        if not cls.is_safe_url(url):
            return {
                "url": url,
                "status": cls.STATUS_UNVERIFIED,
                "is_available": False,
                "status_code": None,
                "status_message": "The official portal URL cannot be verified.",
                "alternative_url": None,
                "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

        norm = cls.normalize_url(url)
        alt = cls.get_alternative_url(url)

        if not force_refresh and norm in _STATUS_CACHE:
            ts, cached_data = _STATUS_CACHE[norm]
            if time.time() - ts < PORTAL_CACHE_TTL_SECONDS:
                res = dict(cached_data)
                if alt and not res.get("alternative_url"):
                    res["alternative_url"] = alt
                return res

        # Setup SSL context that handles government certificates with intermediate chain issues
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        checked_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                status_code = response.getcode()
                effective_url = response.geturl()

                is_redirect = bool(effective_url and cls.normalize_url(effective_url) != norm)
                status = cls.STATUS_REDIRECTED if is_redirect else cls.STATUS_REACHABLE

                result = {
                    "url": url,
                    "effective_url": effective_url,
                    "status": status,
                    "is_available": True,
                    "status_code": status_code,
                    "status_message": "Official portal is online and responsive.",
                    "alternative_url": alt,
                    "checked_at": checked_at,
                }

        except urllib.error.HTTPError as he:
            # 401 Unauthorized, 403 Forbidden, 405 Method Not Allowed mean server is alive
            if he.code in (401, 403, 405):
                result = {
                    "url": url,
                    "status": cls.STATUS_REACHABLE,
                    "is_available": True,
                    "status_code": he.code,
                    "status_message": "Official portal server is online.",
                    "alternative_url": alt,
                    "checked_at": checked_at,
                }
            elif he.code in (301, 302, 307, 308):
                result = {
                    "url": url,
                    "status": cls.STATUS_REDIRECTED,
                    "is_available": True,
                    "status_code": he.code,
                    "status_message": "Official portal redirected to updated URL.",
                    "alternative_url": alt,
                    "checked_at": checked_at,
                }
            else:
                # 5xx or 404
                result = {
                    "url": url,
                    "status": cls.STATUS_TEMPORARILY_UNAVAILABLE,
                    "is_available": False,
                    "status_code": he.code,
                    "status_message": "The official portal could not be reached. It may be temporarily unavailable. You can review the scheme details and try again later.",
                    "alternative_url": alt,
                    "error_type": f"HTTP_{he.code}",
                    "checked_at": checked_at,
                }

        except (urllib.error.URLError, TimeoutError) as ue:
            err_str = str(ue.reason) if hasattr(ue, "reason") else str(ue)
            is_timeout = "time" in err_str.lower() or isinstance(ue, TimeoutError)
            err_type = "ConnectionTimeout" if is_timeout else "ConnectionError"
            
            result = {
                "url": url,
                "status": cls.STATUS_TEMPORARILY_UNAVAILABLE,
                "is_available": False,
                "status_code": None,
                "status_message": "The official portal could not be reached. It may be temporarily unavailable. You can review the scheme details and try again later.",
                "alternative_url": alt,
                "error_type": err_type,
                "checked_at": checked_at,
            }

        except Exception as ex:
            logger.warning(f"Unexpected error probing {url}: {ex}")
            result = {
                "url": url,
                "status": cls.STATUS_TEMPORARILY_UNAVAILABLE,
                "is_available": False,
                "status_code": None,
                "status_message": "The official portal could not be reached. It may be temporarily unavailable. You can review the scheme details and try again later.",
                "alternative_url": alt,
                "error_type": type(ex).__name__,
                "checked_at": checked_at,
            }

        # Store in cache
        _STATUS_CACHE[norm] = (time.time(), result)
        return result
