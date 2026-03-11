"""
Calendar Blueprint
Handles the visual content calendar and scheduling interface.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Draft
from datetime import datetime, timedelta
from sqlalchemy import or_, and_

calendar_bp = Blueprint('calendar', __name__, template_folder='templates')


@calendar_bp.route('/', methods=['GET'])
@login_required
def calendar_view():
    """Render the calendar page."""
    scheduled_posts = Draft.query.filter_by(user_id=current_user.id, status='scheduled').order_by(Draft.scheduled_at).all()
    published_posts = Draft.query.filter_by(user_id=current_user.id, status='published').order_by(Draft.published_at.desc().nullslast()).all()
    return render_template('calendar/index.html', scheduled_posts=scheduled_posts, published_posts=published_posts)


@calendar_bp.route('/api/events', methods=['GET'])
@login_required
def api_events():
    """Return scheduled/published posts as calendar events for the frontend."""
    # Get month/year from query params (default: current month)
    year = request.args.get('year', datetime.utcnow().year, type=int)
    month = request.args.get('month', datetime.utcnow().month, type=int)
    
    # Calculate date range for the month
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)
    
    # Query drafts that are scheduled or published within this range
    drafts = Draft.query.filter(
        Draft.user_id == current_user.id,
        Draft.status.in_(['scheduled', 'published']),
        or_(
            and_(Draft.scheduled_at >= start_date, Draft.scheduled_at < end_date),
            and_(Draft.published_at >= start_date, Draft.published_at < end_date)
        )
    ).order_by(Draft.scheduled_at).all()
    
    events = []
    for draft in drafts:
        events.append({
            'id': draft.id,
            'title': draft.title or (draft.content[:50] + '...' if draft.content and len(draft.content) > 50 else draft.content or 'Untitled'),
            'date': draft.scheduled_at.strftime('%Y-%m-%d'),
            'time': draft.scheduled_at.strftime('%H:%M'),
            'status': draft.status,
            'char_count': draft.char_count or 0,
        })
    
    return jsonify({'success': True, 'events': events, 'year': year, 'month': month})


@calendar_bp.route('/api/schedule', methods=['POST'])
@login_required
def api_schedule():
    """Schedule or reschedule a draft."""
    data = request.json
    draft_id = data.get('draft_id')
    scheduled_at_str = data.get('scheduled_at')  # ISO format: 2026-03-05T09:00
    
    if not draft_id or not scheduled_at_str:
        return jsonify({'success': False, 'error': 'Missing draft_id or scheduled_at'}), 400
    
    draft = Draft.query.filter_by(id=draft_id, user_id=current_user.id).first()
    if not draft:
        return jsonify({'success': False, 'error': 'Draft not found'}), 404
    
    try:
        scheduled_at = datetime.fromisoformat(scheduled_at_str)
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date format. Use ISO format.'}), 400
    
    if scheduled_at <= datetime.utcnow() + timedelta(minutes=5):
        return jsonify({'success': False, 'error': 'Scheduled time must be at least 5 minutes in the future'}), 400
    
    # Check plan limits
    active_scheduled = Draft.query.filter_by(user_id=current_user.id, status='scheduled').count()
    max_allowed = 50 if current_user.plan == 'pro' else 3
    if active_scheduled >= max_allowed and draft.status != 'scheduled':
        return jsonify({
            'success': False,
            'error': f'Free plan allows {max_allowed} scheduled posts. Upgrade to Pro for more.',
            'code': 'PLAN_LIMIT'
        }), 403
    
    draft.scheduled_at = scheduled_at
    draft.status = 'scheduled'
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Post scheduled for {scheduled_at.strftime("%b %d, %Y at %I:%M %p")}',
        'draft_id': draft.id
    })


@calendar_bp.route('/api/unschedule/<int:draft_id>', methods=['POST'])
@login_required
def api_unschedule(draft_id):
    """Remove a post from the schedule (back to draft)."""
    draft = Draft.query.filter_by(id=draft_id, user_id=current_user.id).first()
    if not draft:
        return jsonify({'success': False, 'error': 'Draft not found'}), 404
    
    draft.status = 'draft'
    draft.scheduled_at = None
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Post removed from schedule'})
