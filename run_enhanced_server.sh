#!/bin/bash

echo "🚀 Starting Enhanced YouTube Reels Automation API..."
echo "💡 This server includes better error handling for the frontend"

# Kill any running server on port 8001
lsof -i :8001 | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null

# Start the enhanced server
python3 api_server_enhanced.py
