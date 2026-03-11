import os
import stripe
from flask import Blueprint, jsonify, request, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models import User
from datetime import datetime, timedelta

payments_bp = Blueprint('payments', __name__)

@payments_bp.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Creates a Stripe checkout session for the Pro plan."""
    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
    
    if not stripe.api_key:
        return jsonify(error="Stripe is not configured on the server"), 500

    domain_url = request.url_root.strip('/')
    
    try:
        # Create new Checkout Session for the subscription
        checkout_session = stripe.checkout.Session.create(
            client_reference_id=current_user.id,
            success_url=domain_url + url_for('payments.success') + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=domain_url + url_for('payments.cancelled'),
            payment_method_types=['card'],
            mode='subscription',
            # Replace with the actual price ID from your Stripe Dashboard
            line_items=[{
                'price': current_app.config.get('STRIPE_PRO_PRICE_ID', 'price_fake_12345'),
                'quantity': 1,
            }],
            customer_email=current_user.email
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return jsonify(error=str(e)), 403


@payments_bp.route('/success')
@login_required
def success():
    # Once they come back from Stripe, we can optimistically upgrade them here,
    # OR we just rely on the webhook. Webhook is safer.
    # We will optimistically set them to Pro for immediate feedback.
    if current_user.plan != 'pro':
        current_user.plan = 'pro'
        # Optimistically grant 30 days, webhook will fix this up with actual date
        current_user.plan_expires_at = datetime.utcnow() + timedelta(days=30)
        db.session.commit()
    
    return """
    <html>
        <body>
            <h1>Payment Successful!</h1>
            <p>You are now on the Pro Plan. Redirecting to your dashboard...</p>
            <script>setTimeout(function(){ window.location.href='/'; }, 3000);</script>
        </body>
    </html>
    """


@payments_bp.route('/cancelled')
@login_required
def cancelled():
    return redirect(url_for('index'))


@payments_bp.route('/webhook', methods=['POST'])
def webhook():
    """Stripe webhook handler to provision subscriptions."""
    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
    endpoint_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
    
    payload = request.data
    sig_header = request.headers.get('STRIPE_SIGNATURE')

    if not endpoint_secret:
        # 🔴 ZERO-TRUST NETWORKING: If there's no webhook secret, block it.
        # Dev-mode bypasses introduce hidden production vulnerabilities.
        current_app.logger.error("STRIPE_WEBHOOK_SECRET is not configured. Rejecting request.")
        return jsonify(error="Webhook secret not configured"), 500

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return 'Invalid signature', 400

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session(session)
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        handle_subscription_deleted(subscription)

    return '', 200


def handle_checkout_session(session):
    client_reference_id = session.get('client_reference_id')
    customer_id = session.get('customer')
    
    if client_reference_id:
        user = User.query.get(int(client_reference_id))
        if user:
            user.stripe_customer_id = customer_id
            user.plan = 'pro'
            # Give exactly 31 days to be safe
            user.plan_expires_at = datetime.utcnow() + timedelta(days=31)
            db.session.commit()

def handle_subscription_deleted(subscription):
    customer_id = subscription.get('customer')
    if customer_id:
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            user.plan = 'free'
            user.plan_expires_at = None
            db.session.commit()
