#!/usr/bin/env python3
"""
Railway deployment entry point - PRODUCTION ONLY
Preserves all current working settings and configuration
"""
import os
import sys
import uvicorn
from dotenv import load_dotenv
from environment_manager import env_manager

# Load environment variables
load_dotenv()

def validate_api_keys():
    """Validate that all required API keys are present for production"""
    required_keys = {
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'HEYGEN_API_KEY': os.getenv('HEYGEN_API_KEY'),
        'VIZARD_API_KEY': os.getenv('VIZARD_API_KEY'),
        'CREATOMATE_API_KEY': os.getenv('CREATOMATE_API_KEY')
    }
    
    missing_keys = [key for key, value in required_keys.items() if not value]
    
    if missing_keys:
        print(f"❌ PRODUCTION ERROR: Missing required API keys: {', '.join(missing_keys)}")
        print("🚨 Production deployment requires ALL API keys to be set!")
        print("Please set the missing keys in Railway environment variables.")
        raise Exception(f"Missing required API keys for production: {', '.join(missing_keys)}")
    else:
        print("✅ All required API keys are present for production")
        for key in required_keys.keys():
            print(f"  {key}: {'✓ SET' if required_keys[key] else '✗ MISSING'}")

def main():
    try:
        # Print environment information
        env_manager.print_environment_info()
        
        # Ensure we're in production mode
        if not env_manager.environment == 'railway_production':
            print("❌ ERROR: This script should only run in Railway production!")
            print("🔧 For local development, use: python3 start_development.py")
            sys.exit(1)
        
        # Validate API keys before starting
        print("Validating API keys...")
        validate_api_keys()
        
        # Import the PRODUCTION API server (real APIs only)
        print("Importing PRODUCTION API server...")
        from api_server_production import app
        print("✅ PRODUCTION API server imported successfully")
        
        # Get port from Railway environment variable
        port = int(os.environ.get("PORT", 8000))
        print(f"Starting server on port {port}")
        
        # Start the FastAPI server with same config as local
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=port, 
            log_level="info",
            access_log=True
        )
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
