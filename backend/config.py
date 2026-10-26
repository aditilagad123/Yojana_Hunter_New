import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
load_dotenv()

class Config:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Yojana Hunter")
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    PORT: int = int(os.getenv("PORT", "5000"))
    HOST: str = os.getenv("HOST", "127.0.0.1")

    # Database Configuration via individual components or combined URL
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "yojana_hunter")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # PostgreSQL Database URL
    # Supports postgresql+psycopg:// or postgresql+psycopg2://
    if os.getenv("DATABASE_URL"):
        DATABASE_URL: str = os.getenv("DATABASE_URL")
    else:
        import urllib.parse
        encoded_pwd = urllib.parse.quote_plus(DB_PASSWORD) if DB_PASSWORD else "postgres"
        DATABASE_URL: str = f"postgresql+psycopg://{DB_USER}:{encoded_pwd}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    SECRET_KEY: str = os.getenv("SECRET_KEY", "yojana-hunter-secret-key-change-in-production")
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5000",
        "http://127.0.0.1:5000"
    ]

    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16 MB max file upload

    # Gemini AI Configuration (Official Google Gen AI SDK)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    GEMINI_MAX_RETRIES: int = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
    GEMINI_TIMEOUT_SECONDS: int = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
    DISCOVERY_MAX_REQUESTS: int = int(os.getenv("DISCOVERY_MAX_REQUESTS", "10"))
    DISCOVERY_SCHEDULE_HOURS: int = int(os.getenv("DISCOVERY_SCHEDULE_HOURS", "24"))

    # Razorpay Payment Gateway Configuration (Test Mode)
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "").strip()
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000").strip()

    # Pre-created Razorpay Plan IDs (from Razorpay Dashboard > Subscriptions > Plans)
    RAZORPAY_PLAN_ID_MONTHLY: str = os.getenv("RAZORPAY_PLAN_ID_MONTHLY", "").strip()
    RAZORPAY_PLAN_ID_TWO_MONTHS: str = os.getenv("RAZORPAY_PLAN_ID_TWO_MONTHS", "").strip()
    RAZORPAY_PLAN_ID_YEARLY: str = os.getenv("RAZORPAY_PLAN_ID_YEARLY", "").strip()

config = Config()
