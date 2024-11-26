import fitz
import json
from pathlib import Path
import re

def identify_element_type(text, page_num, y_pos, bottom_y):
    """Identify if text block is a figure/table title, equation, or paragraph"""
    text = text.strip()
    # Check for figure/table titles (case insensitive)
    if re.match(r'^(figure|table)\s+\d+', text.lower()):
        return {
            'type': 'figure_table',
            'title': text,
            'page_number': page_num,
            'file_path': None,  # Will be filled later
            'y_position': y_pos,
            'bottom_y': bottom_y
        }
    # Check for equations (look for mathematical symbols)
    elif any(char in text for char in '∑∫=≠≈≤≥±→←↔') and len(text) < 100:
        return {
            'type': 'equation',
            'text': text,
            'page_number': page_num,
            'file_path': None,
            'y_position': y_pos,
            'bottom_y': bottom_y
        }
    else:
        return {
            'type': 'paragraph',
            'text': text,
            'page_number': page_num,
            'associated_element': None,  # Will be filled later
            'y_position': y_pos,
            'bottom_y': bottom_y
        }

def merge_paragraph_blocks(blocks):
    """Merge text blocks that belong to the same paragraph"""
    merged_blocks = []
    current_paragraph = []
    
    for block in blocks:
        # Get block coordinates - blocks from PyMuPDF have 6 values, not 5
        x0, y0, x1, y1, text, block_type = block[:5] + (block[5] if len(block) > 5 else None,)
        
        if not current_paragraph:
            current_paragraph = [block]
            continue
            
        # Get previous block coordinates
        prev_x0, prev_y0, prev_x1, prev_y1, prev_text = current_paragraph[-1][:5]
        
        # Check if blocks are part of same paragraph:
        # 1. Similar vertical position (within reasonable margin)
        # 2. Reasonable vertical spacing
        # 3. Not a new line starting with figure/table
        vertical_margin = 3  # Adjust based on your PDF
        line_spacing = 15    # Adjust based on your PDF
        
        if (abs(y0 - prev_y1) < vertical_margin or  # Same line
            (y0 - prev_y1 < line_spacing and  # Next line with reasonable spacing
             not re.match(r'^(Figure|Table)\s+\d+', text.strip()))):  # Not a new figure/table reference
            current_paragraph.append(block)
        else:
            # Merge current paragraph blocks and start new paragraph
            merged_text = ' '.join(b[4] for b in current_paragraph)
            merged_blocks.append((
                current_paragraph[0][0],  # x0 from first block
                current_paragraph[0][1],  # y0 from first block
                current_paragraph[-1][2], # x1 from last block
                current_paragraph[-1][3], # y1 from last block
                merged_text
            ))
            current_paragraph = [block]
    
    # Don't forget to merge the last paragraph
    if current_paragraph:
        merged_text = ' '.join(b[4] for b in current_paragraph)
        merged_blocks.append((
            current_paragraph[0][0],
            current_paragraph[0][1],
            current_paragraph[-1][2],
            current_paragraph[-1][3],
            merged_text
        ))
    
    return merged_blocks

def parse_pdf_content(pdf_path):
    """Extract all elements from PDF in sequential order"""
    doc = fitz.open(pdf_path)
    elements = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("blocks")
        
        # Get page dimensions
        page_height = page.rect.height
        # print(f"Page height: {page_height}")
        header_margin = 100  # Adjust based on your PDF
        footer_margin = 200  # Adjust based on your PDF
        
        # Filter out header/footer blocks
        content_blocks = [b for b in blocks if header_margin < b[1] < (page_height - footer_margin)]
        
        # Sort blocks by vertical position
        content_blocks.sort(key=lambda b: (b[1], b[0]))  # Sort by y, then x
        
        # Merge paragraph blocks
        merged_blocks = merge_paragraph_blocks(content_blocks)
        
        for block in merged_blocks:
            if block[3] > page_height - footer_margin and block[3] - block[1] < 350: # Ignore footnotes
                print(f"Skipping footnote found on page number: {page_num + 1}")
                print(f"    >>>Block bottom y: {block[3]}, Page height: {page_height}, Block height: {block[3] - block[1]}")
                print(f"    >>>text: {block[4]}")
                continue
            text = block[4]
            # Remove special characters while preserving basic punctuation and spaces
            text = ''.join(char for char in text if char.isprintable())
            if text.strip():  # Skip empty blocks
                element = identify_element_type(text, page_num + 1, block[1], block[3])  # Pass y position and bottom y
                elements.append(element)

    print(f"Parsed {len(elements)} elements from PDF")
    #save to json file 
    with open('parsed_elements.json', 'w') as f:
        json.dump(elements, f, indent=4, ensure_ascii=False)
    
    return elements

if __name__ == "__main__":
    parse_pdf_content("macro.pdf")