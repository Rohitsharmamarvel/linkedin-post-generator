"""
Drafts Blueprint  
Handles the creation, saving, editing, and deletion of drafts.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
import bleach
from marshmallow import Schema, fields, validate, ValidationError
from app.extensions import db, limiter
from app.models import Draft
from datetime import datetime

# ─── SCHEMA VALIDATION ────────────────────────────────────────────────────────
class DraftSaveSchema(Schema):
    id = fields.Int(required=False, allow_none=True)
    content = fields.Str(required=False, load_default='')
    title = fields.Str(required=False, load_default='')
    tags = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))

drafts_bp = Blueprint('drafts', __name__, template_folder='templates')


@drafts_bp.route('/', methods=['GET'])
@login_required
def drafts_list():
    """Render the drafts management page."""
    return render_template('drafts/index.html')


@drafts_bp.route('/api/list', methods=['GET'])
@login_required
def api_list():
    """Return all drafts for the current user."""
    status_filter = request.args.get('status', None)
    
    query = Draft.query.filter_by(user_id=current_user.id, is_deleted=False)
    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    drafts = query.order_by(Draft.updated_at.desc()).all()
    
    result = []
    for d in drafts:
        result.append({
            'id': d.id,
            'title': d.title or 'Untitled',
            'content': d.content or '',
            'status': d.status,
            'char_count': d.char_count or 0,
            'tags': d.tags or '',
            'scheduled_at': d.scheduled_at.isoformat() if d.scheduled_at else None,
            'published_at': d.published_at.isoformat() if d.published_at else None,
            'created_at': d.created_at.isoformat() if d.created_at else None,
            'updated_at': d.updated_at.isoformat() if d.updated_at else None,
        })
    
    return jsonify({'success': True, 'drafts': result})


@drafts_bp.route('/api/save', methods=['POST'])
@login_required
@limiter.limit("60 per hour")
def api_save():
    """Save a new draft or update an existing one."""
    # 🔴 Mandatory Input Validation (Schema)
    schema = DraftSaveSchema()
    try:
        data = schema.load(request.json or {})
    except ValidationError as err:
        return jsonify({"success": False, "errors": err.messages}), 422
        
    draft_id = data.get('id')
    
    # 🔴 Mandatory Output Sanitization (Bleach against XSS injection)
    # Allows some basic tags if formatting is supported, but cleans dangerous ones.
    ALLOWED_TAGS = ['b', 'i', 'strong', 'em', 'p', 'br', 'ul', 'ol', 'li', 'a']
    ALLOWED_ATTRS = {'a': ['href', 'title']}
    content = bleach.clean(data.get('content', ''), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
    title = bleach.clean(data.get('title', ''), strip=True)
    
    if draft_id:
        # Update existing
        draft = Draft.query.filter_by(id=draft_id, user_id=current_user.id).first()
        if not draft:
            return jsonify({'success': False, 'error': 'Draft not found'}), 404
    else:
        # Create new
        draft = Draft(user_id=current_user.id)
        db.session.add(draft)
    
    draft.title = title or (content[:60] + '...' if len(content) > 60 else content) or 'Untitled'
    draft.content = content
    draft.char_count = len(content)
    draft.updated_at = datetime.utcnow()
    
    if data.get('tags'):
        draft.tags = data['tags']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'draft_id': draft.id,
        'message': 'Draft saved successfully'
    })


@drafts_bp.route('/api/delete/<int:draft_id>', methods=['DELETE'])
@login_required
def api_delete(draft_id):
    """Delete a draft."""
    draft = Draft.query.filter_by(id=draft_id, user_id=current_user.id).first()
    if not draft:
        return jsonify({'success': False, 'error': 'Draft not found'}), 404
    
    draft.soft_delete()
    
    return jsonify({'success': True, 'message': 'Draft deleted'})
