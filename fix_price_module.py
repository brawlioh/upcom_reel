#!/usr/bin/env python3

"""
Fix the module0_price.py file by adding a more reliable image downloader
"""

print("Patching module0_price.py to add reliable image handling...")

# Add import for simple_image_download
patch_import = """
# Import simple image downloader for more reliable downloading
from .simple_image_download import download_image, create_fallback_image
"""

# Add a new method to the PriceComparisonGenerator class
patch_method = """
    async def download_game_image(self, image_url: str):
        """Download a game image from the provided URL"""
        try:
            # Use the more reliable download function from simple_image_download
            image = download_image(image_url)
            
            if image:
                return image
            else:
                # Create a fallback image
                return create_fallback_image(800, 600, "Game Cover")
                
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return create_fallback_image(800, 600, "Game Cover")
"""

# Function to add the import and method to the file
def patch_file(filename):
    with open(filename, 'r') as f:
        content = f.read()
    
    # Add import after other imports
    import_pos = content.find("import cloudinary.uploader")
    if import_pos > 0:
        content = content[:import_pos + len("import cloudinary.uploader")] + patch_import + content[import_pos + len("import cloudinary.uploader"):]
    
    # Find the download_game_image method and replace it
    download_pos = content.find("async def download_game_image")
    if download_pos > 0:
        # Find the end of the method by looking for the next method definition
        next_method_pos = content.find("async def", download_pos + 10)
        if next_method_pos > 0:
            content = content[:download_pos] + patch_method + content[next_method_pos:]
    
    # Write the patched content back
    with open(filename, 'w') as f:
        f.write(content)
    
    print(f"Successfully patched {filename}")

# Make a backup first
import shutil
shutil.copy2("modules/module0_price.py", "modules/module0_price.py.backup")

# Patch the file
patch_file("modules/module0_price.py")
print("Done! Please test the module now.")
