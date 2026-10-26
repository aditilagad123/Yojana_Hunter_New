import json
import logging
from flask import Blueprint, request, jsonify
from database import SessionLocal
from services.subscription_service import SubscriptionService
from services.razorpay_service import RazorpayService

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint("webhooks", __name__)

@webhooks_bp.route("/razorpay", methods=["POST"])
@webhooks_bp.route("", methods=["POST"])
def razorpay_webhook_listener():
    """
    POST /api/webhooks/razorpay (and /api/razorpay/webhook)
    Receives and processes asynchronous Razorpay subscription & payment lifecycle events:
    subscription.activated, subscription.charged, subscription.pending, subscription.halted,
    subscription.cancelled, subscription.completed, payment.captured, payment.failed.

    Requirements:
    1. Reads original, unmodified HTTP request body bytes.
    2. Reads and verifies X-Razorpay-Signature request header against RAZORPAY_WEBHOOK_SECRET.
    3. Rejects missing or invalid signatures with HTTP 400 Bad Request before processing.
    4. Handles missing server webhook secret with clear HTTP 500 configuration error.
    5. Safely parses JSON body and handles malformed requests with HTTP 400 Bad Request.
    6. Processes events idempotently using processed_webhook_events table.
    7. Avoids state downgrades (e.g. out-of-order pending events do not downgrade approved active subscriptions).
    """
    raw_body = request.get_data()
    signature = request.headers.get("X-Razorpay-Signature", "")

    # 1. Missing signature header
    if not signature:
        logger.warning("[RAZORPAY WEBHOOK] Rejected webhook request missing X-Razorpay-Signature header.")
        return jsonify({
            "error": "Missing signature",
            "message": "X-Razorpay-Signature header is required."
        }), 400

    # 2. Check server-side webhook secret configuration
    webhook_secret = RazorpayService.get_webhook_secret()
    if not webhook_secret:
        logger.error("[RAZORPAY WEBHOOK] RAZORPAY_WEBHOOK_SECRET is not configured in backend/.env. Rejecting webhook request.")
        return jsonify({
            "error": "Configuration error",
            "message": "RAZORPAY_WEBHOOK_SECRET is not configured on the server."
        }), 500

    # 3. Cryptographic signature verification
    try:
        is_valid = RazorpayService.verify_webhook_signature(raw_body, signature)
    except ValueError as ve:
        logger.error(f"[RAZORPAY WEBHOOK] Configuration error: {ve}")
        return jsonify({
            "error": "Configuration error",
            "message": str(ve)
        }), 500
    except Exception as e:
        logger.error(f"[RAZORPAY WEBHOOK] Signature verification exception: {e}")
        return jsonify({
            "error": "Signature verification error",
            "message": "Failed to verify webhook signature."
        }), 400

    if not is_valid:
        logger.warning("[RAZORPAY WEBHOOK] Rejected webhook: Invalid cryptographic signature.")
        return jsonify({
            "error": "Invalid signature",
            "message": "X-Razorpay-Signature verification failed."
        }), 400

    # 4. Parse request body as JSON
    try:
        payload_json = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        if not isinstance(payload_json, dict) or not payload_json:
            raise ValueError("Webhook body must be a non-empty JSON object")
    except Exception as e:
        logger.error(f"[RAZORPAY WEBHOOK] Malformed JSON in webhook body: {e}")
        return jsonify({
            "error": "Malformed JSON",
            "message": "Unable to parse request body as JSON."
        }), 400

    event_name = payload_json.get("event")
    if not event_name:
        logger.warning("[RAZORPAY WEBHOOK] Missing 'event' field in webhook payload.")
        return jsonify({
            "error": "Malformed payload",
            "message": "Payload missing required 'event' field."
        }), 400

    # 5. Process validated event in database transaction
    db = SessionLocal()
    try:
        success, message = SubscriptionService.process_razorpay_webhook(
            db=db,
            raw_body=raw_body,
            signature=signature,
            payload_json=payload_json
        )

        if not success:
            logger.warning(f"[RAZORPAY WEBHOOK] Webhook rejected by service: {message}")
            return jsonify({
                "error": "Processing error",
                "message": message
            }), 400

        return jsonify({
            "status": "success",
            "message": message
        }), 200

    except Exception as e:
        db.rollback()
        logger.error(f"[RAZORPAY WEBHOOK] Unhandled exception processing webhook: {e}")
        return jsonify({
            "error": "Internal processing error",
            "message": "An error occurred while processing the webhook event."
        }), 500
    finally:
        db.close()

