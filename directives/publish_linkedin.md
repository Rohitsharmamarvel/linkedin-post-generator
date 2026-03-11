# Directive: Publish to LinkedIn

## Objective
Publish a finalized post to LinkedIn using the user's stored access token via the LinkedIn API.

## Inputs
| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `post_text` | string | Yes | The content to publish |
| `access_token` | string | Yes | LinkedIn OAuth access token (from DB, encrypted) |
| `person_urn` | string | Yes | LinkedIn person URN (e.g., `urn:li:person:abc123`) |
| `idempotency_key` | string | Yes | Unique key per post to prevent duplicates |

## Execution Script
`execution/publish_linkedin.py`

## Process
1. Validate token is not expired (check `expires_at` from DB).
2. Check idempotency — has this key been used before?
3. Build the LinkedIn UGC Post API payload.
4. Send POST request to `https://api.linkedin.com/v2/ugcPosts`.
5. On success: store the LinkedIn post URN, mark draft as `published`.
6. On failure: log error, mark draft as `failed`, store error message.

## Output
```json
{
  "success": true,
  "data": {
    "linkedin_post_urn": "urn:li:share:123456789",
    "published_at": "2026-03-04T12:00:00Z"
  }
}
```

## Error Cases
| Error | Code | Action |
|-------|------|--------|
| Token expired | `TOKEN_EXPIRED` | Show re-auth banner to user |
| Rate limited | `LINKEDIN_RATE_LIMIT` | Queue for retry in 1 hour |
| Duplicate post | `DUPLICATE_POST` | Skip, return existing URN |
| Network error | `NETWORK_ERROR` | Retry up to 3 times with backoff |
| Content policy violation | `CONTENT_BLOCKED` | Notify user, do NOT retry |
