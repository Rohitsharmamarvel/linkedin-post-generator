### LinkScale — Production-Grade Development Bible

> **Purpose:** This document is the single source of truth for every engineering decision made in this project.
> Any AI agent, developer, or contributor **MUST** read and follow this document before writing a single line of code.
> No shortcuts. No "we'll fix it later." Production-ready from Day 1.

---

## 📋 TABLE OF CONTENTS

1. [Core Philosophy](#1-core-philosophy)
2. [Project Architecture](#2-project-architecture)
3. [Security — Non-Negotiable Rules](#3-security--non-negotiable-rules)
4. [Authentication & Authorization (RBAC)](#4-authentication--authorization-rbac)
5. [API Design Standards](#5-api-design-standards)
6. [Rate Limiting](#6-rate-limiting)
7. [Database & Data Handling](#7-database--data-handling)
8. [Error Handling & Logging](#8-error-handling--logging)
9. [External Services & Resilience](#9-external-services--resilience)
10. [Testing Standards](#10-testing-standards)
11. [Frontend Standards](#11-frontend-standards)
12. [CI/CD & Deployment](#12-cicd--deployment)
13. [Performance & Scalability](#13-performance--scalability)
14. [Code Quality & Clean Code Rules](#14-code-quality--clean-code-rules)
15. [Agent-Specific Rules (AI Coding Assistants)](#15-agent-specific-rules-ai-coding-assistants)
16. [Feature Development Checklist](#16-feature-development-checklist)
17. [Common Mistakes to NEVER Repeat](#17-common-mistakes-to-never-repeat)

---

## 1. CORE PHILOSOPHY

> **"Build it once. Build it right. Never build it again."**

Every feature built in this project must satisfy three fundamental pillars:

| Pillar | Question to ask before shipping |
|---|---|
| **Security** | Could this be exploited by a malicious user? |
| **Scalability** | Will this break at 10,000 users? |
| **Maintainability** | Can a new developer understand and change this in 5 minutes? |

If the answer to any of these is uncertain — **STOP and fix it first.**

---

## 2. PROJECT ARCHITECTURE

### 2.1 Directory Structure (Enforced)

```
linkscale/
├── app/
│   ├── __init__.py           # App factory — create_app()
│   ├── config.py             # Environment-based config classes
│   ├── extensions.py         # All Flask extensions (db, login_manager, etc.)
│   ├── models.py             # All SQLAlchemy models
│   ├── auth/                 # Authentication blueprint
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── leads/                # Lead management blueprint
│   ├── drafts/               # Content drafts blueprint
│   ├── editor/               # AI editor blueprint
│   ├── analytics/            # Analytics blueprint
│   ├── payments/             # Payments & subscriptions blueprint
│   ├── calendar/             # Content calendar blueprint
│   ├── templates/            # Jinja2 HTML templates
│   └── static/               # CSS, JS, images
├── directives/               # Agent SOPs (Natural language instructions)
├── execution/                # Deterministic Python scripts
├── cursor_tasks/             # Cursor-specific task files
├── migrations/               # Alembic DB migrations
├── tests/                    # All test files
│   ├── unit/
│   ├── integration/
│   └── security/
├── logs/                     # Application logs (never commit)
├── .env                      # Secrets (NEVER commit)
├── .env.example              # Template for env vars (always commit)
├── PRD.md                    # Product Requirements Document
└── requirements.txt
```

### 2.2 Three-Layer Architecture (Mandatory for AI Agent Work)

This project uses a 3-layer separation as defined in `claude.md`:

- **Layer 1 — Directives** (`directives/`): What to do. Written as markdown SOPs.
- **Layer 2 — Orchestration** (AI Agent): Intelligent routing, reads directives, calls execution tools.
- **Layer 3 — Execution** (`execution/`): Deterministic Python scripts. No AI uncertainty here.

> ⚠️ **Rule:** Never let the AI agent do something directly that a deterministic script can do.
> 90% accuracy × 90% accuracy × 90% accuracy = **73% success** after 3 steps. Push logic down to Layer 3.

### 2.3 Configuration Management

```python
# app/config.py — ALWAYS use class-based config
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')  # Never hardcode
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL')

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SESSION_COOKIE_SECURE = True        # HTTPS only
    SESSION_COOKIE_HTTPONLY = True      # No JS access
    SESSION_COOKIE_SAMESITE = 'Lax'    # CSRF protection
```

> ✅ **Rule:** Every config value that changes between environments MUST come from environment variables. No exceptions.

---

## 3. SECURITY — NON-NEGOTIABLE RULES

### 3.1 OWASP Top 10 — Must Be Defended Against

| Attack | Defense Method | Implementation |
|---|---|---|
| **SQL Injection** | Parameterized queries only | Use SQLAlchemy ORM, never raw `.execute()` with f-strings |
| **XSS (Cross-Site Scripting)** | Auto-escaping in templates | Jinja2 auto-escapes by default — never use `\| safe` on user input |
| **CSRF** | CSRF tokens on all forms | Use `Flask-WTF` with `CSRFProtect()` on all POST/PUT/DELETE |
| **Broken Auth** | Strong session management | Use `Flask-Login`, set cookie flags, short session timeouts |
| **Sensitive Data Exposure** | No API keys in client-side code | All keys must be Server-side env vars only |
| **Zero-Trust Networking** | Internal verification | Zero-trust for all internal endpoints (validate even server-to-server traffic) |
| **Security Misconfiguration** | Strict CORS | Strict CORS enabled (NO `*` origins allowed) |
| **Insecure Deserialization** | Never `pickle` user data | Use JSON for serialization |
| **JWT** | Short expiries | JWTs must have a short expiry time |
| **Known Vulnerabilities** | Dependency scanning | Run `safety check` in CI/CD pipeline |

### 3.2 Security Headers (Required on Every Response)

```python
# In app/__init__.py or a middleware
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' fonts.googleapis.com"
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    return response
```

### 3.3 Input Validation & Sanitization

```python
# ALWAYS validate and sanitize. NEVER trust user input.

# ✅ CORRECT — Parameterized query via ORM
user = User.query.filter_by(email=email).first()

# ❌ WRONG — SQL Injection vulnerability
user = db.engine.execute(f"SELECT * FROM users WHERE email = '{email}'")

# ✅ CORRECT — Sanitize HTML input if rich text is needed
import bleach
ALLOWED_TAGS = ['b', 'i', 'em', 'strong', 'p', 'br']
clean_content = bleach.clean(user_input, tags=ALLOWED_TAGS, strip=True)

# ✅ CORRECT — Validate on every form/API input
from wtforms.validators import DataRequired, Email, Length, Regexp
```

### 3.4 Password & Secrets Handling

```python
# ✅ CORRECT — Use Werkzeug's secure hashing (bcrypt-based)
from werkzeug.security import generate_password_hash, check_password_hash
hashed = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

# ❌ NEVER store plain text passwords
# ❌ NEVER use md5 or sha1 for passwords
# ❌ NEVER log passwords, tokens, or API keys

# ✅ CORRECT — Mask secrets in logs
import re
def mask_sensitive(text):
    return re.sub(r'(api_key|password|token)=[^&\s]+', r'\1=***REDACTED***', str(text))
```

### 3.5 File Uploads (If Applicable)

```python
# Always validate file type, size, and rename on server side
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB hard limit

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Always use secure_filename from werkzeug
from werkzeug.utils import secure_filename
safe_name = secure_filename(file.filename)
```

---

## 4. AUTHENTICATION & AUTHORIZATION (RBAC)

### 4.1 Role-Based Access Control

```python
# In models.py — Define roles clearly
class UserRole(enum.Enum):
    FREE = 'free'
    PRO = 'pro'
    ENTERPRISE = 'enterprise'
    ADMIN = 'admin'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.FREE, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
```

### 4.2 Route Protection Decorators

```python
# Create reusable decorators — never repeat auth logic inline
from functools import wraps
from flask import abort
from flask_login import current_user

def require_role(*roles):
    """Decorator that checks if the current user has one of the required roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Usage on routes:
@bp.route('/admin/users')
@login_required
@require_role(UserRole.ADMIN)
def admin_users():
    ...

@bp.route('/leads')
@login_required
@require_role(UserRole.PRO, UserRole.ENTERPRISE, UserRole.ADMIN)
def leads():
    ...
```

### 4.3 OAuth 2.0 (LinkedIn & Google)

```
RULE: NEVER ask users for their LinkedIn/Google passwords directly.
ALWAYS use OAuth 2.0 authorization code flow.
Store ONLY the OAuth access token (encrypted) and refresh token — never the password.
```

```python
# Store tokens encrypted
from cryptography.fernet import Fernet

def encrypt_token(token: str) -> str:
    f = Fernet(current_app.config['FERNET_KEY'])
    return f.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    f = Fernet(current_app.config['FERNET_KEY'])
    return f.decrypt(encrypted_token.encode()).decode()
```

### 4.4 Session Security

```python
# In Production config — ALL of these are required
SESSION_COOKIE_SECURE = True        # Only sent over HTTPS
SESSION_COOKIE_HTTPONLY = True      # JS cannot access the cookie
SESSION_COOKIE_SAMESITE = 'Lax'    # Prevents CSRF via cross-site requests
PERMANENT_SESSION_LIFETIME = timedelta(hours=24)  # Auto-expire sessions
```

---

## 5. API DESIGN STANDARDS

### 5.1 RESTful Conventions

```
GET    /api/v1/leads          → List all leads (paginated)
POST   /api/v1/leads          → Create a new lead
GET    /api/v1/leads/<id>     → Get a single lead
PUT    /api/v1/leads/<id>     → Update a lead (full update)
PATCH  /api/v1/leads/<id>     → Partially update a lead
DELETE /api/v1/leads/<id>     → Delete a lead
```

### 5.2 Versioning

> **Rule:** Always prefix API routes with `/api/v1/`. When breaking changes happen, bump to `/api/v2/`. Never change existing endpoint contracts.

### 5.3 Standard Response Format

```python
# Every API response MUST follow this format
def success_response(data, message="Success", status_code=200):
    return jsonify({
        "status": "success",
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }), status_code

def error_response(message, status_code=400, errors=None):
    return jsonify({
        "status": "error",
        "message": message,
        "errors": errors or [],
        "timestamp": datetime.utcnow().isoformat()
    }), status_code

# Example usage in a route:
@bp.route('/api/v1/leads', methods=['GET'])
@login_required
def get_leads():
    try:
        leads = Lead.query.filter_by(user_id=current_user.id).paginate(
            page=request.args.get('page', 1, type=int),
            per_page=20
        )
        return success_response({
            "leads": [l.to_dict() for l in leads.items],
            "total": leads.total,
            "pages": leads.pages,
            "current_page": leads.page
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching leads: {e}", exc_info=True)
        return error_response("Failed to fetch leads", 500)
```

### 5.4 Input Validation on Every Endpoint

```python
# Use marshmallow, WTForms, or Spring-style Validator models — NEVER skip this
# Mandatory Input Validation is required for ALL user/AI data.
from marshmallow import Schema, fields, validate, ValidationError

class CreateLeadSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    email = fields.Email(required=True)
    linkedin_url = fields.Url(required=False)
    notes = fields.Str(required=False, validate=validate.Length(max=1000))

@bp.route('/api/v1/leads', methods=['POST'])
@login_required
def create_lead():
    schema = CreateLeadSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response("Validation failed", 422, errors=err.messages)
    # ... proceed with validated data only
```

---

## 6. RATE LIMITING

### 6.1 Rate Limit Configuration (Required on ALL APIs)

```python
# In extensions.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="redis://localhost:6379"  # Use Redis in production
)
```

### 6.2 Per-Route Rate Limits

| Endpoint Type | Rate Limit |
|---|---|
| Login / Register | 10 per minute, 50 per hour |
| Password Reset | 5 per hour |
| API (authenticated user) | 100 per minute |
| AI content generation | 20 per hour (free), 200 per hour (pro) |
| LinkedIn OAuth callback | 10 per minute |
| File uploads | 10 per hour |
| Webhook endpoints | 1000 per minute (source-IP validated) |

```python
# Apply on specific routes
@bp.route('/auth/login', methods=['POST'])
@limiter.limit("10 per minute; 50 per hour")
def login():
    ...

# Apply on an entire blueprint
def register_extensions(app):
    limiter.limit("100/minute")(api_blueprint)
```

### 6.3 Rate Limit Response

```python
@app.errorhandler(429)
def ratelimit_handler(e):
    return error_response(
        f"Rate limit exceeded. {e.description}. Try again later.",
        status_code=429
    )
```

---

## 7. DATABASE & DATA HANDLING

### 7.1 Model Standards

```python
# EVERY model must follow this pattern
class BaseModel(db.Model):
    """Abstract base model with audit fields."""
    __abstract__ = True
    
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, 
                           onupdate=datetime.utcnow, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)  # Soft delete
    
    def soft_delete(self):
        """Never hard-delete records — soft delete only."""
        self.is_deleted = True
        db.session.commit()
    
    def to_dict(self):
        """Every model must implement a serialization method."""
        raise NotImplementedError("Implement to_dict() in every model")
```

### 7.2 Migration Rules

```bash
# EVERY database schema change MUST go through migrations
flask db migrate -m "descriptive migration message"
flask db upgrade

# NEVER manually alter the database in production
# NEVER edit an existing migration file after it's been applied
# ALWAYS test the migration on staging first
```

### 7.3 Sensitive Data Encryption

```python
# Fields like OAuth tokens, API keys must be encrypted at rest
class User(BaseModel):
    # ... other fields
    
    _linkedin_access_token = db.Column('linkedin_access_token', db.Text)
    
    @property
    def linkedin_access_token(self):
        if self._linkedin_access_token:
            return decrypt_token(self._linkedin_access_token)
        return None
    
    @linkedin_access_token.setter
    def linkedin_access_token(self, value):
        if value:
            self._linkedin_access_token = encrypt_token(value)
```

### 7.4 Connection Pooling & Query Optimization

```python
# In config.py
SQLALCHEMY_POOL_SIZE = 10           # Number of persistent connections
SQLALCHEMY_MAX_OVERFLOW = 20        # Extra connections under load
SQLALCHEMY_POOL_TIMEOUT = 30        # Seconds before giving up getting a connection
SQLALCHEMY_POOL_RECYCLE = 1800      # Recycle connections every 30 min

# ALWAYS use pagination — never fetch all records
leads = Lead.query.filter_by(user_id=user_id).paginate(page=page, per_page=20)

# ALWAYS add indexes on frequently queried fields
class Lead(BaseModel):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    email = db.Column(db.String(120), index=True)
    status = db.Column(db.String(50), index=True)
```

---

## 8. ERROR HANDLING & LOGGING

### 8.1 Logging Setup

```python
# In app/__init__.py
import logging
from logging.handlers import RotatingFileHandler
import os

def configure_logging(app):
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    # File handler — rotates at 10MB, keeps last 10 files
    file_handler = RotatingFileHandler(
        'logs/linkedin_studio.log', 
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10
    )
    
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s (%(funcName)s:%(lineno)d): %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    if app.debug:
        file_handler.setLevel(logging.DEBUG)
    else:
        file_handler.setLevel(logging.WARNING)
    
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('LinkedIn Studio started')
```

### 8.2 Logging Rules

```python
# ✅ CORRECT — Log the right things at the right levels
app.logger.debug("Processing lead ID: %s", lead_id)         # Dev only
app.logger.info("User %s created a new draft", user_id)     # Normal operations
app.logger.warning("Rate limit approaching for user %s", uid)  # Warnings
app.logger.error("Failed to connect to LinkedIn API: %s", e, exc_info=True)  # Errors

# ❌ NEVER log — these are security violations
app.logger.info("Password: %s", password)
app.logger.info("Token: %s", access_token)
app.logger.info("Full request: %s", request.json)   # May contain secrets!

# ✅ Include request ID in logs for tracing
import uuid
@app.before_request
def add_request_id():
    g.request_id = str(uuid.uuid4())
```

### 8.3 Global Error Handlers

```python
# In app/__init__.py — ALWAYS register these
@app.errorhandler(400)
def bad_request(e):
    return error_response("Bad request", 400)

@app.errorhandler(401)
def unauthorized(e):
    return error_response("Authentication required", 401)

@app.errorhandler(403)
def forbidden(e):
    return error_response("You don't have permission to access this resource", 403)

@app.errorhandler(404)
def not_found(e):
    return error_response("Resource not found", 404)

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()  # Always rollback on 500
    app.logger.error("Internal error: %s", e, exc_info=True)
    # 🔴 ZERO STACK TRACES TO USERS: Never expose internal flaws globally
    return error_response("An internal error occurred. Our team has been notified.", 500)
```

---

## 9. EXTERNAL SERVICES & RESILIENCE

### 9.1 Retry Logic (Required for ALL External Calls)

```python
# For all external API calls — LinkedIn, Google, AI APIs
import time
from functools import wraps

def retry(max_retries=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    Retry decorator with exponential backoff.
    max_retries: Number of retry attempts
    delay: Initial delay in seconds
    backoff: Multiplier for delay on each retry
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    retries += 1
                    if retries == max_retries:
                        current_app.logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {e}"
                        )
                        raise
                    current_app.logger.warning(
                        f"{func.__name__} failed (attempt {retries}/{max_retries}): {e}. "
                        f"Retrying in {current_delay}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator

# Usage
@retry(max_retries=3, delay=2, exceptions=(requests.RequestException,))
def call_linkedin_api(endpoint, data):
    response = requests.post(endpoint, json=data, timeout=10)
    response.raise_for_status()
    return response.json()
```

### 9.2 Graceful Degradation

```python
# When external services fail, degrade gracefully
def get_ai_suggestions(content: str) -> list:
    """
    Get AI content suggestions. Gracefully degrades if AI service is unavailable.
    Returns empty list instead of crashing — frontend handles the empty state.
    """
    try:
        response = call_ai_api(content)
        return response.get('suggestions', [])
    except Exception as e:
        current_app.logger.error(f"AI suggestion service unavailable: {e}")
        return []  # Return safe default, never let this crash the page load
```

### 9.3 API Timeout Rules

```python
# ALWAYS set timeouts on external requests — no exceptions
import requests

# Quick reads: 5 second timeout
response = requests.get(url, timeout=5)

# File uploads / AI generation: 30 second timeout  
response = requests.post(url, json=data, timeout=30)

# NEVER use requests without a timeout — it will hang forever in production
# ❌ WRONG: requests.get(url)
```

### 9.4 Circuit Breaker Pattern (For High Traffic)

```python
# Use pybreaker for circuit breaker pattern on LinkedIn API calls
import pybreaker

linkedin_circuit_breaker = pybreaker.CircuitBreaker(
    fail_max=5,          # Open circuit after 5 consecutive failures
    reset_timeout=60     # Try again after 60 seconds
)

@linkedin_circuit_breaker
def call_linkedin_api(endpoint):
    ...
```

---

## 10. TESTING STANDARDS

### 10.1 Test File Structure

```
tests/
├── conftest.py              # pytest fixtures, test app, test db
├── unit/
│   ├── test_models.py       # Model methods, validators
│   ├── test_utils.py        # Utility functions
│   └── test_decorators.py   # Auth decorators
├── integration/
│   ├── test_auth_routes.py  # Full auth flow
│   ├── test_leads_routes.py # Lead CRUD operations
│   └── test_drafts_routes.py
└── security/
    ├── test_sql_injection.py  # SQL injection attempts
    ├── test_xss.py            # XSS attempts
    └── test_auth_bypass.py    # Auth bypass attempts
```

### 10.2 Test Writing Rules

```python
# tests/conftest.py — Standard test setup
import pytest
from app import create_app
from app.extensions import db as _db

@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    app = create_app('testing')
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_client(client, test_user):
    """An authenticated test client."""
    client.post('/auth/login', json={
        'email': test_user.email,
        'password': 'TestPassword123!'
    })
    return client

# EVERY route test must verify:
def test_leads_require_authentication(client):
    """Unauthenticated users must not access leads."""
    response = client.get('/api/v1/leads')
    assert response.status_code == 401

def test_leads_pagination(auth_client):
    """Verify pagination is enforced."""
    response = auth_client.get('/api/v1/leads?page=1')
    data = response.get_json()
    assert 'data' in data
    assert 'pages' in data['data']
    assert len(data['data']['leads']) <= 20  # Never more than page_size
```

### 10.3 Minimum Coverage Requirements

| Layer | Minimum Coverage |
|---|---|
| Models | 90% |
| Routes (happy path) | 90% |
| Routes (error path) | 80% |
| Utilities | 95% |
| Security checks | 100% |

```bash
# Run tests with coverage
pytest --cov=app --cov-report=html --cov-fail-under=80
```

---

## 11. FRONTEND STANDARDS

### 11.1 Template Security

```html
{# ✅ CORRECT — Jinja2 auto-escapes. This is safe. #}
<p>{{ user.name }}</p>

{# ❌ WRONG — Only use | safe for content YOU generated, never user input #}
<p>{{ user.bio | safe }}</p>

{# ✅ CORRECT — CSRF token on every form #}
<form method="POST">
    {{ form.hidden_tag() }}
    ...
</form>
```

### 11.2 JavaScript Security

```javascript
// ✅ CORRECT — Use textContent to prevent XSS
element.textContent = userData;

// ❌ WRONG — innerHTML with user data = XSS vulnerability
element.innerHTML = userData;

// ✅ CORRECT — Escape HTML before rendering user content
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// ✅ Always include CSRF token in AJAX requests
fetch('/api/v1/leads', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
    },
    body: JSON.stringify(data)
});
```

### 11.3 UI/UX Standards

- All forms must show **clear validation errors** (field-level, not just page-level).
- All destructive actions (delete, disconnect account) must require **confirmation dialogs**.
- All async actions must show **loading states** — never leave the user with a frozen UI.
- Mobile-first responsive design — test at 320px, 768px, and 1440px widths.
- Page load time must be under **3 seconds** on a standard connection.

---

## 12. CI/CD & DEPLOYMENT

### 12.1 Pre-Deployment Checklist (Automated)

```yaml
# .github/workflows/ci.yml — Run on every PR (Dockerize & Automated CI/CD)
steps:
  - name: Build Docker Image
    run: docker build -t linkscale .
    
  - name: Lint (flake8, black)
    run: docker run linkscale black --check app/ && flake8 app/
    
  - name: Security scan (Updated/Vetted Dependencies ONLY)
    run: docker run linkscale safety check && bandit -r app/
    
  - name: Run tests
    run: docker run linkscale pytest --cov=app --cov-fail-under=80
    
  - name: Check for secrets in code
    run: git-secrets --scan
```

### 12.2 Environment Variables (Never Commit Secrets)

```bash
# .env.example — ALWAYS keep this updated when adding new env vars
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:password@host:5432/dbname
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
LINKEDIN_CLIENT_ID=your-linkedin-client-id
LINKEDIN_CLIENT_SECRET=your-linkedin-client-secret
OPENAI_API_KEY=your-openai-key
REDIS_URL=redis://localhost:6379
FERNET_KEY=your-fernet-encryption-key
SENDGRID_API_KEY=your-email-api-key
```

### 12.3 Deployment Rules

```
1. NEVER deploy directly from the main branch without passing CI/CD.
2. ALWAYS run migrations BEFORE deploying new code: flask db upgrade
3. ALWAYS deploy to staging FIRST, verify, then deploy to production.
4. ALWAYS have a rollback plan: keep the previous Docker image tagged.
5. NEVER hard-restart the server — use zero-downtime deployments (gunicorn --preload).
```

---

## 13. PERFORMANCE & SCALABILITY

### 13.1 Caching Strategy

```python
# Install Flask-Caching with Redis backend
from flask_caching import Cache

cache = Cache(config={
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': os.environ.get('REDIS_URL'),
    'CACHE_DEFAULT_TIMEOUT': 300  # 5 minutes
})

# Cache expensive operations
@cache.cached(timeout=60, key_prefix='user_%s_analytics')
def get_user_analytics(user_id):
    # Expensive DB aggregation — cache it
    ...

# Invalidate cache when data changes
@bp.route('/api/v1/posts', methods=['POST'])
def create_post():
    # ... create post
    cache.delete(f'user_{current_user.id}_analytics')
    return success_response(...)
```

### 13.2 Stateless Service Design

```
RULE: Flask application must be stateless.
- No in-memory session data (use Redis-backed sessions)
- No file system state (use cloud storage like S3)
- No user data in global variables
This allows horizontal scaling — running 5 instances of the app behind a load balancer.
```

### 13.3 Background Jobs

```python
# Use message queues (Celery/Redis/RabbitMQ) for ALL asynchronous and long tasks.
# NEVER run long AI operations synchronously in a route handler
# ❌ WRONG — This blocks the request for 30 seconds
@bp.route('/generate-post')
def generate_post():
    result = call_openai_api(prompt)  # Takes 10-30 seconds!
    return jsonify(result)

# ✅ CORRECT — Queue it as a background message queue job
@bp.route('/generate-post')
def generate_post():
    job = generate_post_task.delay(prompt=prompt, user_id=current_user.id)
    return success_response({"job_id": job.id, "status": "processing"})

@celery.task
def generate_post_task(prompt, user_id):
    # Runs asynchronously in worker queue
    result = call_openai_api(prompt)
    # Save result to DB, then notify user via WebSocket or polling
```

---

## 14. CODE QUALITY & CLEAN CODE RULES

### 14.1 Naming Conventions

```python
# Variables and functions: snake_case (No 'slop squatting' or messy lazy names)
user_linkedin_token = get_user_token(user_id)

# Constants: UPPER_SNAKE_CASE
MAX_LEADS_PER_PAGE = 20
DEFAULT_POST_TIMEOUT = 30

# Classes: PascalCase
class LinkedInAPIClient:
    ...

# Booleans: is_, has_, can_, should_ prefix
is_authenticated = current_user.is_authenticated
has_linkedin_connected = user.linkedin_access_token is not None

# Don't abbreviate — clarity over brevity. Handle business logic explicitly.
# ❌ usr, usr_tok, conn_stat
# ✅ user, user_token, connection_status
```

### 14.2 Function Rules

```python
# RULE: A function should do ONE thing only
# RULE: Functions longer than 30 lines should be broken up
# RULE: Maximum 4 parameters — use a dict/dataclass if you need more

# ✅ CORRECT — Single responsibility  
def validate_email(email: str) -> bool:
    """Validate email format. Returns True if valid."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def hash_password(password: str) -> str:
    """Hash a password for secure storage."""
    return generate_password_hash(password, method='pbkdf2:sha256')

# ❌ WRONG — Does too many things, hard to test
def register_user_and_send_email_and_create_profile(name, email, password, role):
    ...
```

### 14.3 Documentation Standards

```python
def create_lead(user_id: int, name: str, email: str, linkedin_url: str = None) -> dict:
    """
    Create a new lead for a user.
    
    Args:
        user_id: The ID of the user who owns this lead.
        name: Full name of the lead.
        email: Email address of the lead. Must be unique per user.
        linkedin_url: Optional LinkedIn profile URL.
    
    Returns:
        dict: The serialized lead object.
    
    Raises:
        ValueError: If the email already exists for this user.
        SQLAlchemyError: If there is a database error.
    
    Example:
        lead = create_lead(user_id=1, name="John Doe", email="john@example.com")
    """
```

---

## 15. AGENT-SPECIFIC RULES (AI CODING ASSISTANTS)

> **These rules apply to ANY AI agent — Gemini, Claude, Cursor, Copilot — working on this codebase.**

### 15.1 Before Writing Any Code, ALWAYS:

1. **Read PRDV2.md** — Understand the product requirements.
2. **Read THIS FILE** — Know the engineering standards.
3. **Read the relevant directive** in `directives/` — Understand the specific task.
4. **Check existing code** — Never re-implement something that already exists.
5. **Check the model** in `app/models.py` — Never guess the schema.

### 15.2 YOU MUST NEVER:

- ❌ Skip authentication checks on any route — not even "temporary" ones.
- ❌ Use `debug=True` in any code you write.
- ❌ Hardcode API keys, passwords, or secrets.
- ❌ Use raw SQL strings with user input (f-strings in queries).
- ❌ Add `| safe` to any user-generated content in templates.
- ❌ Return stack traces or internal error details in API responses.
- ❌ Skip validation on form/API inputs.
- ❌ Make API calls without timeout parameters.
- ❌ Delete records with hard deletes — always use soft delete.
- ❌ Write code that only handles the "happy path". Always handle errors.
- ❌ Add a TODO comment as a placeholder — implement it now or document why it can't be done.
- ❌ Say "this is fine for now" — it will NOT be fine in production.

### 15.3 YOU MUST ALWAYS:

- ✅ Apply `@login_required` on every protected route.
- ✅ Apply `@require_role(...)` when the route is role-restricted.
- ✅ Apply `@limiter.limit(...)` on every API endpoint.
- ✅ Wrap external API calls in try/except with retry logic.
- ✅ Validate all inputs before using them.
- ✅ Use the `BaseModel` class for all new database models.
- ✅ Add an index to any column that will be used in `WHERE` clauses.
- ✅ Return paginated results for list endpoints.
- ✅ Log errors with `current_app.logger.error(..., exc_info=True)`.
- ✅ Write at least one unit test for every new function you add.
- ✅ Update `requirements.txt` when adding a new dependency.
- ✅ Update `.env.example` when adding a new environment variable.

### 15.4 When a Feature Feels "Too Complex":

```
DO NOT simplify the security or architecture to make it work faster.
Instead:
1. Break the feature into smaller tasks.
2. Document in directives/ how each part should work.
3. Implement each part in execution/ as a deterministic script.
4. Use the orchestration layer to coordinate.
```

---

## 16. FEATURE DEVELOPMENT CHECKLIST

> Copy this checklist for every new feature. Do not mark it done until ALL boxes are ticked.

```markdown
## Feature: [Feature Name]
### Pre-Development
- [ ] Read and understood PRDV2.md requirements for this feature
- [ ] Checked if any similar code already exists (DRY principle)
- [ ] Database schema designed with proper indexes and relationships
- [ ] Migration created and tested

### Security
- [ ] All routes have @login_required
- [ ] Role-based access implemented if needed (@require_role)
- [ ] Rate limiting applied to all API endpoints
- [ ] All inputs validated and sanitized
- [ ] CSRF protection on all forms
- [ ] Sensitive data encrypted if stored in DB
- [ ] No secrets hardcoded anywhere

### Backend
- [ ] Standard response format used (success_response / error_response)
- [ ] All external API calls have timeout, retry logic, and error handling
- [ ] Pagination implemented for list endpoints
- [ ] Proper error handlers registered
- [ ] Logging added for key operations and all errors
- [ ] Background tasks used for operations > 2 seconds

### Frontend
- [ ] CSRF token included in all form/AJAX requests
- [ ] Loading states shown during async operations
- [ ] Error states handled and displayed to users
- [ ] Mobile responsive layout verified
- [ ] No user data inserted via innerHTML (XSS prevention)

### Testing
- [ ] Unit tests written for all new functions
- [ ] Integration tests for all new routes
- [ ] Security tests for auth bypass and injection attempts
- [ ] Test coverage ≥ 80% for new code

### Documentation
- [ ] All functions have docstrings
- [ ] .env.example updated with new vars
- [ ] requirements.txt updated with new packages
- [ ] PRDV2.md updated if requirements changed
```

---

## 17. COMMON MISTAKES TO NEVER REPEAT

This section documents real production issues caused by cutting corners. **Read every entry.**

| # | Mistake | Consequence | Correct Approach |
|---|---|---|---|
| 1 | Skipping `@login_required` because "we'll add it later" | Any user can access any data | Add auth on the FIRST line of development |
| 2 | Using `debug=True` in production | Exposes full stack traces and debugger to public | Use environment-based config |
| 3 | Storing OAuth tokens as plain text in DB | Tokens can be stolen if DB is compromised | Always encrypt sensitive fields |
| 4 | No rate limiting on auth endpoints | Bot attacks can brute-force passwords | Apply strict rate limits from day one |
| 5 | `requests.get(url)` without timeout | A slow external service hangs every request indefinitely | Always set timeout |
| 6 | Fetching all records without pagination | DB crashes at scale; 10k records destroys performance | Always paginate |
| 7 | Using `f"SQL WHERE email = '{email}'"` | Classic SQL injection attack | Always use ORM or parameterized queries |
| 8 | No retry logic on AI/LinkedIn API calls | Single flaky response = broken feature | Implement retry with exponential backoff |
| 9 | Missing error handling on background tasks | Silent failures — user never knows the job failed | Always handle and log task failures |
| 10 | Using `{{ content \| safe }}` on user content | XSS attack — malicious script runs in victim's browser | Never use `\| safe` on user input |
| 11 | Hard-deleting records | Cannot audit, cannot recover, compliance risk | Soft delete with `is_deleted` flag |
| 12 | No session timeout | A stolen device gives permanent access forever | Set `PERMANENT_SESSION_LIFETIME` |
| 13 | Not setting Content-Security-Policy | XSS attacks inject scripts from external domains | Set security headers on every response |
| 14 | `except Exception: pass` | Silent failures — bugs hide forever | Always log the exception at minimum |
| 15 | Global variables for user state | Breaks as soon as you run 2 workers | Never put user state in global variables |

---

## 🚀 FINAL NOTES

This document is **living** — update it every time you discover a new pattern, a new type of bug, or a new requirement.

**The goal is not just a working application. The goal is:**
- An application that is **impossible to hack in obvious ways**.
- An application that **doesn't break under load**.
- An application where **any feature can be changed in minutes without fear**.
- An application that **any developer can pick up and understand on day one**.

> **"Perfect is the enemy of good" does NOT apply to security. Secure from Day 1. Always."**

---

*Last updated: 2026-03-13 | Version: 1.0.1 | Project: LinkScale*
*Author: Engineering Standards Committee — Maintained for all AI agents and developers.*
