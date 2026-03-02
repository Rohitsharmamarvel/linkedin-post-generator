import os
import time
import logging
from logging.handlers import RotatingFileHandler
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, redirect
from flask_compress import Compress
from urllib.parse import urlencode

# Load environment variables
load_dotenv()

app = Flask(__name__)

# ============================================================
# PERFORMANCE: Gzip compression (60-80% smaller responses)
# ============================================================
Compress(app)

# ============================================================
# PERFORMANCE: Template caching in production
# ============================================================
app.config['TEMPLATES_AUTO_RELOAD'] = False

# ============================================================
# PERFORMANCE: Connection pooling via requests.Session
# ============================================================
http_session = requests.Session()
http_session.headers.update({
    "Content-Type": "application/json",
})
# Keep-alive with connection pooling
adapter = requests.adapters.HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=requests.adapters.Retry(total=2, backoff_factor=0.3)
)
http_session.mount("https://", adapter)
http_session.mount("http://", adapter)

# ============================================================
# PERFORMANCE: Thread pool for parallel Gemini calls
# ============================================================
executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="gemini")

# ============================================================
# LOGGING SETUP
# ============================================================
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(funcName)-20s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# File handler (rotating, max 5MB, keep 3 backups)
file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "app.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8"
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

logger = logging.getLogger("linkedin_bot")
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("=" * 60)
logger.info("LinkedIn Bot starting up...")
logger.info("=" * 60)

# ============================================================
# RATE LIMITING (simple in-memory)
# ============================================================
rate_limit_store = defaultdict(list)
MAX_REQUESTS_PER_MINUTE = 10


def check_rate_limit(endpoint):
    """Returns True if rate limit exceeded."""
    now = time.time()
    key = f"{request.remote_addr}:{endpoint}"
    # Clean old entries
    rate_limit_store[key] = [t for t in rate_limit_store[key] if now - t < 60]
    if len(rate_limit_store[key]) >= MAX_REQUESTS_PER_MINUTE:
        logger.warning(f"Rate limit exceeded for {key}")
        return True
    rate_limit_store[key].append(now)
    return False


# ============================================================
# CONFIG (from .env)
# ============================================================
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_REDIRECT_URI = "http://localhost:5001/callback"
MAX_POST_LENGTH = 3000  # LinkedIn's character limit

logger.info(f"LinkedIn Client ID loaded: {'✅' if LINKEDIN_CLIENT_ID else '❌ MISSING'}")
logger.info(f"LinkedIn Access Token loaded: {'✅' if os.getenv('LINKEDIN_ACCESS_TOKEN') else '❌ MISSING'}")
logger.info(f"Gemini API Key loaded: {'✅' if os.getenv('GEMINI_API_KEY') else '❌ MISSING'}")


# ============================================================
# GEMINI SETUP (singleton — initialized once, reused forever)
# ============================================================
_gemini_model_cache = None


def get_gemini_model():
    global _gemini_model_cache
    if _gemini_model_cache is not None:
        return _gemini_model_cache
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key or gemini_key == "your_gemini_api_key_here":
        logger.error("Gemini API key is missing or placeholder")
        return None
    genai.configure(api_key=gemini_key)
    _gemini_model_cache = genai.GenerativeModel('gemini-2.5-flash')
    logger.info("✅ Gemini model initialized (cached for reuse)")
    return _gemini_model_cache


# ============================================================
# PROMPT TEMPLATE
# ============================================================
PROMPT_TEMPLATE = """You are a Software Engineer with 4-6 years of experience. You write highly engaging, human-sounding LinkedIn posts that reflect a senior mindset.

Write {count} different variations of a LinkedIn post about this idea: "{topic}".

STRICT RULES TO MATCH MY STYLE:
1. DO NOT use cringe AI words like "delve", "elevate", "in today's rapidly evolving digital landscape", "testament", "tapestry", "buckle up", "unleash", or "game-changer".
2. Keep sentences short, impactful, and conversational.
3. Use emojis intentionally but sparingly (e.g., 👇, ✅, ❌, ⚖️, 🧠, 👉, ❓) to highlight key points, trade-offs, or bad vs. good practices.
4. Structure the post with plenty of whitespace. Leave empty lines between almost every sentence.
5. Use bulleted lists (with •) for readability when making points.
6. The tone should focus on trade-offs, system design realities, real-world failures, and practical advice rather than textbook theory.
7. Include 5-7 relevant hashtags at the very bottom (e.g., #SoftwareEngineering #BackendDeveloper #SystemDesign).
8. Separate each variation with a distinct divider EXACTLY like this: "---POST---" so I can parse them easily. Do not include any other markdown formatting around the divider.

Do not include any intro or outro text. Just output the {count} posts separated by "---POST---".
"""

# Single-post prompt for parallel generation
SINGLE_PROMPT_TEMPLATE = """You are a Software Engineer with 4-6 years of experience. You write highly engaging, human-sounding LinkedIn posts that reflect a senior mindset.

Write ONE LinkedIn post about this idea: "{topic}".

STRICT RULES TO MATCH MY STYLE:
1. DO NOT use cringe AI words like "delve", "elevate", "in today's rapidly evolving digital landscape", "testament", "tapestry", "buckle up", "unleash", or "game-changer".
2. Keep sentences short, impactful, and conversational.
3. Use emojis intentionally but sparingly (e.g., 👇, ✅, ❌, ⚖️, 🧠, 👉, ❓) to highlight key points, trade-offs, or bad vs. good practices.
4. Structure the post with plenty of whitespace. Leave empty lines between almost every sentence.
5. Use bulleted lists (with •) for readability when making points.
6. The tone should focus on trade-offs, system design realities, real-world failures, and practical advice rather than textbook theory.
7. Include 5-7 relevant hashtags at the very bottom (e.g., #SoftwareEngineering #BackendDeveloper #SystemDesign).

Do not include any intro or outro text. Just output the single post.
"""


def _generate_single_post(model, topic, variation_index):
    """Generate a single post in a thread. Returns (index, post_text)."""
    prompt = SINGLE_PROMPT_TEMPLATE.format(topic=topic)
    try:
        logger.debug(f"Thread {variation_index}: calling Gemini...")
        start = time.time()
        response = model.generate_content(prompt)
        elapsed = round(time.time() - start, 2)
        logger.debug(f"Thread {variation_index}: Gemini responded in {elapsed}s")
        return (variation_index, response.text.strip())
    except Exception as e:
        logger.error(f"Thread {variation_index} failed: {e}")
        return (variation_index, None)


# ============================================================
# HELPER: Post to LinkedIn
# ============================================================
def _post_to_linkedin_api(text):
    """Internal helper to post text to LinkedIn. Returns (success, message, status_code)."""
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    person_urn = os.getenv("LINKEDIN_PERSON_URN")

    if not access_token or not person_urn or access_token == "your_linkedin_access_token_here":
        logger.error("LinkedIn credentials missing in .env")
        return False, "LinkedIn credentials missing. Connect your account first at /connect-linkedin", 500

    logger.info(f"Posting to LinkedIn (text length: {len(text)} chars)")
    logger.debug(f"Using Person URN: {person_urn}")

    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json"
    }
    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }

    try:
        response = http_session.post(url, headers=headers, json=payload, timeout=30)
        logger.info(f"LinkedIn API response: {response.status_code}")
        logger.debug(f"LinkedIn API response body: {response.text[:500]}")

        if response.status_code == 201:
            logger.info("✅ Post published successfully!")
            return True, "Posted to LinkedIn!", 201
        else:
            logger.error(f"LinkedIn API error: {response.status_code} - {response.text[:300]}")
            return False, f"LinkedIn API error ({response.status_code}): {response.text}", response.status_code
    except requests.exceptions.Timeout:
        logger.error("LinkedIn API request timed out")
        return False, "LinkedIn API request timed out. Try again.", 504
    except Exception as e:
        logger.exception(f"LinkedIn API request failed: {e}")
        return False, f"Request failed: {str(e)}", 500


# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def index():
    logger.debug("Serving index page")
    # Check LinkedIn connection status
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    is_connected = bool(access_token and access_token != "your_linkedin_access_token_here")
    return render_template("index.html", linkedin_connected=is_connected)


@app.route("/status")
def status():
    """API health check + connection status."""
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    is_connected = bool(access_token and access_token != "your_linkedin_access_token_here")
    gemini_ok = bool(os.getenv("GEMINI_API_KEY"))
    logger.debug(f"Status check — LinkedIn: {is_connected}, Gemini: {gemini_ok}")
    return jsonify({
        "linkedin_connected": is_connected,
        "gemini_configured": gemini_ok,
        "server": "running"
    })


@app.route("/generate", methods=["POST"])
def generate():
    if check_rate_limit("generate"):
        return jsonify({"error": "Too many requests. Please wait a minute."}), 429

    data = request.get_json()
    topic = data.get("topic", "").strip()
    count = data.get("count", 1)

    logger.info(f"📝 Generate request — topic: '{topic[:80]}', count: {count}")

    if not topic:
        logger.warning("Generate request with empty topic")
        return jsonify({"error": "Topic is required."}), 400
    if not isinstance(count, int) or count < 1 or count > 5:
        logger.warning(f"Invalid count: {count}")
        return jsonify({"error": "Count must be between 1 and 5."}), 400

    model = get_gemini_model()
    if not model:
        return jsonify({"error": "Gemini API key is missing or invalid. Check your .env file."}), 500

    start_time = time.time()

    if count == 1:
        # Single post — straightforward call
        prompt = PROMPT_TEMPLATE.format(count=1, topic=topic)
        try:
            logger.info("🤖 Calling Gemini API (single post)...")
            response = model.generate_content(prompt)
            elapsed = round(time.time() - start_time, 2)
            logger.info(f"✅ Gemini responded in {elapsed}s")
            posts = [response.text.strip()]
            return jsonify({"posts": posts, "elapsed": elapsed})
        except Exception as e:
            logger.exception(f"Gemini generation failed: {e}")
            return jsonify({"error": f"Generation failed: {str(e)}"}), 500
    else:
        # Multiple posts — PARALLEL generation via ThreadPoolExecutor
        logger.info(f"🤖 Firing {count} parallel Gemini calls...")
        futures = []
        for i in range(count):
            future = executor.submit(_generate_single_post, model, topic, i)
            futures.append(future)

        posts = [None] * count
        for future in as_completed(futures):
            idx, text = future.result()
            if text:
                posts[idx] = text

        # Filter out any failed generations
        posts = [p for p in posts if p is not None]
        elapsed = round(time.time() - start_time, 2)
        logger.info(f"✅ {len(posts)} posts generated in {elapsed}s (parallel)")

        if not posts:
            return jsonify({"error": "All generation attempts failed. Try again."}), 500

        return jsonify({"posts": posts, "elapsed": elapsed})


@app.route("/post-to-linkedin", methods=["POST"])
def post_to_linkedin():
    """Post AI-generated content to LinkedIn."""
    if check_rate_limit("post-to-linkedin"):
        return jsonify({"error": "Too many requests. Please wait a minute."}), 429

    data = request.get_json()
    text = data.get("text", "").strip()

    logger.info(f"🚀 Post to LinkedIn request (from AI generate, {len(text)} chars)")

    if not text:
        logger.warning("Empty post text received")
        return jsonify({"error": "Post text is required."}), 400

    if len(text) > MAX_POST_LENGTH:
        logger.warning(f"Post too long: {len(text)} chars (max {MAX_POST_LENGTH})")
        return jsonify({"error": f"Post is too long ({len(text)} chars). LinkedIn limit is {MAX_POST_LENGTH}."}), 400

    success, message, status_code = _post_to_linkedin_api(text)
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"error": message}), status_code


@app.route("/direct-post", methods=["POST"])
def direct_post():
    """Post user-written content directly to LinkedIn (no Gemini call)."""
    if check_rate_limit("direct-post"):
        return jsonify({"error": "Too many requests. Please wait a minute."}), 429

    data = request.get_json()
    text = data.get("text", "").strip()

    logger.info(f"✍️ Direct post request ({len(text)} chars)")

    if not text:
        logger.warning("Empty direct post text")
        return jsonify({"error": "Post text is required."}), 400

    if len(text) > MAX_POST_LENGTH:
        logger.warning(f"Direct post too long: {len(text)} chars")
        return jsonify({"error": f"Post is too long ({len(text)} chars). LinkedIn limit is {MAX_POST_LENGTH}."}), 400

    success, message, status_code = _post_to_linkedin_api(text)
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"error": message}), status_code


# ============================================================
# LINKEDIN OAUTH ROUTES
# ============================================================
@app.route("/connect-linkedin")
def connect_linkedin():
    """Step 1: Redirect user to LinkedIn for authorization."""
    logger.info("🔗 Starting LinkedIn OAuth flow")

    if not LINKEDIN_CLIENT_ID:
        logger.error("LinkedIn Client ID not configured")
        return "<h2>❌ LinkedIn Client ID not configured in .env</h2>", 500

    params = urlencode({
        "response_type": "code",
        "client_id": LINKEDIN_CLIENT_ID,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "scope": "openid profile email w_member_social"
    })
    auth_url = f"https://www.linkedin.com/oauth/v2/authorization?{params}"
    logger.info(f"Redirecting to LinkedIn OAuth (redirect_uri: {LINKEDIN_REDIRECT_URI})")
    return redirect(auth_url)


@app.route("/callback")
def callback():
    """Step 2: Exchange auth code for access token and fetch person URN."""
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        logger.error(f"OAuth error: {error} — {request.args.get('error_description', '')}")
        return f"<h2>❌ Authorization failed</h2><p>{request.args.get('error_description', error)}</p>"

    if not code:
        logger.error("No authorization code received in callback")
        return "<h2>❌ No authorization code received.</h2>"

    logger.info("📥 Received OAuth authorization code, exchanging for token...")

    # Exchange code for access token
    token_response = http_session.post("https://www.linkedin.com/oauth/v2/accessToken", data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "client_id": LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET
    }, timeout=30)

    if token_response.status_code != 200:
        logger.error(f"Token exchange failed: {token_response.status_code} — {token_response.text[:300]}")
        return f"<h2>❌ Token exchange failed</h2><pre>{token_response.text}</pre>"

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    expires_in = token_data.get("expires_in", 0)
    expires_days = expires_in // 86400
    logger.info(f"✅ Access token received (expires in {expires_days} days)")

    # Fetch person URN using userinfo endpoint
    logger.info("Fetching user info from LinkedIn...")
    userinfo_response = http_session.get("https://api.linkedin.com/v2/userinfo", headers={
        "Authorization": f"Bearer {access_token}"
    }, timeout=30)

    person_urn = ""
    name = ""
    if userinfo_response.status_code == 200:
        userinfo = userinfo_response.json()
        sub = userinfo.get("sub", "")
        name = userinfo.get("name", "")
        person_urn = f"urn:li:person:{sub}"
        logger.info(f"✅ User info: {name} ({person_urn})")
    else:
        logger.error(f"Failed to fetch user info: {userinfo_response.status_code}")

    # Save to .env file
    logger.info("💾 Saving credentials to .env...")
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    env_lines = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            env_lines = f.readlines()

    new_lines = []
    token_written = False
    urn_written = False
    for line in env_lines:
        if line.startswith("LINKEDIN_ACCESS_TOKEN"):
            new_lines.append(f'LINKEDIN_ACCESS_TOKEN="{access_token}"\n')
            token_written = True
        elif line.startswith("LINKEDIN_PERSON_URN"):
            new_lines.append(f'LINKEDIN_PERSON_URN="{person_urn}"\n')
            urn_written = True
        else:
            new_lines.append(line)

    if not token_written:
        new_lines.append(f'LINKEDIN_ACCESS_TOKEN="{access_token}"\n')
    if not urn_written:
        new_lines.append(f'LINKEDIN_PERSON_URN="{person_urn}"\n')

    with open(env_path, "w") as f:
        f.writelines(new_lines)

    # Reload environment
    load_dotenv(override=True)
    logger.info("✅ OAuth flow complete — credentials saved and loaded")

    return f"""
    <html>
    <head><style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 80px auto; text-align: center; background: #f4f4f4; }}
        .card {{ background: white; padding: 40px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        h2 {{ color: #0a66c2; }}
        .info {{ background: #f0f7ff; padding: 12px 20px; border-radius: 8px; margin: 12px 0; text-align: left; font-size: 14px; word-break: break-all; }}
        a {{ display: inline-block; margin-top: 20px; background: #0a66c2; color: white; padding: 12px 32px; border-radius: 24px; text-decoration: none; font-weight: 600; }}
        a:hover {{ background: #004182; }}
    </style></head>
    <body><div class="card">
        <h2>✅ LinkedIn Connected!</h2>
        <p>Welcome, <strong>{name}</strong>!</p>
        <div class="info">🔑 <strong>Person URN:</strong> {person_urn}</div>
        <div class="info">⏰ <strong>Token expires in:</strong> {expires_days} days</div>
        <div class="info">💾 Credentials saved to <code>.env</code> automatically</div>
        <a href="/">← Back to Post Generator</a>
    </div></body>
    </html>
    """

# Warm up the Gemini model at startup
get_gemini_model()

if __name__ == "__main__":
    logger.info(f"🚀 Server starting on http://localhost:5001")
    app.run(debug=True, port=5001, threaded=True)
