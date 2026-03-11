"""
app/leads/routes.py
───────────────────
Lead Finder — Waterfall Email & Phone Enrichment

PURPOSE:
    Given a prospect's first name, last name, and company domain, this feature
    runs a "waterfall enrichment" — it tries multiple data providers in sequence
    and returns the first successful result. This minimises API cost while
    maximising the email/phone find rate.

CURRENT STATUS: ⚠️  MOCKED / DEMO MODE
    └── No real API calls are being made.
    └── All results are fabricated from the input data.
    └── This is intentional — the UI and flow are fully built and tested.
    └── Switch to production by replacing the search() body with the real
        waterfall implementation (see PRODUCTION PLAN below).

════════════════════════════════════════════════════════════════════════════════
PRODUCTION PLAN — What to implement when going live
════════════════════════════════════════════════════════════════════════════════

STEP 1: Add API keys to .env
─────────────────────────────
    PROSPEO_API_KEY="your-key"
    DROPCONTACT_API_KEY="your-key"
    FINDYMAIL_API_KEY="your-key"
    DATAGMA_API_KEY="your-key"

STEP 2: Add to config.py
─────────────────────────
    PROSPEO_API_KEY     = os.environ.get('PROSPEO_API_KEY')
    DROPCONTACT_API_KEY = os.environ.get('DROPCONTACT_API_KEY')
    FINDYMAIL_API_KEY   = os.environ.get('FINDYMAIL_API_KEY')
    DATAGMA_API_KEY     = os.environ.get('DATAGMA_API_KEY')

STEP 3: Implement each provider
─────────────────────────────────
    API Documentation:
    • Prospeo:     https://prospeo.io/api  (Email Finder endpoint)
    • Dropcontact: https://dropcontact.com/documentation
    • Findymail:   https://app.findymail.com/docs
    • Datagma:     https://datagma.com/documentation

    Example (Prospeo):
        headers = {"X-KEY": current_app.config['PROSPEO_API_KEY']}
        payload = {"first_name": first_name, "last_name": last_name, "domain": domain}
        r = requests.post("https://api.prospeo.io/email-finder", json=payload, headers=headers)
        if r.ok and r.json().get('response', {}).get('email'):
            return r.json()['response']['email']

STEP 4: Add caching (Redis) to avoid duplicate API calls
──────────────────────────────────────────────────────────
    Cache key: f"lead:{first_name}:{last_name}:{domain}"
    TTL: 7 days (repeat searches on same person use cache, not API credits)

STEP 5: Add UsageLog entry per search
───────────────────────────────────────
    log = UsageLog(user_id=current_user.id, action='lead_search',
                   topic=f"{first_name} {last_name} @ {domain}")
    db.session.add(log)
    db.session.commit()

STEP 6: Track credits per user (Free plan = 10/month, Pro = unlimited)
────────────────────────────────────────────────────────────────────────
    Use the require_plan() decorator from app.utils for Pro-only access,
    or implement a per-user credit counter in the User model.

WATERFALL ORDER (try in this exact order — cheapest/most accurate first):
    1. Prospeo     (~$0.01/credit, 85% find rate)
    2. Dropcontact (~$0.02/credit, good for Europe, GDPR compliant)
    3. Findymail   (~$0.02/credit, very high accuracy)
    4. Datagma     (~$0.03/credit, also returns phone + LinkedIn URL)

════════════════════════════════════════════════════════════════════════════════
"""

from flask import render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from app.extensions import limiter, db
from app.models import UsageLog
from . import leads_bp


@leads_bp.route('/')
@login_required
def index():
    """Render the Lead Finder page."""
    return render_template('leads/index.html')


@leads_bp.route('/search', methods=['POST'])
@login_required
@limiter.limit("30 per hour")   # Throttle: each search will eventually cost API credits
def search():
    """
    Run waterfall enrichment for a given prospect.

    Request body (JSON):
        first_name (str): Required
        last_name  (str): Optional but improves accuracy
        domain     (str): Required — company domain, e.g. "stripe.com"

    Returns:
        JSON with success=True and enriched contact data, or success=False and error message.

    ⚠️  CURRENTLY RETURNING MOCKED DATA.
        Replace the body of this function with the real waterfall implementation
        described in the PRODUCTION PLAN above when going live.
    """
    data = request.get_json()
    first_name = (data.get('first_name') or '').strip()
    last_name  = (data.get('last_name') or '').strip()
    domain     = (data.get('domain') or '').strip().lower()

    if not first_name or not domain:
        return jsonify({"success": False, "error": "First name and domain are required"}), 400

    # ── PRODUCTION: Replace this entire block with real waterfall API calls ──────
    # ── See PRODUCTION PLAN at the top of this file for full implementation ──────
    # ── MOCK DATA BELOW — for UI development and demo purposes only ──────────────

    email = (
        f"{first_name.lower()}.{last_name.lower()}@{domain}"
        if last_name
        else f"{first_name.lower()}@{domain}"
    )

    # Simulate waterfall source results
    # In production: each of these will be a real API call, stopping at first success
    mock_sources = [
        {
            "name": "Prospeo",
            "status": "Found",
            "result": email,
            "note": "MOCK — will be a real Prospeo API call in production"
        },
        {
            "name": "Dropcontact",
            "status": "Not found",
            "result": None,
            "note": "MOCK — waterfall stopped at Prospeo"
        },
        {
            "name": "Findymail",
            "status": "Not found",
            "result": None,
            "note": "MOCK — waterfall stopped at Prospeo"
        },
        {
            "name": "Datagma",
            "status": "Not found",
            "result": None,
            "note": "MOCK — waterfall stopped at Prospeo"
        }
    ]

    # ── PRODUCTION: Also log this search to UsageLog ──────────────────────────────
    # Uncomment when real API is wired up:
    # try:
    #     log = UsageLog(
    #         user_id=current_user.id,
    #         action='lead_search',
    #         topic=f"{first_name} {last_name} @ {domain}"
    #     )
    #     db.session.add(log)
    #     db.session.commit()
    # except Exception as e:
    #     current_app.logger.error("Failed to log lead search: %s", e)

    return jsonify({
        "success": True,
        "data": {
            "name": f"{first_name} {last_name}".strip(),
            "email": email,
            "phone": "+1 555 123 4567",      # MOCK — Datagma will return real phone in prod
            "position": "Growth Manager",     # MOCK — LinkedIn enrichment API will return real title
            "sources": mock_sources
        },
        "_mock": True,                        # Flag to identify mocked responses in logs/tests
        "_production_note": (
            "This response is mocked. See app/leads/routes.py PRODUCTION PLAN "
            "for full implementation instructions."
        )
    })
