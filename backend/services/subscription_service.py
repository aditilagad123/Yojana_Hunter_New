import re
import logging
import datetime
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, and_, cast, String
from models import SubscriptionRequest, User, Profile, ProcessedWebhookEvent, PaymentAuditLog
from services.razorpay_service import RazorpayService, RazorpayAPIError
from services.event_service import EventService
from utils.activity import record_activity

logger = logging.getLogger(__name__)

FREE_SCHEMES_LIMIT = 5

SUBSCRIPTION_PLANS: Dict[str, Dict[str, Any]] = {
    "monthly": {
        "id": "monthly",
        "name": "Monthly Access",
        "price": 50,
        "currency": "INR",
        "duration_days": 30,
        "duration_label": "1 Month",
        "popular": False,
        "badge": "Flexible",
        "description": "Ideal for immediate scheme applications and fast verification.",
        "features": [
            "Full access to all matching government schemes (unlimited)",
            "Instant AI eligibility evaluation & detailed criteria breakdown",
            "Direct application portal links & procedure guidance",
            "Complete document checklists for every scheme",
            "Priority scheme update notifications",
            "30 days uninterrupted validity"
        ]
    },
    "two_months": {
        "id": "two_months",
        "name": "2 Months Standard",
        "price": 100,
        "currency": "INR",
        "duration_days": 60,
        "duration_label": "2 Months",
        "popular": False,
        "badge": "Standard",
        "description": "Perfect for seasonal schemes and continuous tracking across cycles.",
        "features": [
            "Full access to all matching government schemes (unlimited)",
            "Instant AI eligibility evaluation & detailed criteria breakdown",
            "Direct application portal links & procedure guidance",
            "Complete document checklists for every scheme",
            "Multi-scheme tracking & application reminders",
            "60 days uninterrupted validity"
        ]
    },
    "yearly": {
        "id": "yearly",
        "name": "Yearly Premium Pass",
        "price": 500,  # Configurable price
        "currency": "INR",
        "duration_days": 365,
        "duration_label": "12 Months (1 Year)",
        "popular": True,
        "badge": "Best Value (Save ₹100)",
        "description": "Complete year-round coverage for your entire family across Central and State schemes.",
        "features": [
            "Full access to all matching government schemes (unlimited)",
            "Instant AI eligibility evaluation & detailed criteria breakdown",
            "Direct application portal links & procedure guidance",
            "Complete document checklists for every scheme",
            "Priority AI scheme discovery alerts for newly launched schemes",
            "Dedicated family benefit tracking",
            "365 days uninterrupted full access"
        ]
    }
}

PLAN_COMPARISON = [
    {
        "feature": "View Matching Scheme Count",
        "free": "Yes (Total count shown)",
        "premium": "Yes (Total count shown)"
    },
    {
        "feature": "Accessible Scheme Details",
        "free": "First 5 matching schemes",
        "premium": "All matching schemes (Unlimited)"
    },
    {
        "feature": "Official Application Portal Links",
        "free": "First 5 schemes only",
        "premium": "All verified government schemes"
    },
    {
        "feature": "Required Document Checklists",
        "free": "First 5 schemes only",
        "premium": "Full checklists for all schemes"
    },
    {
        "feature": "Detailed Eligibility Explanations",
        "free": "First 5 schemes only",
        "premium": "Instant AI explanations on every scheme"
    },
    {
        "feature": "Application Tracking & Drafts",
        "free": "Limited",
        "premium": "Unlimited draft and application tracking"
    },
    {
        "feature": "New Scheme Launch Alerts",
        "free": "Standard",
        "premium": "Priority automated alerts"
    }
]


class SubscriptionService:
    """
    Manages citizen subscription tiers, manual admin approval workflow,
    and access limits without real payment processing.
    """

    @classmethod
    def get_plans(cls) -> Dict[str, Any]:
        """Returns all configured subscription plans and comparison matrix."""
        return {
            "plans": list(SUBSCRIPTION_PLANS.values()),
            "comparison": PLAN_COMPARISON,
            "free_limit": FREE_SCHEMES_LIMIT
        }

    @classmethod
    def get_active_subscription(cls, db, user_id: Optional[int]) -> Optional[SubscriptionRequest]:
        """
        Retrieves the active, non-expired approved subscription for a user.
        If an approved subscription has expired, marks it inactive.
        """
        if not user_id:
            return None

        now = datetime.datetime.utcnow()
        # Find approved or active subscriptions for this user
        sub = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.user_id == user_id,
            SubscriptionRequest.status.in_(["approved", "Approved", "active", "Active"])
        ).order_by(SubscriptionRequest.expires_at.desc()).first()

        if not sub:
            return None

        if sub.expires_at and sub.expires_at > now:
            if not sub.is_active:
                sub.is_active = True
                db.commit()
            return sub
        else:
            # Expired
            if sub.is_active:
                sub.is_active = False
                db.commit()
            return None

    @classmethod
    def is_user_premium(cls, db, user_id: Optional[int]) -> bool:
        """Determines if a user currently has an approved, unexpired premium pass."""
        if not user_id:
            return False
        return cls.get_active_subscription(db, user_id) is not None

    @classmethod
    def get_user_subscription_status(cls, db, user_id: Optional[int]) -> Dict[str, Any]:
        """
        Returns a rich status overview for the citizen profile:
        is_premium, active subscription details, pending request (if any),
        latest rejection (if any), and free tier limit.
        """
        if not user_id:
            return {
                "is_premium": False,
                "tier": "free",
                "free_limit": FREE_SCHEMES_LIMIT,
                "active_subscription": None,
                "pending_request": None,
                "has_pending_request": False,
                "latest_request": None
            }

        active = cls.get_active_subscription(db, user_id)
        
        # Check for verified payment awaiting admin review
        awaiting_admin = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.user_id == user_id,
            SubscriptionRequest.payment_verification_status == "verified",
            SubscriptionRequest.admin_approval_status.in_(["pending", "PENDING_ADMIN_REVIEW", "PENDING_ADMIN_APPROVAL", "UNDER_REVIEW"]),
            SubscriptionRequest.is_active == False
        ).order_by(SubscriptionRequest.updated_at.desc()).first()

        # Check for pending request
        pending = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.user_id == user_id,
            SubscriptionRequest.admin_approval_status.in_(["pending", "PENDING_ADMIN_REVIEW", "PENDING_ADMIN_APPROVAL", "UNDER_REVIEW"])
        ).order_by(SubscriptionRequest.requested_at.desc()).first()

        # Check for approved request ready for payment (not yet activated)
        approved_for_payment = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.user_id == user_id,
            SubscriptionRequest.admin_approval_status.in_(["APPROVED_FOR_PAYMENT", "ADMIN_APPROVED", "REQUIRES_RETRY"]),
            SubscriptionRequest.is_active == False
        ).order_by(SubscriptionRequest.reviewed_at.desc()).first()

        # Check latest request of any status
        latest = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.user_id == user_id
        ).order_by(SubscriptionRequest.requested_at.desc()).first()

        days_remaining = None
        if active and active.expires_at:
            delta = active.expires_at - datetime.datetime.utcnow()
            days_remaining = max(0, delta.days)

        return {
            "is_premium": bool(active is not None),
            "tier": "premium" if active else "free",
            "free_limit": FREE_SCHEMES_LIMIT,
            "active_subscription": active.to_dict(include_user=False) if active else None,
            "days_remaining": days_remaining,
            "awaiting_admin_approval": awaiting_admin.to_dict(include_user=False) if awaiting_admin else None,
            "has_awaiting_admin_approval": awaiting_admin is not None,
            "pending_request": pending.to_dict(include_user=False) if pending else None,
            "has_pending_request": pending is not None,
            "approved_for_payment": approved_for_payment.to_dict(include_user=False) if approved_for_payment else None,
            "has_approved_payment_request": approved_for_payment is not None,
            "latest_request": latest.to_dict(include_user=False) if latest else None
        }

    @classmethod
    def log_payment_audit(
        cls,
        db,
        subscription_request_id: int,
        action: str,
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        actor_id: Optional[int] = None,
        actor_role: str = "admin",
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """
        Records an audit log entry in PostgreSQL payment_audit_logs table.
        """
        try:
            audit = PaymentAuditLog(
                subscription_request_id=subscription_request_id,
                previous_status=previous_status,
                new_status=new_status,
                actor_id=actor_id,
                actor_role=actor_role,
                action=action,
                reason=reason,
                details=details or {},
                timestamp=datetime.datetime.utcnow()
            )
            db.add(audit)
            db.flush()
            return audit
        except Exception as e:
            logger.warning(f"Failed to record payment audit log: {e}")
            return None

    @classmethod
    def create_subscription_request(
        cls, 
        db, 
        user_id: int, 
        plan_id: str,
        phone_number: Optional[str] = None,
        bank_name: Optional[str] = None,
        bank_account_type: Optional[str] = None,
        payment_method: Optional[str] = None,
        admin_notes: Optional[str] = None
    ) -> Tuple[bool, str, Optional[SubscriptionRequest]]:
        """
        Submits a subscription request for administrative review before payment initiation.
        Prevents duplicate pending requests for the same user.
        Validates phone number and bank details if provided.
        Sets initial status to PENDING_ADMIN_REVIEW.
        """
        if plan_id not in SUBSCRIPTION_PLANS:
            return False, f"Invalid plan '{plan_id}'. Choose from: {', '.join(SUBSCRIPTION_PLANS.keys())}", None

        plan = SUBSCRIPTION_PLANS[plan_id]

        # 1. Prevent duplicate pending requests
        existing_pending = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.user_id == user_id,
            SubscriptionRequest.admin_approval_status.in_(["pending", "PENDING_ADMIN_REVIEW", "PENDING_ADMIN_APPROVAL", "UNDER_REVIEW"]),
            SubscriptionRequest.is_active == False
        ).first()

        if existing_pending:
            return False, f"You already have a pending subscription request for {existing_pending.plan_name}. Please wait for admin review or cancel your current request.", existing_pending

        # Check if already approved and awaiting payment
        existing_approved = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.user_id == user_id,
            SubscriptionRequest.plan_id == plan_id,
            SubscriptionRequest.admin_approval_status.in_(["APPROVED_FOR_PAYMENT", "ADMIN_APPROVED", "REQUIRES_RETRY", "approved"]),
            SubscriptionRequest.is_active == False
        ).first()
        if existing_approved:
            return True, f"Your request for {existing_approved.plan_name} has already been approved! You can proceed to payment.", existing_approved

        # 2. Check if user already has an active subscription
        active = cls.get_active_subscription(db, user_id)
        if active:
            note = f"User has active subscription until {active.expires_at.strftime('%d %b %Y')}. {admin_notes or ''}".strip()
        else:
            note = admin_notes

        clean_phone = (phone_number or "").strip()
        if clean_phone and len(clean_phone) > 20:
            clean_phone = clean_phone[:20]

        now = datetime.datetime.utcnow()
        req = SubscriptionRequest(
            user_id=user_id,
            plan_id=plan["id"],
            plan_name=plan["name"],
            amount=float(plan["price"]),
            currency=plan["currency"],
            duration_days=int(plan["duration_days"]),
            status="pending",
            admin_approval_status="PENDING_ADMIN_REVIEW",
            mandate_status="MANDATE_PENDING",
            payment_status="PAYMENT_PENDING",
            payment_verification_status="pending",
            phone_number=clean_phone or None,
            bank_name=bank_name,
            bank_account_type=bank_account_type,
            payment_method=payment_method,
            admin_notes=note,
            requested_at=now,
            created_at=now,
            is_active=False
        )

        db.add(req)
        db.commit()
        db.refresh(req)

        cls.log_payment_audit(
            db,
            subscription_request_id=req.id,
            action="REQUEST_CREATED",
            previous_status=None,
            new_status="PENDING_ADMIN_REVIEW",
            actor_id=user_id,
            actor_role="citizen",
            reason="Citizen submitted subscription request",
            details={
                "plan_id": plan["id"],
                "plan_name": plan["name"],
                "amount": float(plan["price"]),
                "payment_method": payment_method
            }
        )

        record_activity(
            db,
            user_id,
            "CREATE_SUBSCRIPTION_REQUEST",
            {
                "request_id": req.id,
                "plan": req.plan_name,
                "amount": req.amount
            }
        )

        return True, "Your subscription request has been submitted. Please wait for admin review.", req

    @classmethod
    def cancel_subscription_request(cls, db, user_id: int, request_id: int) -> Tuple[bool, str]:
        """Allows a user to cancel their own pending subscription request."""
        req = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.id == request_id,
            SubscriptionRequest.user_id == user_id
        ).first()

        if not req:
            return False, "Subscription request not found."

        if req.is_active:
            return False, "Cannot cancel an already active subscription through this endpoint."

        req.status = "cancelled"
        req.admin_approval_status = "ADMIN_REJECTED"
        req.rejection_reason = "Cancelled by citizen."
        req.is_active = False
        db.commit()
        return True, "Subscription request cancelled successfully."

    @classmethod
    def approve_subscription_for_payment(
        cls, 
        db, 
        request_id: int, 
        admin_id: int,
        admin_notes: Optional[str] = None
    ) -> Tuple[bool, str, Optional[SubscriptionRequest]]:
        """
        Admin action: Approves a subscription request for payment processing.
        Sets status to APPROVED_FOR_PAYMENT, does NOT mark as paid or activate subscription.
        """
        req = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.id == request_id
        ).first()

        if not req:
            return False, "Subscription request not found.", None

        if req.is_active:
            return True, "This subscription is already active.", req

        now = datetime.datetime.utcnow()
        prev_status = req.admin_approval_status

        req.admin_approval_status = "APPROVED_FOR_PAYMENT"
        req.admin_decision = "approved"
        req.status = "approved"
        req.reviewed_at = now
        req.reviewed_by_admin_id = admin_id
        req.is_active = False
        if admin_notes:
            req.admin_notes = admin_notes

        cls.log_payment_audit(
            db,
            subscription_request_id=req.id,
            action="ADMIN_APPROVED_FOR_PAYMENT",
            previous_status=prev_status,
            new_status="APPROVED_FOR_PAYMENT",
            actor_id=admin_id,
            actor_role="admin",
            reason=admin_notes or "Approved for payment processing",
            details={"plan_name": req.plan_name, "amount": req.amount}
        )

        db.commit()
        db.refresh(req)

        EventService.broadcast_subscription_event(req.user_id, "request_approved_for_payment", req.to_dict(include_user=False))

        record_activity(
            db, 
            admin_id, 
            "ADMIN_APPROVE_FOR_PAYMENT", 
            {
                "request_id": req.id,
                "user_id": req.user_id,
                "plan_name": req.plan_name,
                "amount": req.amount
            }
        )

        return True, f"Subscription request #{req.id} approved for payment processing.", req

    @classmethod
    def approve_subscription_request(
        cls, 
        db, 
        request_id: int, 
        admin_id: int,
        admin_notes: Optional[str] = None
    ) -> Tuple[bool, str, Optional[SubscriptionRequest]]:
        """
        Admin action: Approves a subscription request, authorizes payment workflow,
        and activates subscription if valid or records administrative approval.
        """
        req = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.id == request_id
        ).first()

        if not req:
            return False, "Subscription request not found.", None

        if req.payment_verification_status != "verified" and req.payment_status not in ("PAYMENT_SUCCESS", "PAID"):
            return False, "Unverified or failed requests cannot be marked as paid.", None

        if req.status == "approved" and req.is_active:
            return True, "This subscription request has already been approved and activated.", req

        now = datetime.datetime.utcnow()
        prev_status = req.admin_approval_status
        # Deactivate any previous active subscriptions for this user
        db.query(SubscriptionRequest).filter(
            SubscriptionRequest.user_id == req.user_id,
            SubscriptionRequest.id != req.id,
            SubscriptionRequest.is_active == True
        ).update({"is_active": False})

        # Calculate validity
        starts_at = now
        expires_at = now + datetime.timedelta(days=req.duration_days)

        req.status = "approved"
        req.admin_approval_status = "approved"
        req.admin_decision = "approved"
        req.reviewed_at = now
        req.reviewed_by_admin_id = admin_id
        req.starts_at = starts_at
        req.expires_at = expires_at
        req.payment_verified_at = now
        req.activated_at = now
        req.is_active = True
        req.rejection_reason = None
        if admin_notes:
            req.admin_notes = admin_notes

        cls.log_payment_audit(
            db,
            subscription_request_id=req.id,
            action="ADMIN_APPROVE_SUBSCRIPTION",
            previous_status=prev_status,
            new_status="PAID_AND_ACTIVE",
            actor_id=admin_id,
            actor_role="admin",
            reason=admin_notes or "Subscription approved and activated",
            details={"plan_name": req.plan_name, "amount": req.amount}
        )

        db.commit()
        db.refresh(req)

        EventService.broadcast_subscription_event(req.user_id, "payment_approved", req.to_dict(include_user=False))

        record_activity(
            db, 
            admin_id, 
            "ADMIN_APPROVE_SUBSCRIPTION", 
            {
                "request_id": req.id,
                "user_id": req.user_id,
                "plan_name": req.plan_name,
                "amount": req.amount
            }
        )

        return True, f"Subscription for {req.plan_name} approved successfully. Valid until {expires_at.strftime('%d %b %Y')}.", req

    @classmethod
    def reject_subscription_request(
        cls, 
        db, 
        request_id: int, 
        admin_id: int, 
        rejection_reason: Optional[str] = None
    ) -> Tuple[bool, str, Optional[SubscriptionRequest]]:
        """
        Admin action: Rejects a subscription request.
        Saves rejection status in PostgreSQL, records admin ID and decision timestamp,
        does not activate subscription, and sends updated status to user dashboard immediately.
        """
        req = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.id == request_id
        ).first()

        if not req:
            return False, "Subscription request not found.", None

        now = datetime.datetime.utcnow()
        prev_status = req.admin_approval_status
        req.admin_approval_status = "rejected"
        req.admin_decision = "rejected"
        req.status = "rejected"
        req.reviewed_at = now
        req.reviewed_by_admin_id = admin_id
        req.rejection_reason = (rejection_reason or "Request rejected by administrator.").strip()
        req.is_active = False

        cls.log_payment_audit(
            db,
            subscription_request_id=req.id,
            action="ADMIN_REJECT_SUBSCRIPTION_REQUEST",
            previous_status=prev_status,
            new_status="REJECTED",
            actor_id=admin_id,
            actor_role="admin",
            reason=req.rejection_reason
        )

        db.commit()
        db.refresh(req)

        # Broadcast live status update to user dashboard immediately
        EventService.broadcast_subscription_event(req.user_id, "payment_rejected", req.to_dict(include_user=False))

        record_activity(
            db,
            admin_id,
            "ADMIN_REJECT_SUBSCRIPTION_REQUEST",
            {
                "request_id": req.id,
                "user_id": req.user_id,
                "reason": req.rejection_reason
            }
        )

        return True, "Subscription request rejected.", req

    @classmethod
    def mark_payment_failed(
        cls,
        db,
        request_id: int,
        admin_id: int,
        failure_reason: Optional[str] = None,
        admin_notes: Optional[str] = None
    ) -> Tuple[bool, str, Optional[SubscriptionRequest]]:
        """
        Admin action: Records a confirmed failure or an administrative failure decision.
        """
        req = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.id == request_id
        ).first()

        if not req:
            return False, "Subscription request not found.", None

        now = datetime.datetime.utcnow()
        prev_status = req.payment_status
        req.payment_status = "PAYMENT_FAILED"
        req.mandate_status = "MANDATE_FAILED"
        req.is_active = False
        req.failure_reason = failure_reason or "Payment marked as failed by administrator."
        if admin_notes:
            req.admin_notes = admin_notes
        req.reviewed_at = now
        req.reviewed_by_admin_id = admin_id

        cls.log_payment_audit(
            db,
            subscription_request_id=req.id,
            action="ADMIN_MARK_PAYMENT_FAILED",
            previous_status=prev_status,
            new_status="PAYMENT_FAILED",
            actor_id=admin_id,
            actor_role="admin",
            reason=req.failure_reason
        )

        db.commit()
        db.refresh(req)

        record_activity(
            db,
            admin_id,
            "ADMIN_MARK_PAYMENT_FAILED",
            {
                "request_id": req.id,
                "user_id": req.user_id,
                "reason": req.failure_reason
            }
        )

        return True, f"Payment request #{req.id} marked as failed.", req

    @classmethod
    def mark_under_review(
        cls,
        db,
        request_id: int,
        admin_id: int,
        admin_notes: Optional[str] = None
    ) -> Tuple[bool, str, Optional[SubscriptionRequest]]:
        """
        Admin action: Holds a request for review when gateway response or citizen details require verification.
        """
        req = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.id == request_id
        ).first()

        if not req:
            return False, "Subscription request not found.", None

        now = datetime.datetime.utcnow()
        prev_status = req.admin_approval_status
        req.admin_approval_status = "UNDER_REVIEW"
        req.status = "review"
        if admin_notes:
            req.admin_notes = admin_notes
        req.reviewed_at = now
        req.reviewed_by_admin_id = admin_id

        cls.log_payment_audit(
            db,
            subscription_request_id=req.id,
            action="ADMIN_MARK_UNDER_REVIEW",
            previous_status=prev_status,
            new_status="UNDER_REVIEW",
            actor_id=admin_id,
            actor_role="admin",
            reason=admin_notes
        )

        db.commit()
        db.refresh(req)

        record_activity(
            db,
            admin_id,
            "ADMIN_MARK_UNDER_REVIEW",
            {
                "request_id": req.id,
                "user_id": req.user_id,
                "notes": admin_notes
            }
        )

        return True, f"Payment request #{req.id} marked for review.", req

    @classmethod
    def verify_gateway_status(
        cls,
        db,
        request_id: int,
        admin_id: int
    ) -> Tuple[bool, str, Optional[SubscriptionRequest]]:
        """
        Admin action: Queries Razorpay API for the actual gateway transaction/subscription status.
        Uses verified gateway state as financial source of truth.
        """
        req = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.id == request_id
        ).first()

        if not req:
            return False, "Subscription request not found.", None

        now = datetime.datetime.utcnow()
        reconciled_info = []

        if req.razorpay_subscription_id:
            try:
                rzp_sub = RazorpayService.fetch_subscription_details(req.razorpay_subscription_id)
                if rzp_sub:
                    sub_status = (rzp_sub.get("status") or "").lower()
                    reconciled_info.append(f"Subscription: {sub_status}")
                    if sub_status in ("active", "authenticated", "completed"):
                        req.mandate_status = "MANDATE_ACTIVE"
                        req.payment_status = "PAYMENT_SUCCESS"
                        if not req.is_active:
                            req.is_active = True
                            if not req.starts_at:
                                req.starts_at = now
                                req.expires_at = now + datetime.timedelta(days=req.duration_days)
                    elif sub_status in ("halted", "cancelled"):
                        req.mandate_status = "MANDATE_FAILED"
                        req.is_active = False
                    elif sub_status in ("pending", "created"):
                        req.mandate_status = "MANDATE_PENDING"
            except Exception as e:
                logger.warning(f"Error checking Razorpay subscription for req #{req.id}: {e}")

        if req.razorpay_payment_id:
            try:
                rzp_pay = RazorpayService.fetch_payment_details(req.razorpay_payment_id)
                if rzp_pay:
                    pay_status = (rzp_pay.get("status") or "").lower()
                    reconciled_info.append(f"Payment: {pay_status}")
                    if pay_status == "captured":
                        req.payment_status = "PAYMENT_SUCCESS"
                        req.mandate_status = "MANDATE_ACTIVE"
                        if not req.is_active:
                            req.is_active = True
                            if not req.starts_at:
                                req.starts_at = now
                                req.expires_at = now + datetime.timedelta(days=req.duration_days)
                    elif pay_status == "failed":
                        req.payment_status = "PAYMENT_FAILED"
                        req.mandate_status = "MANDATE_FAILED"
                        req.failure_reason = rzp_pay.get("error_description") or "Declined by bank"
            except Exception as e:
                logger.warning(f"Error checking Razorpay payment for req #{req.id}: {e}")

        if not reconciled_info:
            return False, "No gateway reference ID available on this request to query Razorpay.", req

        db.commit()
        db.refresh(req)

        msg = f"Gateway status verified: {', '.join(reconciled_info)}."
        record_activity(
            db,
            admin_id,
            "ADMIN_VERIFY_GATEWAY_STATUS",
            {
                "request_id": req.id,
                "reconciled": msg,
                "payment_status": req.payment_status,
                "mandate_status": req.mandate_status
            }
        )

        return True, msg, req

    @classmethod
    def record_admin_outcome_success(
        cls,
        db,
        request_id: int,
        admin_id: int,
        admin_notes: Optional[str] = None
    ) -> Tuple[bool, str, Optional[SubscriptionRequest]]:
        """
        Admin Option A: Payment Successful
        Confirms payment and e-mandate success, activating premium access.
        Reconciles with Razorpay if a transaction ID is present.
        """
        req = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.id == request_id
        ).first()

        if not req:
            return False, "Subscription request not found.", None

        now = datetime.datetime.utcnow()
        prev_status = req.payment_status

        # If Razorpay payment ID exists, attempt live reconciliation
        if req.razorpay_payment_id:
            try:
                rzp_pay = RazorpayService.fetch_payment_details(req.razorpay_payment_id)
                if rzp_pay and rzp_pay.get("status") == "failed":
                    return False, f"Cannot mark successful: Gateway reports payment status as failed ({rzp_pay.get('error_description')}).", req
            except Exception as e:
                logger.info(f"Reconciliation check note: {e}")

        # Check test simulation note
        note = admin_notes or ""
        key_id, _, _ = RazorpayService.get_credentials()
        is_test_env = (key_id and key_id.startswith("rzp_test_")) or not req.razorpay_payment_id
        if is_test_env and not req.razorpay_payment_id:
            note = f"[TEST MODE SIMULATION] {note}".strip()

        req.payment_status = "PAYMENT_SUCCESS"
        req.mandate_status = "MANDATE_ACTIVE"
        req.admin_approval_status = "APPROVED_FOR_PAYMENT"
        req.status = "approved"
        req.failure_reason = None
        req.payment_verified_at = now
        req.activated_at = now
        req.admin_notes = note or None
        req.reviewed_at = now
        req.reviewed_by_admin_id = admin_id

        # Activate subscription entitlement
        req.is_active = True
        if not req.starts_at or not req.expires_at or req.expires_at <= now:
            req.starts_at = now
            req.expires_at = now + datetime.timedelta(days=req.duration_days)

        cls.log_payment_audit(
            db,
            subscription_request_id=req.id,
            action="ADMIN_OUTCOME_PAYMENT_SUCCESSFUL",
            previous_status=prev_status,
            new_status="PAID_AND_ACTIVE",
            actor_id=admin_id,
            actor_role="admin",
            reason=note or "Option A: Confirmed payment and activated subscription",
            details={
                "plan_name": req.plan_name,
                "amount": req.amount,
                "payment_status": req.payment_status,
                "mandate_status": req.mandate_status,
                "test_mode": is_test_env
            }
        )

        db.commit()
        db.refresh(req)

        record_activity(
            db,
            admin_id,
            "ADMIN_OUTCOME_PAYMENT_SUCCESSFUL",
            {
                "request_id": req.id,
                "user_id": req.user_id,
                "plan_name": req.plan_name,
                "amount": req.amount,
                "payment_status": req.payment_status,
                "mandate_status": req.mandate_status
            }
        )

        return True, f"Option A Applied: Payment & e-Mandate confirmed successful for #{req.id}. Premium subscription activated.", req

    @classmethod
    def record_admin_outcome_mandate_failed(
        cls,
        db,
        request_id: int,
        admin_id: int,
        failure_reason: Optional[str] = None,
        admin_notes: Optional[str] = None
    ) -> Tuple[bool, str, Optional[SubscriptionRequest]]:
        """
        Admin Option B: Payment Successful but e-Mandate Failed
        Separates payment success from e-mandate failure.
        Payment is recorded as successful, but recurring mandate is recorded as failed.
        Subscription remains inactive until mandate is resolved or retry is completed.
        """
        req = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.id == request_id
        ).first()

        if not req:
            return False, "Subscription request not found.", None

        now = datetime.datetime.utcnow()
        prev_mandate = req.mandate_status
        req.payment_status = "PAYMENT_SUCCESS"
        req.mandate_status = "MANDATE_FAILED"
        req.admin_approval_status = "APPROVED_FOR_PAYMENT"
        req.status = "approved"
        req.is_active = False  # Recurring access requires active mandate
        req.failure_reason = failure_reason or "Payment was captured, but bank recurring e-Mandate registration was declined by issuing bank (e.g. NPCI clearance issue)."
        if admin_notes:
            req.admin_notes = admin_notes
        req.reviewed_at = now
        req.reviewed_by_admin_id = admin_id

        cls.log_payment_audit(
            db,
            subscription_request_id=req.id,
            action="ADMIN_OUTCOME_MANDATE_FAILED",
            previous_status=prev_mandate,
            new_status="MANDATE_FAILED",
            actor_id=admin_id,
            actor_role="admin",
            reason=req.failure_reason,
            details={"mandate_status": "MANDATE_FAILED", "payment_status": "PAYMENT_SUCCESS"}
        )

        db.commit()
        db.refresh(req)

        record_activity(
            db,
            admin_id,
            "ADMIN_OUTCOME_PAYMENT_SUCCESS_MANDATE_FAILED",
            {
                "request_id": req.id,
                "user_id": req.user_id,
                "plan_name": req.plan_name,
                "amount": req.amount,
                "payment_status": req.payment_status,
                "mandate_status": req.mandate_status,
                "failure_reason": req.failure_reason
            }
        )

        return True, f"Option B Applied: Payment successful but e-Mandate failed for #{req.id}. Recorded accurately without false activation.", req

    @classmethod
    def record_admin_outcome_failed(
        cls,
        db,
        request_id: int,
        admin_id: int,
        failure_reason: Optional[str] = None,
        admin_notes: Optional[str] = None
    ) -> Tuple[bool, str, Optional[SubscriptionRequest]]:
        """
        Admin Option C: Payment Failed
        Records both payment and mandate as failed.
        Subscription remains inactive and safe retry can be authorized.
        """
        req = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.id == request_id
        ).first()

        if not req:
            return False, "Subscription request not found.", None

        now = datetime.datetime.utcnow()
        prev_payment = req.payment_status
        req.payment_status = "PAYMENT_FAILED"
        req.mandate_status = "MANDATE_FAILED"
        req.is_active = False
        req.failure_reason = failure_reason or "Payment authorization declined by issuing bank or gateway."
        if admin_notes:
            req.admin_notes = admin_notes
        req.reviewed_at = now
        req.reviewed_by_admin_id = admin_id

        cls.log_payment_audit(
            db,
            subscription_request_id=req.id,
            action="ADMIN_OUTCOME_PAYMENT_FAILED",
            previous_status=prev_payment,
            new_status="PAYMENT_FAILED",
            actor_id=admin_id,
            actor_role="admin",
            reason=req.failure_reason,
            details={"mandate_status": "MANDATE_FAILED", "payment_status": "PAYMENT_FAILED"}
        )

        db.commit()
        db.refresh(req)

        record_activity(
            db,
            admin_id,
            "ADMIN_OUTCOME_PAYMENT_FAILED",
            {
                "request_id": req.id,
                "user_id": req.user_id,
                "plan_name": req.plan_name,
                "amount": req.amount,
                "failure_reason": req.failure_reason
            }
        )

        return True, f"Option C Applied: Payment #{req.id} marked as failed.", req

    @classmethod
    def authorize_retry_mandate(
        cls,
        db,
        request_id: int,
        admin_id: int,
        admin_notes: Optional[str] = None
    ) -> Tuple[bool, str, Optional[SubscriptionRequest]]:
        """
        Admin action: Authorizes the citizen to safely retry payment or e-mandate.
        Resets mandate to MANDATE_PENDING and approval to REQUIRES_RETRY / APPROVED_FOR_PAYMENT.
        Does NOT create duplicate charges.
        """
        req = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.id == request_id
        ).first()

        if not req:
            return False, "Subscription request not found.", None

        now = datetime.datetime.utcnow()
        prev_status = req.admin_approval_status
        req.admin_approval_status = "REQUIRES_RETRY"
        req.mandate_status = "MANDATE_PENDING"
        if req.payment_status != "PAYMENT_SUCCESS":
            req.payment_status = "PAYMENT_PENDING"
        req.failure_reason = None
        if admin_notes:
            req.admin_notes = admin_notes
        req.reviewed_at = now
        req.reviewed_by_admin_id = admin_id

        cls.log_payment_audit(
            db,
            subscription_request_id=req.id,
            action="ADMIN_AUTHORIZE_RETRY_MANDATE",
            previous_status=prev_status,
            new_status="REQUIRES_RETRY",
            actor_id=admin_id,
            actor_role="admin",
            reason=admin_notes or "Citizen authorized to retry e-mandate"
        )

        db.commit()
        db.refresh(req)

        record_activity(
            db,
            admin_id,
            "ADMIN_AUTHORIZE_RETRY_MANDATE",
            {
                "request_id": req.id,
                "user_id": req.user_id,
                "notes": admin_notes
            }
        )

        return True, f"Retry authorized for payment request #{req.id}. Citizen can now retry e-mandate.", req

    @classmethod
    def report_payment_failure(
        cls,
        db,
        user: User,
        razorpay_subscription_id: Optional[str] = None,
        razorpay_payment_id: Optional[str] = None,
        error_code: Optional[str] = None,
        error_description: Optional[str] = None,
        error_source: Optional[str] = None,
        error_step: Optional[str] = None,
        error_reason: Optional[str] = None,
        bank: Optional[str] = None,
        payment_method: Optional[str] = None
    ) -> Tuple[bool, str, Optional[SubscriptionRequest]]:
        """
        Records an isolated, user-specific and transaction-specific payment/mandate failure.
        CRITICAL: Never marks every user's mandate as failed because one user's mandate failed.
        """
        sub = None
        if razorpay_subscription_id:
            sub = db.query(SubscriptionRequest).filter(
                SubscriptionRequest.razorpay_subscription_id == razorpay_subscription_id,
                SubscriptionRequest.user_id == user.id
            ).first()

        if not sub:
            sub = db.query(SubscriptionRequest).filter(
                SubscriptionRequest.user_id == user.id
            ).order_by(SubscriptionRequest.requested_at.desc()).first()

        if not sub:
            return False, "No subscription record found for this user.", None

        # Check bank / e-mandate specifics
        bank_str = (bank or "").upper()
        method_str = (payment_method or "").lower()
        err_str = f"{error_code or ''} {error_description or ''} {error_reason or ''}".lower()

        is_mandate = bool(
            "mandate" in err_str or 
            "nach" in err_str or 
            "recurring" in err_str or 
            method_str in ("netbanking", "emandate", "bank_transfer") or 
            bank_str in ("HDFC", "ICICI")
        )

        if bank_str in ("HDFC", "ICICI"):
            safe_msg = (
                f"Your e-mandate could not be completed with {bank_str} Bank. "
                "In test/sandbox mode or without registered e-mandate authorization, bank authorization is declined. "
                "Please retry the authorization or choose another supported payment method (Credit/Debit Card or UPI AutoPay)."
            )
        elif is_mandate:
            safe_msg = "Your e-mandate could not be completed. Please retry the authorization or choose another supported payment method."
        else:
            safe_msg = error_description or "Payment was declined or cancelled by user. You can retry with a supported payment method."

        sub.payment_status = "PAYMENT_FAILED"
        if is_mandate:
            sub.mandate_status = "MANDATE_FAILED"
        sub.payment_method = payment_method or bank or "emandate"
        sub.failure_reason = safe_msg
        if razorpay_payment_id:
            sub.razorpay_payment_id = razorpay_payment_id
        sub.is_active = False

        db.commit()
        db.refresh(sub)

        record_activity(
            db,
            user.id,
            "PAYMENT_MANDATE_FAILED",
            {
                "request_id": sub.id,
                "bank": bank,
                "method": payment_method,
                "reason": safe_msg
            }
        )

        logger.info(f"Recorded isolated payment failure for user {user.id}, request {sub.id}: {safe_msg}")
        return True, safe_msg, sub

    @classmethod
    def list_admin_subscription_requests(
        cls, 
        db, 
        status_filter: Optional[str] = None, 
        search_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Returns all subscription requests for the admin portal with dynamic,
        mutually exclusive dashboard counts and user metadata.
        """
        now = datetime.datetime.utcnow()
        query = db.query(SubscriptionRequest).options(
            joinedload(SubscriptionRequest.user).joinedload(User.profile)
        )

        if search_query and search_query.strip():
            sq = f"%{search_query.strip().lower()}%"
            query = query.join(User, SubscriptionRequest.user_id == User.id).outerjoin(Profile, User.id == Profile.user_id).filter(
                (User.email.ilike(sq)) | 
                (Profile.full_name.ilike(sq)) | 
                (SubscriptionRequest.plan_name.ilike(sq)) |
                (SubscriptionRequest.plan_id.ilike(sq)) |
                (SubscriptionRequest.razorpay_subscription_id.ilike(sq)) |
                (SubscriptionRequest.razorpay_payment_id.ilike(sq)) |
                (SubscriptionRequest.razorpay_order_id.ilike(sq)) |
                (cast(SubscriptionRequest.id, String).ilike(sq)) |
                (SubscriptionRequest.phone_number.ilike(sq))
            )

        if status_filter and status_filter.lower() != "all":
            sf = status_filter.lower()
            if sf == "pending":
                query = query.filter(
                    SubscriptionRequest.is_active == False,
                    SubscriptionRequest.admin_approval_status.in_(["pending", "PENDING_ADMIN_APPROVAL", "PENDING_ADMIN_REVIEW", "UNDER_REVIEW"]) |
                    (SubscriptionRequest.status.in_(["pending", "review"])),
                    ~SubscriptionRequest.admin_approval_status.in_(["approved", "APPROVED_FOR_PAYMENT", "ADMIN_APPROVED", "REQUIRES_RETRY", "rejected", "ADMIN_REJECTED", "REJECTED", "cancelled"]),
                    ~SubscriptionRequest.status.in_(["rejected", "cancelled"]),
                    ~SubscriptionRequest.payment_status.in_(["PAYMENT_FAILED", "failed"]),
                    SubscriptionRequest.mandate_status != "MANDATE_FAILED"
                )
            elif sf == "approved":
                query = query.filter(
                    SubscriptionRequest.is_active == False,
                    SubscriptionRequest.admin_approval_status.in_(["approved", "APPROVED_FOR_PAYMENT", "ADMIN_APPROVED", "REQUIRES_RETRY"]) |
                    (SubscriptionRequest.status == "approved"),
                    ~SubscriptionRequest.admin_approval_status.in_(["rejected", "ADMIN_REJECTED", "REJECTED", "cancelled"]),
                    ~SubscriptionRequest.status.in_(["rejected", "cancelled"]),
                    ~SubscriptionRequest.payment_status.in_(["PAYMENT_FAILED", "failed"]),
                    SubscriptionRequest.mandate_status != "MANDATE_FAILED"
                )
            elif sf in ("active", "paid_active", "payment_success"):
                query = query.filter(
                    SubscriptionRequest.is_active == True,
                    (SubscriptionRequest.expires_at == None) | (SubscriptionRequest.expires_at > now)
                )
            elif sf in ("review", "under_review"):
                query = query.filter(
                    (SubscriptionRequest.admin_approval_status == "UNDER_REVIEW") |
                    (SubscriptionRequest.status == "review")
                )
            elif sf == "mandate_failed":
                query = query.filter(
                    SubscriptionRequest.mandate_status == "MANDATE_FAILED"
                )
            elif sf in ("failed", "rejected", "failed_rejected"):
                query = query.filter(
                    SubscriptionRequest.is_active == False,
                    (SubscriptionRequest.payment_status.in_(["PAYMENT_FAILED", "failed"])) |
                    (SubscriptionRequest.mandate_status == "MANDATE_FAILED") |
                    (SubscriptionRequest.admin_approval_status.in_(["rejected", "ADMIN_REJECTED", "REJECTED", "cancelled"])) |
                    (SubscriptionRequest.status.in_(["rejected", "Rejected", "cancelled", "Cancelled"]))
                )
            else:
                query = query.filter(
                    (SubscriptionRequest.status == sf) | 
                    (SubscriptionRequest.admin_approval_status == status_filter) |
                    (SubscriptionRequest.payment_status == status_filter)
                )

        requests = query.order_by(SubscriptionRequest.requested_at.desc()).all()

        # Compute dynamic counts across all statuses in PostgreSQL
        all_reqs = db.query(
            SubscriptionRequest.id,
            SubscriptionRequest.status,
            SubscriptionRequest.admin_approval_status,
            SubscriptionRequest.payment_status,
            SubscriptionRequest.mandate_status,
            SubscriptionRequest.is_active,
            SubscriptionRequest.expires_at
        ).all()

        total_count = len(all_reqs)
        active_count = 0
        failed_count = 0
        rejected_count = 0
        approved_count = 0
        pending_count = 0
        review_count = 0
        mandate_failed_count = 0

        for r_id, s, a, p, m, is_act, exp in all_reqs:
            # 1. Paid & Active: verified payment and active subscription
            if is_act and (exp is None or exp > now):
                active_count += 1
            # 2. Failed / Rejected: payment failed or request rejected by admin/user
            elif (
                a in ("rejected", "ADMIN_REJECTED", "REJECTED", "cancelled") or
                s in ("rejected", "Rejected", "cancelled", "Cancelled") or
                p in ("PAYMENT_FAILED", "failed") or
                m == "MANDATE_FAILED"
            ):
                if a in ("rejected", "ADMIN_REJECTED", "REJECTED", "cancelled") or s in ("rejected", "Rejected", "cancelled", "Cancelled"):
                    rejected_count += 1
                else:
                    failed_count += 1
            # 3. Approved for Pay: approved by admin for payment, not yet active or paid
            elif (
                a in ("approved", "APPROVED_FOR_PAYMENT", "ADMIN_APPROVED", "REQUIRES_RETRY") or
                s in ("approved", "Approved")
            ):
                approved_count += 1
            # 4. Pending Review: all awaiting admin review or authorization
            else:
                pending_count += 1

            # Secondary non-exclusive counts for specialized filter badges
            if a == "UNDER_REVIEW" or s == "review":
                review_count += 1
            if m == "MANDATE_FAILED":
                mandate_failed_count += 1

        return {
            "requests": [r.to_dict(include_user=True) for r in requests],
            "stats": {
                "total": total_count,
                "pending": pending_count,
                "approved": approved_count,
                "active": active_count,
                "failed": failed_count,
                "rejected": rejected_count,
                "review": review_count,
                "mandate_failed": mandate_failed_count
            }
        }

    # ==========================================
    # RAZORPAY SUBSCRIPTION PAYMENT METHODS
    # ==========================================

    @classmethod
    def create_checkout_session(
        cls, 
        db, 
        user: User, 
        plan_id: str,
        phone_number: Optional[str] = None,
        bank_name: Optional[str] = None,
        bank_account_type: Optional[str] = None,
        payment_method: Optional[str] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Initializes an authentic Razorpay subscription checkout session for the selected subscription plan.
        1. Validates plan existence and enforces server-side plan price (Monthly: 50, Two-Month: 100, Yearly: 500).
        2. Ensures citizen does not already have an active subscription.
        3. Enforces that the citizen has an approved subscription request prior to checkout.
        4. Creates a validated Razorpay Subscription on the gateway.
        5. Stores the subscription session in PostgreSQL.
        """
        if not plan_id or plan_id not in SUBSCRIPTION_PLANS:
            valid_keys = ", ".join(SUBSCRIPTION_PLANS.keys())
            return False, f"Invalid plan '{plan_id}'. Available plans: {valid_keys}", {}

        # 1. Check if user already has an active, unexpired subscription
        active = cls.get_active_subscription(db, user.id)
        if active:
            expiry_str = active.expires_at.strftime('%d %b %Y') if active.expires_at else "soon"
            return False, f"You already have an active subscription for {active.plan_name} valid until {expiry_str}.", {
                "active_subscription": active.to_dict(include_user=False)
            }

        # Validate phone number if provided
        clean_phone = ""
        if phone_number is not None:
            raw_phone = str(phone_number).strip()
            if raw_phone:
                p = re.sub(r'[\s\-\(\)\+]', '', raw_phone)
                if p.startswith('91') and len(p) == 12:
                    p = p[2:]
                elif p.startswith('0') and len(p) == 11:
                    p = p[1:]
                if len(p) == 10 and p.isdigit() and p[0] in "6789":
                    clean_phone = p
                else:
                    return False, "Please enter a valid 10-digit mobile number.", {}

        # 2. Retrieve existing non-active pending request or create a new one
        # Direct checkout bypasses any prior admin rejection block
        sub_req = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.user_id == user.id,
            SubscriptionRequest.is_active == False,
            SubscriptionRequest.payment_status.in_(["PAYMENT_PENDING", "pending", None])
        ).order_by(SubscriptionRequest.requested_at.desc()).first()

        plan = SUBSCRIPTION_PLANS[plan_id]
        amount = float(plan["price"])
        amount_in_paise = int(plan["price"] * 100)

        # Retrieve user profile name for persistent audit records
        user_profile = db.query(Profile).filter_by(user_id=user.id).first()
        u_name = user_profile.full_name if user_profile and user_profile.full_name else (user.email.split("@")[0].capitalize() if user.email else f"Citizen #{user.id}")

        now = datetime.datetime.utcnow()
        if not sub_req:
            sub_req = SubscriptionRequest(
                user_id=user.id,
                user_name=u_name,
                phone_number=None,  # Strictly NOT persisted in PostgreSQL for privacy compliance
                plan_id=plan["id"],
                plan_name=plan["name"],
                amount=amount,
                amount_in_paise=amount_in_paise,
                currency=plan["currency"],
                duration_days=plan["duration_days"],
                status="created",
                admin_approval_status="pending",
                mandate_status="MANDATE_PENDING",
                payment_status="PAYMENT_PENDING",
                payment_verification_status="pending",
                is_active=False,
                requested_at=now,
                created_at=now,
                updated_at=now
            )
            db.add(sub_req)
            db.flush()
        else:
            sub_req.user_name = u_name
            sub_req.phone_number = None

        key_id, _, _ = RazorpayService.get_credentials()
        if not key_id:
            return False, "Payment gateway is currently unconfigured. Missing Key ID in backend/.env.", {}

        # 3. Create authentic Razorpay subscription via official API in TEST MODE
        total_count = 12 if plan_id == "monthly" else (6 if plan_id == "two_months" else 1)
        sub_id = None
        rzp_plan_id = None
        try:
            rzp_sub = RazorpayService.create_razorpay_subscription(
                plan_id=plan_id,
                total_count=total_count,
                customer_notify=1,
                user_id=user.id,
                user_email=user.email or "",
                plan_config=plan,
                notes={
                    "user_id": str(user.id),
                    "plan_id": plan_id,
                    "request_id": str(sub_req.id)
                }
            )
            sub_id = rzp_sub.get("id")
            rzp_plan_id = rzp_sub.get("plan_id") or RazorpayService.get_or_resolve_plan_id(plan_id, plan)
        except RazorpayAPIError as e:
            logger.error(f"Razorpay subscription creation failed: {e.message}")
            return False, e.message, {"diagnostic": e.to_dict()}
        except Exception as e:
            logger.error(f"Razorpay subscription creation error: {e}")
            return False, f"Failed to initialize payment gateway subscription: {str(e)}", {}

        # 4. Create authentic Razorpay Order for guaranteed checkout completion across all payment methods
        order_id = None
        try:
            rzp_order = RazorpayService.create_order(
                amount_in_paise=amount_in_paise,
                currency=plan["currency"],
                receipt=f"rcpt_{sub_req.id}_{int(datetime.datetime.utcnow().timestamp())}",
                notes={
                    "user_id": str(user.id),
                    "plan_id": plan_id,
                    "request_id": str(sub_req.id),
                    "subscription_id": str(sub_id or "")
                }
            )
            order_id = rzp_order.get("id")
        except Exception as e:
            logger.warning(f"Could not create separate Razorpay order: {e}")
            order_id = sub_id

        # 5. Attach gateway subscription reference to request record
        sub_req.user_name = u_name
        sub_req.phone_number = None  # Ensure phone number is NEVER persisted in PostgreSQL
        sub_req.plan_id = plan["id"]
        sub_req.plan_name = plan["name"]
        sub_req.amount = amount
        sub_req.amount_in_paise = amount_in_paise
        sub_req.duration_days = plan["duration_days"]
        sub_req.currency = plan["currency"]
        sub_req.razorpay_subscription_id = sub_id or order_id
        sub_req.razorpay_order_id = order_id or sub_id
        sub_req.razorpay_plan_id = rzp_plan_id
        sub_req.mandate_status = "MANDATE_PENDING"
        sub_req.payment_status = "PAYMENT_PENDING"
        sub_req.payment_verification_status = "pending"
        if sub_req.admin_approval_status not in ("ADMIN_APPROVED", "APPROVED_FOR_PAYMENT", "approved"):
            sub_req.admin_approval_status = "pending"
            sub_req.status = "created"
        else:
            sub_req.status = "approved"
        sub_req.is_active = False
        sub_req.updated_at = datetime.datetime.utcnow()

        db.commit()
        db.refresh(sub_req)

        # In-memory only contact for Razorpay checkout prefill (never saved in PostgreSQL or user profile)
        contact_number = clean_phone

        return True, "Payment checkout session initialized successfully.", {
            "key_id": key_id,
            "order_id": order_id or sub_id,
            "subscription_id": sub_id or order_id,
            "plan_gateway_id": rzp_plan_id,
            "request_id": sub_req.id,
            "plan_id": plan["id"],
            "plan_name": plan["name"],
            "amount": plan["price"],
            "amount_in_paise": amount_in_paise,
            "currency": plan["currency"],
            "user": {
                "name": u_name,
                "email": user.email or "",
                "contact": contact_number
            }
        }

    @classmethod
    def verify_checkout_payment(
        cls,
        db,
        user: User,
        razorpay_payment_id: str,
        razorpay_order_id: Optional[str] = None,
        razorpay_subscription_id: Optional[str] = None,
        razorpay_signature: Optional[str] = None
    ) -> Tuple[bool, str, Optional[SubscriptionRequest]]:
        """
        Cryptographically verifies the Razorpay payment signature, confirms transaction with Razorpay,
        activates the subscription, and records live activity.
        """
        if not razorpay_payment_id or not razorpay_signature:
            return False, "Missing required payment verification parameters (payment_id, signature).", None

        order_or_sub_id = razorpay_subscription_id or razorpay_order_id

        # 1. Find the expected subscription record in PostgreSQL
        sub = None
        if order_or_sub_id:
            sub = db.query(SubscriptionRequest).filter(
                (SubscriptionRequest.razorpay_subscription_id == order_or_sub_id) |
                (SubscriptionRequest.razorpay_order_id == order_or_sub_id)
            ).first()

        if not sub:
            sub = db.query(SubscriptionRequest).filter(
                SubscriptionRequest.user_id == user.id,
                SubscriptionRequest.is_active == False
            ).order_by(SubscriptionRequest.requested_at.desc()).first()

        if not sub:
            return False, f"No subscription record found for payment order '{order_or_sub_id}'.", None

        # 2. Confirm the subscription belongs to the authenticated user
        if sub.user_id != user.id:
            logger.warning(f"Security: User {user.id} attempted to verify payment belonging to user {sub.user_id}")
            return False, "Unauthorized: This payment request belongs to a different user account.", None

        # 3. Cryptographically verify signature
        # Handles Razorpay Subscriptions (payment_id|subscription_id) and Orders/Fallbacks (order_id|payment_id)
        target_sub_id = razorpay_subscription_id or sub.razorpay_subscription_id
        target_order_id = razorpay_order_id or sub.razorpay_order_id
        is_valid_sig = False

        if razorpay_order_id and str(razorpay_order_id).startswith("order_"):
            is_valid_sig = RazorpayService.verify_payment_signature(
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature
            )

        if not is_valid_sig and target_sub_id and str(target_sub_id).startswith("sub_"):
            is_valid_sig = RazorpayService.verify_subscription_payment_signature(
                razorpay_payment_id=razorpay_payment_id,
                razorpay_subscription_id=target_sub_id,
                razorpay_signature=razorpay_signature
            )
        
        if not is_valid_sig and target_order_id:
            is_valid_sig = RazorpayService.verify_payment_signature(
                razorpay_order_id=target_order_id,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature
            )

        if not is_valid_sig and target_sub_id:
            # Check reverse pattern if client signed target_sub_id | payment_id
            is_valid_sig = RazorpayService.verify_payment_signature(
                razorpay_order_id=target_sub_id,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature
            )

        if not is_valid_sig:
            logger.warning(f"Signature mismatch for user {user.id}, payment {razorpay_payment_id}")
            sub.payment_status = "PAYMENT_FAILED"
            sub.mandate_status = "MANDATE_FAILED"
            sub.failure_reason = "Cryptographic signature verification failed"
            sub.is_active = False
            db.commit()
            EventService.broadcast_subscription_event(user.id, "payment_failed", sub.to_dict(include_user=False))
            return False, "Invalid cryptographic payment signature. Payment cannot be verified.", None

        # 4. Reconcile with Razorpay API (detect if bank declined transaction)
        try:
            pay_info = RazorpayService.fetch_payment_details(razorpay_payment_id)
            if pay_info and pay_info.get("status") == "failed":
                sub.payment_status = "PAYMENT_FAILED"
                sub.mandate_status = "MANDATE_FAILED"
                sub.failure_reason = pay_info.get("error_description", "Payment transaction was declined")
                sub.is_active = False
                db.commit()
                EventService.broadcast_subscription_event(user.id, "payment_failed", sub.to_dict(include_user=False))
                return False, f"Payment was declined by the bank: {sub.failure_reason}", None
        except Exception as e:
            logger.debug(f"Payment reconciliation check non-blocking: {e}")

        # 5. Activate subscription upon verified payment
        now = datetime.datetime.utcnow()
        # Deactivate prior active subscriptions for this user
        db.query(SubscriptionRequest).filter(
            SubscriptionRequest.user_id == user.id,
            SubscriptionRequest.id != sub.id,
            SubscriptionRequest.is_active == True
        ).update({"is_active": False})

        sub.payment_verification_status = "verified"
        sub.payment_status = "PAYMENT_SUCCESS"
        sub.mandate_status = "MANDATE_ACTIVE"
        sub.razorpay_payment_id = razorpay_payment_id
        sub.razorpay_signature = razorpay_signature
        if razorpay_subscription_id:
            sub.razorpay_subscription_id = razorpay_subscription_id
        if razorpay_order_id:
            sub.razorpay_order_id = razorpay_order_id
        sub.payment_verified_at = now

        # 5. Direct activation upon verified Razorpay payment (no admin approval required)
        sub.admin_approval_status = "approved"
        sub.status = "approved"
        sub.is_active = True
        sub.activated_at = now
        sub.starts_at = now
        sub.expires_at = now + datetime.timedelta(days=sub.duration_days)
        message = "Subscription activated successfully! Welcome to Yojana Hunter Premium."

        sub.updated_at = now

        cls.log_payment_audit(
            db,
            subscription_request_id=sub.id,
            action="PAYMENT_VERIFIED_AND_ACTIVATED",
            previous_status="PAYMENT_PENDING",
            new_status="PAID_AND_ACTIVE",
            actor_id=user.id,
            actor_role="citizen",
            reason="Verified cryptographic Razorpay payment signature",
            details={
                "payment_id": razorpay_payment_id,
                "order_id": sub.razorpay_order_id,
                "subscription_id": sub.razorpay_subscription_id,
                "is_active": sub.is_active
            }
        )

        db.commit()
        db.refresh(sub)

        # Broadcast live status update to user and admin dashboards
        EventService.broadcast_subscription_event(user.id, "payment_approved", sub.to_dict(include_user=False))

        record_activity(
            db,
            user.id,
            "SUBSCRIPTION_PAYMENT_VERIFIED",
            {
                "request_id": sub.id,
                "plan_name": sub.plan_name,
                "amount": sub.amount,
                "payment_id": razorpay_payment_id,
                "subscription_id": sub.razorpay_subscription_id
            }
        )

        logger.info(f"Payment verified for user {user.id} ({sub.plan_name}): {message}")
        return True, message, sub

    @classmethod
    def process_razorpay_webhook(
        cls,
        db,
        raw_body: bytes,
        signature: str,
        payload_json: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Processes official Razorpay webhook lifecycle events with cryptographic signature verification,
        idempotency protection via processed_webhook_events table, and state-downgrade prevention.

        Supported events:
        - subscription.activated: mandate established, activates subscription and deactivates older passes.
        - subscription.charged: recurring cycle charged successfully, extends paid period.
        - subscription.pending: charge or mandate pending; preserves active state if already approved.
        - subscription.halted / subscription.paused: failed cycle retries exhausted, deactivates access.
        - subscription.cancelled: subscription terminated; marks cancelled and records reason.
        - subscription.completed: all recurring cycles completed.
        - payment.captured: payment successfully settled.
        - payment.failed: payment attempt rejected.
        - Other events: acknowledged safely without state corruption.
        """
        # 1. Cryptographic signature verification
        if not RazorpayService.verify_webhook_signature(raw_body, signature):
            logger.warning("[RAZORPAY WEBHOOK] Rejected: Invalid cryptographic webhook signature.")
            return False, "Invalid webhook signature."

        # 2. Extract event metadata and check idempotency
        event = payload_json.get("event", "")
        raw_hash = hashlib.sha256(raw_body).hexdigest()[:24]
        event_id = payload_json.get("event_id") or payload_json.get("id") or f"evt_{raw_hash}"

        existing_event = db.query(ProcessedWebhookEvent).filter(
            ProcessedWebhookEvent.event_id == event_id
        ).first()

        if existing_event:
            logger.info(f"[RAZORPAY WEBHOOK] Event {event_id} already processed (idempotent duplicate acknowledged).")
            return True, f"Event '{event_id}' already processed."

        payload = payload_json.get("payload", {})
        sub_entity = payload.get("subscription", {}).get("entity", {})
        pay_entity = payload.get("payment", {}).get("entity", {})

        rzp_sub_id = sub_entity.get("id") or pay_entity.get("subscription_id")
        sub_record = None
        if rzp_sub_id:
            sub_record = db.query(SubscriptionRequest).filter(
                SubscriptionRequest.razorpay_subscription_id == rzp_sub_id
            ).first()

        now = datetime.datetime.utcnow()
        event_created_at = payload_json.get("created_at")
        event_dt = (
            datetime.datetime.fromtimestamp(event_created_at, tz=datetime.timezone.utc).replace(tzinfo=None)
            if event_created_at else now
        )

        # 3. Handle lifecycle events with state-machine & anti-downgrade guards
        if event == "subscription.activated":
            if sub_record:
                # Anti-downgrade guard: If subscription was already cancelled after this event was created, ignore
                if sub_record.status == "cancelled" and sub_record.cancelled_at and event_dt <= sub_record.cancelled_at:
                    logger.warning(
                        f"[RAZORPAY WEBHOOK] Ignored out-of-order 'subscription.activated' created at {event_dt} "
                        f"for subscription {sub_record.id} cancelled at {sub_record.cancelled_at}"
                    )
                else:
                    # Deactivate prior active subscriptions for this user
                    db.query(SubscriptionRequest).filter(
                        SubscriptionRequest.user_id == sub_record.user_id,
                        SubscriptionRequest.id != sub_record.id,
                        SubscriptionRequest.is_active == True
                    ).update({"is_active": False})

                    sub_record.status = "approved"
                    sub_record.admin_approval_status = "ADMIN_APPROVED"
                    sub_record.is_active = True
                    sub_record.payment_status = "PAYMENT_SUCCESS"
                    sub_record.mandate_status = "MANDATE_ACTIVE"
                    if not sub_record.starts_at:
                        sub_record.starts_at = now
                        sub_record.expires_at = now + datetime.timedelta(days=sub_record.duration_days)
                    sub_record.reviewed_at = now
                    logger.info(f"[RAZORPAY WEBHOOK] Activated subscription {sub_record.id} for user {sub_record.user_id}")
                    cls.log_payment_audit(
                        db,
                        subscription_request_id=sub_record.id,
                        action="WEBHOOK_SUBSCRIPTION_ACTIVATED",
                        previous_status=sub_record.admin_approval_status,
                        new_status="PAID_AND_ACTIVE",
                        actor_role="razorpay_webhook",
                        reason=f"Webhook event: {event}",
                        details={"event": event, "rzp_sub_id": rzp_sub_id}
                    )

        elif event == "subscription.charged":
            if sub_record:
                if sub_record.status == "cancelled" and sub_record.cancelled_at and event_dt <= sub_record.cancelled_at:
                    logger.warning(
                        f"[RAZORPAY WEBHOOK] Ignored out-of-order 'subscription.charged' for cancelled subscription {sub_record.id}"
                    )
                else:
                    # Deactivate prior active subscriptions for this user
                    db.query(SubscriptionRequest).filter(
                        SubscriptionRequest.user_id == sub_record.user_id,
                        SubscriptionRequest.id != sub_record.id,
                        SubscriptionRequest.is_active == True
                    ).update({"is_active": False})

                    sub_record.status = "approved"
                    sub_record.admin_approval_status = "ADMIN_APPROVED"
                    sub_record.is_active = True
                    sub_record.payment_status = "PAYMENT_SUCCESS"
                    sub_record.mandate_status = "MANDATE_ACTIVE"
                    pay_id = pay_entity.get("id")
                    if pay_id:
                        sub_record.razorpay_payment_id = pay_id

                    # Renewal extension: extend from current expiry if still valid, or from now
                    base_time = sub_record.expires_at if (sub_record.expires_at and sub_record.expires_at > now) else now
                    sub_record.expires_at = base_time + datetime.timedelta(days=sub_record.duration_days)
                    logger.info(
                        f"[RAZORPAY WEBHOOK] Charged & renewed subscription {sub_record.id} (user {sub_record.user_id}) "
                        f"until {sub_record.expires_at}"
                    )
                    cls.log_payment_audit(
                        db,
                        subscription_request_id=sub_record.id,
                        action="WEBHOOK_SUBSCRIPTION_CHARGED",
                        previous_status="PAID_AND_ACTIVE",
                        new_status="PAID_AND_ACTIVE",
                        actor_role="razorpay_webhook",
                        reason="Recurring charge processed by Razorpay",
                        details={"event": event, "payment_id": pay_id}
                    )

        elif event == "subscription.pending":
            if sub_record:
                # Anti-downgrade guard: If subscription is already active and approved, DO NOT downgrade it to pending!
                if sub_record.status == "approved" and sub_record.is_active and sub_record.expires_at and sub_record.expires_at > now:
                    logger.info(
                        f"[RAZORPAY WEBHOOK] Preserved active approved subscription {sub_record.id}; "
                        "ignored 'subscription.pending' state downgrade."
                    )
                elif sub_record.status not in ("cancelled", "completed", "halted"):
                    sub_record.status = "pending"
                    sub_record.is_active = False
                    logger.info(f"[RAZORPAY WEBHOOK] Marked subscription {sub_record.id} as pending")

        elif event == "payment.captured":
            if sub_record:
                sub_record.payment_status = "PAYMENT_SUCCESS"
                sub_record.mandate_status = "MANDATE_ACTIVE"
                pay_id = pay_entity.get("id")
                if pay_id:
                    sub_record.razorpay_payment_id = pay_id
                logger.info(f"[RAZORPAY WEBHOOK] Payment captured for subscription {sub_record.id}")
                cls.log_payment_audit(
                    db,
                    subscription_request_id=sub_record.id,
                    action="WEBHOOK_PAYMENT_CAPTURED",
                    previous_status=sub_record.payment_status,
                    new_status="PAYMENT_SUCCESS",
                    actor_role="razorpay_webhook",
                    reason="Payment captured by gateway",
                    details={"event": event, "payment_id": pay_id}
                )

        elif event == "payment.failed":
            if sub_record:
                sub_record.payment_status = "PAYMENT_FAILED"
                sub_record.mandate_status = "MANDATE_FAILED"
                err_desc = (
                    pay_entity.get("error_description") or 
                    pay_entity.get("error_reason") or 
                    "Payment authorization failed"
                )
                sub_record.failure_reason = err_desc
                sub_record.rejection_reason = err_desc
                logger.warning(f"[RAZORPAY WEBHOOK] Payment failed for subscription {sub_record.id}: {err_desc}")
                cls.log_payment_audit(
                    db,
                    subscription_request_id=sub_record.id,
                    action="WEBHOOK_PAYMENT_FAILED",
                    previous_status=sub_record.payment_status,
                    new_status="PAYMENT_FAILED",
                    actor_role="razorpay_webhook",
                    reason=err_desc,
                    details={"event": event}
                )

        elif event in ("subscription.halted", "subscription.paused"):
            if sub_record:
                sub_record.is_active = False
                sub_record.mandate_status = "MANDATE_FAILED"
                sub_record.status = "halted"
                sub_record.rejection_reason = "Subscription halted by payment gateway due to failed charges"
                logger.info(f"[RAZORPAY WEBHOOK] Halted subscription {sub_record.id}")
                cls.log_payment_audit(
                    db,
                    subscription_request_id=sub_record.id,
                    action="WEBHOOK_SUBSCRIPTION_HALTED",
                    previous_status="PAID_AND_ACTIVE",
                    new_status="MANDATE_FAILED",
                    actor_role="razorpay_webhook",
                    reason=sub_record.rejection_reason
                )

        elif event == "subscription.cancelled":
            if sub_record:
                sub_record.is_active = False
                sub_record.mandate_status = "MANDATE_FAILED"
                sub_record.status = "cancelled"
                sub_record.cancelled_at = event_dt
                cancel_reason = sub_entity.get("cancel_reason") or "Subscription cancelled via Razorpay"
                sub_record.cancellation_reason = cancel_reason
                logger.info(f"[RAZORPAY WEBHOOK] Cancelled subscription {sub_record.id}: {cancel_reason}")
                cls.log_payment_audit(
                    db,
                    subscription_request_id=sub_record.id,
                    action="WEBHOOK_SUBSCRIPTION_CANCELLED",
                    previous_status=sub_record.status,
                    new_status="cancelled",
                    actor_role="razorpay_webhook",
                    reason=cancel_reason
                )

        elif event == "subscription.completed":
            if sub_record:
                sub_record.status = "completed"
                # If expiry date already passed, mark inactive
                if sub_record.expires_at and sub_record.expires_at < now:
                    sub_record.is_active = False
                logger.info(f"[RAZORPAY WEBHOOK] Completed all cycles for subscription {sub_record.id}")

        else:
            logger.info(f"[RAZORPAY WEBHOOK] Webhook event '{event}' acknowledged without state modification.")

        # 4. Record processed webhook event for reliable idempotency
        try:
            event_log = ProcessedWebhookEvent(
                event_id=event_id,
                event_type=event,
                entity_id=rzp_sub_id,
                payload=payload_json,
                processed_at=now
            )
            db.add(event_log)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[RAZORPAY WEBHOOK] Error persisting webhook event log: {e}")

        return True, f"Webhook event '{event}' processed successfully."

