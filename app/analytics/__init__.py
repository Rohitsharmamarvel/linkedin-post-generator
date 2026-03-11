"""
Analytics Blueprint
───────────────────
Provides usage statistics and post activity data scoped to the current user.

CURRENT STATUS: ⚠️  PARTIAL MOCK
  - Published post counts, draft counts, and AI generation counts are REAL
    (pulled from the database, scoped to current_user.id).
  - LinkedIn engagement stats (impressions, likes, comments) are MOCKED at 0
    because we have not yet integrated the LinkedIn Analytics API.

PRODUCTION PLAN — LinkedIn Engagement Data:
  When ready to show real impressions/likes, integrate the LinkedIn Analytics API:
  Endpoint: GET https://api.linkedin.com/v2/organizationalEntityShareStatistics
  Docs: https://learn.microsoft.com/en-us/linkedin/marketing/integrations/community-management/shares/share-statistics
  Requires: LinkedIn Marketing Developer Platform access (apply at LinkedIn Developer portal)
  For personal posts: use /v2/socialActions/{shareUrn}/likes and /comments
  Store the URN per post in Draft.linkedin_post_urn (already in the model).
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Draft, UsageLog
from datetime import datetime, timedelta
from sqlalchemy import func

analytics_bp = Blueprint('analytics', __name__, template_folder='templates')


@analytics_bp.route('/', methods=['GET'])
@login_required
def index():
    """
    Render the analytics dashboard.

    All counts are scoped to current_user.id — no user ever sees another user's data.
    Engagement stats (impressions/likes) show 0 until LinkedIn API is integrated.
    """
    # ── Real data from DB (scoped strictly to this user) ───────────────────────
    total_gens = UsageLog.query.filter_by(
        user_id=current_user.id, action='generate'
    ).count()

    published_count = Draft.query.filter_by(
        user_id=current_user.id, status='published', is_deleted=False
    ).count()

    scheduled_count = Draft.query.filter_by(
        user_id=current_user.id, status='scheduled', is_deleted=False
    ).count()

    draft_count = Draft.query.filter_by(
        user_id=current_user.id, status='draft', is_deleted=False
    ).count()

    # ── Engagement stats — 0 until LinkedIn Analytics API is wired up ──────────
    # PRODUCTION: Replace with real API calls using draft.linkedin_post_urn
    # See module docstring above for the API endpoint to call.
    total_impressions = 0   # MOCK — will come from LinkedIn Analytics API
    total_likes       = 0   # MOCK — will come from LinkedIn Analytics API
    total_comments    = 0   # MOCK — will come from LinkedIn Analytics API

    return render_template(
        'analytics/index.html',
        total_gens=total_gens,
        published_count=published_count,
        scheduled_count=scheduled_count,
        draft_count=draft_count,
        total_impressions=total_impressions,
        total_likes=total_likes,
        total_comments=total_comments
    )


@analytics_bp.route('/api/activity', methods=['GET'])
@login_required
def api_activity():
    """
    Return real activity counts per day for the last 14 days.

    Scoped to current_user.id. Counts actual UsageLog entries grouped by date.
    No random numbers — every user sees their own real activity.

    Returns:
        JSON with a 'data' array of {date, generations, published} objects.
    """
    days = 14
    data = []
    now = datetime.utcnow()

    # Fetch all usage logs for this user in the last 14 days — one DB query
    since = now - timedelta(days=days)
    logs = UsageLog.query.filter(
        UsageLog.user_id == current_user.id,
        UsageLog.created_at >= since
    ).all()

    # Fetch all published drafts in the same window
    published = Draft.query.filter(
        Draft.user_id == current_user.id,
        Draft.status == 'published',
        Draft.is_deleted == False,
        Draft.published_at >= since
    ).all()

    # Group by date string — build lookup dicts
    gen_by_date = {}
    for log in logs:
        if log.action == 'generate':
            day = log.created_at.strftime('%m-%d')
            gen_by_date[day] = gen_by_date.get(day, 0) + 1

    pub_by_date = {}
    for draft in published:
        if draft.published_at:
            day = draft.published_at.strftime('%m-%d')
            pub_by_date[day] = pub_by_date.get(day, 0) + 1

    # Build the response array — one entry per day, no gaps
    for i in range(days, -1, -1):
        target_date = now - timedelta(days=i)
        day_key = target_date.strftime('%m-%d')
        data.append({
            'date': target_date.strftime('%d'),          # "08" for display on chart
            'label': target_date.strftime('%b %d'),      # "Mar 08" for tooltip
            'generations': gen_by_date.get(day_key, 0), # Real count, not random
            'published': pub_by_date.get(day_key, 0)    # Real count, not random
        })

    return jsonify({'success': True, 'data': data})
