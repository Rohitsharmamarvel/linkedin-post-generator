<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/Gemini_AI-2.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Gemini">
  <img src="https://img.shields.io/badge/LinkedIn_API-v2-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
</p>

# 🤖 LinkedIn Post Generator

> AI-powered LinkedIn content generator that creates human-like, engaging posts and publishes them directly to your profile — all from a beautiful web UI.

<p align="center">
  <em>Generate → Preview → Publish — in under 30 seconds.</em>
</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🤖 **AI Post Generation** | Uses Google Gemini 2.5 Flash to generate engaging, human-like LinkedIn posts |
| ✍️ **Direct Post Mode** | Write your own content and publish directly — no AI needed |
| ⚡ **Parallel Generation** | Generates multiple post variations simultaneously using thread pools |
| 🔐 **LinkedIn OAuth 2.0** | One-click LinkedIn connection with automatic token management |
| 📊 **Rate Limiting** | Built-in rate limiting (10 req/min per IP) to prevent abuse |
| 📝 **Structured Logging** | Rotating log files with timestamped, leveled entries |
| 🌐 **Production-Ready** | Gunicorn, gzip compression, connection pooling, request timeouts |
| 🎨 **Modern Dark UI** | Glassmorphism design with smooth animations and responsive layout |

---

## 🖥️ Screenshots

<!-- Add your own screenshots here -->
<!-- ![AI Generate Tab](screenshots/ai-generate.png) -->
<!-- ![Direct Post Tab](screenshots/direct-post.png) -->

*Screenshots coming soon — run the app locally to see the UI!*

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Browser (UI)                      │
│         Dual-mode: AI Generate / Direct Post         │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (JSON)
┌──────────────────────▼──────────────────────────────┐
│                  Flask Backend                       │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │  /generate│  │/direct-  │  │ /connect-linkedin  │ │
│  │  (AI)    │  │  post    │  │ (OAuth 2.0)        │ │
│  └────┬─────┘  └────┬─────┘  └────────────────────┘ │
│       │              │                               │
│  ┌────▼─────────────▼───────────────────────────┐   │
│  │  Rate Limiter → Validation → Logging          │   │
│  └────┬─────────────┬───────────────────────────┘   │
│       │              │                               │
└───────┼──────────────┼───────────────────────────────┘
        │              │
  ┌─────▼─────┐  ┌─────▼──────────┐
  │ Gemini AI │  │  LinkedIn API   │
  │ (Google)  │  │  (v2/ugcPosts)  │
  └───────────┘  └────────────────┘
```

**Tech Stack:**
- **Backend:** Python 3.8+, Flask, Gunicorn
- **AI:** Google Gemini 2.5 Flash (via `google-generativeai`)
- **API:** LinkedIn v2 (OAuth 2.0 + UGC Posts)
- **Frontend:** Vanilla HTML/CSS/JS with glassmorphism dark theme
- **Performance:** ThreadPoolExecutor, connection pooling, gzip compression

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- A [Google AI Studio](https://aistudio.google.com/app/apikey) API key (free)
- A [LinkedIn Developer App](https://developer.linkedin.com/) (for posting)

### 1. Clone & Install

```bash
git clone https://github.com/Rohitsharmamarvel/linkedin-post-generator.git
cd linkedin-post-generator

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
GEMINI_API_KEY="your_gemini_api_key"
LINKEDIN_CLIENT_ID="your_linkedin_app_client_id"
LINKEDIN_CLIENT_SECRET="your_linkedin_app_client_secret"
```

> **Note:** `LINKEDIN_ACCESS_TOKEN` and `LINKEDIN_PERSON_URN` are automatically populated when you connect via the OAuth flow at `/connect-linkedin`.

### 3. Run

```bash
# Development mode (with hot reload)
python app.py

# Production mode (Gunicorn)
./run.sh
```

Open **http://localhost:5001** in your browser.

### 4. Connect LinkedIn

Click **"Connect LinkedIn →"** in the header to authorize the app via OAuth 2.0. Your access token and person URN will be saved automatically.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web UI |
| `GET` | `/status` | Health check + connection status |
| `POST` | `/generate` | Generate AI posts `{ "topic": "...", "count": 3 }` |
| `POST` | `/post-to-linkedin` | Post AI-generated content to LinkedIn |
| `POST` | `/direct-post` | Post custom text directly `{ "text": "..." }` |
| `GET` | `/connect-linkedin` | Start LinkedIn OAuth 2.0 flow |
| `GET` | `/callback` | OAuth callback (handles token exchange) |

---

## 🔑 Getting API Keys

### Gemini API Key (Free)
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in → **Create API key**
3. Copy the key into `.env` as `GEMINI_API_KEY`

### LinkedIn Developer App
1. Go to [LinkedIn Developer Portal](https://developer.linkedin.com/)
2. **Create app** → fill in details (use your LinkedIn page as the company)
3. Under **Auth** tab → add `http://localhost:5001/callback` as a redirect URL
4. Under **Products** tab → request **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**
5. Copy **Client ID** and **Client Secret** into `.env`

---

## ☁️ Deploy for Free

### Option 1: Render (Recommended)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

1. Push your code to GitHub
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your GitHub repo
4. Render auto-detects the `render.yaml` blueprint
5. Add your environment variables in the Render dashboard
6. Deploy! 🚀

### Option 2: Docker

```bash
docker build -t linkedin-bot .
docker run -p 5001:5001 --env-file .env linkedin-bot
```

### Option 3: Railway

1. Push to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
3. Add environment variables
4. Railway auto-detects the `Procfile`

---

## 📁 Project Structure

```
linkedin-post-generator/
├── app.py                 # Flask backend (routes, Gemini, LinkedIn API)
├── linkedin_bot.py        # CLI version (standalone terminal tool)
├── test_generation.py     # Test script for post generation
├── templates/
│   └── index.html         # Frontend UI (dark glassmorphism theme)
├── requirements.txt       # Python dependencies
├── run.sh                 # Startup script (dev / production)
├── Procfile               # Process file for cloud deployment
├── Dockerfile             # Container build configuration
├── render.yaml            # Render.com deploy blueprint
├── .env.example           # Environment variable template
├── .gitignore             # Git ignore rules
├── LICENSE                # MIT License
└── logs/                  # Auto-created log directory (gitignored)
    └── app.log            # Application logs (rotating, 5MB max)
```

---

## 🛡️ Security

- All secrets stored in `.env` (gitignored, never committed)
- Rate limiting: 10 requests/minute per IP per endpoint
- Input validation: max 3,000 characters (LinkedIn's limit)
- Request timeouts: 30 seconds for all external API calls
- OAuth 2.0 with automatic token storage

---

## 🤝 Contributing

Contributions are welcome! Feel free to:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Built with ❤️ by <strong>Rohit Sharma</strong>
</p>
