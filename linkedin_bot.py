import os
import requests
import google.generativeai as genai
from dotenv import load_dotenv

def initialize_gemini():
    load_dotenv()
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key or gemini_key == "your_gemini_api_key_here":
        print("Error: Please set your GEMINI_API_KEY in the .env file.")
        exit(1)
    
    genai.configure(api_key=gemini_key)
    # Using the fast and cost-effective gemini-2.5-flash model
    model = genai.GenerativeModel('gemini-2.5-flash')
    return model

# --- PROMPT TEMPLATE ---
# You can edit this string to change how the posts are generated in the future!
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

def generate_posts(model, topic, count):
    prompt = PROMPT_TEMPLATE.format(count=count, topic=topic)
    try:
        response = model.generate_content(prompt)
        text = response.text
        # Split by the divider
        posts = [p.strip() for p in text.split("---POST---") if p.strip()]
        return posts
    except Exception as e:
        print(f"Error generating posts: {e}")
        return []

def post_to_linkedin(text):
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    person_urn = os.getenv("LINKEDIN_PERSON_URN")
    
    if not access_token or not person_urn or access_token == "your_linkedin_access_token_here":
        print("Error: LinkedIn credentials missing or invalid in .env file.")
        return False
        
    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json"
    }
    
    # LinkedIn API structure for a text post
    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": text
                },
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 201:
            return True
        else:
            print(f"Failed to post to LinkedIn. HTTP Status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"Exception during LinkedIn posting: {e}")
        return False

def main():
    print("🚀 Welcome to the LinkedIn Content Generator CLI!")
    model = initialize_gemini()
    
    topic = input("\n💡 What idea do you want to post about? \n> ")
    if not topic.strip():
        print("Topic cannot be empty. Exiting.")
        return
        
    try:
        count = int(input("\n🔢 How many variations of the post would you like to generate? (e.g. 2 or 3)\n> "))
        if count <= 0:
            print("Please enter a positive number.")
            return
    except ValueError:                  
        print("Invalid number. Exiting.")
        return
        
    print(f"\n⏳ Generating {count} posts using Gemini API. This might take a few seconds...")
    posts = generate_posts(model, topic, count)
    
    if not posts:
        print("\nNo posts were generated. Please check your API key and try again.")
        return
        
    print(f"\n✅ Generated {len(posts)} posts:")
    print("=" * 50)
    
    for i, post in enumerate(posts, 1):
        print(f"\n--- OPTION {i} ---\n{post}\n")
    
    print("=" * 50)
    
    post_now = input("\nDo you want to post one of these to LinkedIn right now? (y/n)\n> ").strip().lower()
    if post_now == 'y':
        try:
            choice = int(input(f"Which option would you like to post? (1 to {len(posts)})\n> "))
            if 1 <= choice <= len(posts):
                selected_post = posts[choice-1]
                print(f"\nPosting Option {choice} to LinkedIn...")
                success = post_to_linkedin(selected_post)
                if success:
                    print("✅ Successfully posted to LinkedIn!")
                else:
                    print("❌ Failed to post.")
            else:
                print("Invalid choice. Exiting.")
        except ValueError:
            print("Invalid input. Exiting.")
    else:
        print("\nOkay! You can copy and paste the posts above manually whenever you are ready.")

if __name__ == "__main__":
    main()
