from flask import Blueprint

api_bp = Blueprint("api", __name__)

from .health import health_bp
from .schemes import schemes_bp
from .profile import profile_bp
from .documents import documents_bp
from .applications import applications_bp
from .interview import interview_bp
from .eligibility import eligibility_bp
from .admin import admin_bp
from .admin_discovery import admin_discovery_bp
from .auth import auth_bp
from .saved_schemes import saved_schemes_bp
from .subscriptions import subscriptions_bp
from .webhooks import webhooks_bp, razorpay_webhook_listener

# Register all child blueprints under the main api blueprint
api_bp.register_blueprint(health_bp, url_prefix="")
api_bp.register_blueprint(schemes_bp, url_prefix="/schemes")
api_bp.register_blueprint(admin_bp, url_prefix="/admin")
api_bp.register_blueprint(admin_discovery_bp, url_prefix="/admin")
api_bp.register_blueprint(auth_bp, url_prefix="/auth")
api_bp.register_blueprint(saved_schemes_bp, url_prefix="/saved-schemes")
api_bp.register_blueprint(subscriptions_bp, url_prefix="/subscriptions")
api_bp.register_blueprint(webhooks_bp, url_prefix="/webhooks")
# Endpoint alias as requested: POST /api/razorpay/webhook
api_bp.add_url_rule("/razorpay/webhook", view_func=razorpay_webhook_listener, methods=["POST"])
api_bp.register_blueprint(profile_bp, url_prefix="/profile")
api_bp.register_blueprint(profile_bp, url_prefix="/profiles", name="profiles_bp")
api_bp.register_blueprint(documents_bp, url_prefix="/documents")
api_bp.register_blueprint(applications_bp, url_prefix="/applications")
api_bp.register_blueprint(interview_bp, url_prefix="")
api_bp.register_blueprint(eligibility_bp, url_prefix="/eligibility")
