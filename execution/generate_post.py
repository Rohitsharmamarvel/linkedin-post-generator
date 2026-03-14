"""
Execution Script: Generate LinkedIn Post using Google Gemini API
Directive: directives/generate_post.md

This script is deterministic and testable. It handles:
- Input validation
- Prompt construction (Hook → Value → CTA format)
- Gemini API call (using google-genai SDK)
- Output validation and sanitization
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ───
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
DEFAULT_TONE = 'professional'
DEFAULT_MAX_LENGTH = 1500
VALID_TONES = ['professional', 'casual', 'storytelling', 'provocative', 'educational']

# ─── Prompt Templates ───
PROMPT_TEMPLATE = """You are a LinkedIn content strategist. Write a LinkedIn post about: {topic}

Tone: {tone}
Maximum length: {max_length} characters

Structure:
{hook_instruction}
- BODY: Provide 3-5 key insights or actionable points. Use short paragraphs (1-2 sentences each) with whitespace between them for readability.
{cta_instruction}

Rules:
- Write in first person and tone: {tone}
- ABSOLUTELY use 2-3 engaging emojis (e.g. ✨, ➡️, 🚀) sprinkled naturally.
- CRITICAL: Add 1 blank line between EVERY paragraph so it's readable on mobile.
- CRITICAL: Do NOT use markdown. No **bolding**, no *italics*, no `#Headers`.
- CRITICAL: Use bullet points heavily (use real emojis like 1️⃣, ➡️, ✅ instead of text bullets).
- Make the writing punchy, provocative, and highly skimmable.
- IF relevant, include exactly 3-4 professional hashtags at the very bottom.
"""

HOOK_INSTRUCTIONS = {
    'professional': "- HOOK: Start with a bold professional insight or contrarian opinion that stops the scroll.",
    'casual': "- HOOK: Start with a relatable everyday moment or observation.",
    'storytelling': "- HOOK: Start with 'I' followed by a specific moment, failure, or unexpected event.",
    'provocative': "- HOOK: Start with a controversial take or challenge a common belief.",
    'educational': "- HOOK: Start with a surprising statistic or little-known fact."
}

CTA_INSTRUCTION = "- CTA: End with a thought-provoking question or a clear call to action that invites comments."
NO_CTA_INSTRUCTION = "- Do NOT add a call-to-action at the end."


def validate_inputs(topic: str, tone: str, max_length: int) -> dict:
    """Validate all inputs before processing."""
    errors = []
    
    if not topic or not topic.strip():
        errors.append({"code": "EMPTY_TOPIC", "message": "Topic cannot be empty"})
    
    if tone not in VALID_TONES:
        errors.append({"code": "INVALID_TONE", "message": f"Tone must be one of: {', '.join(VALID_TONES)}"})
    
    if max_length < 100 or max_length > 3000:
        errors.append({"code": "INVALID_LENGTH", "message": "Max length must be between 100 and 3000"})
    
    if not GEMINI_API_KEY:
        errors.append({"code": "GEMINI_AUTH_FAIL", "message": "Gemini API key not configured"})
    
    if errors:
        return {"success": False, "errors": errors}
    return {"success": True}


def build_prompt(topic: str, tone: str, max_length: int, include_hook: bool, include_cta: bool) -> str:
    """Construct the AI prompt from the template."""
    hook_instruction = HOOK_INSTRUCTIONS.get(tone, HOOK_INSTRUCTIONS['professional']) if include_hook else ""
    cta_instruction = CTA_INSTRUCTION if include_cta else NO_CTA_INSTRUCTION
    
    return PROMPT_TEMPLATE.format(
        topic=topic.strip(),
        tone=tone,
        max_length=max_length,
        hook_instruction=hook_instruction,
        cta_instruction=cta_instruction
    )


def sanitize_output(text: str, max_length: int) -> str:
    """Clean up the AI output."""
    # Remove any markdown artifacts
    text = text.replace('**', '').replace('__', '').replace('```', '')
    
    # Truncate at last complete sentence if over limit
    if len(text) > max_length:
        truncated = text[:max_length]
        last_period = truncated.rfind('.')
        last_question = truncated.rfind('?')
        last_exclaim = truncated.rfind('!')
        cut_point = max(last_period, last_question, last_exclaim)
        if cut_point > max_length * 0.5:  # Only cut if we keep at least half
            text = truncated[:cut_point + 1]
        else:
            text = truncated.rstrip() + '...'
    
    return text.strip()


def generate_post(topic: str, tone: str = DEFAULT_TONE, max_length: int = DEFAULT_MAX_LENGTH,
                  include_hook: bool = True, include_cta: bool = True) -> dict:
    """
    Main execution function. Generates a LinkedIn post.
    
    Returns a standardized response dict.
    """
    # Step 1: Validate
    validation = validate_inputs(topic, tone, max_length)
    if not validation["success"]:
        return {"success": False, "errors": validation["errors"]}
    
    # Step 2: Build prompt
    prompt = build_prompt(topic, tone, max_length, include_hook, include_cta)
    
    # Step 3: Call Gemini API (using new google-genai SDK)
    # Try multiple models as fallback (each has separate quota)
    MODELS_TO_TRY = ["gemini-2.5-flash", "gemini-2.0-flash"]
    
    raw_text = None
    last_error = None
    
    try:
        from google import genai
        import time
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        for model_name in MODELS_TO_TRY:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                raw_text = response.text
                break  # Success, stop trying other models
            except Exception as model_err:
                last_error = str(model_err)
                # If rate limited, try next model
                if "429" in last_error or "quota" in last_error.lower():
                    continue
                else:
                    break  # Non-quota error, stop trying
        
        if not raw_text:
            error_msg = f"Gemini API returned empty response. It is possible you hit a usage limit or server error."
            if last_error:
                error_msg += f" Underlying error: {last_error}"
            return {"success": False, "error": error_msg, "code": "GEMINI_EMPTY"}
            
    except Exception as e:
        return {"success": False, "error": f"Gemini API Error: {str(e)}", "code": "GEMINI_ERROR"}
    
    # Step 4: Sanitize output
    post_text = sanitize_output(str(raw_text), max_length)
    
    # Step 5: Build response
    hook_line = post_text.split('\n')[0] if post_text else ""
    
    return {
        "success": True,
        "data": {
            "post_text": post_text,
            "char_count": len(post_text),
            "tone": tone,
            "hook_line": hook_line
        }
    }


# ─── CLI Usage (for testing) ───
if __name__ == "__main__":
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "Building a SaaS product as a solo founder"
    tone = sys.argv[2] if len(sys.argv) > 2 else "professional"
    
    result = generate_post(topic, tone)
    print(json.dumps(result, indent=2))
