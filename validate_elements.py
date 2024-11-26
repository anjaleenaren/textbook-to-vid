from pathlib import Path
import json
def match_visual_elements(elements, figures_dir, equations_dir):
    """Match and validate visual elements with extracted files"""
    validated_elements = []
    
    # Get lists of extracted files
    figure_files = Path(figures_dir).glob('*.png')
    # equation_files = Path(equations_dir).glob('*.png')
    
    # Create lookup dictionaries
    figure_lookup = {tuple(f.stem.split('_')[1:]): str(f) for f in figure_files}
    # equation_lookup = {tuple(f.stem.split('_')[1:]): str(f) for f in equation_files}
    
    for element in elements:
        if element['type'] == 'figure_table':
            # Try to find matching figure file
            page_key = f"page{element['page_number']}"
            matching_files = [v for k, v in figure_lookup.items() 
                            if page_key in k]
            
            if matching_files:
                element['file_path'] = matching_files[0]
                validated_elements.append(element)
                
        # elif element['type'] == 'equation':
        #     # Try to find matching equation file
        #     page_key = f"page{element['page_number']}"
        #     matching_files = [v for k, v in equation_lookup.items() 
        #                     if page_key in k]
            
        #     if matching_files:
        #         element['file_path'] = matching_files[0]
        #         validated_elements.append(element)
                
        else:  # Paragraphs are always kept
            validated_elements.append(element)
    
    print(f"Validated {len(validated_elements)} elements")
    json.dump(validated_elements, open('validated_elements.json', 'w'), indent=4)

    return validated_elements 