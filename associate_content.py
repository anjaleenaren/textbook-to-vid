def associate_paragraphs_with_elements(elements):
    """Associate paragraphs with their nearest preceding visual element"""
    current_visual = None
    processed_elements = []
    
    for element in elements:
        if element['type'] in ['figure_table', 'equation'] and element['file_path']:
            current_visual = element
            processed_elements.append(element)
        elif element['type'] == 'paragraph':
            if current_visual:
                element['associated_element'] = {
                    'type': current_visual['type'],
                    'title': current_visual.get('title', ''),
                    'file_path': current_visual['file_path']
                }
            processed_elements.append(element)
    
    return processed_elements 