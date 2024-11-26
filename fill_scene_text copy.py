import os
import json
import anthropic
from pathlib import Path
import time

def load_pdf_content(pdf_path):
    """Load PDF content as bytes to send to Claude"""
    with open(pdf_path, "rb") as file:
        return file.read()

def clean_text(text):
    """Clean text by removing special characters and normalizing whitespace"""
    # Remove special characters but keep basic punctuation
    cleaned = ''.join(char for char in text if char.isprintable())
    # Normalize whitespace
    cleaned = ' '.join(cleaned.split())
    # Remove any remaining unicode characters
    cleaned = cleaned.encode('ascii', 'ignore').decode()
    return cleaned

def create_scene_text_prompt(scenes):
    """Create a prompt for Claude to fill in scene text"""
    return """I have a series of scenes from a textbook PDF document, each associated with a figure or table. 
    Your task is to:
    1. Read ALL text in the textbook PDF
    2. Assign each piece of text to the most relevant scene
    
    Critical Requirements:
    - Every single word from the PDF must be included exactly once
    - Text between figures should be assigned to either the preceding figure, following figure, or Additional Content)
    - Do not skip any text, even if it seems unrelated to figures
    - The text should be plain text, and readable with no special characters. Expand abbreviations and acronyms. Spell out special symbols. Denote any superscripts or subscripts as such.
    
    Output a json that includes all the pdf text split across the scenes in the format:
    [
        {
            "title": "figure/table title or Additional Content",
            "text": "complete text section"
        }
    ]

    Here is the initial scene json:
    {"\n".join([f"- {scene['title']} (page {scene['page_number']})" for scene in scenes])}
    """

def fill_scene_text(pdf_path, scenes_path, output_path, timeout=300):
    """Fill in text content for each scene using Claude"""
    # Load initial scenes
    with open(scenes_path, 'r') as f:
        scenes = json.load(f)
    import sys
    
    # Get API key with better error handling
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable is not set.")
        print("Please set it using:")
        print("export ANTHROPIC_API_KEY='your-api-key-here'  # For Unix/Mac")
        print("set ANTHROPIC_API_KEY='your-api-key-here'     # For Windows")
        sys.exit(1)
        
    try:
        client = anthropic.Client(api_key=api_key)
    except Exception as e:
        print(f"Error initializing Anthropic client: {e}")
        sys.exit(1)
    
    # Load PDF content
    pdf_content = load_pdf_content(pdf_path)
    
    # Create initial message with prompt
    prompt = create_scene_text_prompt(scenes)
    print(prompt)
    
    try:
        # Send initial message with both PDF content and scenes JSON
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8192,
            messages=[{
                "role": "user",
                "content": f"{prompt}\n"
                        #   f"inital_scene.json:{json.dumps(scenes, indent=2)}"
                          f"pdf:{pdf_content.decode('utf-8', errors='ignore')}"
            }]
        )
        
        print("\n\n", message.content, "\n\n")
        
        # Process each scene
        for scene in scenes:
            scene_query = f"""For {scene['title']}, please provide: All text leading up to and including this figure / table that has not been incorporated into a previous scene.

Remember: Every word from the PDF must be included across all scenes."""
            
            message = client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=4096,
                messages=[{
                    "role": "user", 
                    "content": scene_query
                }]
            )
            
            print(message.content)
            scene['text'] = message.content
            
    except Exception as e:
        print(f"Error during Claude API calls: {e}")
        sys.exit(1)
    
    # Save updated scenes
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(scenes, f, indent=4)

if __name__ == "__main__":
    pdf_path = "macro.pdf"
    scenes_path = "initial_scenes.json"
    output_path = "complete_scenes.json"
    
    try:
        fill_scene_text(pdf_path, scenes_path, output_path, timeout=600)  # 10 minute timeout
    except KeyboardInterrupt:
        print("\nScript interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)