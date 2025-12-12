import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API key from environment
API_KEY = os.getenv("HEYGEN_API_KEY")

def get_template_structure(template_id):
    """Get template structure from HeyGen API"""
    url = f"https://api.heygen.com/v2/template/{template_id}"
    
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": API_KEY
    }
    
    print(f"Getting structure for template ID: {template_id}")
    response = requests.get(url, headers=headers)
    
    print(f"Status code: {response.status_code}")
    try:
        json_data = response.json()
        print(f"Response JSON: {json.dumps(json_data, indent=2)}")
        
        # Check for variables structure
        if "variables" in json_data:
            print("\nVariables structure:")
            for var_name, var_structure in json_data["variables"].items():
                print(f"  - {var_name}: {var_structure}")
            
        return json_data
    except:
        print(f"Raw response: {response.text}")
        return None

def list_templates():
    """List all available templates"""
    url = "https://api.heygen.com/v2/template"
    
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": API_KEY
    }
    
    print("Listing available templates...")
    response = requests.get(url, headers=headers)
    
    print(f"Status code: {response.status_code}")
    try:
        json_data = response.json()
        templates = json_data.get("data", {}).get("templates", [])
        print(f"Found {len(templates)} templates")
        
        for i, template in enumerate(templates, 1):
            print(f"{i}. ID: {template.get('id')}, Name: {template.get('name')}")
        
        return templates
    except:
        print(f"Raw response: {response.text}")
        return []

if __name__ == "__main__":
    if not API_KEY:
        print("Error: HEYGEN_API_KEY environment variable is not set.")
        exit(1)
        
    print(f"Using HeyGen API key: {API_KEY[:5]}...{API_KEY[-4:]}")
    
    # List all templates first
    templates = list_templates()
    
    if not templates:
        print("No templates found or error occurred.")
        exit(1)
    
    # Check if we have any templates to inspect
    if templates:
        # Get structure for specific template
        template_id_to_check = templates[0].get('id')  # Check first template
        get_template_structure(template_id_to_check)
        
        # Additional specific template to check
        specific_id = "9f7cd606790b4a61a241bcafd4b67df0"  # The ID we've been using
        if specific_id:
            print(f"\nChecking specific template ID: {specific_id}")
            get_template_structure(specific_id)
