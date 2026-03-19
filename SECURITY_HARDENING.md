# 🛡️ LinkScale: Security Hardening & Audit Report

This document outlines the security measures implemented during the **Senior Security Engineer Audit and Hardening Phase** of the LinkScale (LinkedIn Content Studio) project. These measures were designed to protect user data, prevent API abuse, and ensure a production-ready security posture.

---

### 1. 🛡️ Abuse Protection & Rate Limiting (Multi-Layer)
To prevent bot attacks, scraping, and cost spikes, we implemented a dual-layered rate limiting system:
*   **Layer 1: IP & User Identity Throttling:** Using `Flask-Limiter` with a custom `user_id_key`. Rate limits follow the **Authenticated User ID** (standardizing security across different networks/NATs) or the IP for anonymous users.
*   **Layer 2: AI Generation Quotas:** Restricted AI generation in the Business Logic Layer. Free-tier users are capped at **10 generations/24h**, while Pro users are capped at **100**. This ensures stable system costs and prevents Gemini API exhaustion.
*   **Layer 3: Global Limits:** Strict limits on Google OAuth login, registration, and sensitive API endpoints are applied via decorators.

### 2. 🛢️ Data Security & IDOR Prevention
**Insecure Direct Object Reference (IDOR)** is a top OWASP risk. We eliminated this by:
*   **Strict Query Scoping:** Every single database query (Drafts, Usage Logs, LinkedIn Tokens) is explicitly filtered by `user_id = current_user.id`. A user cannot access or modify any resource simply by guessing or changing an ID in a request.
*   **Encryption at Rest:** LinkedIn OAuth tokens are never stored in plain text. They are encrypted using **Fernet symmetric encryption** (`cryptography` library) before being written to the database, ensuring that even a database leak does not expose user credentials.

### 3. 👤 Secure Authentication & Session Hardening
*   **OAuth 2.0 Hardening:** Integrated `Authlib` with Google OAuth, utilizing the `state` parameter to prevent CSRF during sign-in.
*   **Security Monitoring:** Added explicit logging of failed authentication callbacks to the `UsageLog` table. This provides a clear audit trail for detecting credential stuffing or misconfiguration.
*   **Session Security:** 
    - `SESSION_COOKIE_HTTPONLY`: Prevents client-side scripts from accessing session cookies (Mitigates XSS).
    - `SESSION_COOKIE_SECURE`: Ensures cookies are only sent over HTTPS in production.
    - `SESSION_COOKIE_SAMESITE`: Set to `Lax` to prevent cross-site request forgery.

### 4. 🌐 Infrastructure & Deployment Hardening
*   **Dynamic CORS Control:** Hardcoded CORS origins were replaced with a environment-variable driven system (`CORS_ORIGINS`). This prevents unauthorized domains from making requests to our API.
*   **Security Response Headers:** Implemented OWASP-recommended headers on every response:
    - `X-Content-Type-Options: nosniff` (MIME sniffing protection)
    - `X-Frame-Options: DENY` (Clickjacking protection)
    - `Content-Security-Policy` (Strict CSP to restrict script sources)
    - `HSTS` (Enforced in production for 1 year)

### 5. 🧹 Input Validation & Sanitization
*   **Schema Enforcement:** All incoming JSON payloads for the Editor, Drafts, and AI Generation are validated against strict `Marshmallow` schemas to prevent malformed data or injection.
*   **XSS Sanitization:** User-generated content (topics, tones, draft body) is sanitized using `Bleach` before ingestion. This allows safe formatting (e.g., `<b>`, `<i>`) while stripping dangerous tags like `<script>`.

### 6. 📦 Dependency & Secret Management
*   **Zero Hardcoded Secrets:** All sensitive keys (Gemini, LinkedIn, Database, Encryption) are pulled strictly from environment variables.
*   **Hardened Production Check:** The application factory now includes a **Mandatory Production Variable Check**. The server will refuse to start if any security-critical environment variables are missing.
*   **Pinned Dependencies:** Every package in `requirements.txt` is pinned to a specific, verified version to prevent supply-chain attacks and ensure build stability.

---

### ✅ Summary of Tools Used:
- **Flask-Limiter:** Distributed rate limiting.
- **Bleach:** Output sanitization.
- **Marshmallow:** Input validation.
- **Fernet/Cryptography:** Storage encryption.
- **Flask-WTF (CSRF):** Protection for state-changing requests.
- **Authlib:** Secure OAuth integration.
- **Gunicorn (ProxyFix):** Secure edge-proxy handling.
