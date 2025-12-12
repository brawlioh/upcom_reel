#!/usr/bin/env python3
"""
Script to register a webhook endpoint with HeyGen
"""

import os
import requests
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Get the API key from environment
heygen_api_key = os.getenv('HEYGEN_API_KEY')
if not heygen_api_key:
    print("❌ Error: HEYGEN_API_KEY not found in environment variables")
    exit(1)

# Allow user to input webhook URL or use default
webhook_url = input("Enter your webhook URL (or press Enter to use default ngrok URL): ")
if not webhook_url:
    webhook_url = "https://etymologic-mimi-postoral.ngrok-free.dev/api/webhooks/heygen"
    print(f"Using default webhook URL: {webhook_url}")

# HeyGen webhook registration endpoint
url = "https://api.heygen.com/v1/webhook/endpoint.add"

# Payload for registering webhook
payload = {
    "url": webhook_url
}

# Headers with API key
headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "x-api-key": heygen_api_key
}

# Make the request
print(f"\n🔗 Registering webhook URL with HeyGen: {webhook_url}")
try:
    response = requests.post(url, json=payload, headers=headers)
    
    # Pretty print response
    print("\n📥 Response from HeyGen:")
    print(f"HTTP Status: {response.status_code}")
    try:
        json_response = response.json()
        print(json.dumps(json_response, indent=2))
    except:
        print(response.text)
    
    # Check if successful
    if response.status_code == 200 or response.status_code == 201:
        print("\n✅ Webhook successfully registered with HeyGen!")
        print("\nNow, when you generate videos with HeyGen, status updates will be sent to your webhook URL.")
    else:
        print("\n❌ Failed to register webhook")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
