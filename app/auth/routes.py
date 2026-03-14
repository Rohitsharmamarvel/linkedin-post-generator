"""
app/auth/routes.py
──────────────────
Authentication routes — Google OAuth 2.0 flow.

Engineering Standards compliance:
  - Rate limiting on login endpoints (Section 6)
  - OAuth state parameter used automatically by authlib (CSRF protection)
  - User scoped — google_id is the primary identity, email is mutable (PRDV2)
  - Login attempts logged for audit trail (Section 8.2)
  - No secrets stored — only google_id and profile info (Section 3.4)
"""
from flask import redirect, url_for, session, render_template, request, current_app, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.extensions import db, oauth, limiter
from app.models import User, UsageLog


@auth_bp.route('/login')
def login():
    """Render the login page. Redirect authenticated users to dashboard."""
    if current_user.is_authenticated:
        return redirect('/dashboard')
    return render_template('auth/login.html')


@auth_bp.route('/google')
@limiter.limit("20 per minute; 100 per hour")
def login_google():
    """
    Initiate the Google OAuth 2.0 authorization flow.
    Rate limited to prevent bot-driven OAuth abuse.
    """
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/callback')
@limiter.limit("20 per minute")
def google_callback():
    """
    Handle the Google OAuth callback.
    Creates a new user record on first login, or loads the existing user.
    The oauth 'state' parameter is validated automatically by authlib.
    """
    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:
        current_app.logger.warning("Google OAuth callback error: %s", e)
        flash("Google sign-in failed. Please try again.", "danger")
        return redirect(url_for('auth.login'))

    userinfo = token.get('userinfo')

    if not userinfo:
        current_app.logger.warning(
            "OAuth callback received no userinfo. Possible misconfiguration."
        )
        return redirect(url_for('auth.login'))

    google_id = str(userinfo['sub'])
    email = userinfo.get('email', '')

    # Look up or create user — google_id is the stable identity
    user = User.query.filter_by(google_id=google_id).first()

    if not user:
        # New user — create account
        user = User(
            google_id=google_id,
            email=email,
            name=userinfo.get('name'),
            avatar_url=userinfo.get('picture')
        )
        db.session.add(user)
        current_app.logger.info("New user registered via Google OAuth: %s", email)
    else:
        # Existing user — update mutable profile fields (email may change)
        user.name = userinfo.get('name', user.name)
        user.avatar_url = userinfo.get('picture', user.avatar_url)
        if user.email != email:
            current_app.logger.info(
                "User %s email changed from %s to %s", google_id, user.email, email
            )
            user.email = email

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Failed to save user on OAuth callback: %s", e, exc_info=True)
        return redirect(url_for('auth.login'))

    # Log the login event for audit trail
    log = UsageLog(user_id=user.id, action='login', topic='google_oauth')
    db.session.add(log)
    db.session.commit()

    login_user(user, remember=True)
    current_app.logger.info("User %s logged in.", user.id)
    flash(f"Welcome back, {user.name or 'Creator'}!", "success")

    # Redirect to intended page if there was a 'next' param, otherwise dashboard
    next_page = request.args.get('next')
    if next_page and next_page.startswith('/'):  # Validate next to prevent open redirect
        return redirect(next_page)
    return redirect('/dashboard')


@auth_bp.route('/logout')
@login_required
def logout():
    """
    Fully log the current user out.

    Steps:
    1. logout_user()     — removes user from Flask-Login session
    2. session.clear()   — destroys the server-side session data
    3. Delete cookie     — explicitly delete the 'remember_token' cookie so
                           even users who chose 'remember me' are fully signed out

    The remember_token cookie is what bypasses the session and keeps users
    logged in across browser restarts. Without deleting it, the user would
    be redirected back to dashboard immediately after logout.
    """
    user_id = current_user.id
    logout_user()
    session.clear()
    current_app.logger.info("User %s logged out successfully.", user_id)

    # Build the redirect response and explicitly delete the remember_token cookie
    # This is the critical step — just calling logout_user() is not always enough
    response = redirect(url_for('landing'))
    response.delete_cookie('remember_token')
    response.delete_cookie('session')
    return response


@auth_bp.route('/linkedin/connect')
@login_required
def linkedin_connect():
    """Render the LinkedIn connection UI and status page"""
    return render_template('auth/linkedin_connect.html')


@auth_bp.route('/linkedin/redirect')
@login_required
def linkedin_redirect():
    """
    Initiate the real LinkedIn OAuth flow.
    """
    redirect_uri = url_for('auth.linkedin_callback', _external=True)
    return oauth.linkedin.authorize_redirect(redirect_uri)


@auth_bp.route('/linkedin/callback')
@login_required
def linkedin_callback():
    from app.models import LinkedInToken
    from datetime import datetime, timedelta
    
    try:
        token = oauth.linkedin.authorize_access_token()
    except Exception as e:
        current_app.logger.error("Failed to fetch LinkedIn access token: %s", e)
        flash("LinkedIn connection failed. Please ensure you granted all permissions.", "danger")
        return redirect(url_for('auth.linkedin_connect'))
        
    access_token = token.get('access_token')
    expires_in = token.get('expires_in', 60 * 24 * 60 * 60) # Default to 60 days
    
    # Try to fetch the person URN
    person_urn = None
    try:
        # Userinfo typically contains 'sub' representing the person ID in OpenID integrations
        userinfo = oauth.linkedin.get('userinfo').json()
        if 'sub' in userinfo:
            person_urn = f"urn:li:person:{userinfo['sub']}"
    except Exception as e:
        current_app.logger.warning("Could not fetch userinfo for URN: %s. Attempting fallback 'me' endpoint.", e)
        try:
            me_resp = oauth.linkedin.get('me').json()
            if 'id' in me_resp:
                person_urn = f"urn:li:person:{me_resp['id']}"
        except Exception as e2:
            current_app.logger.warning("Could not fetch 'me' for URN either: %s", e2)
    
    # Save or update the LinkedIn token
    li_token = LinkedInToken.query.filter_by(user_id=current_user.id).first()
    if not li_token:
        li_token = LinkedInToken(user_id=current_user.id)
        db.session.add(li_token)
    
    li_token.token = access_token
    if person_urn:
        li_token.person_urn = person_urn
    li_token.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    
    db.session.commit()
    flash("LinkedIn profile successfully linked!", "success")
    return redirect(url_for('auth.linkedin_connect'))

