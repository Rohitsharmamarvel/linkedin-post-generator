import os
import google.generativeai as genai
from dotenv import load_dotenv
from linkedin_bot import initialize_gemini, generate_posts

def main():
    print("Initializing Gemini...")
    model = initialize_gemini()
    
    topic = "Why software engineers should care about writing clean code, even when deadlines are super tight."
    count = 3
    print(f"Generating {count} post variations for topic:\n'{topic}'\n")
    
    posts = generate_posts(model, topic, count)
    
    if not posts:
        print("Failed to generate posts. Check your API key and network connection.")
        return
        
    output_file = "sample_posts.txt"
    with open(output_file, "w") as f:
        f.write(f"Topic: {topic}\n")
        f.write("=" * 50 + "\n\n")
        
        for i, post in enumerate(posts, 1):
            f.write(f"--- OPTION {i} ---\n")
            f.write(f"{post}\n\n")
            f.write("=" * 50 + "\n\n")
            
    print(f"✅ Successfully wrote {len(posts)} posts to {output_file}")

if __name__ == "__main__":
    main()
