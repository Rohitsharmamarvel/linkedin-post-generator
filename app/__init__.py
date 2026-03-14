"""
app/__init__.py
───────────────
Application factory for LinkScale.

Engineering Standards compliance:
  - App factory pattern with environment-aware config (Section 2.3)
  - Security headers on every response (Section 3.2)
  - Rate limiter and CSRF protection initialised (Section 6)
  - Global error handlers with consistent JSON responses (Section 8.3)
  - Structured logging with rotating file handler (Section 8.1)
  - No secrets or debug=True hardcoded here (Section 15.2)
"""
import os
import logging
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template, redirect, url_for, g, jsonify, request
from flask_login import current_user, login_required

from app.config import config_by_name
from app.extensions import db, migrate, login_manager, oauth, limiter, csrf


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _success_response(data, message="Success", status_code=200):
    """Standard success envelope for all API responses."""
    return jsonify({
        "status": "success",
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }), status_code


def _error_response(message, status_code=400, errors=None):
    """Standard error envelope for all API responses."""
    return jsonify({
        "status": "error",
        "message": message,
        "errors": errors or [],
        "timestamp": datetime.utcnow().isoformat()
    }), status_code


# ─── LOGGING ─────────────────────────────────────────────────────────────────

def _configure_logging(app: Flask):
    """
    Set up rotating file handler for application logs.
    Logs rotate at 10 MB, keeping the last 10 files.
    """
    if not os.path.exists('logs'):
        os.mkdir('logs')

    file_handler = RotatingFileHandler(
        'logs/linkscale.log',
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10
    )
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s '
        '(%(funcName)s:%(lineno)d) [%(request_id)s]: %(message)s'
    )

    class RequestIdFilter(logging.Filter):
        def filter(self, record):
            try:
                record.request_id = getattr(g, 'request_id', 'no-req')
            except RuntimeError:
                # Flask g is not accessible outside application/request context
                # This happens during CLI commands (flask db migrate, etc.)
                record.request_id = 'cli'
            return True

    file_handler.setFormatter(formatter)
    file_handler.addFilter(RequestIdFilter())
    file_handler.setLevel(logging.WARNING if not app.debug else logging.DEBUG)

    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('LinkScale starting up.')


# ─── APP FACTORY ─────────────────────────────────────────────────────────────

def create_app(config_name='dev') -> Flask:
    """
    Create and configure the Flask application.

    Args:
        config_name: One of 'dev', 'test', 'prod'. Defaults to 'dev'.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    app.config.from_object(config_by_name[config_name])

    # ── Extensions ───────────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to access this page.'
    oauth.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)
    
    # ── Strict CORS ───────────────────────────────────────────────────────────
    from flask_cors import CORS
    CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5001", "https://yourproductiondomain.com"]}}, supports_credentials=True)

    # ── Google OAuth Client ───────────────────────────────────────────────────
    oauth.register(
        name='google',
        client_id=app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'  # Minimal scopes — never request more than needed
        }
    )

    # ── LinkedIn OAuth Client ─────────────────────────────────────────────────
    oauth.register(
        name='linkedin',
        client_id=app.config.get('LINKEDIN_CLIENT_ID'),
        client_secret=app.config.get('LINKEDIN_CLIENT_SECRET'),
        access_token_url='https://www.linkedin.com/oauth/v2/accessToken',
        access_token_params=None,
        authorize_url='https://www.linkedin.com/oauth/v2/authorization',
        authorize_params=None,
        api_base_url='https://api.linkedin.com/v2/',
        client_kwargs={'scope': 'openid profile w_member_social email'},
    )

    # ── Import models so Flask-Migrate tracks schema ──────────────────────────
    from app import models

    # ── User Loader ───────────────────────────────────────────────────────────
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    # ── Request ID (for log tracing) ──────────────────────────────────────────
    @app.before_request
    def assign_request_id():
        """Attach a unique ID to every request for log correlation."""
        g.request_id = str(uuid.uuid4())[:8]

    # ── Security Headers (applied to every response) ──────────────────────────
    @app.after_request
    def set_security_headers(response):
        """
        Apply OWASP-recommended security headers on every HTTP response.
        These prevent clickjacking, MIME sniffing, XSS, and data leakage.
        """
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'

        # Content Security Policy — allows our own scripts, CDN fonts, and inline styles
        # Tighten this further as the project matures
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' fonts.googleapis.com cdn.jsdelivr.net; "
            "font-src 'self' fonts.gstatic.com; "
            "img-src 'self' data: lh3.googleusercontent.com *.licdn.com; "
            "connect-src 'self';"
        )

        # HSTS — only enable in production (requires HTTPS)
        if not app.debug:
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains'
            )

        return response

    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        """
        CSRF token missing or invalid — most commonly happens when:
        1. The user's session expired (token no longer valid)
        2. The user opened the page in two tabs and submitted an old one
        Show a friendly message telling them to refresh and try again.
        """
        app.logger.warning("CSRF error on %s: %s", request.path, e.description)
        if request.is_json or request.path.startswith('/api/'):
            return _error_response(
                "Your session has expired. Please refresh the page and try again.", 400
            )
        return render_template('errors/400.html'), 400

    @app.errorhandler(400)
    def bad_request(e):
        if request.is_json or request.path.startswith('/api/'):
            return _error_response("Bad request", 400)
        return render_template('errors/400.html'), 400

    @app.errorhandler(401)
    def unauthorized(e):
        if request.is_json or request.path.startswith('/api/'):
            return _error_response("Authentication required. Please sign in.", 401)
        return redirect(url_for('auth.login'))

    @app.errorhandler(403)
    def forbidden(e):
        if request.is_json or request.path.startswith('/api/'):
            return _error_response(
                "You don't have permission to access this resource. "
                "Upgrade your plan if this is a paid feature.", 403
            )
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        if request.is_json or request.path.startswith('/api/'):
            return _error_response("Resource not found.", 404)
        return render_template('errors/404.html'), 404

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        app.logger.warning(
            "Rate limit exceeded for IP %s on %s", request.remote_addr, request.path
        )
        return _error_response(
            f"Too many requests. {e.description}. Please slow down and try again later.",
            429
        )

    @app.errorhandler(500)
    def internal_server_error(e):
        db.session.rollback()  # Always rollback the DB session on 500
        app.logger.error(
            "Internal server error on %s: %s", request.path, e, exc_info=True
        )
        if request.is_json or request.path.startswith('/api/'):
            return _error_response(
                "An internal error occurred. Our team has been notified.", 500
            )
        return render_template('errors/500.html'), 500

    # ── Blueprints ────────────────────────────────────────────────────────────
    from app.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.editor import editor_bp
    app.register_blueprint(editor_bp, url_prefix='/editor')

    from app.calendar import calendar_bp
    app.register_blueprint(calendar_bp, url_prefix='/calendar')

    from app.drafts import drafts_bp
    app.register_blueprint(drafts_bp, url_prefix='/drafts')

    from app.leads import leads_bp
    app.register_blueprint(leads_bp, url_prefix='/leads')

    from app.analytics import analytics_bp
    app.register_blueprint(analytics_bp, url_prefix='/analytics')

    from app.payments import payments_bp
    app.register_blueprint(payments_bp, url_prefix='/payments')

    # ── Dashboard Root Route ──────────────────────────────────────────────────
    # ── Landing Page Route ────────────────────────────────────────────────────
    @app.route('/')
    def landing():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('landing.html')

    # ── Dashboard Route ───────────────────────────────────────────────────────
    @app.route('/dashboard')
    @login_required
    def dashboard():
        # Scope all queries to the current user — multi-tenancy rule
        drafts_count = models.Draft.query.filter_by(
            user_id=current_user.id, status='draft', is_deleted=False
        ).count()
        scheduled_count = models.Draft.query.filter_by(
            user_id=current_user.id, status='scheduled', is_deleted=False
        ).count()
        published_count = models.Draft.query.filter_by(
            user_id=current_user.id, status='published', is_deleted=False
        ).count()
        ai_gens_count = models.UsageLog.query.filter_by(
            user_id=current_user.id, action='generate'
        ).count()

        return render_template(
            'index.html',
            drafts_count=drafts_count,
            scheduled_count=scheduled_count,
            published_count=published_count,
            ai_gens_count=ai_gens_count
        )

    # ── Scheduler (background thread) ────────────────────────────────────────
    import threading
    from app.scheduler import start_scheduler

    if not os.environ.get('DISABLE_INLINE_SCHEDULER'):
        t = threading.Thread(target=start_scheduler, args=(app,))
        t.daemon = True
        t.start()

    # ── Logging ──────────────────────────────────────────────────────────────
    _configure_logging(app)

    return app
