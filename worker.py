import os
from datetime import datetime, timezone
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

# Load env before importing app
load_dotenv()

from app import create_app
from app.extensions import db
from app.models import Draft, LinkedInToken, UsageLog
from execution.publish_linkedin import publish_to_linkedin

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Create app context for DB access
env_name = os.environ.get('APP_ENV', 'dev')
app = create_app(env_name)

def publish_pending_posts():
    """Finds scheduled posts whose time has passed and publishes them."""
    with app.app_context():
        now = datetime.utcnow()
        
        # Find posts scheduled for now or in the past that are still 'scheduled'
        pending_posts = Draft.query.filter(
            Draft.status == 'scheduled',
            Draft.scheduled_at <= now
        ).all()
        
        if not pending_posts:
            logger.debug("No pending scheduled posts found.")
            return
            
        logger.info(f"Found {len(pending_posts)} pending posts to publish.")
        
        for draft in pending_posts:
            logger.info(f"Publishing draft {draft.id} for user {draft.user_id}...")
            
            # Get user's LinkedIn token
            token_record = LinkedInToken.query.filter_by(user_id=draft.user_id).first()
            
            if not token_record or not token_record.token:
                logger.error(f"  Error: No LinkedIn token found for user {draft.user_id}. Reverting to draft.")
                draft.status = 'draft' # Revert to draft
                db.session.commit()
                continue
                
            # Use timestamp to make the key unique if re-scheduled
            idem_key = f"draft_{draft.id}_{int(draft.scheduled_at.timestamp())}"
            
            # Execute actual publishing
            result = publish_to_linkedin(
                post_text=draft.content,
                access_token=token_record.token,
                person_urn=token_record.person_urn,
                idempotency_key=idem_key,
                expires_at=token_record.expires_at
            )
            
            if result['success']:
                logger.info(f"  Success! URN: {result['data']['linkedin_post_urn']}")
                draft.status = 'published'
                draft.published_at = datetime.utcnow()
                
                # Log the publish action
                log = UsageLog(
                    user_id=draft.user_id,
                    action='publish',
                    char_count=draft.char_count
                )
                db.session.add(log)
            else:
                logger.error(f"  Failed: {result['error']} ({result.get('code')})")
                draft.status = 'draft'
                
            db.session.commit()

if __name__ == '__main__':
    logger.info("Starting LinkedIn Content Studio Scheduler Worker...")
    scheduler = BlockingScheduler()
    
    # Run the job every minute
    scheduler.add_job(publish_pending_posts, 'interval', minutes=1)
    
    try:
        # Check immediately on startup
        publish_pending_posts()
        # Start blocking scheduler
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
