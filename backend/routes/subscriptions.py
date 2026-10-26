import logging
from flask import Blueprint, request, jsonify, g
from database import SessionLocal
from utils.auth import token_required, optional_auth
from services.subscription_service import SubscriptionService
from services.razorpay_service import RazorpayService

logger = logging.getLogger(__name__)

subscriptions_bp = Blueprint("subscriptions", __name__)

@subscriptions_bp.route("/plans", methods=["GET"])
def get_subscription_plans():
    """
    GET /api/subscriptions/plans
    Returns list of active subscription plans, pricing, Free vs Premium comparison,
    and verified Razorpay Test Mode configuration.
    """
    plans_data = SubscriptionService.get_plans()
    plans_data["test_mode"] = True
    return jsonify(plans_data)

@subscriptions_bp.route("/plans/verify-gateway", methods=["GET"])
def verify_gateway_plans():
    """
    GET /api/subscriptions/plans/verify-gateway
    Verifies that all three configured Plan IDs belong to the same active Razorpay Test Mode account.
    """
    verification = RazorpayService.verify_all_configured_plans()
    return jsonify(verification), 200 if verification.get("success") else 500

@subscriptions_bp.route("/my-status", methods=["GET"])
@token_required
def get_my_subscription_status():
    """
    GET /api/subscriptions/my-status
    Returns the authenticated user's active plan, expiry date, and pending requests.
    """
    db = SessionLocal()
    try:
        user = g.current_user
        status = SubscriptionService.get_user_subscription_status(db, user.id)
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error fetching subscription status for user {g.current_user.id}: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@subscriptions_bp.route("/checkout", methods=["POST"])
@token_required
def create_subscription_checkout():
    """
    POST /api/subscriptions/checkout
    Initializes a Razorpay checkout session for the selected subscription plan.
    Validates server-side plan pricing, accepts in-memory phone number for prefill only,
    accepts bank details, and registers a pending SubscriptionRequest.
    Never exposes Key Secret.
    """
    db = SessionLocal()
    try:
        user = g.current_user
        payload = request.get_json() or {}
        plan_id = payload.get("plan_id") or payload.get("planId")
        phone_number = payload.get("phone_number") or payload.get("phone") or payload.get("mobile")
        bank_name = payload.get("bank_name") or payload.get("bankName")
        bank_account_type = payload.get("bank_account_type") or payload.get("account_type") or payload.get("accountType")
        payment_method = payload.get("payment_method") or payload.get("paymentMethod")

        if not plan_id:
            return jsonify({
                "error": "Plan selection required",
                "message": "Please choose a valid subscription plan (monthly, two_months, yearly)."
            }), 400

        success, message, checkout_data = SubscriptionService.create_checkout_session(
            db,
            user=user,
            plan_id=plan_id,
            phone_number=phone_number,
            bank_name=bank_name,
            bank_account_type=bank_account_type,
            payment_method=payment_method
        )

        if not success:
            status_code = 403 if checkout_data.get("requires_admin_approval") else 400
            return jsonify({
                "error": "Admin approval required" if checkout_data.get("requires_admin_approval") else "Checkout initialization failed",
                "message": message,
                "diagnostic": checkout_data.get("diagnostic"),
                "details": checkout_data
            }), status_code

        return jsonify({
            "success": True,
            "message": message,
            **checkout_data
        }), 200

    except Exception as e:
        db.rollback()
        logger.error(f"Error in subscription checkout: {e}")
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
    finally:
        db.close()

@subscriptions_bp.route("/verify", methods=["POST"])
@token_required
def verify_subscription_payment():
    """
    POST /api/subscriptions/verify
    Cryptographically verifies the Razorpay payment signature from the client callback.
    Sets payment_verification_status = 'verified' and admin_approval_status = 'pending'.
    Does NOT mark as paid or activate the subscription until an administrator explicitly approves!
    Returns 'Your payment request is awaiting admin review.'
    """
    db = SessionLocal()
    try:
        user = g.current_user
        payload = request.get_json() or {}
        
        payment_id = payload.get("razorpay_payment_id") or payload.get("payment_id")
        order_id = payload.get("razorpay_order_id") or payload.get("order_id")
        subscription_id = payload.get("razorpay_subscription_id") or payload.get("subscription_id")
        signature = payload.get("razorpay_signature") or payload.get("signature")

        order_or_sub_id = order_id or subscription_id

        if not payment_id or not order_or_sub_id or not signature:
            return jsonify({
                "error": "Missing verification parameters",
                "message": "razorpay_payment_id, razorpay_order_id (or subscription_id), and razorpay_signature are required."
            }), 400

        success, message, sub_record = SubscriptionService.verify_checkout_payment(
            db,
            user=user,
            razorpay_payment_id=payment_id,
            razorpay_order_id=order_id,
            razorpay_subscription_id=subscription_id,
            razorpay_signature=signature
        )

        if not success:
            return jsonify({
                "error": "Payment verification failed",
                "message": message
            }), 400

        is_premium = sub_record.is_active if sub_record else True
        return jsonify({
            "success": True,
            "message": message or "Subscription activated successfully! Welcome to Yojana Hunter Premium.",
            "is_premium": is_premium,
            "subscription": sub_record.to_dict(include_user=False) if sub_record else None
        }), 200

    except Exception as e:
        db.rollback()
        logger.error(f"Error verifying subscription payment: {e}")
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
    finally:
        db.close()

@subscriptions_bp.route("/stream-status", methods=["GET"])
@token_required
def stream_subscription_status():
    """
    GET /api/subscriptions/stream-status
    Server-Sent Events (SSE) stream for real-time subscription lifecycle updates.
    Yields events whenever payment verification or admin approval changes.
    """
    import json
    from flask import Response
    from services.event_service import EventService

    user = g.current_user

    def event_stream():
        q = EventService.subscribe_user(user.id)
        try:
            # Send initial connected event
            yield f"data: {json.dumps({'type': 'connected', 'userId': user.id})}\n\n"
            while True:
                msg = EventService.get_next_event(q, timeout=25.0)
                if msg is not None:
                    yield f"data: {msg}\n\n"
                else:
                    yield f": keep-alive\n\n"
        except GeneratorExit:
            EventService.unsubscribe_user(user.id, q)
        except Exception as e:
            logger.debug(f"SSE stream closed for user {user.id}: {e}")
            EventService.unsubscribe_user(user.id, q)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )

@subscriptions_bp.route("/request", methods=["POST"])
@token_required
def submit_subscription_request():
    """
    POST /api/subscriptions/request
    Submits a subscription request for admin review and approval.
    Does NOT activate subscription or charge real money.
    """
    db = SessionLocal()
    try:
        user = g.current_user
        payload = request.get_json() or {}
        plan_id = payload.get("plan_id") or payload.get("planId")
        phone_number = payload.get("phone_number") or payload.get("phone") or payload.get("mobile")
        bank_name = payload.get("bank_name") or payload.get("bankName")
        bank_account_type = payload.get("bank_account_type") or payload.get("bankAccountType")
        payment_method = payload.get("payment_method") or payload.get("paymentMethod")
        notes = payload.get("admin_notes") or payload.get("notes") or payload.get("adminNotes")

        if not plan_id:
            return jsonify({
                "error": "Plan selection required",
                "message": "Please choose a valid subscription plan (monthly, two_months, yearly)."
            }), 400

        success, message, sub_req = SubscriptionService.create_subscription_request(
            db, 
            user_id=user.id, 
            plan_id=plan_id,
            phone_number=phone_number,
            bank_name=bank_name,
            bank_account_type=bank_account_type,
            payment_method=payment_method,
            admin_notes=notes
        )

        if not success:
            return jsonify({
                "error": "Request rejected",
                "message": message,
                "request": sub_req.to_dict(include_user=False) if sub_req else None
            }), 400

        return jsonify({
            "message": message,
            "request": sub_req.to_dict(include_user=False)
        }), 201

    except Exception as e:
        db.rollback()
        logger.error(f"Error submitting subscription request: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@subscriptions_bp.route("/cancel", methods=["POST"])
@token_required
def cancel_subscription_request():
    """
    POST /api/subscriptions/cancel
    Allows a citizen to cancel their pending subscription request.
    """
    db = SessionLocal()
    try:
        user = g.current_user
        payload = request.get_json() or {}
        request_id = payload.get("request_id") or payload.get("requestId")

        if not request_id:
            return jsonify({"error": "Request ID is required."}), 400

        success, message = SubscriptionService.cancel_subscription_request(
            db, 
            user_id=user.id, 
            request_id=int(request_id)
        )

        if not success:
            return jsonify({"error": message}), 400

        return jsonify({"message": message}), 200

    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling subscription request: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@subscriptions_bp.route("/report-failure", methods=["POST"])
@token_required
def report_subscription_failure():
    """
    POST /api/subscriptions/report-failure
    Records an isolated, user-specific and transaction-specific payment/mandate failure.
    Ensures that a failure for one user never affects another citizen's subscription status.
    """
    db = SessionLocal()
    try:
        user = g.current_user
        payload = request.get_json() or {}
        
        success, safe_msg, sub_record = SubscriptionService.report_payment_failure(
            db,
            user=user,
            razorpay_subscription_id=payload.get("subscription_id") or payload.get("razorpay_subscription_id"),
            razorpay_payment_id=payload.get("payment_id") or payload.get("razorpay_payment_id"),
            error_code=payload.get("error_code") or payload.get("code"),
            error_description=payload.get("error_description") or payload.get("description"),
            error_source=payload.get("error_source"),
            error_step=payload.get("error_step"),
            error_reason=payload.get("error_reason"),
            bank=payload.get("bank"),
            payment_method=payload.get("payment_method") or payload.get("method")
        )

        return jsonify({
            "success": True,
            "message": safe_msg,
            "subscription": sub_record.to_dict(include_user=False) if sub_record else None
        }), 200

    except Exception as e:
        db.rollback()
        logger.error(f"Error reporting subscription payment failure: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

