import logging
from apscheduler.schedulers.background import BackgroundScheduler
from tzlocal import get_localzone
from app.models import Draft
from app.extensions import db
from datetime import datetime

logger = logging.getLogger('scheduler')

def start_scheduler(app):
    """Start APScheduler in the background to handle scheduled posts."""
    
    # We use BackgroundScheduler for local dev. In Prod, this should be a separate worker.
    scheduler = BackgroundScheduler(timezone=get_localzone())
    
    def process_scheduled_posts():
        with app.app_context():
            now = datetime.utcnow()
            # Fetch posts scheduled before NOW that are still in 'scheduled' status
            due_posts = Draft.query.filter(
                Draft.status == 'scheduled',
                Draft.scheduled_at <= now,
                Draft.is_deleted == False
            ).all()
            
            if due_posts:
                logger.info(f"Checking schedule... Found {len(due_posts)} posts ready to publish.")
            
            from app.models import LinkedInToken, UsageLog
            from execution.publish_linkedin import publish_to_linkedin
            
            for post in due_posts:
                try:
                    logger.info(f"Publishing Post ID {post.id} for User {post.user_id}")
                    
                    token_record = LinkedInToken.query.filter_by(user_id=post.user_id).first()
                    if not token_record or not token_record.token:
                        logger.error(f"  Error: No LinkedIn token found for user {post.user_id}. Reverting to draft.")
                        post.status = 'draft'
                        db.session.commit()
                        continue
                        
                    idem_key = f"draft_{post.id}_{int(post.scheduled_at.timestamp())}"
                    
                    result = publish_to_linkedin(
                        post_text=post.content,
                        access_token=token_record.token,
                        person_urn=token_record.person_urn,
                        idempotency_key=idem_key,
                        expires_at=token_record.expires_at
                    )
                    
                    if result['success']:
                        logger.info(f"  Success! Post ID {post.id} marked as published.")
                        post.status = 'published'
                        post.published_at = now
                        post.linkedin_post_urn = result['data']['linkedin_post_urn']
                        
                        # Log the publish action
                        db.session.add(UsageLog(
                            user_id=post.user_id,
                            action='publish',
                            char_count=post.char_count
                        ))
                    else:
                        logger.error(f"  Failed: {result['error']} ({result.get('code')})")
                        post.status = 'draft'
                        post.publish_error = result.get('error', 'Unknown Error')
                    
                    db.session.commit()
                except Exception as e:
                    logger.error(f"Failed to publish Post ID {post.id}: {e}")
                    db.session.rollback()

    # Run the check every 60 seconds
    scheduler.add_job(process_scheduled_posts, trigger='interval', seconds=60, max_instances=1)
    
    try:
        scheduler.start()
        logger.info("Background Scheduler started successfully. Listening for scheduled posts...")
    except Exception as e:
        logger.error(f"Failed to start Background Scheduler: {e}")
