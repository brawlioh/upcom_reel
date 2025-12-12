#!/usr/bin/env python3

"""
This script fixes the module0_price.py file by replacing the problematic functions
with corrected versions.
"""

import os
import re

# Paths
module_path = "modules/module0_price.py"
fixed_cloudinary_path = "modules/fixed_cloudinary.py"
fixed_download_path = "modules/fixed_download.py"
backup_path = "modules/module0_price.py.bak2"

# Make another backup
if os.path.exists(module_path):
    print(f"Making backup of {module_path} to {backup_path}")
    with open(module_path, 'r') as src, open(backup_path, 'w') as dst:
        dst.write(src.read())

# Read the fixed functions
with open(fixed_cloudinary_path, 'r') as f:
    fixed_cloudinary = f.read()
    # Extract just the function definition
    cloudinary_func = re.search(r'async def upload_to_cloudinary.*?return str\(file_path\)', 
                               fixed_cloudinary, re.DOTALL).group(0)

with open(fixed_download_path, 'r') as f:
    fixed_download = f.read()
    # Extract just the function definition
    download_func = re.search(r'async def download_game_image.*?return None', 
                             fixed_download, re.DOTALL).group(0)

# Read the current module
with open(backup_path, 'r') as f:
    module_content = f.read()

# Replace the problematic functions
# 1. First, fix the upload_to_cloudinary function
pattern_cloudinary = r'async def upload_to_cloudinary.*?return str\(file_path\)'
fixed_module = re.sub(pattern_cloudinary, cloudinary_func, module_content, flags=re.DOTALL)

# 2. Then fix the download_game_image function
pattern_download = r'async def download_game_image.*?return None'
fixed_module = re.sub(pattern_download, download_func, fixed_module, flags=re.DOTALL)

# Write the fixed module
with open(module_path, 'w') as f:
    f.write(fixed_module)

print(f"Fixed {module_path} with corrected functions")
print("You can now run the module and it should work correctly.")
