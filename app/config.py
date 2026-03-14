import os
from datetime import timedelta
from dotenv import load_dotenv

# Load .env variables
load_dotenv()


class Config:
    """
    Base configuration shared across all environments.
    """
    # ─── Flask Core ───────────────────────────────────────────────────────────
    # STRICT: This will crash if not set in production.
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # ─── Database ─────────────────────────────────────────────────────────────
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = database_url
    
    # ─── Authentication (Google OAuth) ────────────────────────────────────────
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    # These are OIDC Standards — the internet usually keeps these fixed.
    GOOGLE_METADATA_URL = os.environ.get(
        'GOOGLE_METADATA_URL', 
        'https://accounts.google.com/.well-known/openid-configuration'
    )

    # ─── LinkedIn ─────────────────────────────────────────────────────────────
    LINKEDIN_CLIENT_ID = os.environ.get('LINKEDIN_CLIENT_ID')
    LINKEDIN_CLIENT_SECRET = os.environ.get('LINKEDIN_CLIENT_SECRET')
    # Refined default — but easily overridden in Render
    LINKEDIN_METADATA_URL = os.environ.get(
        'LINKEDIN_METADATA_URL', 
        'https://www.linkedin.com/oauth/.well-known/openid-configuration'
    )

    # ─── AI (Gemini) ──────────────────────────────────────────────────────────
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODELS = os.environ.get('GEMINI_MODELS', 'gemini-2.5-flash,gemini-2.0-flash')

    # ─── Security ───────────────────────────────────────────────────────────────
    FERNET_KEY = os.environ.get('FERNET_KEY')
    
    # ─── Stripe ───────────────────────────────────────────────────────────────
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRO_PRICE_ID = os.environ.get('STRIPE_PRO_PRICE_ID')

    # ─── Rate Limiting ────────────────────────────────────────────────────────
    RATELIMIT_STORAGE_URI = os.environ.get('REDIS_URL', 'memory://')
    RATELIMIT_HEADERS_ENABLED = True

    # ─── Session Security ──────────────────────────────────────────────────────
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600


class DevelopmentConfig(Config):
    """Development config — verbose errors, no HTTPS requirement."""
    DEBUG = True
    ENV = 'development'
    # Allow HTTP for local OAuth (never set this in production)
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """
    Production config — strict security.
    DATABASE_URL, SECRET_KEY, FERNET_KEY must all be set in environment.
    """
    DEBUG = False
    TESTING = False
    ENV = 'production'
    # Cookies only sent over HTTPS
    SESSION_COOKIE_SECURE = True
    # Ratelimiter must use Redis in production (set REDIS_URL env var)
    RATELIMIT_STORAGE_URI = os.environ.get('REDIS_URL', 'memory://')


class TestingConfig(Config):
    """Testing config — in-memory DB, CSRF disabled for easier test clients."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False          # Disable CSRF in tests
    RATELIMIT_ENABLED = False         # Disable rate limiting in tests
    SESSION_COOKIE_SECURE = False


# Dictionary to easily get the config by name string
config_by_name = dict(
    dev=DevelopmentConfig,
    test=TestingConfig,
    prod=ProductionConfig
)
