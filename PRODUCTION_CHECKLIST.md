# 🚀 Production Deployment Checklist
### LinkScale — Before You Go Live

> **HOW TO USE THIS FILE**
> Work through every section top to bottom before deploying.
> Each item has a ✅ checkbox. Mark it done as you go.
> Items marked **🔴 CRITICAL** will cause data loss or security breaches if skipped.
> Items marked **🟡 IMPORTANT** will cause degraded performance or missing features.
> Items marked **🟢 RECOMMENDED** improve reliability but the app will work without them.

---

## 🚦 CURRENT STATUS SUMMARY (Updated: 2026-03-14)
**✅ Completed Recently:** 
- **Production Database Migration:** Moved from expiring Render Free DB to **Neon.tech** (Free Forever). Successfully tested connection and table migrations.
- **Dynamic Configuration:** Extracted all critical URLs (Google/LinkedIn Metadata) and Gemini model lists into environment variables (`GOOGLE_METADATA_URL`, `GEMINI_MODELS`, etc.).
- **LinkedIn OIDC Fix:** Resolved "Missing jwks_uri" error by implementing full OpenID Connect metadata discovery and forcing `client_secret_post` auth method.
- **UI UX Improvements:** Implemented a global **Flash Alert** system to show success/failure messages at the top of the page.
- **Gemini SDK Upgrade:** Replaced deprecated `google-generativeai` with the modern `google-genai` SDK and updated model names to `gemini-2.5-flash`.

**⏳ PENDING BEFORE LAUNCH:**
- **Payments:** Set up real Stripe testing & webhooks for subscriptions.
- **Leads:** Replace mocked output with waterfall logic for actual lead providers (Prospeo, etc.).
- **UI Tweaks:** Setup Editor char count limit, Drafts frontend CSRF, multi-workspace drops, etc. 

---

## SECTION 1 — Environment Variables & Secrets

> **🔴 CRITICAL** — The app will not start or will be insecure without these.

- [ ] **SECRET_KEY** — Must be a long, random string. Never reuse the dev value.
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```
  Set in Render → Environment → `SECRET_KEY`

- [ ] **FERNET_KEY** — Encrypts LinkedIn tokens at rest. Generate once and never change.
  ```bash
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
  ⚠️ **WARNING:** If this key changes, ALL stored LinkedIn tokens become unreadable.
  Users will need to reconnect LinkedIn. Back this up in a password manager.

- [ ] **GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET** — Google OAuth credentials.
  - Go to [console.cloud.google.com](https://console.cloud.google.com) → APIs → Credentials
  - Add production redirect URI: `https://yourdomain.com/auth/callback`
  - Remove the dev redirect URI (`http://localhost:5000/...`) from the list

- [ ] **LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET** — From LinkedIn Developer App.
  - Update redirect URL in LinkedIn app settings to your production domain.

- [ ] **GEMINI_API_KEY** — Upgrade to Pay-As-You-Go billing on Google Cloud.
  - Free tier = 15 req/min, 1,500/day. This WILL be hit by real users.
  - Go to Google Cloud Console → Billing → Link billing account.

- [ ] **STRIPE_SECRET_KEY** — Switch from `sk_test_...` to `sk_live_...`
  - Also switch STRIPE_PUBLIC_KEY from `pk_test_...` to `pk_live_...`
  - Update STRIPE_PRO_PRICE_ID to the live price ID from Stripe dashboard.

- [ ] **STRIPE_WEBHOOK_SECRET** — Set up a real Stripe webhook for production domain.
  - Stripe Dashboard → Developers → Webhooks → Add endpoint
  - URL: `https://yourdomain.com/payments/webhook`
  - Events to listen: `checkout.session.completed`, `customer.subscription.deleted`

- [ ] **APP_ENV=prod** — Switches to `ProductionConfig` (HTTPS cookies, no debug mode).

- [ ] Remove `OAUTHLIB_INSECURE_TRANSPORT=1` — This dev-only flag allows HTTP OAuth.
  - It must NOT exist in the production environment.

---

## SECTION 2 — Database

> **🔴 CRITICAL** — SQLite on Render will be wiped on every deploy.

- [x] **Provision a managed PostgreSQL database.**
  - [x] **Migrated to Neon.tech** (Serverless Postgres). No 30-day expiration.
  - [x] **Set `DATABASE_URL`** to the Neon connection string in Render.
- [x] **Run migrations on deploy** — Added `flask db upgrade` to the start command.
  In Render: Settings → Build & Deploy → Pre-deploy command:
  ```
  flask db upgrade
  ```

- [ ] **Verify SQLite is NOT used** — Check that `DATABASE_URL` env var is set correctly.
  SQLite URI looks like `sqlite:///app.db` — if you see this in production, it's wrong.

- [ ] **Backup strategy** — Enable automated daily backups on your Postgres provider.

---

## SECTION 3 — Security Headers & HTTPS

> **🔴 CRITICAL** — Without HTTPS, session cookies are sent in plain text.

- [ ] **Force HTTPS** — Render and most PaaS providers handle this automatically with their
  custom domain setup. Verify the SSL certificate is active and `https://` redirects work.

- [ ] **Verify security headers are active** — Visit your site through
  [securityheaders.com](https://securityheaders.com) and check you get an A or B rating.
  Headers we set in `app/__init__.py`:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Content-Security-Policy`
  - `Strict-Transport-Security` (only active when `DEBUG=False`)
  - `Referrer-Policy`
  - `Permissions-Policy`

- [ ] **SESSION_COOKIE_SECURE=True** — Already set in `ProductionConfig`. Verify `APP_ENV=prod`.

- [ ] **CSRF Protection** — Flask-WTF CSRFProtect is active globally.
  Verify all forms in templates include `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.
  Forms to verify: Upgrade button in `base.html` ✅ (already fixed).

---

## SECTION 4 — Rate Limiting

> **🟡 IMPORTANT** — In-memory rate limiting does not work across multiple server instances.

- [ ] **Provision a Redis instance.**
  **Options:**
  - [Upstash Redis](https://upstash.com) — Free tier (10,000 requests/day). Best for small apps.
  - [Render Redis](https://render.com/docs/redis) — $10/month.
  - [Railway Redis](https://railway.app) — Pay-per-use.

- [ ] **Set `REDIS_URL`** environment variable.
  Format: `redis://default:<password>@<host>:<port>`
  This automatically switches Flask-Limiter from `memory://` to Redis storage.

- [ ] **Verify rate limiting is working** — Hit `/auth/google` 25 times rapidly. You should
  get a `429 Too Many Requests` response after 20 attempts.

- [ ] **Review rate limits per route** — Current limits:
  | Route | Limit |
  |---|---|
  | All routes (default) | 200/day, 50/hour |
  | `/auth/google` | 20/minute, 100/hour |
  | `/auth/callback` | 20/minute |
  | `/leads/search` | 30/hour |
  Adjust these based on real usage data after launch.

---

## SECTION 5 — Background Worker (Scheduler)

> **🟡 IMPORTANT** — Posts will not auto-publish without this.

- [ ] **Deploy the worker as a separate process** — The `Procfile` already has:
  ```
  web:    gunicorn "app:create_app('prod')" --bind 0.0.0.0:$PORT --workers 2 --threads 4
  worker: python worker.py
  ```
  In Render: Add a "Background Worker" service pointing to the same repo.
  Set start command to: `python worker.py`

- [ ] **Worker needs same environment variables** — The worker reads from `.env` too.
  Ensure all env vars (DB, LINKEDIN, FERNET_KEY, etc.) are also set for the worker service.

- [x] **Fix `token_record.access_token` in `worker.py`** — The worker currently accesses
  `token_record.access_token` directly (plain text). After our encryption changes, it must
  use `token_record.token` (the decrypted property).
  **File:** `worker.py` line 46:
  ```python
  # ❌ Old (broken with encryption):
  if not token_record or not token_record.access_token:
      access_token=token_record.access_token,

  # ✅ Fix to:
  if not token_record or not token_record.token:
      access_token=token_record.token,
  ```

- [ ] **Idempotency** — The `idem_key` in `worker.py` prevents double-publishing if the
  worker crashes mid-job. Verify this logic is intact before deploying.

---

## SECTION 6 — Lead Finder (Currently Mocked)

> **🟡 IMPORTANT** — The Lead Finder page shows fake data. No real API is called.

- [ ] **Decide which enrichment APIs to subscribe to:**
  | Provider | Cost | Find Rate | Best For |
  |---|---|---|---|
  | [Prospeo](https://prospeo.io) | ~$39/mo | 85% | Starting point |
  | [Dropcontact](https://dropcontact.com) | ~$24/mo | Good | Europe/GDPR |
  | [Findymail](https://app.findymail.com) | ~$49/mo | Very High | Accuracy |
  | [Datagma](https://datagma.com) | ~$39/mo | High | Phone + LinkedIn |

- [ ] **Add API keys to environment variables** (see `app/leads/routes.py` for full list).

- [ ] **Replace mock `search()` function** in `app/leads/routes.py` with real waterfall calls.
  The full implementation plan with code examples is in that file.

- [ ] **Add Redis caching** for lead results (TTL: 7 days) to avoid duplicate API costs.

- [ ] **Implement credit limits** — Free users: 10 searches/month. Pro: unlimited.

---

## SECTION 7 — Payment & Subscription Flow

> **🟡 IMPORTANT** — Test with real card before launch.

- [ ] **Test Stripe checkout end-to-end** in staging with test cards first.
  Test card: `4242 4242 4242 4242` (any future date, any CVC)

- [ ] **Verify webhook delivers correctly** — Use Stripe CLI to test locally:
  ```bash
  stripe listen --forward-to localhost:5001/payments/webhook
  ```

- [ ] **Test subscription cancellation** — Ensure downgrade to free plan works.

- [ ] **Verify `plan_expires_at`** is being set correctly on the User model.

---

## SECTION 8 — Performance & Monitoring

> **🟢 RECOMMENDED** — Important but not launch-blocking.

- [ ] **Set up error monitoring** — [Sentry](https://sentry.io) free tier is excellent.
  Add `sentry-sdk[flask]` to requirements.txt and initialise in `app/__init__.py`:
  ```python
  import sentry_sdk
  sentry_sdk.init(dsn=os.environ.get('SENTRY_DSN'), traces_sample_rate=0.1)
  ```

- [ ] **Set up uptime monitoring** — [UptimeRobot](https://uptimerobot.com) free tier.
  Ping your `/` route every 5 minutes. Alert on downtime.

- [ ] **Review logs at first launch** — Check `logs/linkedin_studio.log` after first real users.
  Look for any `ERROR` or `WARNING` entries.

- [ ] **Database connection pooling** — Already configured in `config.py`:
  `SQLALCHEMY_POOL_SIZE=10`, `SQLALCHEMY_MAX_OVERFLOW=20`. Adjust for your Postgres plan.



---

## SECTION 9 — Pre-launch Testing

> **🟢 RECOMMENDED** — Do this 24 hours before launch.

- [ ] **Full login → post → schedule flow** with a real Google account.
- [ ] **LinkedIn connect → publish flow** with a real LinkedIn account.
- [ ] **Sign out** — confirm cookies are cleared and login page shows.
- [ ] **404 and 500 pages** — visit `/nonexistent-page` and verify the custom page shows.
- [ ] **Rate limit** — confirm you get blocked after exceeding the limit.
- [ ] **Mobile layout** — check dashboard, calendar, and editor on a phone.
- [ ] **.env not committed** — run `git status` and confirm `.env` is not tracked.
  ```bash
  git ls-files | grep .env   # Should return nothing
  ```

---

## SECTION 10 — Render Deployment Commands (Quick Reference)

```bash
# Build command (Render will run this):
pip install -r requirements.txt

# Pre-deploy command (runs migrations automatically):
flask db upgrade

# Web process start command:
gunicorn "app:create_app('prod')" --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120

# Worker process start command (separate Background Worker service):
python worker.py
```

---

---

## SECTION 11 — Full Application Audit (Page-by-Page Issues)

> **Audit Date:** 2026-03-08
> Every page was read in full. Issues are listed below by page.
> 🔴 = data integrity / security risk | 🟡 = wrong behaviour / misleading | 🟢 = polish / UX

---

### 📄 Page 1: Dashboard (`/` → `index.html` + `app/__init__.py`)

- [ ] 🟡 **"My first workspace" dropdown is hardcoded.**
  `index.html` line 166 — `<option>My first workspace</option>` is static HTML.
  Multi-workspace support does not exist yet. When added, this must be dynamic.
  **Decision needed:** Do we want multi-workspace (like Taplio)? Leave as single-workspace for v1?

- [ ] 🟡 **"Activate your trial" button does nothing.**
  `index.html` line 177 — It shows the star icon and text but has no `href` or `onclick`.
  It should link to `/payments/create-checkout-session` or the pricing page.

- [ ] 🟡 **"Connect your LinkedIn account" button shows a browser `alert()` popup.**
  `index.html` line 223 — `onclick="alert('LinkedIn OAuth flow...')"`.
  This is a placeholder. The real LinkedIn OAuth flow must be wired to `/auth/linkedin` when ready.

- [ ] 🟡 **Dashboard `analytics` time filter dropdown does nothing.**
  `index.html` line 278-281 — The "This Week" / "All Time" select has no JavaScript handler.
  The stats always show all-time totals regardless of selection.

---

### 📄 Page 2: Editor (`/editor/`)

- [x] 🔴 **No rate limiting on `/editor/api/generate`.**
  `app/editor/__init__.py` line 24 — The AI generation endpoint has no `@limiter.limit()`.
  A user (or attacker) could spam Gemini API calls and exhaust your quota.
  **Action:** Add `@limiter.limit("20 per hour")` before the route.

- [x] 🔴 **No `UsageLog` entry is saved when AI generates a post.**
  `app/editor/__init__.py` lines 41-56 — `generate_post()` is called but no `UsageLog` record
  is written. This means AI generation counts on the Dashboard ("AI Generations" stat) and
  the Analytics chart will always show **0** even after real usage.
  **Action:** After a successful generation, add:
  `db.session.add(UsageLog(user_id=current_user.id, action='generate', char_count=len(result)))` 

- [ ] 🟡 **No character count enforcer on the editor.**
  LinkedIn's post limit is 3,000 characters. The editor has `max_length=1500` as a default,
  but there is no hard block if the user exceeds it before saving.

- [x] 🟡 **`sys.path.append` in a web request handler.**
  `app/editor/__init__.py` lines 34-38 — Every API call to `/editor/api/generate` appends
  to `sys.path`. This works but is bad practice. The `execution/` module should be installed
  as a package or moved inside `app/`.

---

### 📄 Page 3: Drafts (`/drafts/`)

- [x] 🔴 **Hard delete — drafts are permanently removed from the DB.**
  `app/drafts/__init__.py` line 95 — `db.session.delete(draft)` is a hard delete.
  We added `is_deleted` soft-delete to the `Draft` model (via `BaseModel`) but the Drafts
  blueprint still uses hard delete. If a user accidentally deletes a draft, it is gone forever.
  **Action:** Change to `draft.soft_delete()` + `db.session.commit()`.

- [x] 🔴 **`api/list` does not filter out soft-deleted drafts.**
  `app/drafts/__init__.py` line 27 — `Draft.query.filter_by(user_id=current_user.id)` does
  not include `is_deleted=False`. Soft-deleted drafts from the future fix above would still
  appear in the list.
  **Action:** Add `is_deleted=False` to the filter.

- [ ] 🟡 **Delete API has no CSRF protection on the frontend.**
  `drafts/index.html` line 319 — `fetch('/drafts/api/delete/${id}', { method: 'DELETE' })`
  does not send a CSRF token. Flask-WTF exempts `DELETE` by default, so it works for now,
  but this is inconsistent and should be noted.

- [x] 🟡 **No rate limiting on `/drafts/api/save`.**
  A user could save thousands of drafts in a loop filling up the database.
  **Action:** Add `@limiter.limit("60 per hour")` to `api_save`.

---

### 📄 Page 4: Calendar (`/calendar/`)

- [x] 🟡 **Published posts query uses `scheduled_at` for ordering, not `published_at`.**
  `app/calendar/__init__.py` line 19:
  `Draft.query.filter_by(..., status='published').order_by(Draft.scheduled_at.desc())`
  A post published before its scheduled time (e.g. manually triggered) will sort incorrectly.
  **Action:** Change to `.order_by(Draft.published_at.desc().nullslast())`.

- [x] 🟡 **`/api/events` only finds events by `scheduled_at`, not `published_at`.**
  `app/calendar/__init__.py` lines 42-43 — If a post's `published_at` is outside the
  queried month range but `scheduled_at` is not, published posts can disappear from the calendar.
  **Action:** Query using `OR (scheduled_at IN range OR published_at IN range)`.

- [ ] 🟢 **No confirmation before unscheduling.**
  The unschedule button in `calendar/index.html` fires immediately. A user may misclick.
  A simple `confirm()` dialog would prevent accidental unscheduling.

---

### 📄 Page 5: Analytics (`/analytics/`)

- [ ] 🔴 **(FIXED TODAY)** Impressions/likes showed fake baseline numbers for ALL users.
  `total_impressions = published_count * 342 + 1240` — **Fixed.** Now shows 0 until
  LinkedIn Analytics API is integrated. Both the `analytics/__init__.py` and audit are done.

- [ ] 🔴 **(FIXED TODAY)** Chart bars used `random.randint()` — different bars on every refresh.
  **Fixed.** Now uses real DB queries grouped by date per user.

- [x] 🟡 **Analytics template references `d.date.split(' ')[1]` but the new API returns a `date`
  field that is just `"08"` (day number only).** `analytics/index.html` line 165:
  `${d.date.split(' ')[1]}` will be `undefined` since there is no space anymore.
  **Action:** Update the JS to just use `${d.date}` (the day number directly).

- [x] 🟡 **No data for impressions/likes shown on the Analytics page.**
  The template renders `{{ total_impressions }}` and `{{ total_likes }}` as `0`.
  A user will see all-zero cards with no explanation. Should show a banner:
  _"Connect LinkedIn to see real engagement data."_

---

### 📄 Page 6: Lead Finder (`/leads/`)

- [ ] 🔴 **All data is mocked — no real API is called.**
  Fully documented in `app/leads/routes.py`. See **Section 6** of this checklist.

- [x] 🟡 **No "DEMO MODE" banner shown to the user.**
  A real user might think the results are real and act on fake phone numbers.
  **Action:** Add a yellow banner at the top of the leads page:
  _"⚠️ Demo Mode — results are illustrative only. Real API integration coming soon."_

- [ ] 🟡 **No search history saved per user.**
  Each search vanishes when the page is refreshed. No results are stored.
  **Action (post-launch):** Save each search result to a `LeadSearch` table.

- [ ] 🟢 **Lead Finder page has no "Export to CSV" button.**
  Users will want to export found leads. This is a common feature in competitor tools.

---

### ⚙️ Scheduler (`app/scheduler.py` + `worker.py`)

- [x] 🔴 **Scheduler marks posts "published" WITHOUT calling the LinkedIn API.**
  `app/scheduler.py` lines 33-34:
  ```python
  post.status = 'published'   # ← Fake! No LinkedIn API call happens!
  post.published_at = now
  ```
  This is the dev-mode simulation. Scheduled posts will show as "Published" in the UI
  but will **never actually appear on LinkedIn** until the real API call is added.
  **Action:** Replace the body of `process_scheduled_posts()` with a real call to
  `execution/publish_linkedin.py`, similar to `worker.py`.

- [x] 🔴 **`worker.py` uses `token_record.access_token` (raw encrypted bytes).**
  `worker.py` lines 46 and 59 — must use `token_record.token` (the decrypted property).
  See **Section 5** of this checklist.

- [x] 🟡 **In-process scheduler + web server on same thread is a dev-only pattern.**
  `app/__init__.py` lines 286-292 — `start_scheduler` runs in a daemon thread inside the web
  process. In production, this must be the separate `worker.py` process (see Section 5).
  **Action before deploy:** Set an env var `DISABLE_INLINE_SCHEDULER=true` and guard the
  thread start with `if not os.environ.get('DISABLE_INLINE_SCHEDULER'):` so the inline
  scheduler only runs locally.

- [x] 🟡 **Scheduler does not filter `is_deleted=False`.**
  `app/scheduler.py` line 20 — `Draft.query.filter(Draft.status == 'scheduled', ...)` does
  not exclude soft-deleted drafts. A soft-deleted scheduled post would still be published.
  **Action:** Add `Draft.is_deleted == False` to the filter.

---

### 🔐 Auth (`app/auth/routes.py`)

- [x] 🟡 **LinkedIn OAuth is not implemented.**
  There is no `/auth/linkedin` or `/auth/linkedin/callback` route. The "Connect LinkedIn"
  button on the dashboard shows an `alert()`. Without this, posts cannot be published to
  LinkedIn from the app. This is a core feature gap.
  **Action:** Implement LinkedIn OAuth 2.0 flow (separate task, requires LinkedIn Developer
  app approval for the `w_member_social` scope).

- [x] 🟢 **No login with email/password fallback.**
  Currently 100% dependent on Google OAuth. If Google has an outage, no user can log in.
  **Decision needed:** Add email/password auth as a backup? Or leave as Google-only? (UI added, backend routing remaining).

---

*Last updated: 2026-03-13 | Updated by: Antigravity AI*
*Covers changes through this session: Editor UsageLog & rate limiting, Drafts soft deletes & rate limiting, Calendar sorting & cross-period querying, Background worker token extraction & idempotency, inline scheduler disabling, Analytics UI, Leads demo UI, and overall alignment built on top of previous security revisions.*
