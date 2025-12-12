import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get HeyGen API key
API_KEY = os.getenv("HEYGEN_API_KEY")

def list_avatars():
    """List all available avatars"""
    url = "https://api.heygen.com/v2/avatar"
    
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": API_KEY
    }
    
    print(f"Checking available avatars with API key: {API_KEY[:5]}...{API_KEY[-4:]}")
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            avatars = data.get('data', {}).get('avatars', [])
            
            if avatars:
                print(f"\n✅ Found {len(avatars)} avatars!")
                print("\nAvailable avatars:")
                for i, avatar in enumerate(avatars, 1):
                    print(f"{i}. ID: {avatar.get('id')}, Name: {avatar.get('name', 'Unnamed')}")
                    # Print additional details for the first few avatars
                    if i <= 3:
                        print(f"   Details: {json.dumps(avatar, indent=2)}\n")
            else:
                print("\n❌ No avatars found in the response.")
                print(f"Response: {json.dumps(data, indent=2)}")
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        
def test_v2_avatar_generation():
    """Try v2 avatar generation with the most basic possible options"""
    url = "https://api.heygen.com/v2/video/generate"
    
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": API_KEY
    }
    
    # Try with the most minimal possible payload
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": "ar-female-1" # Try a generic ID that might exist
                },
                "voice": {
                    "type": "text",
                    "input_text": "This is a simple test of the HeyGen API.",
                    "voice_id": "en-US-1" # Try a generic voice ID
                }
            }
        ]
    }
    
    print("\nTrying v2 avatar generation with minimal payload:")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Success! Response: {json.dumps(data, indent=2)}")
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"\n❌ Exception: {e}")

if __name__ == "__main__":
    if not API_KEY:
        print("Error: HEYGEN_API_KEY environment variable is not set.")
        exit(1)
    
    # First list available avatars
    list_avatars()
    
    # Then try a basic v2 generation
    test_v2_avatar_generation()
