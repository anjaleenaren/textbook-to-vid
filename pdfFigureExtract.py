import os
import shutil
import fitz
import cv2
import pytesseract
from PIL import Image

def contains_figure_or_table(image_path):
    # Read text from image using OCR
    text = pytesseract.image_to_string(Image.open(image_path)).lower()
    return 'figure' in text or 'table' in text

def extract_region_with_adaptive_margins(image, base_x, base_y, base_w, base_h, margin_x, margin_y):
    height, width = image.shape[:2]
    
    # Calculate coordinates with current margins
    x = max(base_x - margin_x, 0)
    y = max(base_y - margin_y, 0)
    w = min(base_w + 2 * margin_x, width - x)
    h = min(base_h + 2 * margin_y, height - y)
    
    # If width is more than half the page, use full width
    if w > 0.5 * width:
        x = 0
        w = width
        
    return x, y, w, h

def calculate_iou(box1, box2):
    # box format: (x, y, w, h)
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    
    # Calculate intersection coordinates
    x_left = max(x1, x2)
    y_top = max(y1, y2)
    x_right = min(x1 + w1, x2 + w2)
    y_bottom = min(y1 + h1, y2 + h2)
    
    if x_right < x_left or y_bottom < y_top:
        return 0.0
        
    # Calculate areas
    intersection_area = max(0, (x_right - x_left) * (y_bottom - y_top))
    box1_area = w1 * h1
    box2_area = w2 * h2
    
    # if we intersect more than 70% of one of the boxes, we consider it a match
    if intersection_area / box1_area > 0.7 or intersection_area / box2_area > 0.7:
        return 1.0

def process_pdf_with_extra_large_margins(pdf_path, output_directory):
    doc = fitz.open(pdf_path)
    extracted_files = []
    saved_boxes = []  # List to store saved bounding boxes per page
    
    for page_num in range(len(doc)):
        page_boxes = []  # Store boxes for current page
        # Render the page as an image
        pixmap = doc.load_page(page_num).get_pixmap()
        image_path = os.path.join(output_directory, f'page_{page_num}.png')
        pixmap.save(image_path)
        
        # Reload the saved image with OpenCV
        image = cv2.imread(image_path)
        height, width = image.shape[:2]
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Threshold and detect contours
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for i, contour in enumerate(contours):
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            aspect_ratio = w / h if h > 0 else 0
            
            if area > 10000 and 0.5 < aspect_ratio < 2.5:
                # Check for overlap with existing boxes
                current_box = (x, y, w, h)
                overlap_found = False
                
                for saved_box in page_boxes:
                    iou = calculate_iou(current_box, saved_box)
                    print(f"    iou: {iou}")
                    if iou > 0.7:  # 80% overlap threshold
                        overlap_found = True
                        break
                
                if overlap_found:
                    continue
                
                # Start with initial margins
                margin_x = 240
                margin_y = 240
                found_text = False
                
                # Keep trying with larger margins until we find the text or reach page limits
                while not found_text:
                    x_crop, y_crop, w_crop, h_crop = extract_region_with_adaptive_margins(image, x, y, w, h, margin_x, margin_y)
                    print(f"image {page_num}_{i}: x_crop: {x_crop} y_crop: {y_crop} w_crop: {w_crop} h_crop: {h_crop}")
                    cropped_image = image[y_crop:y_crop+h_crop, x_crop:x_crop+w_crop]
                    cropped_image_path = os.path.join(output_directory, f'figure_page{page_num}_{i}.png')
                    cv2.imwrite(cropped_image_path, cropped_image)
                    
                    found_text = contains_figure_or_table(cropped_image_path)
                    
                    if found_text:
                        extracted_files.append(cropped_image_path)
                        page_boxes.append(current_box)  # Save the box if we found a figure/table
                        # print("SAVED FILE", cropped_image_path)
                    elif not found_text:
                        margin_x += 50
                        margin_y += 200
                        # print("REMOVE TEMP FILE", cropped_image_path)
                        os.remove(cropped_image_path)  # Remove the temporary file if no figure/table found
        print(f" Page boxes: {page_boxes}")
        saved_boxes.append(page_boxes)  # Save boxes for this page
    
    return extracted_files

# Create a directory for extra large margin output
output_dir_extra_large_margin = './extracted_figures_extra_large_margin'
os.makedirs(output_dir_extra_large_margin, exist_ok=True)


# Reprocess the PDF with extra large margins
extra_large_margin_results = process_pdf_with_extra_large_margins("macro.pdf", output_dir_extra_large_margin)

# Create a zip file for the extra large margin extracted figures
zip_file_extra_large_margin = './extracted_figures_extra_large_margin.zip'
shutil.make_archive(zip_file_extra_large_margin.replace('.zip', ''), 'zip', output_dir_extra_large_margin)

zip_file_extra_large_margin