import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get HeyGen API key
API_KEY = os.getenv("HEYGEN_API_KEY")

def check_api_version():
    """Check what version of the HeyGen API is available"""
    endpoints = [
        # Basic health check endpoints
        "https://api.heygen.com/health",
        "https://api.heygen.com/v1/health",
        "https://api.heygen.com/v2/health",
        
        # Version check endpoints
        "https://api.heygen.com/version",
        "https://api.heygen.com/v1/version",
        "https://api.heygen.com/v2/version",
        
        # Documentation endpoints
        "https://api.heygen.com/docs",
        "https://api.heygen.com/v1/docs",
        "https://api.heygen.com/v2/docs"
    ]
    
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": API_KEY
    }
    
    print(f"Using HeyGen API key: {API_KEY[:5]}...{API_KEY[-4:] if len(API_KEY) > 8 else ''}")
    print(f"Checking available HeyGen API versions...")
    
    working_endpoints = []
    
    for endpoint in endpoints:
        try:
            print(f"\nTrying: {endpoint}")
            response = requests.get(endpoint, headers=headers)
            print(f"Status: {response.status_code}")
            
            if response.status_code < 400:  # Any non-error response
                print(f"✅ Accessible endpoint found: {endpoint}")
                working_endpoints.append(endpoint)
                try:
                    content = response.json()
                    print(f"Response: {json.dumps(content, indent=2)}")
                except:
                    print(f"Raw response: {response.text[:200]}")
            else:
                print(f"❌ Endpoint not accessible: {response.status_code}")
                try:
                    error = response.json()
                    print(f"Error: {json.dumps(error, indent=2)}")
                except:
                    print(f"Raw error: {response.text[:200]}")
        except Exception as e:
            print(f"❌ Error accessing {endpoint}: {e}")
            
    return working_endpoints

def check_api_authorization():
    """Check what resources can be accessed with the current API key"""
    resource_endpoints = [
        # v1 endpoints
        "https://api.heygen.com/v1/avatar",
        "https://api.heygen.com/v1/avatar/list",
        "https://api.heygen.com/v1/voice",
        "https://api.heygen.com/v1/voice/list",
        "https://api.heygen.com/v1/video.list",
        "https://api.heygen.com/v1/template/list",
        
        # v2 endpoints
        "https://api.heygen.com/v2/avatar",
        "https://api.heygen.com/v2/voice",
        "https://api.heygen.com/v2/video",
        "https://api.heygen.com/v2/template"
    ]
    
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": API_KEY
    }
    
    print("\n\nChecking accessible resources...")
    
    for endpoint in resource_endpoints:
        try:
            print(f"\nTrying resource: {endpoint}")
            response = requests.get(endpoint, headers=headers)
            print(f"Status: {response.status_code}")
            
            if response.status_code < 400:  # Any non-error response
                print(f"✅ Resource accessible: {endpoint}")
                try:
                    content = response.json()
                    # Just show a summary if the response is large
                    if len(str(content)) > 500:
                        print(f"Response summary (truncated): {str(content)[:100]}...")
                    else:
                        print(f"Response: {json.dumps(content, indent=2)}")
                except:
                    print(f"Raw response: {response.text[:200]}")
            else:
                print(f"❌ Resource not accessible: {response.status_code}")
                try:
                    error = response.json()
                    print(f"Error: {json.dumps(error, indent=2)}")
                except:
                    print(f"Raw error: {response.text[:200]}")
        except Exception as e:
            print(f"❌ Error accessing resource {endpoint}: {e}")

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: HEYGEN_API_KEY environment variable is not set.")
        exit(1)
    
    # Check API version
    working_endpoints = check_api_version()
    
    if working_endpoints:
        print(f"\n✅ Found {len(working_endpoints)} working endpoints.")
    else:
        print("\n❌ No HeyGen API endpoints are accessible.")
        print("RECOMMENDATIONS:")
        print("1. Check if your HeyGen API key is valid")
        print("2. Check if you have the correct permissions")
        print("3. Check if HeyGen's API has changed")
    
    # Check resource access
    check_api_authorization()
