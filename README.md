# LinkedIn Content Generator CLI

A command-line tool that uses the Gemini API to generate relatable, human-like LinkedIn posts tailored for Software Engineers, and optionally posts them directly to LinkedIn.

## Setup Instructions

### 1. Prerequisites
- Python 3.8+
- A Google account (for Gemini API)
- A LinkedIn account

### 2. Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Obtain API Keys

#### 🔐 Gemini API Key
1. Go to Google AI Studio: https://aistudio.google.com/app/apikey
2. Sign in with your Google account.
3. Click on **Create API key**.
4. Copy the generated API key.
5. Paste it into your `.env` file as `GEMINI_API_KEY="your_api_key_here"`.

#### 🔐 LinkedIn API Credentials
To post automatically to LinkedIn, you need an Access Token and your Person URN.
*(Wait, building a LinkedIn app for just posting can be complex for a personal script, you might want to consider just copying the text and posting manually unless you want to set up an app on the LinkedIn Developer Portal).*

If you want to use the automated posting feature:
1. Go to the [LinkedIn Developer Portal](https://developer.linkedin.com/).
2. Click **Create app** and fill in the details.
3. Under the **Auth** tab, request the `w_member_social` permission.
4. Generate an OAuth 2.0 Access Token. 
5. To find your `LINKEDIN_PERSON_URN` (it looks like `urn:li:person:12345678`), you can query the `/me` endpoint with your token.
6. Paste both into your `.env` file as `LINKEDIN_ACCESS_TOKEN` and `LINKEDIN_PERSON_URN`.

### 4. Setup Environment Variables
1. Copy the `.env.example` file to a new file named `.env`.
2. Fill in the placeholders in `.env` with the keys you obtained.

### 5. Run the Script
```bash
python linkedin_bot.py
```
Follow the interactive prompts in the terminal to generate and review your posts!
