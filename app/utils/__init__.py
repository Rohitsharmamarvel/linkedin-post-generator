"""
app/utils/security.py
─────────────────────
Security utility functions.
Centralised location for encryption helpers, role decorators,
and input sanitisation so logic is never duplicated in routes.

Engineering Standards compliance:
  - Fernet symmetric encryption for tokens at rest (Section 3.3, 7.3)
  - Role-based access control decorator (Section 4.2)
  - Input sanitisation helper (Section 3.3)
"""
import re
import bleach
from functools import wraps
from flask import abort, current_app
from flask_login import current_user
from cryptography.fernet import Fernet, InvalidToken


# ─── ALLOWED HTML TAGS (for rich text content only) ──────────────────────────
# Never allow <script>, <iframe>, <object>, or event attributes.
ALLOWED_TAGS = ['b', 'i', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li']
ALLOWED_ATTRIBUTES = {}  # No attributes allowed to prevent event-handler injection


# ─── TOKEN ENCRYPTION ────────────────────────────────────────────────────────

def encrypt_token(plain_token: str) -> str:
    """
    Encrypt a secret token (e.g. LinkedIn access token) using Fernet
    symmetric encryption before writing it to the database.

    Args:
        plain_token: The raw token string to encrypt.

    Returns:
        URL-safe base64-encoded encrypted string.

    Raises:
        RuntimeError: If FERNET_KEY is not set in the application config.
    """
    fernet_key = current_app.config.get('FERNET_KEY')
    if not fernet_key:
        raise RuntimeError(
            "FERNET_KEY is not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    f = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)
    return f.encrypt(plain_token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str | None:
    """
    Decrypt a Fernet-encrypted token retrieved from the database.

    Args:
        encrypted_token: The encrypted token string.

    Returns:
        The original plain-text token, or None if decryption fails.
        Returning None instead of raising is intentional — callers
        should treat a None token as "token unavailable" and prompt
        the user to reconnect.
    """
    fernet_key = current_app.config.get('FERNET_KEY')
    if not fernet_key:
        current_app.logger.error("FERNET_KEY not configured — cannot decrypt token.")
        return None
    try:
        f = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)
        return f.decrypt(encrypted_token.encode()).decode()
    except (InvalidToken, Exception) as e:
        current_app.logger.error(
            "Token decryption failed. Token may have been encrypted with a different key. "
            "User will need to reconnect. Error: %s", e
        )
        return None


# ─── ROLE-BASED ACCESS CONTROL ───────────────────────────────────────────────

def require_plan(*plans):
    """
    Route decorator that restricts access to users on specific subscription plans.

    Args:
        *plans: Accepted plan strings, e.g. 'pro', 'enterprise'.

    Usage:
        @bp.route('/premium-feature')
        @login_required
        @require_plan('pro')
        def premium_feature():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.plan not in plans:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ─── INPUT SANITISATION ──────────────────────────────────────────────────────

def sanitize_html(raw_html: str) -> str:
    """
    Strip disallowed HTML tags and attributes from user-provided rich text.
    Uses the bleach library. This is NOT for plain-text fields — use
    Jinja2's auto-escaping for those. Only use this when you intentionally
    want to allow a limited set of formatting tags (e.g. post editor content).

    Args:
        raw_html: The raw HTML string from user input.

    Returns:
        Sanitised HTML string safe for storage and rendering.
    """
    return bleach.clean(raw_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)


def mask_sensitive_log(text: str) -> str:
    """
    Remove secret values from a string before logging.
    Prevents accidental secret leakage into log files.

    Args:
        text: Log message that may contain sensitive data.

    Returns:
        The message with secrets replaced by '***REDACTED***'.

    Example:
        mask_sensitive_log("token=abc123&password=secret")
        → "token=***REDACTED***&password=***REDACTED***"
    """
    sensitive_pattern = re.compile(
        r'(access_token|api_key|secret|password|token|authorization)=[^\s&"\']+',
        re.IGNORECASE
    )
    return sensitive_pattern.sub(r'\1=***REDACTED***', str(text))
