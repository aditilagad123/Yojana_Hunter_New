import sys
import os
import hmac
import hashlib
import json
import uuid
import datetime
import pytest

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from database import engine, Base, SessionLocal
from models import Scheme, Profile, User, SubscriptionRequest, ProcessedWebhookEvent
from services.subscription_service import SubscriptionService, FREE_SCHEMES_LIMIT, SUBSCRIPTION_PLANS
from services.razorpay_service import RazorpayService, RazorpayAPIError
from services.eligibility_service import SchemeEligibilityService
from utils.auth import hash_password, create_access_token
from app import create_app

@pytest.fixture(scope="module")
def test_app():
    Base.metadata.create_all(bind=engine)
    app = create_app()
    app.config["TESTING"] = True
    yield app
    SessionLocal.remove()

@pytest.fixture(scope="module")
def client(test_app):
    return test_app.test_client()

@pytest.fixture(autouse=True)
def mock_razorpay_subscription_api(monkeypatch):
    """Mocks the external Razorpay subscription creation API by default for hermetic unit testing."""
    def _mock_create_sub(cls, *args, **kwargs):
        plan_id = kwargs.get("plan_id") or (args[2] if len(args) > 2 else "monthly")
        return {
            "id": f"sub_unit_test_{uuid.uuid4().hex[:12]}",
            "plan_id": f"plan_{plan_id}",
            "status": "created",
            "total_count": 12,
            "customer_notify": 1,
            "short_url": "https://rzp.io/i/mock_checkout"
        }
    monkeypatch.setattr(RazorpayService, "create_razorpay_subscription", classmethod(_mock_create_sub))

def get_or_create_user(db, email, role="citizen"):
    user = db.query(User).filter_by(email=email).first()
    if not user:
        seed_num = abs(hash(email)) % 900000000 + 100000000
        mobile = f"9{seed_num}"[:10]
        while db.query(User).filter_by(mobile=mobile).first():
            seed_num += 1
            mobile = f"9{seed_num}"[:10]
        user = User(
            email=email,
            mobile=mobile,
            password_hash=hash_password("RazorpayPass123!"),
            role=role,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def get_or_create_profile(db, user_id, occupation="Student", state="Maharashtra", gender="Female"):
    profile = db.query(Profile).filter_by(user_id=user_id).first()
    if not profile:
        profile = Profile(
            user_id=user_id,
            full_name="Razorpay Test Citizen",
            occupation=occupation,
            state=state,
            gender=gender,
            age=22,
            annual_income=150000,
            education="Graduate",
            category="General",
            is_student=True,
            is_farmer=False
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile

def generate_valid_subscription_signature(payment_id: str, subscription_id: str, secret: str) -> str:
    """Computes Razorpay official subscription payment signature."""
    payload = f"{payment_id}|{subscription_id}"
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

def generate_valid_webhook_signature(raw_body: bytes, secret: str) -> str:
    """Computes Razorpay official webhook HMAC-SHA256 signature."""
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

def create_and_approve_subscription_request(db, user_id: int, plan_id: str = "monthly") -> SubscriptionRequest:
    """Helper to ensure a user has an approved SubscriptionRequest prior to payment checkout."""
    db.query(SubscriptionRequest).filter_by(user_id=user_id).delete()
    db.commit()
    plan = SUBSCRIPTION_PLANS.get(plan_id, SUBSCRIPTION_PLANS["monthly"])
    price = plan["price"]
    req = SubscriptionRequest(
        user_id=user_id,
        plan_id=plan_id,
        plan_name=plan["name"],
        amount=price,
        amount_in_paise=int(price * 100),
        currency=plan.get("currency", "INR"),
        duration_days=plan.get("duration_days", 30),
        status="approved",
        admin_approval_status="ADMIN_APPROVED",
        mandate_status="MANDATE_PENDING",
        payment_status="PAYMENT_PENDING",
        is_active=False
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req



# =========================================================================
# 14 CRITICAL RAZORPAY SUBSCRIPTION VERIFICATION TESTS
# =========================================================================

def test_1_free_user_scheme_exploration_within_limit(client):
    """Test 1: A user within the free limit can explore schemes without paying."""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, "rzp_free_user_limit@example.com")
        get_or_create_profile(db, user.id, occupation="Student")
        token = create_access_token(user.id, user.role)
        headers = {"Authorization": f"Bearer {token}"}

        # Clear existing subscriptions
        db.query(SubscriptionRequest).filter_by(user_id=user.id).delete()
        db.commit()

        resp = client.get("/api/schemes?profile_occupation=Student&profile_state=Maharashtra", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["is_premium"] is False
        assert data["free_limit"] == 5
        assert len(data["schemes"]) <= 5
    finally:
        db.close()


def test_2_free_user_reaches_limit_sees_subscription_options(client):
    """Test 2: A user who reaches the free limit sees subscription options."""
    resp = client.get("/api/subscriptions/plans")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "plans" in data
    assert "comparison" in data
    assert data["free_limit"] == 5
    plan_ids = [p["id"] for p in data["plans"]]
    assert "monthly" in plan_ids
    assert "two_months" in plan_ids
    assert "yearly" in plan_ids


def test_3_select_one_month_plan_creates_razorpay_subscription(client):
    """Test 3: Selecting the one-month plan creates the correct Razorpay subscription."""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, "rzp_checkout_monthly@example.com")
        get_or_create_profile(db, user.id, occupation="Student")
        token = create_access_token(user.id, user.role)
        headers = {"Authorization": f"Bearer {token}"}

        # Verify checkout creation without admin approval or with direct checkout flow
        db.query(SubscriptionRequest).filter_by(user_id=user.id).delete()
        db.commit()
        unapproved_resp = client.post("/api/subscriptions/checkout", headers=headers, json={"plan_id": "monthly"})
        assert unapproved_resp.status_code in (200, 403)

        # Now approve subscription request
        create_and_approve_subscription_request(db, user.id, "monthly")

        resp = client.post(
            "/api/subscriptions/checkout",
            headers=headers,
            json={"plan_id": "monthly"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["plan_id"] == "monthly"
        assert data["amount"] == 50
        assert data["amount_in_paise"] == 5000
        assert "key_id" in data
        assert "subscription_id" in data
        assert data["subscription_id"].startswith("sub_")

        # Verify persisted record in PostgreSQL
        sub = db.query(SubscriptionRequest).filter_by(
            user_id=user.id, 
            razorpay_subscription_id=data["subscription_id"]
        ).first()
        assert sub is not None
        assert sub.status in ("created", "approved")
        assert sub.payment_status in ("pending", "PAYMENT_PENDING")
        assert sub.is_active is False
    finally:
        db.close()


def test_4_invalid_or_inactive_plan_rejected(client):
    """Test 4: An invalid or inactive plan is rejected."""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, "rzp_checkout_invalid@example.com")
        token = create_access_token(user.id, user.role)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/api/subscriptions/checkout",
            headers=headers,
            json={"plan_id": "infinite_free_plan"}
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "Invalid plan" in data["message"]
    finally:
        db.close()


def test_5_client_price_manipulation_rejected(client):
    """Test 5: Client-side price manipulation is rejected (backend uses trusted plan config)."""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, "rzp_tamper_price@example.com")
        token = create_access_token(user.id, user.role)
        headers = {"Authorization": f"Bearer {token}"}

        db.query(SubscriptionRequest).filter_by(user_id=user.id).delete()
        db.commit()
        create_and_approve_subscription_request(db, user.id, "yearly")

        # Attacker submits ₹1 instead of ₹500 for yearly plan
        resp = client.post(
            "/api/subscriptions/checkout",
            headers=headers,
            json={"plan_id": "yearly", "price": 1, "amount": 1, "amount_in_paise": 100}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        # Authoritative price must remain ₹500 (50000 paise)
        assert data["amount"] == 500
        assert data["amount_in_paise"] == 50000
    finally:
        db.close()


def test_6_missing_credentials_produces_clear_configuration_error(monkeypatch):
    """Test 6: Missing credentials produce a clear configuration error."""
    # Temporarily blank out credentials
    monkeypatch.setattr(RazorpayService, "get_credentials", classmethod(lambda cls: ("", "", "")))

    db = SessionLocal()
    try:
        user = get_or_create_user(db, "rzp_no_creds@example.com")
        create_and_approve_subscription_request(db, user.id, "monthly")
        success, message, data = SubscriptionService.create_checkout_session(db, user, "monthly")
        assert success is False
        assert "unconfigured" in message.lower() or "missing" in message.lower()
    finally:
        db.close()


def test_7_invalid_subscription_signature_rejected(client):
    """Test 7: Invalid subscription signatures are rejected."""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, "rzp_sig_invalid@example.com")
        token = create_access_token(user.id, user.role)
        headers = {"Authorization": f"Bearer {token}"}

        # Create checkout session
        create_and_approve_subscription_request(db, user.id, "monthly")
        checkout_resp = client.post("/api/subscriptions/checkout", headers=headers, json={"plan_id": "monthly"})
        assert checkout_resp.status_code == 200
        sub_id = checkout_resp.get_json()["subscription_id"]

        # Attempt verification with bogus forged signature
        verify_resp = client.post(
            "/api/subscriptions/verify",
            headers=headers,
            json={
                "razorpay_payment_id": "pay_fake_test_12345",
                "razorpay_subscription_id": sub_id,
                "razorpay_signature": "0000000000000000000000000000000000000000000000000000000000000000"
            }
        )
        assert verify_resp.status_code == 400
        data = verify_resp.get_json()
        assert "verification failed" in data["error"].lower() or "signature" in data["message"].lower()

        # Database record must not be active
        sub = db.query(SubscriptionRequest).filter_by(razorpay_subscription_id=sub_id).first()
        assert sub.is_active is False
        assert sub.payment_status in ("failed", "PAYMENT_FAILED")
    finally:
        db.close()


def test_8_user_cannot_verify_another_users_subscription(client):
    """Test 8: A user cannot verify or access another user's subscription."""
    db = SessionLocal()
    try:
        victim = get_or_create_user(db, "victim_user@example.com")
        attacker = get_or_create_user(db, "attacker_user@example.com")
        attacker_id = attacker.id

        victim_token = create_access_token(victim.id, victim.role)
        attacker_token = create_access_token(attacker.id, attacker.role)

        # Victim creates checkout session
        create_and_approve_subscription_request(db, victim.id, "monthly")
        checkout_resp = client.post(
            "/api/subscriptions/checkout",
            headers={"Authorization": f"Bearer {victim_token}"},
            json={"plan_id": "monthly"}
        )
        assert checkout_resp.status_code == 200
        victim_sub_id = checkout_resp.get_json()["subscription_id"]

        _, key_secret, _ = RazorpayService.get_credentials()
        pay_id = f"pay_test_{uuid.uuid4().hex[:12]}"
        valid_sig = generate_valid_subscription_signature(pay_id, victim_sub_id, key_secret)

        # Attacker tries to verify victim's subscription
        attacker_resp = client.post(
            "/api/subscriptions/verify",
            headers={"Authorization": f"Bearer {attacker_token}"},
            json={
                "razorpay_payment_id": pay_id,
                "razorpay_subscription_id": victim_sub_id,
                "razorpay_signature": valid_sig
            }
        )
        assert attacker_resp.status_code == 400
        data = attacker_resp.get_json()
        assert "unauthorized" in data["message"].lower() or "different user" in data["message"].lower()

        # Attacker status must remain free
        attacker_status = SubscriptionService.is_user_premium(db, attacker_id)
        assert attacker_status is False
    finally:
        db.close()


def test_9_checkout_cancellation_does_not_activate_premium(client):
    """Test 9: Checkout cancellation does not activate premium access."""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, "rzp_cancel_test@example.com")
        token = create_access_token(user.id, user.role)
        headers = {"Authorization": f"Bearer {token}"}

        # Initialize checkout
        create_and_approve_subscription_request(db, user.id, "monthly")
        checkout_resp = client.post("/api/subscriptions/checkout", headers=headers, json={"plan_id": "monthly"})
        assert checkout_resp.status_code == 200

        # User closes window without paying
        is_premium = SubscriptionService.is_user_premium(db, user.id)
        assert is_premium is False

        status_resp = client.get("/api/subscriptions/my-status", headers=headers)
        assert status_resp.status_code == 200
        assert status_resp.get_json()["is_premium"] is False
    finally:
        db.close()


def test_10_failed_payment_does_not_grant_premium(client, monkeypatch):
    """Test 10: Failed payments do not grant premium access."""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, "rzp_failed_pay@example.com")
        token = create_access_token(user.id, user.role)
        headers = {"Authorization": f"Bearer {token}"}

        create_and_approve_subscription_request(db, user.id, "monthly")
        checkout_resp = client.post("/api/subscriptions/checkout", headers=headers, json={"plan_id": "monthly"})
        assert checkout_resp.status_code == 200
        sub_id = checkout_resp.get_json()["subscription_id"]

        _, key_secret, _ = RazorpayService.get_credentials()
        pay_id = f"pay_failed_{uuid.uuid4().hex[:12]}"
        valid_sig = generate_valid_subscription_signature(pay_id, sub_id, key_secret)

        # Mock Razorpay payment fetch returning failed status
        monkeypatch.setattr(
            RazorpayService, 
            "fetch_payment_details", 
            classmethod(lambda cls, pid: {"id": pid, "status": "failed", "error_description": "Card expired"})
        )

        verify_resp = client.post(
            "/api/subscriptions/verify",
            headers=headers,
            json={
                "razorpay_payment_id": pay_id,
                "razorpay_subscription_id": sub_id,
                "razorpay_signature": valid_sig
            }
        )
        assert verify_resp.status_code == 400
        assert SubscriptionService.is_user_premium(db, user.id) is False
    finally:
        db.close()


def test_11_verified_subscription_receives_correct_access(client):
    """Test 11: Verified eligible subscriptions receive correct premium access and unlock schemes beyond free limit."""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, "rzp_premium_verified@example.com")
        get_or_create_profile(db, user.id, occupation="Student")
        token = create_access_token(user.id, user.role)
        headers = {"Authorization": f"Bearer {token}"}

        # Checkout monthly plan
        create_and_approve_subscription_request(db, user.id, "monthly")
        checkout_resp = client.post("/api/subscriptions/checkout", headers=headers, json={"plan_id": "monthly"})
        assert checkout_resp.status_code == 200
        sub_id = checkout_resp.get_json()["subscription_id"]

        _, key_secret, _ = RazorpayService.get_credentials()
        pay_id = f"pay_success_{uuid.uuid4().hex[:12]}"
        valid_sig = generate_valid_subscription_signature(pay_id, sub_id, key_secret)

        # Verify payment
        verify_resp = client.post(
            "/api/subscriptions/verify",
            headers=headers,
            json={
                "razorpay_payment_id": pay_id,
                "razorpay_subscription_id": sub_id,
                "razorpay_signature": valid_sig
            }
        )
        assert verify_resp.status_code == 200
        v_data = verify_resp.get_json()
        assert v_data["success"] is True
        assert v_data["is_premium"] is True

        # Confirm user is now premium in database
        assert SubscriptionService.is_user_premium(db, user.id) is True

        # Confirm scheme explorer unlocks all schemes (beyond 5)
        schemes_resp = client.get("/api/schemes?profile_occupation=Student&profile_state=Maharashtra", headers=headers)
        assert schemes_resp.status_code == 200
        s_data = schemes_resp.get_json()
        assert s_data["is_premium"] is True
        assert s_data["has_more"] is False
    finally:
        db.close()


def test_12_duplicate_webhook_events_idempotent(client, monkeypatch):
    """Test 12: Duplicate webhook events do not cause duplicate updates (idempotency)."""
    db = SessionLocal()
    test_event_id = f"evt_dedup_{uuid.uuid4().hex[:12]}"
    test_sub_id = f"sub_wh_{uuid.uuid4().hex[:12]}"
    try:
        user = get_or_create_user(db, "rzp_webhook_dedup@example.com")
        # Insert subscription record
        sub = SubscriptionRequest(
            user_id=user.id,
            plan_id="monthly",
            plan_name="Monthly Access",
            amount=50.0,
            duration_days=30,
            status="created",
            payment_status="pending",
            razorpay_subscription_id=test_sub_id,
            is_active=False
        )
        db.add(sub)
        db.commit()

        webhook_payload = {
            "event_id": test_event_id,
            "event": "subscription.activated",
            "payload": {
                "subscription": {
                    "entity": {
                        "id": test_sub_id,
                        "status": "active"
                    }
                }
            }
        }
        raw_body = json.dumps(webhook_payload).encode("utf-8")
        test_secret = "test_webhook_secret_key"
        valid_sig = generate_valid_webhook_signature(raw_body, test_secret)

        monkeypatch.setattr(RazorpayService, "get_credentials", classmethod(lambda cls: ("key", "secret", test_secret)))

        # 1st Webhook delivery
        resp1 = client.post(
            "/api/webhooks/razorpay",
            data=raw_body,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_sig}
        )
        assert resp1.status_code == 200
        assert resp1.get_json()["status"] == "success"

        # Subscription is activated
        sub = db.query(SubscriptionRequest).filter_by(razorpay_subscription_id=test_sub_id).first()
        assert sub.is_active is True
        assert sub.status == "approved"

        # 2nd Webhook delivery (duplicate retry from Razorpay)
        resp2 = client.post(
            "/api/webhooks/razorpay",
            data=raw_body,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_sig}
        )
        assert resp2.status_code == 200
        assert "already processed" in resp2.get_json()["message"].lower()

        # Exactly 1 event recorded in processed_webhook_events
        event_count = db.query(ProcessedWebhookEvent).filter_by(event_id=test_event_id).count()
        assert event_count == 1
    finally:
        db.query(ProcessedWebhookEvent).filter_by(event_id=test_event_id).delete()
        db.commit()
        db.close()


def test_13_webhook_renewal_extends_access_and_expiry(client, monkeypatch):
    """Test 13: Renewals (subscription.charged) extend paid-through period correctly."""
    db = SessionLocal()
    test_sub_id = f"sub_renew_{uuid.uuid4().hex[:12]}"
    test_event_id = f"evt_renew_{uuid.uuid4().hex[:12]}"
    try:
        user = get_or_create_user(db, "rzp_renew_user@example.com")
        now = datetime.datetime.utcnow()
        initial_expiry = now + datetime.timedelta(days=10)

        sub = SubscriptionRequest(
            user_id=user.id,
            plan_id="monthly",
            plan_name="Monthly Access",
            amount=50.0,
            duration_days=30,
            status="approved",
            payment_status="captured",
            razorpay_subscription_id=test_sub_id,
            starts_at=now - datetime.timedelta(days=20),
            expires_at=initial_expiry,
            is_active=True
        )
        db.add(sub)
        db.commit()

        webhook_payload = {
            "event_id": test_event_id,
            "event": "subscription.charged",
            "payload": {
                "subscription": {
                    "entity": {
                        "id": test_sub_id,
                        "status": "active"
                    }
                },
                "payment": {
                    "entity": {
                        "id": f"pay_renew_{uuid.uuid4().hex[:12]}",
                        "status": "captured"
                    }
                }
            }
        }
        raw_body = json.dumps(webhook_payload).encode("utf-8")
        test_secret = "test_webhook_secret_key"
        valid_sig = generate_valid_webhook_signature(raw_body, test_secret)

        monkeypatch.setattr(RazorpayService, "get_credentials", classmethod(lambda cls: ("key", "secret", test_secret)))

        resp = client.post(
            "/api/webhooks/razorpay",
            data=raw_body,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_sig}
        )
        assert resp.status_code == 200

        # Verified renewal: expiry extended by 30 days beyond previous expiry
        sub = db.query(SubscriptionRequest).filter_by(razorpay_subscription_id=test_sub_id).first()
        expected_expiry_days = (sub.expires_at - initial_expiry).days
        assert expected_expiry_days == 30
    finally:
        db.query(ProcessedWebhookEvent).filter_by(event_id=test_event_id).delete()
        db.commit()
        db.close()


def test_14_webhook_unverified_signature_rejected(client, monkeypatch):
    """Test 14: Unverified webhook signatures are rejected."""
    monkeypatch.setattr(RazorpayService, "get_credentials", classmethod(lambda cls: ("key", "secret", "configured_test_webhook_secret")))
    payload = {"event": "subscription.activated", "id": "evt_fraud_123"}
    raw_body = json.dumps(payload).encode("utf-8")
    resp = client.post(
        "/api/webhooks/razorpay",
        data=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "bad_invalid_signature"}
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "signature" in data["error"].lower() or "signature" in data["message"].lower()



def test_15_razorpay_gateway_error_returns_clean_diagnostic_without_fake_fallback(client, monkeypatch):
    """Test 15: Razorpay gateway errors (e.g. 401 Subscriptions unactivated) return clean diagnostic 400 without fake ID."""
    def _mock_failing_sub(cls, *args, **kwargs):
        raise RazorpayAPIError(
            message="Plan creation failed: Subscriptions product is not activated on this Razorpay account (HTTP 401 Unauthorized).",
            operation="client.plan.create",
            status_code=401,
            error_code="ServerError",
            description="Subscriptions product is not activated on this Razorpay account (HTTP 401 Unauthorized).",
            action_required="Enable Subscriptions in Razorpay Dashboard or set RAZORPAY_PLAN_ID_MONTHLY in backend/.env"
        )
    monkeypatch.setattr(RazorpayService, "create_razorpay_subscription", classmethod(_mock_failing_sub))

    db = SessionLocal()
    try:
        user = get_or_create_user(db, "rzp_fail_diag@example.com")
        create_and_approve_subscription_request(db, user.id, "monthly")
        token = create_access_token(user.id, user.role)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/api/subscriptions/checkout",
            headers=headers,
            json={"plan_id": "monthly"}
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Checkout initialization failed"
        assert "diagnostic" in data
        diag = data["diagnostic"]
        assert diag["operation"] == "client.plan.create"
        assert diag["status_code"] == 401
        assert "action_required" in diag
        # CRITICAL: Verify NO fake subscription ID is returned to caller
        assert "subscription_id" not in data
    finally:
        db.close()
