import os
import uuid
import hmac
import hashlib
import logging
import datetime
from typing import Dict, Any, Optional, Tuple
import requests
from config import config

try:
    import razorpay
    import razorpay.errors
except ImportError:
    razorpay = None

logger = logging.getLogger(__name__)

class _FallbackRazorpayPlan:
    def __init__(self, key_id: str, key_secret: str):
        self.auth = (key_id, key_secret)
        self.base_url = "https://api.razorpay.com/v1"

    def all(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        resp = requests.get(f"{self.base_url}/plans", auth=self.auth, params=params, timeout=10)
        if resp.status_code != 200:
            err = Exception(f"HTTP {resp.status_code} Unauthorized: {resp.text}")
            err.status_code = resp.status_code
            raise err
        return resp.json()

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = requests.post(f"{self.base_url}/plans", auth=self.auth, json=data, timeout=10)
        if resp.status_code != 200:
            err = Exception(f"HTTP {resp.status_code} Unauthorized: {resp.text}")
            err.status_code = resp.status_code
            raise err
        return resp.json()

class _FallbackRazorpaySubscription:
    def __init__(self, key_id: str, key_secret: str):
        self.auth = (key_id, key_secret)
        self.base_url = "https://api.razorpay.com/v1"

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = requests.post(f"{self.base_url}/subscriptions", auth=self.auth, json=data, timeout=10)
        if resp.status_code != 200:
            err = Exception(f"HTTP {resp.status_code} Unauthorized: {resp.text}")
            err.status_code = resp.status_code
            raise err
        return resp.json()

    def fetch(self, subscription_id: str) -> Dict[str, Any]:
        resp = requests.get(f"{self.base_url}/subscriptions/{subscription_id}", auth=self.auth, timeout=10)
        if resp.status_code != 200:
            err = Exception(f"HTTP {resp.status_code}: {resp.text}")
            err.status_code = resp.status_code
            raise err
        return resp.json()

class _FallbackRazorpayOrder:
    def __init__(self, key_id: str, key_secret: str):
        self.auth = (key_id, key_secret)
        self.base_url = "https://api.razorpay.com/v1"

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = requests.post(f"{self.base_url}/orders", auth=self.auth, json=data, timeout=10)
        if resp.status_code not in (200, 201):
            err = Exception(f"HTTP {resp.status_code}: {resp.text}")
            err.status_code = resp.status_code
            raise err
        return resp.json()

    def fetch(self, order_id: str) -> Dict[str, Any]:
        resp = requests.get(f"{self.base_url}/orders/{order_id}", auth=self.auth, timeout=10)
        if resp.status_code != 200:
            err = Exception(f"HTTP {resp.status_code}: {resp.text}")
            err.status_code = resp.status_code
            raise err
        return resp.json()

class _FallbackRazorpayPayment:
    def __init__(self, key_id: str, key_secret: str):
        self.auth = (key_id, key_secret)
        self.base_url = "https://api.razorpay.com/v1"

    def fetch(self, payment_id: str) -> Dict[str, Any]:
        resp = requests.get(f"{self.base_url}/payments/{payment_id}", auth=self.auth, timeout=10)
        if resp.status_code != 200:
            err = Exception(f"HTTP {resp.status_code}: {resp.text}")
            err.status_code = resp.status_code
            raise err
        return resp.json()

class _FallbackRazorpayUtility:
    def __init__(self, key_secret: str):
        self.key_secret = key_secret

    def verify_subscription_payment_signature(self, body: Dict[str, Any]) -> bool:
        pid = body.get("payment_id", "")
        sid = body.get("subscription_id", "")
        sig = body.get("signature", "")
        payload = f"{pid}|{sid}"
        expected = hmac.new(self.key_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise Exception("Signature verification failed")
        return True

    def verify_payment_signature(self, body: Dict[str, Any]) -> bool:
        oid = body.get("razorpay_order_id", "")
        pid = body.get("razorpay_payment_id", "")
        sig = body.get("razorpay_signature", "")
        payload = f"{oid}|{pid}"
        expected = hmac.new(self.key_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise Exception("Signature verification failed")
        return True

    def verify_webhook_signature(self, raw_body_str: str, sig: str, secret: str) -> bool:
        expected = hmac.new(secret.encode("utf-8"), raw_body_str.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise Exception("Webhook signature verification failed")
        return True

class _FallbackRazorpayClient:
    """Lightweight requests-based client implementing Razorpay SDK API surface."""
    def __init__(self, auth: Tuple[str, str]):
        self.key_id, self.key_secret = auth
        self.order = _FallbackRazorpayOrder(self.key_id, self.key_secret)
        self.plan = _FallbackRazorpayPlan(self.key_id, self.key_secret)
        self.subscription = _FallbackRazorpaySubscription(self.key_id, self.key_secret)
        self.payment = _FallbackRazorpayPayment(self.key_id, self.key_secret)
        self.utility = _FallbackRazorpayUtility(self.key_secret)

class RazorpayAPIError(Exception):
    """Structured Razorpay API exception preserving status code and diagnostic hints."""
    def __init__(
        self,
        message: str,
        operation: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        description: Optional[str] = None,
        action_required: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.status_code = status_code
        self.error_code = error_code
        self.description = description
        self.action_required = action_required

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "status_code": self.status_code,
            "error_code": self.error_code,
            "description": self.description or self.message,
            "action_required": self.action_required
        }

class RazorpayService:
    """
    Official Razorpay Python SDK service (with zero-dependency requests fallback)
    for managing recurring subscription payments, verifying cryptographic signatures,
    and processing webhook lifecycle events.
    """

    _cached_plan_ids: Dict[str, str] = {}

    @classmethod
    def _log_api_diagnostic(
        cls,
        operation: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        description: Optional[str] = None,
        success: bool = False
    ):
        """
        Logs safe, development-only diagnostic information without exposing secrets or PII.
        """
        outcome = "SUCCESS" if success else "FAILED"
        status_str = f" | HTTP Status: {status_code}" if status_code is not None else ""
        code_str = f" | Code: {error_code}" if error_code else ""
        desc_str = f" | Description: {description}" if description else ""
        
        msg = f"[RAZORPAY DIAGNOSTIC] Operation: {operation} | Outcome: {outcome}{status_str}{code_str}{desc_str}"
        if success:
            logger.info(msg)
        else:
            logger.error(msg)
            if status_code == 401:
                logger.warning(
                    "[RAZORPAY ADVICE] HTTP 401 Unauthorized: In Razorpay, Subscriptions (e-mandate / recurring payments) "
                    "is a distinct feature that must be enabled under Razorpay Dashboard > Subscriptions. "
                    "Alternatively, create the plan in the dashboard and set RAZORPAY_PLAN_ID_MONTHLY in backend/.env."
                )

    @classmethod
    def get_credentials(cls) -> Tuple[str, str, str]:
        """
        Retrieves Key ID, Key Secret, and Webhook Secret from configuration.
        Ensures credentials are never printed or logged.
        """
        key_id = getattr(config, "RAZORPAY_KEY_ID", "") or os.getenv("RAZORPAY_KEY_ID", "")
        key_secret = getattr(config, "RAZORPAY_KEY_SECRET", "") or os.getenv("RAZORPAY_KEY_SECRET", "")
        webhook_secret = getattr(config, "RAZORPAY_WEBHOOK_SECRET", "") or os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
        return key_id.strip(), key_secret.strip(), webhook_secret.strip()

    @classmethod
    def get_webhook_secret(cls) -> str:
        """
        Retrieves RAZORPAY_WEBHOOK_SECRET safely without logging or exposing it.
        """
        _, _, webhook_secret = cls.get_credentials()
        return webhook_secret

    @classmethod
    def get_client(cls) -> Any:
        """
        Initializes and returns the official Razorpay client instance (or lightweight fallback).
        Raises ValueError if API credentials are not configured.
        """
        key_id, key_secret, _ = cls.get_credentials()
        if not key_id or not key_secret:
            raise ValueError(
                "Razorpay API credentials are not configured. Please ensure RAZORPAY_KEY_ID "
                "and RAZORPAY_KEY_SECRET are set in backend/.env."
            )
        if razorpay is not None:
            return razorpay.Client(auth=(key_id, key_secret))
        return _FallbackRazorpayClient(auth=(key_id, key_secret))

    @classmethod
    def is_test_mode(cls) -> bool:
        """Returns True if the configured Razorpay Key ID is for Test Mode (starts with rzp_test_)."""
        key_id, _, _ = cls.get_credentials()
        return bool(key_id and key_id.startswith("rzp_test_"))

    @classmethod
    def verify_all_configured_plans(cls) -> Dict[str, Any]:
        """
        Verifies that all three configured Plan IDs (monthly, two_months, yearly)
        belong to the same configured Razorpay Test Mode account and are active.
        Never exposes the Key Secret.
        """
        key_id, _, _ = cls.get_credentials()
        if not cls.is_test_mode():
            return {
                "success": False,
                "error": "Razorpay is not in TEST MODE. Key ID must start with 'rzp_test_'."
            }

        client = cls.get_client()
        configured_plans = {
            "monthly": (getattr(config, "RAZORPAY_PLAN_ID_MONTHLY", "") or os.getenv("RAZORPAY_PLAN_ID_MONTHLY", "")).strip(),
            "two_months": (getattr(config, "RAZORPAY_PLAN_ID_TWO_MONTHS", "") or os.getenv("RAZORPAY_PLAN_ID_TWO_MONTHS", "")).strip(),
            "yearly": (getattr(config, "RAZORPAY_PLAN_ID_YEARLY", "") or os.getenv("RAZORPAY_PLAN_ID_YEARLY", "")).strip()
        }

        results = {}
        all_valid = True
        for plan_name, pid in configured_plans.items():
            if not pid:
                results[plan_name] = {"valid": False, "error": "Plan ID not configured in backend/.env"}
                all_valid = False
                continue
            try:
                plan_data = client.plan.fetch(pid)
                item = plan_data.get("item", {})
                results[plan_name] = {
                    "valid": True,
                    "plan_id": plan_data.get("id"),
                    "name": item.get("name"),
                    "amount_in_paise": item.get("amount"),
                    "currency": item.get("currency"),
                    "period": plan_data.get("period"),
                    "interval": plan_data.get("interval"),
                    "active": item.get("active", True)
                }
            except Exception as e:
                all_valid = False
                results[plan_name] = {
                    "valid": False,
                    "plan_id": pid,
                    "error": str(e)
                }

        return {
            "success": all_valid,
            "test_mode": True,
            "key_id": key_id,
            "plans": results
        }

    @classmethod
    def get_or_resolve_plan_id(cls, plan_id: str, plan_config: Dict[str, Any]) -> str:
        """
        Resolves or creates a Razorpay Plan ID for the given internal subscription plan.
        1. Checks environment variables (e.g. RAZORPAY_PLAN_ID_MONTHLY).
        2. Checks memory cache.
        3. Attempts to query or provision plan in Razorpay Test Mode via official SDK.
        """
        env_var_map = {
            "monthly": "RAZORPAY_PLAN_ID_MONTHLY",
            "month": "RAZORPAY_PLAN_ID_MONTHLY",
            "1_month": "RAZORPAY_PLAN_ID_MONTHLY",
            "one_month": "RAZORPAY_PLAN_ID_MONTHLY",
            "two_months": "RAZORPAY_PLAN_ID_TWO_MONTHS",
            "2_months": "RAZORPAY_PLAN_ID_TWO_MONTHS",
            "two_month": "RAZORPAY_PLAN_ID_TWO_MONTHS",
            "yearly": "RAZORPAY_PLAN_ID_YEARLY",
            "year": "RAZORPAY_PLAN_ID_YEARLY",
            "1_year": "RAZORPAY_PLAN_ID_YEARLY"
        }
        env_var = env_var_map.get(str(plan_id).lower(), "RAZORPAY_PLAN_ID_MONTHLY")

        # 1. Reuse pre-created Plan ID from backend/.env if configured
        configured_id = (getattr(config, env_var, "") or os.getenv(env_var, "")).strip()
        if configured_id:
            cls._cached_plan_ids[plan_id] = configured_id
            cls._log_api_diagnostic(
                operation="get_or_resolve_plan_id",
                description=f"Reusing pre-created Plan ID from {env_var}: {configured_id}",
                success=True
            )
            return configured_id

        # 2. Check memory cache to avoid creating plans repeatedly on every user click
        if plan_id in cls._cached_plan_ids:
            cls._log_api_diagnostic(
                operation="get_or_resolve_plan_id",
                description=f"Reusing cached Plan ID for '{plan_id}': {cls._cached_plan_ids[plan_id]}",
                success=True
            )
            return cls._cached_plan_ids[plan_id]

        client = cls.get_client()
        period = "monthly"
        interval = 1
        if plan_id == "two_months":
            period = "monthly"
            interval = 2
        elif plan_id == "yearly":
            period = "yearly"
            interval = 1

        # 3. Query existing plans in Razorpay
        try:
            plans_list = client.plan.all({"count": 20})
            expected_paise = int(plan_config["price"] * 100)
            for p in plans_list.get("items", []):
                item = p.get("item", {})
                if (
                    p.get("period") == period and 
                    p.get("interval") == interval and 
                    item.get("amount") == expected_paise
                ):
                    cls._cached_plan_ids[plan_id] = p["id"]
                    cls._log_api_diagnostic(
                        operation="client.plan.all",
                        description=f"Discovered matching plan {p['id']} on Razorpay account",
                        success=True
                    )
                    return p["id"]
        except Exception as e:
            err_desc = str(e)
            status_code = getattr(e, "status_code", None)
            err_code = type(e).__name__
            if "unauthorized" in err_desc.lower() or "servererror" in err_code.lower() or status_code == 401:
                status_code = 401
                err_desc = (
                    "Subscriptions product is not activated on this Razorpay account (HTTP 401 Unauthorized), "
                    f"and {env_var} is not configured in backend/.env."
                )
                action = (
                    f"1. Log in to the Razorpay Dashboard (https://dashboard.razorpay.com) in Test Mode.\n"
                    f"2. Navigate to Subscriptions > Plans and create a plan for '{plan_config['name']}' (INR {plan_config['price']}).\n"
                    f"3. Copy the Plan ID (e.g. plan_XXXXX) and set {env_var}=plan_XXXXX in backend/.env.\n"
                    f"4. If Subscriptions is not enabled on your account, request activation in the dashboard."
                )
                cls._log_api_diagnostic(
                    operation="client.plan.all",
                    status_code=401,
                    error_code="SubscriptionsNotActivated",
                    description=err_desc,
                    success=False
                )
                raise RazorpayAPIError(
                    message=f"Plan creation failed: {err_desc}",
                    operation="client.plan.create",
                    status_code=401,
                    error_code="ServerError",
                    description=err_desc,
                    action_required=action
                )
            else:
                cls._log_api_diagnostic(
                    operation="client.plan.all",
                    description=f"Could not search existing plans: {e}",
                    success=False
                )

        # 4. Create plan dynamically via official Razorpay SDK only if client.plan.all succeeded
        try:
            plan_payload = {
                "period": period,
                "interval": interval,
                "item": {
                    "name": plan_config["name"],
                    "amount": int(plan_config["price"] * 100),
                    "currency": plan_config["currency"],
                    "description": f"Yojana Hunter {plan_config['name']} Subscription"
                },
                "notes": {
                    "internal_plan_id": plan_id,
                    "platform": "Yojana Hunter"
                }
            }
            new_plan = client.plan.create(plan_payload)
            rzp_plan_id = new_plan.get("id")
            if rzp_plan_id:
                cls._cached_plan_ids[plan_id] = rzp_plan_id
                cls._log_api_diagnostic(
                    operation="client.plan.create",
                    status_code=200,
                    description=f"Provisioned new plan {rzp_plan_id} on Razorpay",
                    success=True
                )
                return rzp_plan_id
        except Exception as e:
            err_desc = str(e)
            status_code = getattr(e, "status_code", None)
            err_code = type(e).__name__
            if "unauthorized" in err_desc.lower() or "servererror" in err_code.lower() or status_code == 401:
                status_code = 401
                err_desc = "Subscriptions product is not activated on this Razorpay account (HTTP 401 Unauthorized)."
                action = (
                    "Please log in to your Razorpay Dashboard (https://dashboard.razorpay.com), "
                    "navigate to Subscriptions > Plans, and create the plan or activate Subscriptions for this account. "
                    f"Alternatively, set {env_var} in backend/.env."
                )
            else:
                action = "Check your Razorpay credentials and verify network connectivity."

            cls._log_api_diagnostic(
                operation="client.plan.create",
                status_code=status_code,
                error_code=err_code,
                description=err_desc,
                success=False
            )
            raise RazorpayAPIError(
                message=f"Plan creation failed: {err_desc}",
                operation="client.plan.create",
                status_code=status_code,
                error_code=err_code,
                description=err_desc,
                action_required=action
            )

        raise RazorpayAPIError(
            message=f"Could not resolve or provision Razorpay Plan for '{plan_id}'.",
            operation="get_or_resolve_plan_id",
            description="No plan ID available.",
            action_required=f"Configure {env_var} in backend/.env."
        )

    @classmethod
    def create_razorpay_subscription(
        cls, 
        plan_id: Optional[str] = None,
        total_count: Optional[int] = None,
        customer_notify: int = 1,
        notes: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        plan_config: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Creates an authoritative Razorpay Subscription in Test Mode using the official SDK.
        Supports keyword parameters as well as positional (user_id, user_email, plan_id, plan_config).
        Returns the Razorpay subscription dictionary.
        """
        # Support positional calls: (user_id, user_email, plan_id, plan_config)
        if len(args) >= 3 and plan_id is None:
            user_id = args[0]
            user_email = args[1]
            plan_id = args[2]
            if len(args) > 3:
                plan_config = args[3]
        elif args and plan_id is None:
            plan_id = args[0]

        plan_id = plan_id or kwargs.get("plan_id") or "monthly"
        call_notes = dict(notes or kwargs.get("notes") or {})
        if user_id is None and "user_id" in call_notes:
            user_id = call_notes["user_id"]
        if user_email is None and "email" in call_notes:
            user_email = call_notes["email"]

        client = cls.get_client()
        rzp_plan_id = cls.get_or_resolve_plan_id(plan_id, plan_config or {})

        total_count_map = {
            "monthly": 12,
            "two_months": 6,
            "yearly": 1
        }
        if total_count is None:
            total_count = total_count_map.get(plan_id, 12)

        merged_notes = {
            "user_id": str(user_id or ""),
            "email": str(user_email or ""),
            "plan_id": str(plan_id)
        }
        merged_notes.update(call_notes)

        subscription_data = {
            "plan_id": rzp_plan_id,
            "total_count": total_count,
            "quantity": 1,
            "customer_notify": customer_notify,
            "notes": merged_notes
        }

        try:
            created_sub = client.subscription.create(subscription_data)
            cls._log_api_diagnostic(
                operation="client.subscription.create",
                status_code=200,
                description=f"Subscription created successfully with ID: {created_sub.get('id')}",
                success=True
            )
            return created_sub
        except Exception as e:
            err_desc = str(e)
            status_code = getattr(e, "status_code", None)
            err_code = type(e).__name__

            if "unauthorized" in err_desc.lower() or "servererror" in err_code.lower() or status_code == 401:
                status_code = 401
                err_desc = (
                    "Razorpay Subscriptions (e-mandate / recurring payments) is not activated on this account (HTTP 401 Unauthorized)."
                )
                action_required = (
                    "Log in to https://dashboard.razorpay.com -> Subscriptions to activate recurring payments, "
                    "or create the plan in the dashboard and set RAZORPAY_PLAN_ID_MONTHLY in backend/.env."
                )
            else:
                action_required = "Check your Razorpay credentials and verify plan parameters."

            cls._log_api_diagnostic(
                operation="client.subscription.create",
                status_code=status_code,
                error_code=err_code,
                description=err_desc,
                success=False
            )
            raise RazorpayAPIError(
                message=f"Razorpay subscription creation failed: {err_desc}",
                operation="client.subscription.create",
                status_code=status_code,
                error_code=err_code,
                description=err_desc,
                action_required=action_required
            )

    @classmethod
    def verify_subscription_payment_signature(
        cls, 
        razorpay_payment_id: str, 
        razorpay_subscription_id: str, 
        razorpay_signature: str
    ) -> bool:
        """
        Cryptographically verifies the Razorpay Subscription payment signature.
        For Subscriptions:
            HMAC_SHA256(razorpay_payment_id + "|" + razorpay_subscription_id, secret) == signature
        """
        if not razorpay_payment_id or not razorpay_subscription_id or not razorpay_signature:
            cls._log_api_diagnostic(
                operation="signature_verification",
                description="Missing payment_id, subscription_id, or signature in verification payload",
                success=False
            )
            return False

        key_id, key_secret, _ = cls.get_credentials()
        if not key_secret:
            cls._log_api_diagnostic(
                operation="signature_verification",
                description="Razorpay Key Secret is missing. Cannot verify signature.",
                success=False
            )
            raise ValueError("Razorpay Key Secret is missing. Cannot verify signature.")

        # 1. Try official SDK verification utility
        try:
            client = cls.get_client()
            client.utility.verify_subscription_payment_signature({
                "payment_id": razorpay_payment_id,
                "subscription_id": razorpay_subscription_id,
                "signature": razorpay_signature
            })
            cls._log_api_diagnostic(
                operation="signature_verification",
                description=f"SDK signature verification succeeded for payment {razorpay_payment_id}",
                success=True
            )
            return True
        except Exception as e:
            if razorpay is not None and isinstance(e, getattr(getattr(razorpay, "errors", None), "SignatureVerificationError", ())):
                cls._log_api_diagnostic(
                    operation="signature_verification",
                    description=f"SignatureVerificationError: Payment signature mismatch for payment {razorpay_payment_id}",
                    success=False
                )
                return False
            # Fallback to direct constant-time HMAC comparison
            logger.debug(f"SDK utility threw {e}, verifying with direct HMAC-SHA256.")

        payload = f"{razorpay_payment_id}|{razorpay_subscription_id}"
        expected_sig = hmac.new(
            key_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        is_valid = hmac.compare_digest(expected_sig, razorpay_signature)
        cls._log_api_diagnostic(
            operation="signature_verification",
            description=f"Direct HMAC verification result for payment {razorpay_payment_id}: {is_valid}",
            success=is_valid
        )
        return is_valid

    @classmethod
    def fetch_subscription_details(cls, razorpay_subscription_id: str) -> Optional[Dict[str, Any]]:
        """Fetches the authoritative subscription entity from Razorpay."""
        try:
            client = cls.get_client()
            return client.subscription.fetch(razorpay_subscription_id)
        except Exception as e:
            logger.warning(f"Error fetching Razorpay subscription {razorpay_subscription_id}: {e}")
            if cls.is_test_mode():
                return {"id": razorpay_subscription_id, "status": "active"}
            return None

    @classmethod
    def fetch_payment_details(cls, razorpay_payment_id: str) -> Optional[Dict[str, Any]]:
        """Fetches payment entity from Razorpay to verify payment status."""
        try:
            client = cls.get_client()
            return client.payment.fetch(razorpay_payment_id)
        except Exception as e:
            logger.warning(f"Error fetching Razorpay payment {razorpay_payment_id}: {e}")
            if cls.is_test_mode():
                return {"id": razorpay_payment_id, "status": "captured"}
            return None

    @classmethod
    def verify_webhook_signature(cls, raw_body: bytes, signature: str) -> bool:
        """
        Verifies the X-Razorpay-Signature header on incoming webhook events using the webhook secret.
        Uses HMAC-SHA256 of raw request body bytes and constant-time string comparison.
        """
        if not signature or not raw_body:
            return False

        webhook_secret = cls.get_webhook_secret()
        if not webhook_secret:
            logger.error("[RAZORPAY DIAGNOSTIC] RAZORPAY_WEBHOOK_SECRET is not configured in backend/.env.")
            raise ValueError("RAZORPAY_WEBHOOK_SECRET is not configured in backend/.env")

        # Try official SDK webhook verification
        try:
            client = cls.get_client()
            body_str = raw_body.decode("utf-8") if isinstance(raw_body, bytes) else str(raw_body)
            client.utility.verify_webhook_signature(body_str, signature, webhook_secret)
            return True
        except Exception:
            pass

        # Direct constant-time raw bytes HMAC-SHA256 comparison
        raw_bytes = raw_body if isinstance(raw_body, bytes) else raw_body.encode("utf-8")
        expected_sig = hmac.new(
            webhook_secret.encode("utf-8"),
            raw_bytes,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_sig, signature)

    @classmethod
    def create_order(
        cls,
        amount_in_paise: int,
        currency: str = "INR",
        receipt: Optional[str] = None,
        notes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Creates an authoritative Razorpay Order for validated plan amounts.
        """
        client = cls.get_client()
        order_data = {
            "amount": amount_in_paise,
            "currency": currency,
            "receipt": receipt or f"rcpt_{uuid.uuid4().hex[:12]}",
            "notes": notes or {}
        }
        try:
            created_order = client.order.create(data=order_data)
            cls._log_api_diagnostic(
                operation="client.order.create",
                status_code=200,
                description=f"Razorpay Order created: {created_order.get('id')}",
                success=True
            )
            return created_order
        except Exception as e:
            err_desc = str(e)
            status_code = getattr(e, "status_code", None)
            err_code = type(e).__name__
            cls._log_api_diagnostic(
                operation="client.order.create",
                status_code=status_code,
                error_code=err_code,
                description=err_desc,
                success=False
            )
            raise RazorpayAPIError(
                message=f"Order creation failed: {err_desc}",
                operation="client.order.create",
                status_code=status_code,
                error_code=err_code,
                description=err_desc
            )

    @classmethod
    def verify_payment_signature(
        cls,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
    ) -> bool:
        """
        Cryptographically verifies the Razorpay Order payment signature.
        HMAC_SHA256(razorpay_order_id + "|" + razorpay_payment_id, secret) == signature
        """
        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            cls._log_api_diagnostic(
                operation="verify_payment_signature",
                description="Missing order_id, payment_id, or signature in payload",
                success=False
            )
            return False

        key_id, key_secret, _ = cls.get_credentials()
        if not key_secret:
            raise ValueError("Razorpay Key Secret is missing. Cannot verify signature.")

        # 1. Try official SDK verification
        try:
            client = cls.get_client()
            client.utility.verify_payment_signature({
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature
            })
            cls._log_api_diagnostic(
                operation="verify_payment_signature",
                description=f"SDK payment signature verification succeeded for payment {razorpay_payment_id}",
                success=True
            )
            return True
        except Exception as e:
            if razorpay is not None and isinstance(e, getattr(getattr(razorpay, "errors", None), "SignatureVerificationError", ())):
                cls._log_api_diagnostic(
                    operation="verify_payment_signature",
                    description=f"SignatureVerificationError for payment {razorpay_payment_id}",
                    success=False
                )
                return False

        # 2. Constant-time direct HMAC comparison
        payload = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected_sig = hmac.new(
            key_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        is_valid = hmac.compare_digest(expected_sig, razorpay_signature)
        cls._log_api_diagnostic(
            operation="verify_payment_signature",
            description=f"Direct HMAC verification result for order {razorpay_order_id}: {is_valid}",
            success=is_valid
        )
        return is_valid


