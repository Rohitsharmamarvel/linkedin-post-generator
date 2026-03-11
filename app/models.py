"""
app/models.py
─────────────
SQLAlchemy models for LinkedIn Content Studio.

Engineering Standards compliance:
  - All models extend BaseModel for consistent audit fields (Section 7.1)
  - Soft-delete via is_deleted — hard deletes are forbidden (Section 15.3)
  - LinkedInToken.access_token is encrypted at rest via Fernet (Section 7.3)
  - Indexes added on all columns used in WHERE clauses (Section 7.4)
  - to_dict() on every model for consistent API serialisation (Section 5.3)

IMPORTANT: After any schema change, run:
    flask db migrate -m "description of change"
    flask db upgrade
"""
from datetime import datetime
from typing import Optional
from app.extensions import db
from flask_login import UserMixin


# ─── BASE MODEL ──────────────────────────────────────────────────────────────

class BaseModel(db.Model):
    """
    Abstract base model.
    All models MUST extend this to get:
      - Consistent primary key
      - created_at / updated_at audit timestamps (auto-managed)
      - is_deleted soft-delete flag — NEVER hard-delete records
    """
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)

    def soft_delete(self):
        """
        Mark this record as deleted without removing it from the database.
        Use this instead of db.session.delete() everywhere.
        """
        self.is_deleted = True
        db.session.commit()

    def to_dict(self):
        """
        Serialise this model instance to a JSON-safe dictionary.
        Every subclass MUST override this method.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.to_dict() must be implemented."
        )


# ─── USER ────────────────────────────────────────────────────────────────────

class User(UserMixin, BaseModel):
    """
    Represents an authenticated user.
    Identity comes from Google OAuth — no password is stored.
    plan: 'free' | 'pro'
    """
    __tablename__ = 'users'

    # Google OAuth identity — primary identifier (immutable)
    google_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=True)
    avatar_url = db.Column(db.String(512), nullable=True)

    # Subscription plan
    plan = db.Column(db.String(20), default='free', nullable=False, index=True)
    plan_expires_at = db.Column(db.DateTime, nullable=True)
    stripe_customer_id = db.Column(db.String(100), nullable=True, unique=True)

    # Relationships — cascade delete ensures orphaned records are cleaned up
    drafts = db.relationship(
        'Draft', backref='user', lazy=True, cascade="all, delete-orphan"
    )
    usage_logs = db.relationship(
        'UsageLog', backref='user', lazy=True, cascade="all, delete-orphan"
    )
    linkedin_token = db.relationship(
        'LinkedInToken', backref='user', uselist=False, cascade="all, delete-orphan"
    )

    def to_dict(self):
        """Serialise user for API responses. Never include secrets."""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'avatar_url': self.avatar_url,
            'plan': self.plan,
            'plan_expires_at': self.plan_expires_at.isoformat() if self.plan_expires_at else None,
            'has_linkedin': self.linkedin_token is not None,
            'created_at': self.created_at.isoformat(),
        }

    def __repr__(self):
        return f'<User {self.email} [{self.plan}]>'


# ─── DRAFT ───────────────────────────────────────────────────────────────────

class Draft(BaseModel):
    """
    Represents a LinkedIn post in any stage of the content lifecycle.
    status: 'draft' | 'scheduled' | 'published' | 'failed'

    Scheduling note: scheduled_at is always stored in UTC.
    Convert to user's local timezone only in the UI layer.
    """
    __tablename__ = 'drafts'

    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True
    )
    title = db.Column(db.String(200), nullable=True)
    content = db.Column(db.Text, nullable=True)           # Plain text
    formatted_content = db.Column(db.Text, nullable=True) # With markup

    # Lifecycle status — indexed for frequent WHERE status = ? queries
    status = db.Column(
        db.String(20), default='draft', nullable=False, index=True
    )
    tags = db.Column(db.String(200), nullable=True)

    # Scheduling — stored in UTC
    scheduled_at = db.Column(db.DateTime, nullable=True, index=True)
    published_at = db.Column(db.DateTime, nullable=True)

    # Publishing outcome
    linkedin_post_urn = db.Column(db.String(200), nullable=True)  # URN from LinkedIn after publish
    publish_error = db.Column(db.Text, nullable=True)             # Error message if publish failed

    char_count = db.Column(db.Integer, default=0)

    def to_dict(self):
        """Serialise draft for API responses."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'content': self.content,
            'status': self.status,
            'tags': self.tags.split(',') if self.tags else [],
            'char_count': self.char_count or 0,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'linkedin_post_urn': self.linkedin_post_urn,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    def content_preview(self, max_chars: int = 120) -> str:
        """Return a truncated content preview safe for list views."""
        if not self.content:
            return 'No content'
        if len(self.content) > max_chars:
            return self.content[:max_chars] + '...'
        return self.content

    def __repr__(self):
        return f'<Draft id={self.id} status={self.status}>'


# ─── USAGE LOG ───────────────────────────────────────────────────────────────

class UsageLog(BaseModel):
    """
    Tracks all significant user actions for analytics and abuse detection.
    action: 'generate' | 'publish' | 'schedule' | 'login'
    """
    __tablename__ = 'usage_logs'

    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True
    )
    action = db.Column(db.String(50), nullable=False, index=True)
    topic = db.Column(db.String(200), nullable=True)
    char_count = db.Column(db.Integer, nullable=True)
    extra_data = db.Column(db.Text, nullable=True)  # JSON string for extra context (e.g. model used, prompt topic)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'topic': self.topic,
            'char_count': self.char_count,
            'created_at': self.created_at.isoformat(),
        }

    def __repr__(self):
        return f'<UsageLog user={self.user_id} action={self.action}>'


# ─── LINKEDIN TOKEN ───────────────────────────────────────────────────────────

class LinkedInToken(BaseModel):
    """
    Stores a user's LinkedIn OAuth access token.

    SECURITY: access_token is encrypted at rest using Fernet symmetric
    encryption. Use the .token property (not ._token_encrypted) to read/write.
    The encryption key comes from FERNET_KEY in the app config.

    Never log the decrypted token. Never return it in API responses.
    """
    __tablename__ = 'linkedin_tokens'

    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True
    )

    # ENCRYPTED field — do not access this column directly in application code
    # Use the .token property below instead.
    _token_encrypted = db.Column('access_token', db.Text, nullable=False)

    person_urn = db.Column(db.String(100), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)
    last_used_at = db.Column(db.DateTime, nullable=True)

    # ── Encrypted token property ──────────────────────────────────────────────

    @property
    def token(self) -> Optional[str]:
        """
        Decrypt and return the LinkedIn access token.
        Returns None if decryption fails (key mismatch or token corrupted).
        Treat None as "user needs to reconnect LinkedIn".
        """
        if not self._token_encrypted:
            return None
        from app.utils import decrypt_token
        return decrypt_token(self._token_encrypted)

    @token.setter
    def token(self, plain_token: str) -> None:
        """
        Encrypt and store the LinkedIn access token.
        Called automatically when you do: linkedin_token.token = "some_value"
        """
        from app.utils import encrypt_token
        self._token_encrypted = encrypt_token(plain_token)

    # ─────────────────────────────────────────────────────────────────────────

    def is_expired(self) -> bool:
        """Return True if the LinkedIn token has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at

    def is_expiring_soon(self, days: int = 7) -> bool:
        """Return True if the token expires within `days` days."""
        from datetime import timedelta
        if not self.expires_at:
            return False
        return datetime.utcnow() >= (self.expires_at - timedelta(days=days))

    def to_dict(self):
        """Never include the token value in serialisation."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'person_urn': self.person_urn,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_expired': self.is_expired(),
            'is_expiring_soon': self.is_expiring_soon(),
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'created_at': self.created_at.isoformat(),
        }

    def __repr__(self):
        return f'<LinkedInToken user={self.user_id} expired={self.is_expired()}>'
