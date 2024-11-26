import os
import json
from openai import OpenAI
from pathlib import Path
import time

def load_pdf_content(pdf_path):
    """Load PDF content as bytes to send to GPT-4"""
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

def create_scene_text_prompt(scene):
    """Create a prompt for GPT-4 to fill in text for a single scene"""
    return f"""I have a scene from a textbook PDF document associated with {scene['title']} on page {scene['page_number']}.
    Your task is to:
    1. Read the text around this page in the PDF
    2. Identify the text that belongs to this {scene['title']}
    
    Critical Requirements:
    - Include all relevant text for this scene
    - Include text before and after the figure/table that directly relates to it
    - The text should be plain text, readable with no special characters
    - Expand abbreviations and acronyms
    - Spell out special symbols
    - Denote any superscripts or subscripts as such
    
    Output a json in the format:
    '''json
    {{
        "pre_text": "text that introduces or leads into the figure/table",
        "scene_text": "text that is part of the figure/table itself (captions, labels, etc)",
        "post_text": "text that follows and directly relates to the figure/table"
    }}
    '''
    """

def process_single_scene(client, thread, assistant, scene, file):
    """Process a single scene and return its text content"""
    # Create message with prompt for this scene
    prompt = create_scene_text_prompt(scene)
    print(f"\nProcessing {scene['title']} on page {scene['page_number']}")
    
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=prompt,
        attachments=[{"file_id": file.id, "tools": [{"type": "file_search"}]}]
    )
    
    # Create and monitor run
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id
    )
    
    start_time = time.time()
    while run.status != "completed":
        if time.time() - start_time > 120:  # 2 minute timeout per scene
            raise TimeoutError(f"Processing {scene['title']} timed out")
            
        time.sleep(5)
        print(f"Status for {scene['title']}: {run.status}")
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )
    
    # Get response
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    response = messages.data[0].content[0].text.value
    print(f"Response for {scene['title']}: {response}")
    
    try:
        # Look for JSON between ```json and ``` markers
        json_start = response.find("```json")
        if json_start == -1:
            # Try alternative format with '''json
            json_start = response.find("'''json")
            json_end = response.find("'''", json_start + 6) if json_start != -1 else -1
        else:
            json_end = response.find("```", json_start + 6)
            
        if json_start == -1 or json_end == -1:
            raise ValueError(f"Could not find JSON content between markdown code blocks")
            
        # Extract just the JSON portion (skipping the markers)
        json_content = response[json_start + 7:json_end].strip()
        
        # Parse the JSON
        scene_data = json.loads(json_content)
        
        return scene_data
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print("Raw JSON content:", json_content)
        raise

def fill_scene_text(pdf_path, scenes_path, output_path, timeout=300):
    """Fill in text content for each scene using GPT-4"""
    # Load initial scenes
    with open(scenes_path, 'r') as f:
        scenes = json.load(f)
    import sys
    
    # Get API key with better error handling
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("Please set it using:")
        print("export OPENAI_API_KEY='your-api-key-here'  # For Unix/Mac")
        print("set OPENAI_API_KEY='your-api-key-here'     # For Windows")
        sys.exit(1)
        
    try:
        client = OpenAI(api_key=api_key)
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")
        sys.exit(1)
    
    # Create assistant with PDF file
    file = client.files.create(
        file=open(pdf_path, "rb"),
        purpose='assistants'
    )
    
    assistant = client.beta.assistants.create(
        name="PDF Scene Text Assistant",
        instructions="You will help identify relevant text sections for figures and tables in a PDF document.",
        model="gpt-4o",
        tools=[{"type": "file_search"}],
    )
    
    processed_scenes = []
    failed_scenes = []
    
    for scene in scenes:
        try:
            # Create new thread for each scene
            thread = client.beta.threads.create()
            
            # Process scene
            scene_data = process_single_scene(client, thread, assistant, scene, file)
            
            # Update scene with text
            scene['text'] = (
                clean_text(scene_data.get('pre_text', '')) + 
                clean_text(scene_data.get('scene_text', '')) + 
                clean_text(scene_data.get('post_text', ''))
            )
            processed_scenes.append(scene)
            
            # Save progress after each successful scene
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(processed_scenes, f, indent=4, ensure_ascii=False)
                
            print(f"Successfully processed {scene['title']}")
            
        except Exception as e:
            print(f"Error processing {scene['title']}: {e}")
            failed_scenes.append({
                'title': scene['title'],
                'error': str(e)
            })
            
            # Save error log
            with open('failed_scenes.json', 'w', encoding='utf-8') as f:
                json.dump(failed_scenes, f, indent=4, ensure_ascii=False)
    
    if failed_scenes:
        print(f"\nWarning: {len(failed_scenes)} scenes failed to process.")
        print("See failed_scenes.json for details")
    
    print(f"\nSuccessfully processed {len(processed_scenes)} scenes")
    return processed_scenes

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