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
from models import Profile, User, SubscriptionRequest, ProcessedWebhookEvent
from services.subscription_service import SubscriptionService
from services.razorpay_service import RazorpayService
from app import create_app

TEST_WEBHOOK_SECRET = "test_webhook_secret_for_integration_tests_12345"

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

def generate_signature(raw_body: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    """Generates official HMAC-SHA256 hex digest signature for webhook payload."""
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

def get_or_create_user(db, email: str = "webhook_tester@example.com") -> User:
    user = db.query(User).filter_by(email=email).first()
    if not user:
        rand_digits = f"{uuid.uuid4().int % 100000000:08d}"
        user = User(
            email=email,
            password_hash="mock_hash",
            mobile=f"98{rand_digits}",
            role="citizen",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

# ==============================================================================
# TEST 1: Valid webhook signature (Both /api/razorpay/webhook and /api/webhooks/razorpay)
# ==============================================================================
def test_1_valid_webhook_signature_on_both_endpoints(client, monkeypatch):
    """Test 1: Webhook requests with valid HMAC-SHA256 signature are accepted on both path aliases."""
    monkeypatch.setattr(RazorpayService, "get_credentials", classmethod(lambda cls: ("key", "secret", TEST_WEBHOOK_SECRET)))
    db = SessionLocal()
    sub_id = f"sub_{uuid.uuid4().hex[:12]}"
    event_id_1 = f"evt_{uuid.uuid4().hex[:12]}"
    event_id_2 = f"evt_{uuid.uuid4().hex[:12]}"

    try:
        user = get_or_create_user(db, "valid_sig_user@example.com")
        sub = SubscriptionRequest(
            user_id=user.id,
            plan_id="monthly",
            plan_name="Monthly Access",
            amount=50.0,
            duration_days=30,
            status="pending",
            razorpay_subscription_id=sub_id,
            is_active=False
        )
        db.add(sub)
        db.commit()

        # Path 1: POST /api/razorpay/webhook
        payload_1 = {
            "entity": "event",
            "event_id": event_id_1,
            "event": "subscription.activated",
            "payload": {
                "subscription": {
                    "entity": {
                        "id": sub_id,
                        "status": "active"
                    }
                }
            }
        }
        body_1 = json.dumps(payload_1).encode("utf-8")
        sig_1 = generate_signature(body_1)

        resp1 = client.post(
            "/api/razorpay/webhook",
            data=body_1,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig_1}
        )
        assert resp1.status_code == 200
        assert resp1.get_json()["status"] == "success"

        # Path 2: POST /api/webhooks/razorpay
        payload_2 = {
            "entity": "event",
            "event_id": event_id_2,
            "event": "payment.captured",
            "payload": {
                "subscription": {"entity": {"id": sub_id}},
                "payment": {"entity": {"id": f"pay_{uuid.uuid4().hex[:10]}"}}
            }
        }
        body_2 = json.dumps(payload_2).encode("utf-8")
        sig_2 = generate_signature(body_2)

        resp2 = client.post(
            "/api/webhooks/razorpay",
            data=body_2,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig_2}
        )
        assert resp2.status_code == 200
        assert resp2.get_json()["status"] == "success"

    finally:
        db.query(ProcessedWebhookEvent).filter(ProcessedWebhookEvent.event_id.in_([event_id_1, event_id_2])).delete()
        db.commit()
        db.close()

# ==============================================================================
# TEST 2: Invalid webhook signature rejected
# ==============================================================================
def test_2_invalid_webhook_signature_rejected(client, monkeypatch):
    """Test 2: Webhook requests with tampered body or invalid signature return HTTP 400."""
    monkeypatch.setattr(RazorpayService, "get_credentials", classmethod(lambda cls: ("key", "secret", TEST_WEBHOOK_SECRET)))
    payload = {"entity": "event", "event": "subscription.activated", "id": "evt_tampered_1"}
    body = json.dumps(payload).encode("utf-8")

    resp = client.post(
        "/api/razorpay/webhook",
        data=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "invalid_forged_signature_hex"}
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Invalid signature"
    assert "verification failed" in data["message"].lower()

# ==============================================================================
# TEST 3: Missing signature header rejected
# ==============================================================================
def test_3_missing_signature_header_rejected(client, monkeypatch):
    """Test 3: Webhook requests missing the X-Razorpay-Signature header return HTTP 400."""
    monkeypatch.setattr(RazorpayService, "get_credentials", classmethod(lambda cls: ("key", "secret", TEST_WEBHOOK_SECRET)))
    payload = {"entity": "event", "event": "subscription.activated", "id": "evt_nosig_1"}
    body = json.dumps(payload).encode("utf-8")

    resp = client.post(
        "/api/razorpay/webhook",
        data=body,
        headers={"Content-Type": "application/json"}  # No X-Razorpay-Signature header
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Missing signature"
    assert "X-Razorpay-Signature" in data["message"]

# ==============================================================================
# TEST 4: Missing webhook secret produces clear HTTP 500 configuration error
# ==============================================================================
def test_4_missing_webhook_secret_produces_configuration_error(client, monkeypatch):
    """Test 4: When RAZORPAY_WEBHOOK_SECRET is not configured, server returns HTTP 500 configuration error."""
    # Simulate unconfigured webhook secret
    monkeypatch.setattr(RazorpayService, "get_credentials", classmethod(lambda cls: ("key", "secret", "")))
    payload = {"entity": "event", "event": "subscription.activated", "id": "evt_nosecret_1"}
    body = json.dumps(payload).encode("utf-8")

    resp = client.post(
        "/api/razorpay/webhook",
        data=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "some_sig"}
    )
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["error"] == "Configuration error"
    assert "RAZORPAY_WEBHOOK_SECRET" in data["message"]

# ==============================================================================
# TEST 5: Malformed JSON payload safely rejected
# ==============================================================================
def test_5_malformed_json_safely_rejected(client, monkeypatch):
    """Test 5: Payloads with broken/unparseable JSON return HTTP 400 Bad Request."""
    monkeypatch.setattr(RazorpayService, "get_credentials", classmethod(lambda cls: ("key", "secret", TEST_WEBHOOK_SECRET)))
    malformed_body = b"{\"event\": \"subscription.activated\", broken_json...}"
    valid_sig = generate_signature(malformed_body)

    resp = client.post(
        "/api/razorpay/webhook",
        data=malformed_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_sig}
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Malformed JSON"

# ==============================================================================
# TEST 6: Duplicate event delivery is idempotent
# ==============================================================================
def test_6_duplicate_event_delivery_is_idempotent(client, monkeypatch):
    """Test 6: Repeated deliveries of the same webhook event return HTTP 200 without duplicate records."""
    monkeypatch.setattr(RazorpayService, "get_credentials", classmethod(lambda cls: ("key", "secret", TEST_WEBHOOK_SECRET)))
    db = SessionLocal()
    sub_id = f"sub_dup_{uuid.uuid4().hex[:12]}"
    event_id = f"evt_dup_{uuid.uuid4().hex[:12]}"

    try:
        user = get_or_create_user(db, "dup_evt_user@example.com")
        sub = SubscriptionRequest(
            user_id=user.id,
            plan_id="monthly",
            plan_name="Monthly Access",
            amount=50.0,
            duration_days=30,
            status="pending",
            razorpay_subscription_id=sub_id,
            is_active=False
        )
        db.add(sub)
        db.commit()

        payload = {
            "entity": "event",
            "event_id": event_id,
            "event": "subscription.activated",
            "payload": {
                "subscription": {
                    "entity": {
                        "id": sub_id,
                        "status": "active"
                    }
                }
            }
        }
        body = json.dumps(payload).encode("utf-8")
        sig = generate_signature(body)

        # 1st delivery
        resp1 = client.post(
            "/api/razorpay/webhook",
            data=body,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig}
        )
        assert resp1.status_code == 200
        assert resp1.get_json()["status"] == "success"

        # 2nd delivery (Razorpay automatic retry)
        resp2 = client.post(
            "/api/razorpay/webhook",
            data=body,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig}
        )
        assert resp2.status_code == 200
        assert "already processed" in resp2.get_json()["message"].lower()

        # Exactly 1 record exists in processed_webhook_events
        count = db.query(ProcessedWebhookEvent).filter_by(event_id=event_id).count()
        assert count == 1

    finally:
        db.query(ProcessedWebhookEvent).filter_by(event_id=event_id).delete()
        db.commit()
        db.close()

# ==============================================================================
# TEST 7: Subscription lifecycle status transitions & anti-downgrade guards
# ==============================================================================
def test_7_subscription_status_transitions_and_anti_downgrade(client, monkeypatch):
    """
    Test 7: Tests all relevant subscription status changes:
    - subscription.activated activates subscription.
    - subscription.pending does NOT downgrade an approved active subscription.
    - subscription.halted sets status to halted and deactivates access.
    - subscription.cancelled terminates subscription and records cancellation metadata.
    - payment.failed updates payment status and records reason.
    """
    monkeypatch.setattr(RazorpayService, "get_credentials", classmethod(lambda cls: ("key", "secret", TEST_WEBHOOK_SECRET)))
    db = SessionLocal()
    sub_id = f"sub_lifecycle_{uuid.uuid4().hex[:12]}"
    evts_to_clean = []

    try:
        user = get_or_create_user(db, "lifecycle_user@example.com")
        sub = SubscriptionRequest(
            user_id=user.id,
            plan_id="monthly",
            plan_name="Monthly Access",
            amount=50.0,
            duration_days=30,
            status="pending",
            razorpay_subscription_id=sub_id,
            is_active=False
        )
        db.add(sub)
        db.commit()

        # Step A: subscription.activated -> marks approved & active
        evt_a = f"evt_act_{uuid.uuid4().hex[:10]}"
        evts_to_clean.append(evt_a)
        payload_a = {
            "event_id": evt_a,
            "event": "subscription.activated",
            "payload": {"subscription": {"entity": {"id": sub_id, "status": "active"}}}
        }
        body_a = json.dumps(payload_a).encode("utf-8")
        resp_a = client.post("/api/razorpay/webhook", data=body_a, headers={"Content-Type": "application/json", "X-Razorpay-Signature": generate_signature(body_a)})
        assert resp_a.status_code == 200

        sub = db.query(SubscriptionRequest).filter_by(razorpay_subscription_id=sub_id).first()
        assert sub.status == "approved"
        assert sub.is_active is True

        # Step B: subscription.pending arrives LATER -> MUST NOT downgrade approved subscription
        evt_b = f"evt_pnd_{uuid.uuid4().hex[:10]}"
        evts_to_clean.append(evt_b)
        payload_b = {
            "event_id": evt_b,
            "event": "subscription.pending",
            "payload": {"subscription": {"entity": {"id": sub_id, "status": "pending"}}}
        }
        body_b = json.dumps(payload_b).encode("utf-8")
        resp_b = client.post("/api/razorpay/webhook", data=body_b, headers={"Content-Type": "application/json", "X-Razorpay-Signature": generate_signature(body_b)})
        assert resp_b.status_code == 200

        sub = db.query(SubscriptionRequest).filter_by(razorpay_subscription_id=sub_id).first()
        # CRITICAL ASSERTION: status remains approved, is_active remains True
        assert sub.status == "approved"
        assert sub.is_active is True

        # Step C: payment.failed -> records failure reason without destroying approved period unless halted
        evt_c = f"evt_fail_{uuid.uuid4().hex[:10]}"
        evts_to_clean.append(evt_c)
        payload_c = {
            "event_id": evt_c,
            "event": "payment.failed",
            "payload": {
                "subscription": {"entity": {"id": sub_id}},
                "payment": {"entity": {"id": "pay_fail_123", "error_description": "Card expired"}}
            }
        }
        body_c = json.dumps(payload_c).encode("utf-8")
        resp_c = client.post("/api/razorpay/webhook", data=body_c, headers={"Content-Type": "application/json", "X-Razorpay-Signature": generate_signature(body_c)})
        assert resp_c.status_code == 200

        db.expire_all()
        sub = db.query(SubscriptionRequest).filter_by(razorpay_subscription_id=sub_id).first()
        assert sub.payment_status in ("failed", "PAYMENT_FAILED")
        assert "expired" in sub.rejection_reason.lower()

        # Step D: subscription.halted -> deactivates access
        evt_d = f"evt_halt_{uuid.uuid4().hex[:10]}"
        evts_to_clean.append(evt_d)
        payload_d = {
            "event_id": evt_d,
            "event": "subscription.halted",
            "payload": {"subscription": {"entity": {"id": sub_id, "status": "halted"}}}
        }
        body_d = json.dumps(payload_d).encode("utf-8")
        resp_d = client.post("/api/razorpay/webhook", data=body_d, headers={"Content-Type": "application/json", "X-Razorpay-Signature": generate_signature(body_d)})
        assert resp_d.status_code == 200

        db.expire_all()
        sub = db.query(SubscriptionRequest).filter_by(razorpay_subscription_id=sub_id).first()
        assert sub.status == "halted"
        assert sub.is_active is False

        # Step E: subscription.cancelled -> marks cancelled with timestamp and reason
        evt_e = f"evt_cancel_{uuid.uuid4().hex[:10]}"
        evts_to_clean.append(evt_e)
        payload_e = {
            "event_id": evt_e,
            "event": "subscription.cancelled",
            "payload": {
                "subscription": {
                    "entity": {
                        "id": sub_id,
                        "status": "cancelled",
                        "cancel_reason": "Customer requested cancellation via bank portal"
                    }
                }
            }
        }
        body_e = json.dumps(payload_e).encode("utf-8")
        resp_e = client.post("/api/razorpay/webhook", data=body_e, headers={"Content-Type": "application/json", "X-Razorpay-Signature": generate_signature(body_e)})
        assert resp_e.status_code == 200

        db.expire_all()
        sub = db.query(SubscriptionRequest).filter_by(razorpay_subscription_id=sub_id).first()
        assert sub.status == "cancelled"
        assert sub.is_active is False
        assert sub.cancelled_at is not None
        assert "Customer requested" in sub.cancellation_reason

    finally:
        db.query(ProcessedWebhookEvent).filter(ProcessedWebhookEvent.event_id.in_(evts_to_clean)).delete()
        db.commit()
        db.close()

# ==============================================================================
# TEST 8: Unexpected or unsupported event types safely acknowledged
# ==============================================================================
def test_8_unexpected_or_unsupported_event_types_safely_acknowledged(client, monkeypatch):
    """Test 8: Events not requiring subscription state changes (e.g. order.paid, virtual_account.created) return 200."""
    monkeypatch.setattr(RazorpayService, "get_credentials", classmethod(lambda cls: ("key", "secret", TEST_WEBHOOK_SECRET)))
    db = SessionLocal()
    evt_id = f"evt_unsupported_{uuid.uuid4().hex[:10]}"
    try:
        payload = {
            "entity": "event",
            "event_id": evt_id,
            "event": "order.paid",
            "payload": {
                "order": {"entity": {"id": "order_xyz123", "amount": 5000}}
            }
        }
        body = json.dumps(payload).encode("utf-8")
        sig = generate_signature(body)

        resp = client.post(
            "/api/razorpay/webhook",
            data=body,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "order.paid" in data["message"]

        # Verified recorded in idempotency log
        assert db.query(ProcessedWebhookEvent).filter_by(event_id=evt_id).count() == 1
    finally:
        db.query(ProcessedWebhookEvent).filter_by(event_id=evt_id).delete()
        db.commit()
        db.close()

# ==============================================================================
# TEST 9: Simulated full webhook request with synthetic data
# ==============================================================================
def test_9_simulated_webhook_request_with_synthetic_data(client, monkeypatch):
    """Test 9: End-to-end simulation of standard Razorpay subscription webhook delivery using synthetic payload."""
    monkeypatch.setattr(RazorpayService, "get_credentials", classmethod(lambda cls: ("key", "secret", TEST_WEBHOOK_SECRET)))
    db = SessionLocal()
    sub_id = f"sub_sim_{uuid.uuid4().hex[:12]}"
    evt_id = f"evt_sim_{uuid.uuid4().hex[:12]}"
    pay_id = f"pay_sim_{uuid.uuid4().hex[:12]}"

    try:
        user = get_or_create_user(db, "simulated_user@example.com")
        sub = SubscriptionRequest(
            user_id=user.id,
            plan_id="two_months",
            plan_name="2 Months Standard",
            amount=100.0,
            duration_days=60,
            status="pending",
            razorpay_subscription_id=sub_id,
            is_active=False
        )
        db.add(sub)
        db.commit()

        # Synthetic payload matching exact official Razorpay webhook structure
        synthetic_payload = {
            "entity": "event",
            "account_id": "acc_synthetic_test_001",
            "event": "subscription.charged",
            "event_id": evt_id,
            "contains": ["subscription", "payment"],
            "payload": {
                "subscription": {
                    "entity": {
                        "id": sub_id,
                        "entity": "subscription",
                        "plan_id": "plan_synthetic_two_months",
                        "status": "active",
                        "quantity": 1,
                        "total_count": 6,
                        "paid_count": 1,
                        "notes": {
                            "user_id": str(user.id),
                            "email": user.email
                        }
                    }
                },
                "payment": {
                    "entity": {
                        "id": pay_id,
                        "entity": "payment",
                        "amount": 10000,
                        "currency": "INR",
                        "status": "captured",
                        "method": "upi",
                        "captured": True
                    }
                }
            },
            "created_at": int(datetime.datetime.now(datetime.UTC).timestamp())
        }

        raw_body = json.dumps(synthetic_payload).encode("utf-8")
        signature = generate_signature(raw_body, TEST_WEBHOOK_SECRET)

        resp = client.post(
            "/api/razorpay/webhook",
            data=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": signature
            }
        )

        assert resp.status_code == 200
        res_data = resp.get_json()
        assert res_data["status"] == "success"

        # Verify state in database
        sub = db.query(SubscriptionRequest).filter_by(razorpay_subscription_id=sub_id).first()
        assert sub.status == "approved"
        assert sub.is_active is True
        assert sub.payment_status in ("captured", "PAYMENT_SUCCESS")
        assert sub.razorpay_payment_id == pay_id
        assert sub.expires_at is not None
        assert sub.duration_days == 60

    finally:
        db.query(ProcessedWebhookEvent).filter_by(event_id=evt_id).delete()
        db.commit()
        db.close()
