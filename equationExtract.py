import os
import fitz
import cv2
import pytesseract
from PIL import Image
import numpy as np

def is_equation_region(image, x, y, w, h, page_width):
    """
    Determine if a region contains an equation based on:
    1. Position (centered)
    2. Isolation (whitespace around it)
    3. Density of mathematical symbols
    """
    # Check if centered
    content_center = x + (w/2)
    page_center = page_width/2
    margin = page_width * 0.15  # 15% margin of error
    if abs(content_center - page_center) > margin:
        return False
    
    # Check for whitespace around region
    padding = 50
    y1 = max(0, y - padding)
    y2 = min(image.shape[0], y + h + padding)
    x1 = max(0, x - padding)
    x2 = min(image.shape[1], x + w + padding)
    
    surrounding = image[y1:y2, x1:x2]
    white_ratio = np.sum(surrounding > 250) / surrounding.size
    if white_ratio < 0.85:  # Require 85% whitespace around equation
        return False
    
    return True

def process_pdf_for_equations(pdf_path, output_directory):
    doc = fitz.open(pdf_path)
    extracted_files = []
    
    for page_num in range(len(doc)):
        # Increase resolution significantly for better equation detection
        page = doc.load_page(page_num)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(3, 3))  # Higher resolution
        image_path = os.path.join(output_directory, f'page_{page_num}.png')
        pixmap.save(image_path)
        
        # Load and preprocess image
        image = cv2.imread(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Enhanced preprocessing
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.threshold(blurred, 0, 255, 
                             cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, 
                                     cv2.CHAIN_APPROX_SIMPLE)
        
        # Sort contours by y-coordinate to maintain order
        contours = sorted(contours, key=lambda c: cv2.boundingRect(c)[1])
        
        for i, contour in enumerate(contours):
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter based on size and aspect ratio
            aspect_ratio = w / float(h)
            if (w < 50 or h < 20 or  # Too small
                aspect_ratio < 1.0 or aspect_ratio > 20.0):  # Wrong shape
                continue
            
            if is_equation_region(gray, x, y, w, h, image.shape[1]):
                # Add margins
                margin_x = int(w * 0.1)
                margin_y = int(h * 0.3)
                x_crop = max(x - margin_x, 0)
                y_crop = max(y - margin_y, 0)
                w_crop = min(w + 2 * margin_x, image.shape[1] - x_crop)
                h_crop = min(h + 2 * margin_y, image.shape[0] - y_crop)
                
                # Extract equation region
                equation = image[y_crop:y_crop+h_crop, x_crop:x_crop+w_crop]
                
                # Save equation
                equation_path = os.path.join(output_directory, 
                                           f'equation_page{page_num}_{i}.png')
                cv2.imwrite(equation_path, equation)
                extracted_files.append(equation_path)
        
        os.remove(image_path)
    
    return extracted_files

# Create output directory and process PDF
output_dir = './extracted_equations'
os.makedirs(output_dir, exist_ok=True)
equation_files = process_pdf_for_equations("macro.pdf", output_dir) 