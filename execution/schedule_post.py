"""
Execution Script: Schedule a Post for Future Publishing
Directive: directives/schedule_post.md

This script is deterministic and testable. It handles:
- Draft ownership validation
- Plan limit enforcement
- Token expiry pre-check
- Job creation for APScheduler
"""

import os
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ───
FREE_PLAN_MAX_SCHEDULED = 3
PRO_PLAN_MAX_SCHEDULED = 50
MIN_SCHEDULE_BUFFER_MINUTES = 5


def validate_schedule_inputs(draft, user, scheduled_at: datetime, 
                              active_scheduled_count: int,
                              token_expires_at: datetime = None) -> dict:
    """
    Validate all preconditions before scheduling.
    Returns success or list of errors.
    """
    errors = []
    now = datetime.now(timezone.utc)
    
    # Check draft exists
    if not draft:
        errors.append({"code": "DRAFT_NOT_FOUND", "message": "Draft not found"})
        return {"valid": False, "errors": errors}
    
    # Check ownership
    if draft.user_id != user.id:
        errors.append({"code": "UNAUTHORIZED", "message": "You don't own this draft"})
        return {"valid": False, "errors": errors}
    
    # Check time is in the future with buffer
    min_time = now + timedelta(minutes=MIN_SCHEDULE_BUFFER_MINUTES)
    if scheduled_at <= min_time:
        errors.append({
            "code": "INVALID_TIME",
            "message": f"Scheduled time must be at least {MIN_SCHEDULE_BUFFER_MINUTES} minutes in the future",
            "server_time": now.isoformat()
        })
    
    # Check plan limits
    max_scheduled = PRO_PLAN_MAX_SCHEDULED if user.plan == 'pro' else FREE_PLAN_MAX_SCHEDULED
    if active_scheduled_count >= max_scheduled:
        errors.append({
            "code": "PLAN_LIMIT",
            "message": f"Your {user.plan} plan allows {max_scheduled} scheduled posts. Upgrade to Pro for more.",
            "current": active_scheduled_count,
            "limit": max_scheduled
        })
    
    # Check token won't expire before scheduled time
    if token_expires_at and scheduled_at >= token_expires_at:
        errors.append({
            "code": "TOKEN_EXPIRY_RISK",
            "message": "Your LinkedIn token will expire before the scheduled time. Please re-authenticate first.",
            "token_expires": token_expires_at.isoformat(),
            "scheduled_for": scheduled_at.isoformat()
        })
    
    if errors:
        return {"valid": False, "errors": errors}
    return {"valid": True}


def create_schedule(draft, scheduled_at: datetime, user_timezone: str = "UTC") -> dict:
    """
    Create the scheduling record. In production this would update the DB
    and register an APScheduler job.
    
    Returns standardized response.
    """
    import uuid
    job_id = f"job_{draft.id}_{uuid.uuid4().hex[:8]}"
    
    return {
        "success": True,
        "data": {
            "draft_id": draft.id,
            "scheduled_at": scheduled_at.isoformat(),
            "user_timezone": user_timezone,
            "job_id": job_id,
            "status": "scheduled"
        }
    }


# ─── CLI Usage (for testing) ───
if __name__ == "__main__":
    print("This script should be called from the app, not directly.")
    print("Usage: validate_schedule_inputs(draft, user, scheduled_at, count) then create_schedule(draft, scheduled_at)")
