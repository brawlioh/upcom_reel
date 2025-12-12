import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get HeyGen API key
API_KEY = os.getenv("HEYGEN_API_KEY")

def list_available_videos():
    """List available videos to understand what's available in the account"""
    url = "https://api.heygen.com/v1/video.list"
    
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": API_KEY
    }
    
    print(f"Using HeyGen API key: {API_KEY[:5]}...{API_KEY[-4:] if len(API_KEY) > 8 else ''}")
    print(f"Getting available videos...")
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response structure: {json.dumps(data.keys() if isinstance(data, dict) else 'Not a dict', indent=2)}")
            
            videos = data.get('data', {}).get('videos', [])
            if videos:
                print(f"\n✅ Found {len(videos)} videos")
                
                # Analyze the first video to understand the structure
                if len(videos) > 0:
                    first_video = videos[0]
                    print(f"\nFirst video structure:")
                    print(f"Keys: {list(first_video.keys())}")
                    
                    # Show details of the first few videos
                    for i, video in enumerate(videos[:5]):
                        print(f"\nVideo {i+1}:")
                        print(f"  ID: {video.get('video_id')}")
                        print(f"  Status: {video.get('status')}")
                        if 'url' in video:
                            print(f"  URL: {video.get('url')}")
                        if 'template_id' in video:
                            print(f"  Template ID: {video.get('template_id')}")
            else:
                print("\n❌ No videos found.")
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"\n❌ Exception: {e}")

def try_video_generate_endpoint():
    """Try the video.generate endpoint specifically"""
    url = "https://api.heygen.com/v1/video.generate"
    
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": API_KEY
    }
    
    # Try the most basic possible payload
    payload = {
        "video_inputs": [
            {
                "input_text": "This is a simple test of the HeyGen API. I need to see if this endpoint is working.",
                "voice_id": "en_us_001"
            }
        ]
    }
    
    print("\nTrying v1 video.generate endpoint with minimal payload:")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Success! Response: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False

def check_general_authentication():
    """Check if the API key is valid by trying a simple authentication check"""
    url = "https://api.heygen.com/v1/auth/check"
    
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": API_KEY
    }
    
    print("\nChecking API key authentication...")
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status code: {response.status_code}")
        
        if response.status_code < 400:
            print(f"\n✅ API key appears valid!")
            print(f"Response: {response.text}")
            return True
        else:
            print(f"\n❌ API key may be invalid or lacks permissions")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: HEYGEN_API_KEY environment variable is not set.")
        exit(1)
    
    # Check authentication
    auth_valid = check_general_authentication()
    
    # List available videos
    list_available_videos()
    
    # Try video generate endpoint
    generate_works = try_video_generate_endpoint()
    
    # Summary
    print("\n--- SUMMARY ---")
    print(f"API Key Authentication: {'✅ Valid' if auth_valid else '❌ Invalid/Unknown'}")
    print(f"Video Generation Endpoint: {'✅ Working' if generate_works else '❌ Not Working'}")
    
    if not auth_valid or not generate_works:
        print("\nRECOMMENDATIONS:")
        print("1. Check if your HeyGen API key is valid and has not expired")
        print("2. Verify you have sufficient credits in your HeyGen account")
        print("3. Contact HeyGen support to confirm the correct API endpoints to use")
        print("4. Request new API documentation if the current endpoints have changed")
