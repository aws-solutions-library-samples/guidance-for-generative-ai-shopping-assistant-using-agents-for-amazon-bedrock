import base64
import os
from PIL import Image

def encode_image(file_path):

    # The maximum image size allowed is 5MB
    current_size = os.path.getsize(file_path) / (1024 * 1024) 
    if current_size > 5:
        resize_image(file_path, 300, 300)

    with open(file_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def resize_image(file_path, max_width=300, max_height=300):
    
    # Open the image
    with Image.open(file_path) as img:
        # Get original dimensions
        original_width, original_height = img.size
        
        # Calculate the aspect ratio
        aspect_ratio = original_width / original_height
        
        # Determine new dimensions
        if original_width > original_height:
            new_width = min(max_width, original_width)
            new_height = int(new_width / aspect_ratio)
        else:
            new_height = min(max_height, original_height)
            new_width = int(new_height * aspect_ratio)
        
        # Resize the image
        img_resized = img.resize((new_width, new_height), Image.LANCZOS)
        
        # Save the resized image back to the same file path
        img_resized.save(file_path, optimize=True, quality=85)