# 🤖 AGENT RULES & CONTEXT
> **CRITICAL CONSTRAINTS TO REMEMBER FOREVER**
> Read this file before suggesting any major actions, deployments, or architecture changes.

## 💰 Render Free Tier Limitations (CRITICAL)
1. **NO Shell Access:** The user is on the Free tier. The Render "Shell" tab is locked behind the Starter ($7/mo) plan. DO NOT ask the user to open the Shell. 
2. **Build Minute limits (500/mo):** Do not waste build minutes on small typos or broken code.
3. **Auto-Deploy is OFF:** To save build minutes and prevent accidental exhaustions, Github push auto-deploys are disabled.
4. **Manual Deploy Required:** After pushing code to `main` or fixing a setting, the user **must manually click "Manual Deploy" -> "Deploy latest commit"** in the Render Dashboard. Wait for the user to confirm they have done this before assuming it's live.

## 🛠 Render Web Service Start Command
Since we cannot use the Shell to migrate the database on the Free Tier, the database migration (`flask db upgrade`) **MUST** be chained to the start command in the Render dashboard Web Service settings.
**The required start command is:**
`flask db upgrade && gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --threads 4`

## 🚀 Branching Strategy
* Local development happens on `dev` branch.
* Production deployments run off the `main` branch.
* After fixing bugs locally, they must be merged heavily into `main` and pushed so Render can pick them up when the user clicks Manual Deploy.

## 🛰️ Future-Proof Dynamic Configuration
Critical URLs and model names are now managed via environment variables. Do NOT hardcode these in scripts:
1. `GOOGLE_METADATA_URL` / `LINKEDIN_METADATA_URL`: For OIDC discovery.
2. `GEMINI_MODELS`: Comma-separated list of models for `execution/generate_post.py`.

## 🛢️ Database (Neon.tech)
The app uses **Neon.tech** for production data. It is "Free Forever." 
1. The connection string is in the Render environment as `DATABASE_URL`.
2. Migrations still run automatically via the start command.

## 🪪 OAuth Configuration Reminders
When URLs change, remind the user to update:
1. Google Cloud Console -> Authorized JavaScript origins & Authorized redirect URIs (`/auth/callback`)
2. LinkedIn Developer Console -> Authorized redirect URLs for your app (`/auth/linkedin/callback`)
