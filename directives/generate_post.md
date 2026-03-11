# Directive: Generate LinkedIn Post

## Objective
Generate a high-quality LinkedIn post using AI (Google Gemini) based on a user-provided topic and tone.

## Inputs
| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `topic` | string | Yes | The subject of the post |
| `tone` | string | No | professional, casual, storytelling, provocative (default: professional) |
| `max_length` | int | No | Maximum character count (default: 1500) |
| `include_hook` | bool | No | Whether to add an attention-grabbing first line (default: true) |
| `include_cta` | bool | No | Whether to add a call-to-action at the end (default: true) |

## Execution Script
`execution/generate_post.py`

## Process
1. Validate inputs (topic not empty, tone is valid, length within bounds).
2. Build the prompt using the structured format: Hook → Value → CTA.
3. Call the Gemini API with the prompt.
4. Validate output (check character count, ensure no markdown artifacts).
5. Return the generated post text.

## Output
```json
{
  "success": true,
  "data": {
    "post_text": "...",
    "char_count": 1234,
    "tone": "professional",
    "hook_line": "..."
  }
}
```

## Error Cases
| Error | Code | Action |
|-------|------|--------|
| Empty topic | `EMPTY_TOPIC` | Return error, prompt user |
| API rate limit | `GEMINI_RATE_LIMIT` | Wait 60s, retry once |
| API key invalid | `GEMINI_AUTH_FAIL` | Log error, notify admin |
| Response too long | `CONTENT_TOO_LONG` | Truncate at last sentence before limit |
