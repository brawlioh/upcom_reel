# HeyGen Webhook Integration

This document explains how the HeyGen webhook integration works to improve reliability and performance of the video generation pipeline.

## Overview

Instead of continuously polling the HeyGen API to check if a video is ready, we use webhooks to let HeyGen notify us when the video generation is complete. This approach:

1. Reduces API calls to HeyGen
2. Decreases latency in detecting when videos are complete
3. Improves reliability by eliminating polling timeouts
4. Prevents WebSocket errors seen previously

## Official Webhook Registration

HeyGen provides an official API endpoint to register your webhook URL:

```python
import requests

url = "https://api.heygen.com/v1/webhook/endpoint.add"

payload = { "url": "https://your-webhook-url.com/api/webhooks/heygen" }
headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "x-api-key": "YOUR_HEYGEN_API_KEY"
}

response = requests.post(url, json=payload, headers=headers)
```

We've included a utility script to help with this registration:
```bash
python register_heygen_webhook.py
```

## How It Works

1. When we send a video generation request to HeyGen, we include a `webhook_url` parameter
2. HeyGen will call this URL when the video is complete (or if it fails)
3. Our API server receives this notification and stores the video information
4. The application checks our local API server for updates before falling back to direct HeyGen API polling

## Setup Instructions

### 1. Install ngrok

Ngrok creates a secure tunnel to your local machine, making your local API server accessible from the internet:

```bash
sudo npm install -g ngrok
```

### 2. Run ngrok

```bash
ngrok http 8000
```

This will display a URL like `https://your-id.ngrok-free.dev` that forwards to your local server.

### 3. Update the webhook URL

In `modules/module1_intro.py`, update the webhook_url:

```python
webhook_url = "https://your-id.ngrok-free.dev/api/webhooks/heygen"
```

### 4. Test the webhook

You can test if your webhook is accessible by:

```bash
curl -X POST https://your-id.ngrok-free.dev/api/webhooks/heygen \
  -H "Content-Type: application/json" \
  -d '{"video_id": "test", "status": "completed", "video_url": "https://example.com/test.mp4"}'
```

### 5. Restart the API server

```bash
python3 api_server.py
```

## Troubleshooting

If you encounter webhook issues:

1. Check ngrok is running and the URL is correct
2. Ensure your API server is running on port 8000
3. Check the logs for webhook requests in the API server output
4. Verify HeyGen supports webhooks for your account level

The system will automatically fall back to API polling if webhooks fail, but using webhooks is strongly recommended for better reliability.
