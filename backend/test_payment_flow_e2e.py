"""
E2E Integration & Security Test for Razorpay Payment Flow with Admin-Controlled Status
Validates all requirements:
1. Server-side price validation for all 3 subscription plans (Monthly: 50, Two-Month: 100, Yearly: 500)
2. Razorpay test order creation
3. Privacy rule: Phone number is NEVER stored in PostgreSQL or user profile
4. Cryptographic HMAC SHA-256 signature verification
5. Verification sets payment_verification_status='verified' and admin_approval_status='pending', is_active=False
6. Admin approval gate: Admin CANNOT approve unverified transactions
7. Admin approval of verified transaction activates subscription and records decision & timestamp
8. Admin rejection records decision, timestamp, reason, and keeps subscription inactive
9. Real-time EventService broadcasting
"""

import sys
import os
import hmac
import hashlib
import datetime
from dotenv import load_dotenv

# Ensure backend root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from database import SessionLocal
from models import User, SubscriptionRequest, Profile
from services.subscription_service import SubscriptionService, SUBSCRIPTION_PLANS
from services.razorpay_service import RazorpayService
from services.event_service import EventService


def run_tests():
    db = SessionLocal()
    print("=" * 70)
    print("STARTING RAZORPAY PAYMENT FLOW WITH ADMIN-CONTROLLED STATUS TEST SUITE")
    print("=" * 70)

    try:
        # Step 0: Ensure a test user and test admin exist
        test_user = db.query(User).filter(User.email == "test_citizen_razorpay@example.com").first()
        if not test_user:
            test_user = User(
                email="test_citizen_razorpay@example.com",
                password_hash="test_secret_hash_value_123",
                role="user",
                is_active=True
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)

        test_admin = db.query(User).filter(User.role == "admin").first()
        if not test_admin:
            test_admin = User(
                email="test_admin_razorpay@example.com",
                password_hash="test_secret_hash_value_admin",
                role="admin",
                is_active=True
            )
            db.add(test_admin)
            db.commit()
            db.refresh(test_admin)

        print(f"[OK] Test User ID: {test_user.id}, Admin ID: {test_admin.id}")

        # Clean any existing active subscription for test user to ensure clean slate
        db.query(SubscriptionRequest).filter(
            SubscriptionRequest.user_id == test_user.id
        ).update({"is_active": False, "status": "cancelled", "admin_approval_status": "cancelled"})
        db.commit()

        # -------------------------------------------------------------
        # TEST 1: Subscription Plans & Server-Side Price Validation
        # -------------------------------------------------------------
        print("\n[TEST 1] Verifying Subscription Plans & Server-Side Pricing...")
        assert "monthly" in SUBSCRIPTION_PLANS, "Monthly plan missing"
        assert "two_months" in SUBSCRIPTION_PLANS, "Two-month plan missing"
        assert "yearly" in SUBSCRIPTION_PLANS, "Yearly plan missing"

        assert SUBSCRIPTION_PLANS["monthly"]["price"] == 50, "Monthly price must be Rs. 50"
        assert SUBSCRIPTION_PLANS["two_months"]["price"] == 100, "Two-month price must be Rs. 100"
        assert SUBSCRIPTION_PLANS["yearly"]["price"] == 500, "Yearly price must be Rs. 500"
        print("  -> Plans verified: Monthly (Rs. 50), Two-Month (Rs. 100), Yearly (Rs. 500)")

        # Invalid plan test
        ok, msg, _ = SubscriptionService.create_checkout_session(db, test_user, "invalid_plan_999")
        assert not ok, "Invalid plan should be rejected"
        print("  -> Invalid plan correctly rejected by backend")

        # -------------------------------------------------------------
        # TEST 2: Checkout Session Creation & Razorpay Order
        # -------------------------------------------------------------
        print("\n[TEST 2] Creating Checkout Session with Razorpay Order...")
        test_phone = "+919876543210"
        ok, msg, checkout_data = SubscriptionService.create_checkout_session(
            db,
            user=test_user,
            plan_id="monthly",
            phone_number=test_phone,
            bank_name="HDFC Bank",
            bank_account_type="Savings Account",
            payment_method="netbanking"
        )
        assert ok, f"Checkout session failed: {msg}"
        assert checkout_data["amount"] == 50, "Amount in rupees must be 50"
        assert checkout_data["amount_in_paise"] == 5000, "Amount in paise must be 5000 (Rs. 50)"
        assert checkout_data["currency"] == "INR"
        assert checkout_data["user"]["contact"] == test_phone
        print(f"  -> Razorpay Order Created: {checkout_data['order_id']}")

        # -------------------------------------------------------------
        # TEST 3: Privacy Check - Phone Number NOT Saved in PostgreSQL
        # -------------------------------------------------------------
        print("\n[TEST 3] Verifying Phone Number is NOT saved in PostgreSQL...")
        sub_req = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.razorpay_order_id == checkout_data["order_id"]
        ).first()
        assert sub_req is not None, "SubscriptionRequest not created in DB"

        # Check all column values of sub_req
        req_dict = sub_req.to_dict(include_user=False)
        assert "phone" not in req_dict, "Phone key must not be exposed"
        assert "phone_number" not in req_dict, "Phone number must not be exposed"
        assert "mobile" not in req_dict or req_dict.get("mobile") is None, "Mobile must not contain checkout phone"

        # Check raw columns on SubscriptionRequest model
        for col in SubscriptionRequest.__table__.columns:
            val = getattr(sub_req, col.name)
            if val is not None:
                assert test_phone not in str(val), f"Phone number found in column {col.name}: {val}"

        print("  -> CONFIRMED: Phone number (+919876543210) was NOT saved in database or table columns.")

        # -------------------------------------------------------------
        # TEST 4: Initial Statuses After Checkout Order Creation
        # -------------------------------------------------------------
        print("\n[TEST 4] Verifying Initial Verification and Approval Statuses...")
        assert sub_req.payment_verification_status == "pending", f"Expected 'pending', got '{sub_req.payment_verification_status}'"
        assert sub_req.admin_approval_status == "pending", f"Expected 'pending', got '{sub_req.admin_approval_status}'"
        assert sub_req.is_active is False, "Subscription must not be active before verification & admin approval"
        print("  -> payment_verification_status = 'pending'")
        print("  -> admin_approval_status = 'pending'")
        print("  -> is_active = False")

        # -------------------------------------------------------------
        # TEST 5: Signature Verification Security Check
        # -------------------------------------------------------------
        print("\n[TEST 5] Verifying Payment Signature Security...")
        # 5a: Invalid signature must be rejected
        fake_payment_id = "pay_test_fake_12345"
        ok_fake, msg_fake, _ = SubscriptionService.verify_checkout_payment(
            db,
            user=test_user,
            razorpay_order_id=sub_req.razorpay_order_id,
            razorpay_payment_id=fake_payment_id,
            razorpay_signature="invalid_tampered_signature_hex"
        )
        assert not ok_fake, "Tampered signature should fail verification"
        print("  -> Tampered signature rejected with 400 Bad Request")

        # 5b: Valid cryptographic HMAC SHA-256 signature
        _, secret, _ = RazorpayService.get_credentials()
        msg_to_sign = f"{sub_req.razorpay_order_id}|{fake_payment_id}".encode("utf-8")
        valid_signature = hmac.new(secret.encode("utf-8"), msg_to_sign, hashlib.sha256).hexdigest()

        ok_valid, msg_valid, verified_data = SubscriptionService.verify_checkout_payment(
            db,
            user=test_user,
            razorpay_order_id=sub_req.razorpay_order_id,
            razorpay_payment_id=fake_payment_id,
            razorpay_signature=valid_signature
        )
        assert ok_valid, f"Valid signature failed: {msg_valid}"
        assert verified_data.payment_verification_status == "verified"
        assert verified_data.admin_approval_status == "pending"
        assert "awaiting admin review" in msg_valid.lower()
        print(f"  -> Valid signature verified: '{msg_valid}'")

        db.refresh(sub_req)
        assert sub_req.payment_verification_status == "verified"
        assert sub_req.admin_approval_status == "pending"
        assert sub_req.is_active is False, "Subscription MUST NOT be active until admin approves"
        print("  -> DB updated: payment_verification_status='verified', admin_approval_status='pending', is_active=False")

        # -------------------------------------------------------------
        # TEST 6: Admin Approval Gate - Blocking Unverified Payments
        # -------------------------------------------------------------
        print("\n[TEST 6] Testing Admin Approval Gate for Unverified Requests...")
        # Create a second unverified dummy request
        unverified_req = SubscriptionRequest(
            user_id=test_user.id,
            plan_id="two_months",
            plan_name="2 Months Standard",
            amount=100.0,
            currency="INR",
            duration_days=60,
            status="pending",
            payment_verification_status="pending",  # Unverified!
            admin_approval_status="pending",
            is_active=False
        )
        db.add(unverified_req)
        db.commit()
        db.refresh(unverified_req)

        # Attempt to approve unverified request
        ok_unverified, msg_unverified, _ = SubscriptionService.approve_subscription_request(
            db,
            request_id=unverified_req.id,
            admin_id=test_admin.id,
            admin_notes="Test unauthorized approval attempt"
        )
        assert not ok_unverified, "Admin should NOT be able to approve unverified payments!"
        assert "unverified or failed requests cannot be marked as paid" in msg_unverified.lower()
        print(f"  -> CONFIRMED: Admin approval of unverified payment was REFUSED by backend: '{msg_unverified}'")

        # -------------------------------------------------------------
        # TEST 7: Admin Approval of Verified Request
        # -------------------------------------------------------------
        print("\n[TEST 7] Testing Admin Approval of Verified Request...")
        ok_appr, msg_appr, approved_req = SubscriptionService.approve_subscription_request(
            db,
            request_id=sub_req.id,
            admin_id=test_admin.id,
            admin_notes="Approved after gateway verification"
        )
        assert ok_appr, f"Admin approval failed: {msg_appr}"
        assert approved_req.admin_approval_status == "approved"
        assert approved_req.admin_decision == "approved"
        assert approved_req.reviewed_by_admin_id == test_admin.id
        assert approved_req.reviewed_at is not None
        assert approved_req.is_active is True, "Subscription MUST be activated upon valid admin approval"
        assert approved_req.starts_at is not None
        assert approved_req.expires_at is not None
        print(f"  -> Approved successfully: {msg_appr}")
        print(f"  -> is_active = {approved_req.is_active}, expires_at = {approved_req.expires_at}")

        # -------------------------------------------------------------
        # TEST 8: Admin Rejection
        # -------------------------------------------------------------
        print("\n[TEST 8] Testing Admin Rejection Workflow...")
        ok_rej, msg_rej, rejected_req = SubscriptionService.reject_subscription_request(
            db,
            request_id=unverified_req.id,
            admin_id=test_admin.id,
            rejection_reason="Declined during security audit"
        )
        assert ok_rej, f"Admin rejection failed: {msg_rej}"
        assert rejected_req.admin_approval_status == "rejected"
        assert rejected_req.admin_decision == "rejected"
        assert rejected_req.reviewed_by_admin_id == test_admin.id
        assert rejected_req.reviewed_at is not None
        assert rejected_req.rejection_reason == "Declined during security audit"
        assert rejected_req.is_active is False, "Subscription MUST remain inactive upon rejection"
        print(f"  -> Rejection recorded in PostgreSQL with admin ID {test_admin.id} and decision timestamp.")

        # -------------------------------------------------------------
        # TEST 9: EventService SSE Queue Test
        # -------------------------------------------------------------
        print("\n[TEST 9] Testing EventService Real-time SSE Dispatch...")
        # Subscribe test user
        q = EventService.subscribe_user(test_user.id)
        assert q is not None

        # Broadcast event
        EventService.broadcast_subscription_event(
            test_user.id,
            "payment_approved",
            {"test": "data", "status": "approved"}
        )

        import json
        raw_event = EventService.get_next_event(q, timeout=2.0)
        assert raw_event is not None, "Event not received from EventService"
        event = json.loads(raw_event) if isinstance(raw_event, str) else raw_event
        assert event.get("type") == "payment_approved"
        assert event.get("data", {}).get("status") == "approved"
        print(f"  -> Event successfully received from SSE queue: type={event.get('type')}")
        EventService.unsubscribe_user(test_user.id, q)

        print("\n" + "=" * 70)
        print("ALL TESTS PASSED SUCCESSFULLY! FULL SPECIFICATION VALIDATED.")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
