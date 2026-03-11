# Directive: Schedule Post

## Objective
Schedule a draft post for auto-publishing at a specific future date/time.

## Inputs
| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `draft_id` | int | Yes | The draft to schedule |
| `user_id` | int | Yes | Owner of the draft |
| `scheduled_at` | datetime | Yes | Target publish time (UTC) |
| `user_timezone` | string | No | IANA timezone name for display |

## Execution Script
`execution/schedule_post.py`

## Process
1. Validate draft exists and belongs to user.
2. Check user plan limits (free = max 3 active scheduled posts).
3. Validate `scheduled_at` is in the future (with 5-min buffer).
4. Check LinkedIn token is valid and won't expire before scheduled time.
5. Create/update APScheduler job in DB.
6. Update draft status to `scheduled`.

## Output
```json
{
  "success": true,
  "data": {
    "draft_id": 42,
    "scheduled_at": "2026-03-05T09:00:00Z",
    "job_id": "job_42_abc123"
  }
}
```

## Error Cases
| Error | Code | Action |
|-------|------|--------|
| Past datetime | `INVALID_TIME` | Return error with current server time |
| Plan limit reached | `PLAN_LIMIT` | Show upgrade prompt |
| Token will expire | `TOKEN_EXPIRY_RISK` | Warn user, suggest re-auth first |
| Draft not found | `DRAFT_NOT_FOUND` | Return 404 |
