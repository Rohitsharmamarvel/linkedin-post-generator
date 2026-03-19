from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
oauth = OAuth()
csrf = CSRFProtect()

from flask_login import current_user

def user_id_key():
    """Identifies the user for rate limiting. Returns user ID if logged in, otherwise IP."""
    if current_user and current_user.is_authenticated:
        return str(current_user.id)
    return get_remote_address()

# Rate limiter — identifies users by ID if logged in, otherwise IP.
# Storage URI is configured via app.config['RATELIMIT_STORAGE_URI'] 
# during app.init_app(app) or via the 'storage_uri' parameter.
limiter = Limiter(
    key_func=user_id_key,
    default_limits=["500 per day", "100 per hour"],
    storage_uri="memory://", # This is overridden by app.config['RATELIMIT_STORAGE_URI'] in create_app
)

# Set login view — redirects unauthenticated users to login page
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please sign in to access this page.'
login_manager.login_message_category = 'info'
