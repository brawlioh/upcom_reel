import asyncio
import aiohttp
import ssl
import cloudinary
import cloudinary.uploader
import os
import tempfile
import requests
import re
import json
from pathlib import Path
from loguru import logger
from config import Config
from openai import OpenAI
from typing import Dict, Optional, Tuple

class IntroGenerator:
    """
    Generates intro videos for game presentations using HeyGen API.
    
    Features:
    - Script generation using OpenAI
    - Video generation with HeyGen
    """
    def __init__(self):
        try:
            self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        except Exception as e:
            logger.warning(f"OpenAI client initialization failed: {e}")
            self.openai_client = None
        self.config = Config
        # Initialize Cloudinary
        cloudinary.config(
            cloud_name=Config.CLOUDINARY_CLOUD_NAME,
            api_key=Config.CLOUDINARY_API_KEY,
            api_secret=Config.CLOUDINARY_API_SECRET
        )
    
    def _clean_trademark_symbols(self, script: str) -> str:
        """Remove trademark symbols and company references from script"""
        import re
        
        # Remove trademark symbols
        trademark_symbols = ['™', '®', '©', 'TM', 'SM', '(TM)', '(R)', '(C)']
        for symbol in trademark_symbols:
            script = script.replace(symbol, '')
        
        # Remove common company/trademark patterns
        patterns_to_remove = [
            r'\b(Inc\.?|LLC|Ltd\.?|Corporation|Corp\.?)\b',  # Company suffixes
            r'\b(Studios?|Entertainment|Games?|Interactive)\b(?=\s|$)',  # Game company words
            r'\bTrademark\b',  # The word "Trademark"
            r'\bAll rights reserved\b',  # Rights text
        ]
        
        for pattern in patterns_to_remove:
            script = re.sub(pattern, '', script, flags=re.IGNORECASE)
        
        # Clean up extra spaces and normalize
        script = ' '.join(script.split())
        
        logger.info(f"Cleaned script of trademark symbols: {script}")
        return script
    
    async def generate_intro_script(self, game_title: str, game_details: Dict = None) -> str:
        """Generate intro script using OpenAI"""
        try:
            # Ensure we have a valid game title from either parameter or game_details
            if not game_title and game_details:
                if 'title' in game_details:
                    game_title = game_details['title']
                elif 'name' in game_details:
                    game_title = game_details['name']
                else:
                    game_title = "Unknown Game"
            
            logger.info(f"Generating intro script for {game_title}")
            
            # Clean game title of trademark symbols before using in script
            clean_game_title = self._clean_trademark_symbols(game_title)
            
            # Build context from game details
            context = f"Game: {clean_game_title}"
            if game_details:
                if game_details.get('developer'):
                    context += f"\nDeveloper: {game_details['developer']}"
                if game_details.get('release_date'):
                    context += f"\nRelease Date: {game_details['release_date']}"
                if game_details.get('description'):
                    context += f"\nDescription: {game_details['description'][:200]}..."
                if game_details.get('genres'):
                    context += f"\nGenres: {', '.join(game_details['genres'][:3])}"
                
                # Intentionally skipping price information
                if game_details.get('editions'):
                    context += f"\nEditions: {', '.join(game_details.get('editions', []))}"
                if game_details.get('platforms'):
                    context += f"\nPlatforms: {', '.join(game_details.get('platforms', []))}"
                if game_details.get('updates'):
                    context += f"\nLatest Updates: {game_details.get('updates', 'No recent updates')}"
            
            # Extract and format release date for script context
            release_date_context = ""
            if game_details and game_details.get('release_date'):
                release_date = game_details['release_date']
                if release_date and release_date != "Unknown":
                    # Smart release date formatting for different formats
                    release_lower = release_date.lower()
                    
                    # Handle different date formats
                    if "2024" in release_date or "2025" in release_date or "2026" in release_date or "2027" in release_date:
                        # Future releases
                        if "coming soon" in release_lower or "tba" in release_lower:
                            release_date_context = "coming soon"
                        elif "q1" in release_lower or "q2" in release_lower or "q3" in release_lower or "q4" in release_lower:
                            release_date_context = f"dropping {release_date}"
                        elif "early access" in release_lower:
                            release_date_context = f"in early access {release_date}"
                        else:
                            release_date_context = f"releasing {release_date}"
                    elif "2023" in release_date or "2022" in release_date:
                        # Recent releases
                        release_date_context = f"now available since {release_date}"
                    else:
                        # Generic format
                        release_date_context = f"available {release_date}"

            prompt = f"""
            Create a concise intro script for a YouTube Reel about the game "{clean_game_title}". The script should be 1 minute or less and include:

            1. A quick introduction about "{clean_game_title}" - what type of game it is and what makes it special
            2. Release date and latest updates - mention when it was released or will release and any recent significant updates
            3. Game editions - mention any special editions or versions if available
            4. Available platforms - list which platforms the game can be played on
            5. End with an enthusiastic call to action for the viewer to check out the game

            Requirements:
            - Keep it under 1 minute when spoken (concise and to the point)
            - Energetic and engaging tone
            - Make sure to cover ALL the requested information points
            - EXCLUDE all trademarks, logos, and symbols (™, ®, ©, TM)
            - Do NOT include company names or trademark references
            - Do NOT include any price information, comparisons, or store references
            - End with an exciting call to action

            Context: {context}
            
            Script format: Just return the script text, no additional formatting.
            """
            
            if self.openai_client:
                response = await asyncio.to_thread(
                    self.openai_client.chat.completions.create,
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a gaming content creator who creates comprehensive but concise game information scripts for YouTube videos. Your scripts include: game introductions, release dates, latest updates, game editions, available platforms, and always end with an exciting call to action for viewers. Keep scripts informative, engaging, and under 1 minute when spoken. NEVER include trademarks, logos, company names, or symbols like ™, ®, ©, TM. Focus on factual information about the games. Do NOT include any price information, comparisons, or store references."
                        },
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ],
                    max_tokens=500,
                    temperature=0.8
                )
                script = response.choices[0].message.content.strip()
                
                # Clean any trademark symbols that might have appeared
                script = self._clean_trademark_symbols(script)
                
            else:
                logger.error("OpenAI API not available")
                raise Exception("OpenAI API is required for script generation")
            
            logger.info(f"Generated intro script: {script[:50]}...")
            return script
            
        except Exception as e:
            logger.error(f"Error generating intro script: {e}")
            raise Exception(f"OpenAI API failed for intro script generation: {e}")

    async def generate_heygen_video(self, script: str, game_title: str) -> Optional[str]:
        """Generate video using HeyGen API - Template-based approach with the correct format"""
        try:
            logger.info(f"Generating HeyGen video for {game_title}")
            
            # Use the updated template ID provided by user
            template_id = "cca04f1fe06e427293a1b162db6b59cc"  # Updated template with built-in stylized subtitles
            
            # Validate template ID format (should be 32 hex characters)
            if not re.match(r'^[0-9a-f]{32}$', template_id):
                logger.warning(f"Template ID '{template_id}' doesn't match expected format (32 hex characters)")
            
            # Using the reference format that's known to work
            url = f"https://api.heygen.com/v2/template/{template_id}/generate"
            logger.info(f"Using HeyGen API endpoint: {url} (based on working reference)")
            
            # Don't use webhook URL as it's causing connection issues
            webhook_url = None
            logger.info("Skipping webhook URL to avoid connection issues")
            
            headers = {
                'X-Api-Key': Config.HEYGEN_API_KEY,
                'accept': 'application/json',
                'content-type': 'application/json'
            }
            
            # Format the script to match the screenshot style with "ABOUT GAME_TITLE"
            # The template has a specific style for "ABOUT X" as shown in the reference
            formatted_script = f"About {game_title}. {script[:700] if len(script) > 700 else script}"
            
            # Payload format based on the working reference example
            payload = {
                "caption": True,  # Enable captions for the video (required for burned-in captions)
                "dimension": {
                    "width": 720,
                    "height": 1280
                },
                "include_gif": True,
                "title": f"Intro for {game_title}",
                "variables": {
                    "script": {
                        "name": "script",
                        "type": "text",
                        "properties": {
                            "content": formatted_script
                        }
                    }
                }
            }
            
            # Only add webhook if specified (which we're now skipping to avoid connection issues)
            if webhook_url:
                logger.info(f"Using webhook URL: {webhook_url}")
                payload["webhook"] = {
                    "url": webhook_url
                }
            else:
                logger.info("No webhook URL specified - skipping webhook to avoid connection issues")
            
            # Log the payload for debugging
            logger.info(f"Payload being sent: {json.dumps(payload)}")
            
            # Log the approach being used
            logger.info(f"Using HeyGen v2 template API with reference-based format")
            logger.info(f"Template ID being used: {template_id}")
            logger.info(f"Script length: {len(formatted_script)} characters")
            logger.info(f"Game title: {game_title}")
            logger.info(f"Using endpoint: {url}")
            logger.info(f"Payload structure matches working reference example")
            logger.info(f"Setting caption: True to enable standard captions")
            logger.info(f"Will download video with burned-in captions using ?captioned=true parameter")
            
            # Create SSL context that doesn't verify certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                # Call HeyGen v2 template generate API
                logger.info(f"Calling HeyGen API: {url} using reference-based format")
                async with session.post(
                    url,
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200 or response.status == 201 or response.status == 202:
                        result = await response.json()
                        logger.info(f"Success response: {json.dumps(result)}")
                        
                        # Extract task_id or video_id from response
                        data = result.get('data', {})
                        task_id = data.get('task_id') or data.get('video_id') or data.get('id')
                        
                        if not task_id:
                            logger.error(f"No task_id found in response: {json.dumps(result)}")
                            logger.error(f"Response data fields: {list(data.keys()) if data else 'None'}")
                            logger.error(f"Expected one of: 'task_id', 'video_id', or 'id' in the data object")
                        
                        # Print full response for debugging
                        logger.info(f"API Response: {result}")
                        
                        if task_id:
                            logger.info(f"Success! Got task ID: {task_id} from HeyGen Template API")
                            # Poll for completion and get URL
                            video_url = await self._poll_heygen_status(session, headers, task_id)
                            
                            if video_url and video_url.startswith('http'):
                                logger.info(f"Got video URL: {video_url}")
                                
                                # Check if this is a dashboard URL (can't be downloaded automatically)
                                if "app.heygen.com/videos" in video_url:
                                    dashboard_url = video_url
                                    logger.error(f"HeyGen returned dashboard URL instead of downloadable URL: {dashboard_url}")
                                    raise Exception(f"HeyGen video ready but requires manual download. Dashboard URL: {dashboard_url}")
                                
                                # Attempt automatic download
                                cloudinary_url = await self._download_video(session, video_url, game_title, "intro")
                                if cloudinary_url:
                                    logger.info(f"✅ HeyGen video processed and uploaded to Cloudinary: {cloudinary_url}")
                                    return cloudinary_url
                                else:
                                    raise Exception(f"Failed to download/upload video from URL: {video_url}")
                            else:
                                raise Exception("Failed to get valid video URL from polling")
                        else:
                            raise Exception("HeyGen Template API returned no task ID")
                    else:
                        error_text = await response.text()
                        error_msg = f"HeyGen Template API error: {response.status} - {error_text}"
                        logger.error(error_msg)
                        
                        # Add more detailed debugging information
                        logger.error(f"Request details:\nURL: {url}\nHeaders: {headers}\nPayload: {json.dumps(payload)}")
                        logger.error(f"Make sure your template variables match what's expected in the HeyGen dashboard")
                        
                        # Look for specific error codes
                        try:
                            error_data = json.loads(error_text)
                            error_code = error_data.get('error', {}).get('code')
                            error_message = error_data.get('error', {}).get('message')
                            
                            if error_code == "invalid_parameter":
                                # Handle various common error messages
                                if "variables is invalid" in error_message:
                                    logger.error("ERROR: This template doesn't use a 'variables' object. Try putting text_input directly at the root level.")
                                    logger.error("SOLUTION: Use payload = {\"text_input\": formatted_script, \"caption\": true}")
                                elif "variables.text_input is invalid" in error_message:
                                    logger.error("ERROR: text_input should be a string directly in the root payload, not in variables.")
                                    logger.error("SOLUTION: Move text_input out of the variables object")
                                elif "text_input is invalid" in error_message:
                                    logger.error("ERROR: The text_input format is not what the template expects")
                                    logger.error("SOLUTION: Check the template in HeyGen dashboard to see the expected format")
                                else:
                                    logger.error(f"ERROR: Invalid parameter: {error_message}")
                                    logger.error(f"SOLUTION: Check the template requirements in HeyGen dashboard")
                            elif error_code == "unauthorized" or response.status == 401:
                                logger.error("ERROR: API key is invalid or expired.")
                                logger.error("SOLUTION: Check your HEYGEN_API_KEY in the config and verify it in HeyGen dashboard")
                                    
                            # Always log the full payload for debugging
                            logger.error(f"Request payload was: {json.dumps(payload)}")
                        except json.JSONDecodeError:
                            # Not valid JSON, continue with generic error
                            logger.error(f"Non-JSON error response: {error_text}")
                            
                        raise Exception(error_msg)
        
        except Exception as e:
            logger.error(f"Error generating HeyGen video: {e}")
            # Log that we're exiting with a clear error
            logger.critical("❌ HeyGen video generation failed! As requested, not using fallback video.")
            # Re-raise the exception to stop execution
            raise Exception(f"HeyGen API error: {e}")
    
    async def _poll_heygen_status(self, session: aiohttp.ClientSession, headers: Dict, task_id: str) -> Optional[str]:
        """Poll HeyGen API for video completion status directly via API polling"""
        max_attempts = 360  # 30 minutes with 5-second intervals (increased from 10 to 30 minutes)
        attempt = 0
        
        # Store dashboard URL for direct access if API fails
        dashboard_url = f"https://app.heygen.com/videos/{task_id}"
        logger.info(f"🎥 HeyGen video being processed. Dashboard URL: {dashboard_url}")
        
        # Skip webhook checks as they're causing WebSocket connection issues
        logger.info("Skipping webhook checks and using API polling directly to avoid WebSocket connection issues")
        
        # Use the most reliable API status endpoint first
        # Only try alternatives if the primary endpoint fails consistently
        primary_endpoint = f"https://api.heygen.com/v2/task/{task_id}"  # V2 API format is most reliable
        backup_endpoints = [
            f"https://api.heygen.com/v1/video_status.get?video_id={task_id}",  # V1 fallback
            f"https://api.heygen.com/v1/video.status?video_id={task_id}"       # Alternative V1 format
        ]
        
        # Start with just the primary endpoint for faster checks
        status_endpoints = [primary_endpoint]
        failed_primary_checks = 0  # Track primary endpoint failures
        
        # Make sure headers match exactly what works in the reference code
        api_headers = {
            "accept": "application/json",
            "x-api-key": Config.HEYGEN_API_KEY
        }
        
        # Main polling loop with extended timeout
        while attempt < max_attempts:
            # Try the current endpoint selection (starts with just primary, adds backups if needed)
            primary_failed_this_round = True  # Assume failure until proven otherwise
            
            for endpoint_idx, status_endpoint in enumerate(status_endpoints):
                try:
                    # Only log every 5th attempt to reduce console spam
                    if attempt % 5 == 0:
                        logger.info(f"Checking HeyGen status endpoint: {status_endpoint.split('?')[0]}")
                    
                    async with session.get(status_endpoint, headers=api_headers) as response:
                        if response.status == 200:
                            # Reset failure counter for primary endpoint
                            if status_endpoint == primary_endpoint:
                                failed_primary_checks = 0
                                primary_failed_this_round = False
                                
                            result = await response.json()
                            data = result.get('data', result)  # Handle both formats
                            status = data.get('status')
                            state = data.get('state')
                            
                            # Only log status every 5th attempt to reduce console spam
                            if attempt % 5 == 0 or status in ['completed', 'complete', 'ready', 'done', 'success'] or state in ['completed', 'complete', 'ready', 'done', 'success']:
                                logger.info(f"HeyGen status: {status or state or 'unknown'} (attempt {attempt + 1})")
                            
                            # Process is considered complete if either status or state indicates completion
                            is_completed = False
                            if status and status.lower() in ['completed', 'complete', 'ready', 'done', 'success']:
                                is_completed = True
                            elif state and state.lower() in ['completed', 'complete', 'ready', 'done', 'success']:
                                is_completed = True
                            
                            # If video is complete, extract URL with a simplified approach
                            if is_completed:
                                # Prefer captioned URL if available (matches Make/HeyGen screenshot "video_url_caption")
                                video_url = (
                                    data.get('video_url_caption')
                                    or data.get('video_url')
                                    or data.get('url')
                                )
                                
                                # If not found at top level, check nested structures
                                if not video_url:
                                    # Check in nested data
                                    nested_data = data.get('data', {})
                                    if isinstance(nested_data, dict):
                                        video_url = (
                                            nested_data.get('video_url_caption')
                                            or nested_data.get('video_url')
                                            or nested_data.get('url')
                                        )
                                    
                                    # Check in result
                                    if not video_url:
                                        result_data = data.get('result', {})
                                        if isinstance(result_data, dict):
                                            video_url = (
                                                result_data.get('video_url_caption')
                                                or result_data.get('video_url')
                                                or result_data.get('url')
                                            )
                                
                                # Return URL if valid
                                if video_url and isinstance(video_url, str) and video_url.startswith('http'):
                                    logger.info(f"✅ Found HeyGen video URL: {video_url}")
                                    
                                    # Extract video ID from URL for direct API download
                                    try:
                                        # Try to extract video ID from URL path
                                        from urllib.parse import urlparse
                                        path_parts = urlparse(video_url).path.split('/')
                                        video_id = None
                                        for part in path_parts:
                                            if part and len(part) > 20:  # Video IDs are typically long strings
                                                video_id = part
                                                break
                                        
                                        # Use video ID for captioned download
                                        if video_id:
                                            logger.info(f"🔤 Found video ID for captioned download: {video_id}")
                                            
                                            # Rather than returning a dict, call the download API directly here
                                            download_api_url = "https://api.heygen.com/v1/video.download"
                                            download_headers = {
                                                "accept": "application/json",
                                                "content-type": "application/json",
                                                "x-api-key": Config.HEYGEN_API_KEY
                                            }
                                            download_payload = {
                                                "video_id": video_id,
                                                "captioned": True
                                            }
                                            
                                            logger.info(f"Requesting captioned video download URL from HeyGen API")
                                            async with session.post(download_api_url, json=download_payload, headers=download_headers) as download_response:
                                                if download_response.status == 200:
                                                    download_result = await download_response.json()
                                                    download_url = download_result.get('data', {}).get('url')
                                                    if download_url:
                                                        logger.info(f"✅ Successfully obtained URL for video WITH captions: {download_url}")
                                                        return download_url
                                                    else:
                                                        logger.warning(f"HeyGen download API didn't return a URL: {download_result}")
                                                else:
                                                    error_text = await download_response.text()
                                                    logger.warning(f"HeyGen download API error: {download_response.status} - {error_text}")
                                    except Exception as e:
                                        logger.warning(f"Error extracting video ID or using download API: {e}")
                                    
                                    # Just return the direct URL as a fallback
                                    return video_url
                                else:
                                    logger.warning("Video marked as complete but URL not found in response")
                            
                            # Handle failed status
                            elif (status and status.lower() == 'failed') or (state and state.lower() == 'failed'):
                                logger.warning(f"HeyGen reports process failure")
                                error_msg = data.get('error', {}).get('message') or "Unknown error"
                                logger.warning(f"Error details: {error_msg}")
                                # Don't raise exception yet - continue checking in case it's recoverable
                            
                            # Exit this endpoint loop since we got a valid response
                            break
                        else:
                            if status_endpoint == primary_endpoint:
                                primary_failed_this_round = True
                                
                            # Only log error details every few attempts
                            if attempt % 5 == 0:
                                response_text = await response.text()
                                logger.warning(f"HeyGen status check failed with HTTP {response.status}")
                except Exception as e:
                    if status_endpoint == primary_endpoint:
                        primary_failed_this_round = True
                        
                    # Only log errors every few attempts
                    if attempt % 5 == 0:
                        logger.warning(f"Error checking status: {str(e)[:100]}")
            
            # If primary endpoint failed, increment counter
            if primary_failed_this_round:
                failed_primary_checks += 1
                
                # After 3 consecutive failures of primary endpoint, add backup endpoints
                if failed_primary_checks == 3 and len(status_endpoints) == 1:
                    status_endpoints.extend(backup_endpoints)
                    logger.info("Adding backup endpoints after primary endpoint failures")
            
            # Increment attempt counter
            attempt += 1
            
            # Third attempt: Try to scrape the HeyGen dashboard directly
            # After a certain number of attempts, try to check the dashboard for the video URL
            if attempt % 30 == 0:  # Every 30 attempts (2.5 minutes), try to scrape the dashboard
                # Just log a reminder that the video should be available on the dashboard
                logger.info(f"⏱️ HeyGen processing taking longer than expected. Video should be available at: {dashboard_url} once complete.")
                
                # Option to manually get the video URL from the dashboard in the future
                # We could implement this feature if needed
            
            # Sleep interval - keep it shorter to check more frequently
            # This will speed up detection of completed videos
            if attempt < 20:      # First minute: check every 3 seconds
                await asyncio.sleep(3)
            elif attempt < 120:   # Next 6 minutes: check every 5 seconds 
                await asyncio.sleep(5)
            else:                 # After 7 minutes: check every 10 seconds
                await asyncio.sleep(10)
        
        # As a last resort, return the dashboard URL if we timeout
        logger.warning(f"⚠️ HeyGen video processing is taking longer than expected. Please check the dashboard URL manually: {dashboard_url}")
        return dashboard_url

    async def _download_video(self, session: aiohttp.ClientSession, video_url: str, game_title: str, module_type: str) -> Optional[str]:
        """Download video from URL, save locally, and upload to Cloudinary with improved error handling
        
        Note: If the URL is from the HeyGen download API, it may already include captions burned into the video.
        """
        try:
            # Clean filename for safe storage
            safe_title = "".join(c for c in game_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title}_{module_type}.mp4"
            
            # Ensure directory exists
            save_dir = self.config.ASSETS_PATH / f"{module_type}s"
            save_dir.mkdir(parents=True, exist_ok=True)
            file_path = save_dir / filename
            
            # Check if this is a HeyGen dashboard URL
            if "app.heygen.com/videos" in video_url:
                logger.error(f"Cannot download directly from HeyGen dashboard: {video_url}")
                logger.error(f"Please download the video from the dashboard URL manually")
                # Fail clearly instead of using a fallback
                raise Exception(f"HeyGen dashboard URLs cannot be downloaded automatically: {video_url}")
            
            # Check if this appears to be a captioned video from various indicators
            captioned = False
            if "download" in video_url and "captioned=true" in video_url.lower():
                captioned = True
            elif "v1/video.download" in video_url:
                captioned = True
            elif "captioned" in video_url.lower():
                captioned = True
            
            # Log the URL we'll be using for download
            if captioned:
                logger.info(f"🔤 Downloading video WITH BURNED-IN CAPTIONS from: {video_url}")
            else:
                logger.info(f"Attempting to download video from: {video_url} (no captions confirmed)")
                # Attempt to add captioned parameter if not already present
                if "?" not in video_url and "captioned" not in video_url.lower():
                    video_url = f"{video_url}?captioned=true"
                    logger.info(f"Added captioned parameter to URL: {video_url}")
            
            # Import requests for fallback
            import requests
            import os
            
            # Extract video ID if available
            video_id = None
            try:
                if "/videos/" in video_url:
                    video_id = video_url.split("/videos/")[1].split("/")[0].split("?")[0]
                elif "video_id=" in video_url:
                    video_id = video_url.split("video_id=")[1].split("&")[0]
                
                if video_id:
                    logger.info(f"Extracted video ID: {video_id}")
            except Exception as e:
                logger.warning(f"Could not extract video ID: {e}")
            
            # Direct API download approach - most reliable method
            if video_id:
                try:
                    download_api_url = "https://api.heygen.com/v1/video.download"
                    download_headers = {
                        "accept": "application/json",
                        "content-type": "application/json",
                        "x-api-key": Config.HEYGEN_API_KEY
                    }
                    download_payload = {
                        "video_id": video_id,
                        "captioned": True
                    }
                    
                    logger.info(f"Using direct download API with auth: {download_api_url}")
                    
                    # Use requests for this call - more reliable than aiohttp for this endpoint
                    response = requests.post(download_api_url, json=download_payload, headers=download_headers)
                    if response.status_code == 200:
                        result = response.json()
                        direct_url = result.get('data', {}).get('url')
                        if direct_url and isinstance(direct_url, str) and direct_url.startswith('http'):
                            logger.info(f"Got authorized direct download URL: {direct_url}")
                            
                            # Now download from the authorized direct URL with streaming
                            stream_headers = {
                                "accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
                                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
                                "referer": "https://app.heygen.com/"
                            }
                            
                            with requests.get(direct_url, headers=stream_headers, stream=True) as r:
                                r.raise_for_status()
                                with open(file_path, 'wb') as f:
                                    for chunk in r.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
                            
                            logger.info(f"✅ Successfully downloaded video via API to {file_path}")
                            # Skip the aiohttp attempt since we already succeeded
                            cloudinary_url = await self._upload_to_cloudinary_public(str(file_path), f"{safe_title}_{module_type}")
                            return cloudinary_url
                except Exception as api_e:
                    logger.warning(f"API download method failed: {api_e}, trying fallback methods")
            
            # Fallback approach - Try requests library with special headers
            try:
                # Special headers with auth for files2.heygen.ai domain
                if "files2.heygen.ai" in video_url or "heygen.ai" in video_url:
                    # Full comprehensive headers with authentication
                    headers = {
                        "accept": "video/mp4,video/*;q=0.9,*/*;q=0.8,*/*",
                        "accept-language": "en-US,en;q=0.9",
                        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
                        "referer": "https://app.heygen.com/",
                        "origin": "https://app.heygen.com",
                        "sec-fetch-dest": "video",
                        "sec-fetch-mode": "no-cors",
                        "sec-fetch-site": "same-site",
                        "Connection": "keep-alive",
                        "Authorization": f"Bearer {Config.HEYGEN_API_KEY}",  # Critical auth header
                        "x-api-key": Config.HEYGEN_API_KEY  # Secondary auth header
                    }
                    logger.info(f"Using requests library with enhanced auth headers: {video_url}")
                    
                    try:
                        with requests.get(video_url, headers=headers, stream=True, timeout=60) as r:
                            r.raise_for_status()  # This will raise an exception for 4XX/5XX errors
                            with open(file_path, 'wb') as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                        
                        logger.info(f"✅ Successfully downloaded using requests library: {file_path}")
                        cloudinary_url = await self._upload_to_cloudinary_public(str(file_path), f"{safe_title}_{module_type}")
                        return cloudinary_url
                    
                    except Exception as req_e:
                        logger.warning(f"Requests download failed: {req_e}, trying aiohttp")
            except Exception as outer_e:
                logger.warning(f"Outer requests attempt failed: {outer_e}, trying aiohttp")
            
            # Last attempt with aiohttp (least reliable for HeyGen)
            try:
                # Special headers for HeyGen files
                headers = {
                    "accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
                    "referer": "https://app.heygen.com/",
                    "origin": "https://app.heygen.com",
                    "Connection": "keep-alive",
                    "Authorization": f"Bearer {Config.HEYGEN_API_KEY}", 
                    "x-api-key": Config.HEYGEN_API_KEY
                }
                
                logger.info(f"Final attempt with aiohttp: {video_url}")
                timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes timeout
                
                # Use context manager to ensure the file is properly closed
                with open(file_path, 'wb') as f:
                    async with session.get(video_url, headers=headers, timeout=timeout) as response:
                        if response.status == 200:
                            # Stream the content to file in chunks to handle large files
                            chunk_size = 1024 * 1024  # 1MB chunks
                            downloaded = 0
                            content_length = int(response.headers.get('Content-Length', '0'))
                            
                            async for chunk in response.content.iter_chunked(chunk_size):
                                f.write(chunk)
                                downloaded += len(chunk)
                                if content_length > 0:
                                    percent = int((downloaded / content_length) * 100)
                                    if downloaded % (10 * chunk_size) == 0:  # Log every 10MB
                                        logger.info(f"Download progress: {percent}% ({downloaded}/{content_length} bytes)")
                            
                            logger.info(f"✅ Successfully downloaded video to {file_path}")
                        else:
                            # Log the error and try a direct download with requests
                            logger.error(f"Failed to download with aiohttp, status: {response.status}")
                            raise Exception(f"Failed to download video: HTTP {response.status}")
            
            except Exception as download_error:
                # If aiohttp fails, try with requests as a fallback
                logger.warning(f"Aiohttp download failed: {download_error}, trying requests library")
                
                try:
                    import requests
                    logger.info(f"Downloading using requests library: {video_url}")
                    
                    # Make sure we're using the right headers even when falling back to requests
                    if "heygen.ai" in video_url:
                        # Use more robust headers for HeyGen downloads with requests
                        headers = {
                            "accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
                            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
                            "referer": "https://app.heygen.com/",
                            "origin": "https://app.heygen.com",
                            "Connection": "keep-alive",
                            "sec-fetch-dest": "video",
                            "sec-fetch-mode": "cors",
                            "sec-fetch-site": "cross-site"
                        }
                        logger.info("Using enhanced HeyGen-specific headers for requests library")
                    
                    with requests.get(video_url, headers=headers, stream=True, timeout=300) as response:
                        if response.status_code == 200:
                            with open(file_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                                    if chunk:
                                        f.write(chunk)
                            logger.info(f"✅ Successfully downloaded video with requests to {file_path}")
                        else:
                            # Both methods failed - this is a fatal error
                            error_msg = f"Failed to download with requests library: HTTP {response.status_code}"
                            logger.error(error_msg)
                            raise Exception(error_msg)
                except Exception as req_error:
                    # Both aiohttp and requests failed
                    logger.error(f"All download methods failed for URL: {video_url}")
                    logger.error(f"Original error: {download_error}")
                    logger.error(f"Requests error: {req_error}")
                    # Fail clearly with a detailed error message
                    raise Exception(f"Failed to download HeyGen video after multiple attempts: {req_error}")
            
            # Check if the file was actually downloaded and has content
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                # Upload to Cloudinary
                logger.info(f"Uploading to Cloudinary: {file_path}")
                cloudinary_url = await self._upload_to_cloudinary(str(file_path), f"{module_type}_{safe_title}")
                
                if cloudinary_url:
                    logger.info(f"✅ Successfully uploaded to Cloudinary: {cloudinary_url}")
                    return cloudinary_url
                else:
                    # Cloudinary upload failed - this is a fatal error
                    logger.error("Cloudinary upload returned None")
                    raise Exception("Failed to upload video to Cloudinary")
            else:
                # File wasn't downloaded properly
                file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                logger.error(f"Downloaded file is missing or empty: {file_path} (size: {file_size} bytes)")
                raise Exception("Downloaded video file is missing or empty")
                
        except Exception as e:
            logger.error(f"Error in download_video: {e}")
            # Re-raise the exception to stop execution (no fallbacks)
            raise Exception(f"Failed to download and upload video to Cloudinary: {e}")

    async def _upload_to_cloudinary_public(self, file_path: str, public_id: str) -> str:
        """Upload video to Cloudinary with maximum public accessibility"""
        try:
            logger.info(f"Uploading to Cloudinary with public access: {file_path}")
            
            # Clean public_id to avoid URL encoding issues
            clean_public_id = public_id.replace(" ", "_").replace(":", "").replace("'", "").replace("%", "")
            
            # Upload video to Cloudinary with maximum public accessibility
            result = cloudinary.uploader.upload(
                file_path,
                resource_type="video",
                public_id=clean_public_id,
                folder="youtube_reels",
                overwrite=True,
                type="upload",
                access_mode="public",
                use_filename=False,
                unique_filename=True,
                # Maximum public accessibility settings
                secure=False,  # Use HTTP instead of HTTPS
                invalidate=True,  # Clear CDN cache
                format="mp4",  # Ensure MP4 format
                # Additional settings for public access
                transformation=[
                    {"quality": "auto"},
                    {"format": "mp4"}
                ]
            )
            
            # Use HTTP URL for better compatibility
            cloudinary_url = result.get('url', result.get('secure_url'))
            if cloudinary_url and cloudinary_url.startswith('https://'):
                cloudinary_url = cloudinary_url.replace('https://', 'http://')
            
            logger.info(f"✅ Uploaded to Cloudinary with public access: {cloudinary_url}")
            return cloudinary_url
            
        except Exception as e:
            logger.error(f"Error uploading to Cloudinary: {e}")
            raise Exception(f"Cloudinary upload failed: {e}")

    async def _upload_to_cloudinary(self, file_path: str, public_id: str) -> str:
        try:
            logger.info(f"Uploading to Cloudinary: {file_path}")
            
            # Clean public_id to avoid URL encoding issues
            clean_public_id = public_id.replace(" ", "_").replace(":", "").replace("'", "").replace("%", "")
            
            # Upload video to Cloudinary with maximum public accessibility
            result = cloudinary.uploader.upload(
                file_path,
                resource_type="video",
                public_id=clean_public_id,
                folder="youtube_reels",
                overwrite=True,
                type="upload",
                access_mode="public",
                use_filename=False,
                unique_filename=True,
                # Add additional settings for maximum accessibility
                secure=False,  # Use HTTP instead of HTTPS for better compatibility
                invalidate=True,  # Clear CDN cache
                format="mp4"  # Ensure MP4 format
            )
            
            # Use the regular URL instead of secure_url for better Creatomate compatibility
            cloudinary_url = result.get('url', result['secure_url'])
            logger.info(f"✅ Uploaded to Cloudinary: {cloudinary_url}")
            return cloudinary_url
            
        except Exception as e:
            logger.error(f"Error uploading to Cloudinary: {e}")
            raise Exception(f"Cloudinary upload failed: {e}")

    async def _prompt_manual_download(self, video_url: str, task_id: str, game_title: str) -> str:
        """Handle manual download process by prompting the user
        
        Args:
            video_url: Original video URL (may be a dashboard URL)
            task_id: HeyGen task ID
            game_title: Title of the game
            
        Returns:
            str: Cloudinary URL provided by the user
        """
        # Generate the dashboard URL where the user can view and download the video
        dashboard_url = f"https://app.heygen.com/videos/{task_id}"
        
        # Check if running in production (Railway) - no interactive terminal available
        is_production = os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_PROJECT_ID')
        
        if is_production:
            # In production, we can't use input() - raise error with the dashboard URL
            logger.error(f"Manual download required but running in production mode")
            logger.error(f"HeyGen Dashboard URL: {dashboard_url}")
            raise Exception(f"HeyGen video generation requires manual intervention. Video available at: {dashboard_url}")
        
        # Print instructions with clear formatting to make them stand out
        print("\n" + "=" * 80)
        print("⚠️  MANUAL ACTION REQUIRED: HeyGen Video Download  ⚠️")
        print("=" * 80)
        print(f"\n1. Please open this URL in your browser: {dashboard_url}")
        print("   If this URL doesn't work, go to https://app.heygen.com/ and log in")
        print("\n2. Once the video is ready, click on the download button (bottom right)")
        print("\n3. Select 'Download Captioned Video' option to get the video with captions")
        print("\n4. Upload the downloaded video to Cloudinary manually:")
        print("   a. Go to https://cloudinary.com/ and log in")
        print("   b. Click on 'Media Library' > 'Upload' button")
        print("   c. Select the downloaded video file")
        print("   d. Wait for upload to complete")
        print("   e. Click on the uploaded video")
        print("   f. Copy the 'Video URL' (not the secure URL)")
        print("\n5. Paste the Cloudinary URL below and press Enter")
        print("   Example URL format: http://res.cloudinary.com/your-cloud-name/video/upload/...")
        print("\n" + "-" * 80)
        
        # Log the instructions as well
        logger.info(f"Manual download URL: {dashboard_url}")
        logger.info("Waiting for user to manually download, upload to Cloudinary, and provide the URL")
        
        # Prompt user for input
        cloudinary_url = input("\nPlease paste the Cloudinary URL here: ")
        
        # Validate the input URL
        while not cloudinary_url.startswith("http") or "cloudinary.com" not in cloudinary_url:
            print("\n❌ Invalid URL! Please provide a valid Cloudinary URL.")
            cloudinary_url = input("\nPlease paste the Cloudinary URL here: ")
        
        logger.info(f"User provided manual Cloudinary URL: {cloudinary_url}")
        print("\n✅ URL accepted! Continuing with the pipeline...")
        print("-" * 80 + "\n")
        
        return cloudinary_url
    
    async def create_intro(self, game_title: str, game_details: Dict = None) -> Optional[str]:
        """Main method to create intro video"""
        try:
            # Ensure we have a valid game title from either parameter or game_details
            if not game_title and game_details:
                if 'title' in game_details:
                    game_title = game_details['title']
                elif 'name' in game_details:
                    game_title = game_details['name']
                else:
                    game_title = "Unknown Game"
            
            logger.info(f"Creating intro for {game_title}")
            
            # Generate script without price comparison information
            script = await self.generate_intro_script(game_title, game_details)
            
            # Generate video with HeyGen
            video_path = await self.generate_heygen_video(script, game_title)
            
            logger.info(f"Intro created successfully: {video_path}")
            return video_path
                
        except Exception as e:
            logger.error(f"Error creating intro: {e}")
            raise Exception(f"Intro creation failed: {e}")
