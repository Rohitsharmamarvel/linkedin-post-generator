"""
Editor Blueprint
Handles the post creation interface, AI generation, and draft saving.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
import sys
import os
import bleach
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime, timedelta
from app.extensions import db, limiter
from app.models import UsageLog

# Add project root to sys.path so we can import execution module
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)
from execution.generate_post import generate_post

# ─── SCHEMA VALIDATION ────────────────────────────────────────────────────────
class GeneratePostSchema(Schema):
    topic = fields.Str(required=True, validate=validate.Length(min=1, max=5000))
    tone = fields.Str(required=False, load_default='professional', validate=validate.Length(max=50))
    maxLength = fields.Int(required=False, load_default=1500, validate=validate.Range(min=100, max=5000))

editor_bp = Blueprint('editor', __name__, template_folder='templates')

@editor_bp.route('/', methods=['GET'])
@login_required
def new_post():
    """Render the post editor interface."""
    draft_id = request.args.get('draft_id')
    draft = None
    if draft_id:
        from app.models import Draft
        draft = Draft.query.filter_by(id=draft_id, user_id=current_user.id).first()
        
    return render_template('editor/index.html', draft=draft)

@editor_bp.route('/api/generate', methods=['POST'])
@login_required
@limiter.limit("20 per hour")
def api_generate():
    """Handle frontend requests for AI generation, utilizing our 3-layer architecture execution script."""
    # 🔴 Mandatory Input Validation (Schema)
    schema = GeneratePostSchema()
    try:
        data = schema.load(request.json or {})
    except ValidationError as err:
        return jsonify({"success": False, "errors": err.messages}), 422
    
    # 🔴 Mandatory Output Sanitization (Bleach against XSS injection on topic)
    raw_topic = data.get('topic')
    topic = bleach.clean(raw_topic, strip=True)
    tone = bleach.clean(data.get('tone'), strip=True)
    max_length = data.get('maxLength')
    
    # 🔴 Mandatory Usage Limits (Business Logic Layer)
    # Check if user has exceeded their daily AI generation quota
    day_ago = datetime.utcnow() - timedelta(days=1)
    gen_count = UsageLog.query.filter(
        UsageLog.user_id == current_user.id,
        UsageLog.action == 'generate',
        UsageLog.created_at >= day_ago
    ).count()
    
    max_gens = 100 if current_user.plan == 'pro' else 10
    if gen_count >= max_gens:
        return jsonify({
            "success": False, 
            "errors": [{"message": f"Daily AI quota reached ({max_gens} generations). Upgrade to Pro for more."}],
            "code": "QUOTA_EXCEEDED"
        }), 403

    # Layer 2 (Orchestration): Call Layer 3 (Execution script)
    # (Note: In future, this blocks. To be converted to Celery later step as per standards.)
    result = generate_post(
        topic=topic,
        tone=tone,
        max_length=max_length
    )
    
    if result["success"]:
        post_text = result["data"]["post_text"]
        db.session.add(UsageLog(
            user_id=current_user.id,
            action='generate',
            char_count=len(post_text)
        ))
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "post_text": post_text
        })
    else:
        return jsonify({
            "success": False, 
            "errors": result.get("errors", [{"message": result.get("error")}])
        }), 400
