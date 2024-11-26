import os
import json
import pytesseract
from PIL import Image

def extract_figure_info(image_path):
    """Extract figure/table name and number from image using OCR"""
    text = pytesseract.image_to_string(Image.open(image_path)).lower()
    
    # Look for figure or table references
    lines = text.split('\n')
    for line in lines:
        if 'figure' in line or 'table' in line:
            # Clean up the title
            title = line.strip()
            return title
    return None

def create_initial_scenes(figures_dir):
    """Create initial scene objects from extracted figures"""
    scenes = []
    # scenes.append({
    #     "title": "Additional Content",
    #     "visual_path": "N/A",
    #     "page_number": 0,  # Put at end
    #     "text": ""
    # })
    
    # Get all PNG files in the figures directory
    figure_files = [f for f in os.listdir(figures_dir) if f.endswith('.png')]
    count_rel_to_page = 0
    last_page_num = 0
    
    for figure_file in figure_files:
        # Extract page number from filename (assumes format figure_pageX_Y.png)
        try:
            page_num = int(figure_file.split('page')[1].split('_')[0])
            if float(page_num) != float(last_page_num):
                count_rel_to_page = 0
            else:
                count_rel_to_page += 1
            last_page_num = page_num
        except:
            continue
            
        full_path = os.path.join(figures_dir, figure_file)
        title = extract_figure_info(full_path)
        
        if title:
            scene = {
                "title": title,
                "visual_path": full_path,
                "page_number": page_num,
                "text": ""  # Will be filled in later with GPT-4
            }
            scenes.append(scene)

            # Add Additional Content scene
            # Set page number to be just after the figure, add a count of figures on each page to do this

            # scenes.append({
            #     "title": "Additional Content",
            #     "visual_path": "N/A",
            #     "page_number": page_num + 0.1 * count_rel_to_page,
            #     "text": ""
            # })
    
    
    
    # Sort scenes by page number
    scenes.sort(key=lambda x: x["page_number"])
    
    return scenes

def save_scenes(scenes, output_file):
    """Save scenes to JSON file"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(scenes, f, indent=4)

if __name__ == "__main__":
    figures_dir = "./extracted_figures_extra_large_margin"
    output_file = "initial_scenes.json"
    
    # Create initial scene structure
    scenes = create_initial_scenes(figures_dir)
    
    # Save to JSON file
    save_scenes(scenes, output_file)
    
    print(f"Created {len(scenes)} initial scenes")
    print("Next step: Use GPT-4 to fill in the text content for each scene") 