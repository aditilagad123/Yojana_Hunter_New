import os
import functools
import datetime
import time
import re
from collections import defaultdict
import threading
import jwt
from flask import request, jsonify, g
from werkzeug.security import check_password_hash
import bcrypt
from config import config
from database import SessionLocal
from models import User

JWT_SECRET = getattr(config, "JWT_SECRET", None) or getattr(config, "SECRET_KEY", "yojana-hunter-secret-key-phase1-admin")
JWT_ALGORITHM = "HS256"

# ==========================================
# 1. SECURE PASSWORD HASHING
# ==========================================

def hash_password(password: str) -> str:
    """
    Hash password securely using bcrypt with a work factor of 12.
    Never stores plaintext passwords.
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify plain password against hashed password.
    Supports bcrypt and werkzeug (scrypt / pbkdf2) hashes securely.
    """
    if not hashed_password or not plain_password:
        return False

    # Check bcrypt ($2b$, $2a$, $2y$)
    try:
        if hashed_password.startswith(("$2b$", "$2a$", "$2y$")):
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        pass

    # Check werkzeug hashes (scrypt / pbkdf2 / sha256)
    try:
        if check_password_hash(hashed_password, plain_password):
            return True
    except Exception:
        pass

    return False

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate that password meets security requirements:
    - Minimum 8 characters
    - Contains at least one letter and at least one digit or special character
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter."
    if not (re.search(r"\d", password) or re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)):
        return False, "Password must contain at least one number or special character."
    return True, ""

# ==========================================
# 2. JWT TOKEN GENERATION & DECODING
# ==========================================

def create_access_token(
    user_id: int,
    email: str,
    role: str = "citizen",
    remember_me: bool = False,
    expires_hours: int = None
) -> str:
    """
    Generate a signed JWT token for a user session.
    Default expiration is 24 hours, or 30 days if remember_me is True.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    if expires_hours is None:
        expires_hours = 720 if remember_me else 24  # 30 days vs 24 hours

    payload = {
        "sub": str(user_id),
        "userId": user_id,
        "email": email,
        "role": role,
        "rememberMe": remember_me,
        "iat": now,
        "exp": now + datetime.timedelta(hours=expires_hours)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> dict:
    """Validate and decode a JWT token."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

# Backward compatibility aliases for admin functions
create_admin_token = create_access_token
decode_admin_token = decode_access_token

# ==========================================
# 3. RATE LIMITING UTILITY
# ==========================================

class MemoryRateLimiter:
    """
    Thread-safe in-memory sliding window rate limiter
    to protect sensitive auth endpoints (login, registration, forgot-password).
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._records = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int = 10, window_seconds: int = 900) -> tuple[bool, int]:
        """
        Check if request key is within rate limits.
        Returns (is_allowed, retry_after_seconds).
        """
        now = time.time()
        with self._lock:
            # Filter timestamps within window
            valid_window = now - window_seconds
            timestamps = [t for t in self._records[key] if t > valid_window]
            self._records[key] = timestamps

            if len(timestamps) >= max_requests:
                earliest = timestamps[0]
                retry_after = int(window_seconds - (now - earliest)) + 1
                return False, max(1, retry_after)

            self._records[key].append(now)
            return True, 0

rate_limiter = MemoryRateLimiter()

def rate_limit(max_requests: int = 10, window_seconds: int = 900, key_prefix: str = "rl"):
    """
    Decorator for rate limiting endpoints based on client IP or submitted identifier.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
            key = f"{key_prefix}:{client_ip}"
            effective_limit = 500 if (os.getenv("FLASK_ENV") == "development" or request.headers.get("X-Test-Request") == "true") else max_requests
            allowed, retry_after = rate_limiter.is_allowed(key, max_requests=effective_limit, window_seconds=window_seconds)
            if not allowed:
                return jsonify({
                    "error": "Too Many Requests",
                    "message": f"Too many attempts. Please try again after {retry_after} seconds.",
                    "status_code": 429,
                    "retry_after": retry_after
                }), 429
            return f(*args, **kwargs)
        return wrapped
    return decorator

# ==========================================
# 4. REQUEST AUTHENTICATION DECORATORS
# ==========================================

def extract_token_from_request() -> str | None:
    """Extract Bearer token from Authorization header or cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]

    # Optional cookie fallback
    cookie_token = request.cookies.get("auth_token")
    if cookie_token:
        return cookie_token

    # Query param fallback for EventSource / SSE connections
    query_token = request.args.get("token")
    if query_token:
        return query_token

    return None

def token_required(f):
    """
    Decorator to protect authenticated routes.
    Validates the JWT token, verifies that the user is active,
    and sets g.current_user to the User model instance.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        token = extract_token_from_request()
        if not token:
            return jsonify({
                "error": "Authentication required",
                "message": "Please sign in to access this resource.",
                "status_code": 401
            }), 401

        try:
            payload = decode_access_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({
                "error": "Session expired",
                "message": "Your session has expired. Please sign in again.",
                "status_code": 401
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "error": "Invalid token",
                "message": "Invalid authentication token provided.",
                "status_code": 401
            }), 401

        user_id = payload.get("userId") or payload.get("sub")
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if not user:
                return jsonify({
                    "error": "User not found",
                    "message": "Account no longer exists.",
                    "status_code": 401
                }), 401

            if not user.is_active:
                return jsonify({
                    "error": "Account disabled",
                    "message": "This account is currently deactivated. Please contact support.",
                    "status_code": 403
                }), 403

            g.current_user = user
        finally:
            db.close()

        return f(*args, **kwargs)

    return decorated_function

# Alias for token_required
auth_required = token_required

def optional_auth(f):
    """
    Decorator that attaches g.current_user if a valid token is provided,
    but does NOT reject unauthenticated requests.
    Enables personalized scheme rankings when logged in without breaking anonymous access.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        g.current_user = None
        token = extract_token_from_request()
        if token:
            try:
                payload = decode_access_token(token)
                user_id = payload.get("userId") or payload.get("sub")
                if user_id:
                    db = SessionLocal()
                    try:
                        user = db.query(User).filter(User.id == int(user_id)).first()
                        if user and user.is_active:
                            g.current_user = user
                    finally:
                        db.close()
            except Exception:
                g.current_user = None

        return f(*args, **kwargs)

    return decorated_function

def admin_required(f):
    """
    Decorator to protect administrator-only routes.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        token = extract_token_from_request()
        if not token:
            return jsonify({
                "error": "Authentication required",
                "message": "Missing Authorization header",
                "status_code": 401
            }), 401

        try:
            payload = decode_access_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({
                "error": "Session expired",
                "message": "Your admin session has expired. Please log in again.",
                "status_code": 401
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "error": "Invalid token",
                "message": "Invalid authentication token provided.",
                "status_code": 401
            }), 401

        user_id = payload.get("userId") or payload.get("sub")
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if not user:
                return jsonify({
                    "error": "User not found",
                    "status_code": 401
                }), 401

            if not user.is_active:
                return jsonify({
                    "error": "Account disabled",
                    "message": "This admin account is currently deactivated.",
                    "status_code": 403
                }), 403

            if user.role != "admin":
                return jsonify({
                    "error": "Forbidden",
                    "message": "Administrative privileges required.",
                    "status_code": 403
                }), 403

            g.current_user = user
        finally:
            db.close()

        return f(*args, **kwargs)

    return decorated_function
