"""
Execution Script: Publish Post to LinkedIn
Directive: directives/publish_linkedin.md

This script is deterministic and testable. It handles:
- Token validation
- Idempotency checks
- LinkedIn UGC Posts API call
- Error classification and response
"""

import os
import json
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ───
LINKEDIN_API_BASE = "https://api.linkedin.com/v2"
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = [1, 3, 10]

# ─── In-memory idempotency store (replace with DB in production) ───
_used_keys = set()


def validate_token(access_token: str, expires_at: datetime = None) -> dict:
    """Check if the LinkedIn token is valid and not expired."""
    if not access_token:
        return {"valid": False, "code": "TOKEN_MISSING", "message": "No access token provided"}
    
    if expires_at and datetime.now(timezone.utc) >= expires_at:
        return {"valid": False, "code": "TOKEN_EXPIRED", "message": "LinkedIn token has expired. Please re-authenticate."}
    
    return {"valid": True}


def check_idempotency(key: str) -> bool:
    """Check if this idempotency key has been used. Returns True if duplicate."""
    return key in _used_keys


def build_ugc_payload(person_urn: str, post_text: str) -> dict:
    """Build the LinkedIn UGC Post API payload."""
    return {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": post_text
                },
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }


def publish_to_linkedin(post_text: str, access_token: str, person_urn: str,
                         idempotency_key: str, expires_at: datetime = None) -> dict:
    """
    Main execution function. Publishes a post to LinkedIn.
    
    Returns a standardized response dict.
    """
    # Step 1: Validate token
    token_check = validate_token(access_token, expires_at)
    if not token_check["valid"]:
        return {"success": False, "error": token_check["message"], "code": token_check["code"]}
    
    # Step 2: Check idempotency
    if check_idempotency(idempotency_key):
        return {"success": False, "error": "This post has already been published", "code": "DUPLICATE_POST"}
    
    # Step 3: Build payload
    payload = build_ugc_payload(person_urn, post_text)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0"
    }
    
    # Step 4: Send request with retries
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                f"{LINKEDIN_API_BASE}/ugcPosts",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 201:
                # Success
                result = response.json()
                post_urn = result.get("id", "unknown")
                _used_keys.add(idempotency_key)
                
                return {
                    "success": True,
                    "data": {
                        "linkedin_post_urn": post_urn,
                        "published_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            
            elif response.status_code == 429:
                return {"success": False, "error": "LinkedIn rate limit reached", "code": "LINKEDIN_RATE_LIMIT"}
            
            elif response.status_code == 422:
                return {"success": False, "error": "Content policy violation or invalid content", "code": "CONTENT_BLOCKED"}
            
            elif response.status_code == 401:
                return {"success": False, "error": "LinkedIn token expired or invalid", "code": "TOKEN_EXPIRED"}
            
            else:
                last_error = f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.Timeout:
            last_error = "Request timed out"
        except requests.exceptions.ConnectionError:
            last_error = "Network connection error"
        except Exception as e:
            last_error = str(e)
    
    return {"success": False, "error": f"Failed after {MAX_RETRIES} retries: {last_error}", "code": "NETWORK_ERROR"}


# ─── CLI Usage (for testing) ───
if __name__ == "__main__":
    print("This script should be called from the app, not directly.")
    print("Usage: publish_to_linkedin(post_text, access_token, person_urn, idempotency_key)")
