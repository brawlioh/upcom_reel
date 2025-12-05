import asyncio
import aiohttp
import json
import ssl
import cloudinary
import cloudinary.uploader
from pathlib import Path
from loguru import logger
from config import Config
from typing import Dict, Optional, List
import time
import re

class VizardProcessor:
    def __init__(self):
        self.config = Config
        # Initialize Cloudinary
        cloudinary.config(
            cloud_name=Config.CLOUDINARY_CLOUD_NAME,
            api_key=Config.CLOUDINARY_API_KEY,
            api_secret=Config.CLOUDINARY_API_SECRET
        )
        
    async def find_game_video_url(self, game_title: str, game_details: Dict = None) -> Optional[str]:
        """Find gameplay video URL using real Steam data and fallbacks"""
        try:
            logger.info(f"🔍 Searching for gameplay video for {game_title}")
            
            # Method 1: Check for custom user-provided videos first
            if game_details and game_details.get('custom_videos'):
                custom_videos = game_details['custom_videos']
                logger.info(f"🎯 Found {len(custom_videos)} custom video(s) from user")
                # Use the first custom video (user's choice)
                custom_video = custom_videos[0]
                
                # Convert YouTube Shorts and youtu.be URLs to regular YouTube URLs (Vizard requirement)
                try:
                    if '/shorts/' in custom_video:
                        # Extract video ID from shorts URL
                        video_id = custom_video.split('/shorts/')[-1].split('?')[0].split('&')[0]
                        custom_video = f"https://www.youtube.com/watch?v={video_id}"
                        logger.info(f"🔄 Converted Shorts URL to regular YouTube URL: {custom_video}")
                    elif 'youtu.be/' in custom_video:
                        # Extract video ID from youtu.be URL
                        video_id = custom_video.split('youtu.be/')[-1].split('?')[0].split('&')[0]
                        custom_video = f"https://www.youtube.com/watch?v={video_id}"
                        logger.info(f"🔄 Converted youtu.be URL to regular YouTube URL: {custom_video}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to convert URL format: {e}. Using original URL: {custom_video}")
                
                # Optional: Validate video content matches game (basic check)
                try:
                    import re
                    # Extract video ID for basic validation
                    if 'watch?v=' in custom_video:
                        video_id = custom_video.split('watch?v=')[-1].split('&')[0]
                        logger.info(f"🆔 Video ID: {video_id}")
                        
                        # Warning if the video might not match the game
                        game_keywords = game_title.lower().split()
                        if len(game_keywords) > 0:
                            logger.info(f"🎮 Game keywords to match: {game_keywords}")
                            logger.info(f"⚠️  Please verify the video content matches '{game_title}'")
                except Exception as e:
                    logger.debug(f"Video validation check failed: {e}")
                
                logger.info(f"✅ Using custom user video: {custom_video}")
                return custom_video
            
            # Method 2: Use videos from Steam game details if available
            if game_details and game_details.get('videos'):
                steam_videos = game_details['videos']
                logger.info(f"🎬 Found {len(steam_videos)} videos from Steam data")
                
                # Filter and prioritize YouTube videos from Steam data
                youtube_videos = []
                for video in steam_videos:
                    if 'youtube.com' in video or 'youtu.be' in video:
                        youtube_videos.append(video)
                
                if youtube_videos:
                    # Prioritize videos with better keywords (trailers over podcasts)
                    prioritized_video = self._prioritize_steam_videos(youtube_videos, game_title)
                    logger.info(f"✅ Using prioritized Steam YouTube video: {prioritized_video}")
                    return prioritized_video
                
                # If no YouTube videos in Steam data, skip to next method
                logger.info(f"⚠️ Steam videos are not YouTube URLs, trying other methods...")
            
            # Method 3: Try to extract Steam App ID and scrape more videos
            app_id = self._extract_steam_app_id(game_title, game_details)
            if app_id:
                logger.info(f"📋 Found Steam App ID: {app_id}")
                videos = await self._scrape_youtube_videos(app_id, game_title)
                if videos:
                    logger.info(f"✅ Found {len(videos)} YouTube videos via Steam scraping")
                    return videos[0]  # Return the first (best) video
            
            # Method 4: Direct YouTube search fallback
            logger.info(f"🔍 Trying direct YouTube search")
            search_videos = await self._search_youtube_directly(game_title)
            if search_videos:
                logger.info(f"✅ Found {len(search_videos)} videos via YouTube search")
                # Use the first video (already prioritized by search terms)
                selected_video = search_videos[0]
                logger.info(f"🎯 Selected YouTube search video: {selected_video}")
                return selected_video
            
            # No videos found
            logger.error(f"❌ No videos found for {game_title}")
            raise Exception(f"No gameplay video URL found for '{game_title}' via custom URL, Steam data, scraping, or YouTube search")
            
        except Exception as e:
            logger.error(f"Error finding video URL for {game_title}: {e}")
            raise Exception(f"Failed to find video URL for {game_title}: {e}")

    def _prioritize_steam_videos(self, youtube_videos: List[str], game_title: str) -> str:
        """Prioritize Steam videos by content type, favoring pure gameplay with minimal text overlays"""
        try:
            # Score each video based on URL patterns and likely content type
            scored_videos = []
            
            for video in youtube_videos:
                score = 0
                video_lower = video.lower()
                
                # Prefer gameplay videos over trailers/announcements (which often have text)
                if 'gameplay' in video_lower:
                    score += 20
                if 'no commentary' in video_lower:
                    score += 15
                if 'walkthrough' in video_lower and 'no commentary' in video_lower:
                    score += 10
                    
                # Avoid videos likely to have text overlays
                if 'trailer' in video_lower:
                    score -= 10
                if 'announcement' in video_lower:
                    score -= 15
                if 'review' in video_lower:
                    score -= 5
                if 'reaction' in video_lower:
                    score -= 10
                
                # Prefer shorter video IDs (often official content)
                if 'watch?v=' in video:
                    video_id = video.split('watch?v=')[-1].split('&')[0]
                    if len(video_id) == 11:  # Standard YouTube video ID length
                        score += 5
                
                logger.info(f"📊 Video scored: {video} (score: {score})") 
                scored_videos.append((score, video))
            
            # Sort by score (highest first) and return the best video
            scored_videos.sort(key=lambda x: x[0], reverse=True)
            best_video = scored_videos[0][1]
            
            logger.info(f"🏆 Selected best text-free gameplay video: {best_video}")
            return best_video
            
        except Exception as e:
            logger.warning(f"Error prioritizing videos, using first: {e}")
            return youtube_videos[0]

    def _extract_steam_app_id(self, game_title: str, game_details: Dict = None) -> Optional[str]:
        """Extract Steam App ID from game details or title"""
        try:
            # Method 1: From game_details if provided
            if game_details:
                app_id = game_details.get('app_id') or game_details.get('steam_id') or game_details.get('id')
                if app_id:
                    return str(app_id)
            
            # Method 2: Extract App ID from generic Steam game names like "Steam_Game_1962700"
            game_lower = game_title.lower()
            if "steam_game_" in game_lower:
                app_id = game_title.split("_")[-1]
                if app_id.isdigit():
                    logger.info(f"📋 Extracted App ID from generic name: {app_id}")
                    return app_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Steam App ID: {e}")
            return None

    async def _scrape_youtube_videos(self, app_id: str, game_title: str) -> List[str]:
        """Scrape YouTube videos from Steam page and search"""
        try:
            # Import here to avoid circular imports
            from utils.youtube_scraper import YouTubeScraper
            
            async with YouTubeScraper() as scraper:
                videos = await scraper.get_steam_game_videos(app_id, game_title)
                return videos
                
        except Exception as e:
            logger.error(f"Error scraping YouTube videos: {e}")
            return []

    def _get_curated_video(self, game_title: str) -> Optional[str]:
        """Get video from curated database - disabled for cleaner troubleshooting"""
        logger.info(f"⚠️ Curated video database disabled - skipping for {game_title}")
        return None

    async def _search_youtube_directly(self, game_title: str) -> List[str]:
        """Direct YouTube search as final fallback"""
        try:
            from utils.youtube_scraper import YouTubeScraper
            
            async with YouTubeScraper() as scraper:
                # Use fallback method which includes search
                videos = await scraper.get_fallback_videos(game_title)
                return videos
                
        except Exception as e:
            logger.error(f"Error in direct YouTube search: {e}")
            return []
    
    def _select_optimal_template(self, game_title: str, video_url: str) -> int:
        """Select optimal Vizard template based on content type, prioritizing pure gameplay with minimal text"""
        try:
            # UPDATED TEMPLATE IDs - always using template 73952796 as requested
            templates = {
                # All template types use the same requested template ID
                'pure_gameplay': 73952796,  # Using requested template
                'gameplay_focused': 73952796,  # Using requested template
                'action_gameplay': 73952796,  # Using requested template
                'strategy_gameplay': 73952796,  # Using requested template
                'general': 73952796,  # Using requested template
                'safe_crop': 73952796,  # Using requested template
                'sonic': 73952796  # Special template for Sonic games
            }
            
            # Check if this is a Sonic game and log special handling
            game_title_lower = game_title.lower()
            if 'sonic' in game_title_lower:
                logger.info(f"🔵 Special handling for Sonic game: {game_title} - using fullscreen template")
                # Force the strongest fullscreen settings for Sonic
                return templates['sonic']
            
            # Log the template selection
            logger.info(f"🎮 Using requested template ID 73952796 for {game_title}")
            return 73952796  # Always return the requested template ID
                
        except Exception as e:
            logger.warning(f"Template selection failed, still using the requested template: {e}")
            return 73952796  # Always use the requested template ID
    
    async def submit_to_vizard(self, video_url: str, game_title: str) -> Optional[str]:
        """Submit video to Vizard AI for processing"""
        try:
            logger.info(f"Submitting {game_title} video to Vizard AI")
            logger.info(f"🔗 Video URL being sent to Vizard: {video_url}")
            
            headers = {
                'VIZARDAI_API_KEY': Config.VIZARD_API_KEY,
                'content-type': 'application/json'
            }
            
            # Select optimal template based on content type
            template_id = self._select_optimal_template(game_title, video_url)
            
            # UPDATED Vizard AI processing payload with full-screen settings (no distortion)
            payload = {
                "lang": "en",
                "preferLength": [2],  # 2 = 60-90 second clips
                "videoType": 2,  # YouTube video type
                "videoUrl": video_url,
                "ext": "mp4",
                "maxClipNumber": 2,  # Limit to 2 clips as requested
                "templateId": template_id,
                "cropMode": 4,  # Value 4 = Maximum fill (fills the entire screen)
                "textDetection": True,  # Enable text detection to detect and avoid text
                "aspectRatio": "9:16",  # Fixed vertical aspect ratio for mobile
                "quality": "Medium",  # Lower quality for faster processing
                "preserveText": True,  # Do not preserve visible text
                "minDuration": 60,  # Minimum 60 seconds
                "maxDuration": 90,  # Maximum 90 seconds
                "optimalDuration": 75,  # Target 75-second clips
                "showCaptions": False,  # Do not show captions
                "fillScreen": True,  # Ensure video fills the entire screen
                "smartCrop": True,  # Use smart crop to focus on important content
                "scaleMode": "fit",  # Maintain aspect ratio while maximizing screen usage
                "fillFramesVertically": True,  # Force vertical fill mode
                "filterOptions": {
                    "minTextFreeArea": 0.9,  # Require at least 90% of the frame to be text-free
                    "avoidTextFrames": True,  # Actively avoid frames with text
                    "preferGameplay": True,  # Prefer pure gameplay footage
                    "avoidTitles": True,  # Avoid title cards and splash screens
                    "preferFullScreen": True  # Prioritize footage that fills the screen
                    }
            }
            
            logger.info(f"📦 Vizard payload: {payload}")
            
            # Create SSL context that doesn't verify certificates (for development)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    "https://elb-api.vizard.ai/hvizard-server-front/open-api/v1/project/create",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"🔍 Vizard API response: {result}")
                        project_id = result.get('projectId')
                        
                        if project_id:
                            logger.info(f"✅ Vizard project created: {project_id}")
                            
                            # Only use direct polling since webhooks are no longer used
                            logger.info(f"🔄 Using direct polling for project status")
                            clips_data = await self._poll_vizard_status(session, headers, project_id)
                            if clips_data:
                                # Download the best clip
                                output_path = await self._download_best_clip(session, clips_data, game_title)
                                return output_path
                        else:
                            logger.error(f"No project ID returned from Vizard. Full response: {result}")
                            # Check if there's an error message in the response
                            error_msg = result.get('message', result.get('error', 'Unknown error'))
                            raise Exception(f"Vizard API did not return a project ID: {error_msg}")
                    else:
                        logger.error(f"Vizard API error: {response.status}")
                        error_text = await response.text()
                        logger.error(f"Error details: {error_text}")
                        raise Exception(f"Vizard API failed with status {response.status}: {error_text}")
            
        except Exception as e:
            logger.error(f"Error submitting to Vizard: {e}")
            raise Exception(f"Vizard submission failed: {e}")
    
    async def _poll_vizard_status(self, session: aiohttp.ClientSession, headers: Dict, project_id: str) -> Optional[List[Dict]]:
        """Poll Vizard API for processing completion"""
        max_attempts = 60  # 30 minutes with 30-second intervals
        attempt = 0
        
        while attempt < max_attempts:
            try:
                async with session.get(
                    f"https://elb-api.vizard.ai/hvizard-server-front/open-api/v1/project/query/{project_id}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # Debug: Log the full API response to understand structure
                        logger.info(f"Vizard API response: {result}")
                        
                        # Check multiple possible completion indicators
                        videos = None
                        if 'videos' in result and result['videos']:
                            videos = result['videos']
                        elif 'data' in result and 'videos' in result['data'] and result['data']['videos']:
                            videos = result['data']['videos']
                        elif 'clips' in result and result['clips']:
                            videos = result['clips']
                        
                        # Check if processing is complete based on status or videos availability
                        status = result.get('status', '').lower()
                        if videos and len(videos) > 0:
                            logger.info(f"✅ Vizard processing completed with {len(videos)} clips")
                            
                            # Log viral scores for each clip
                            for i, video in enumerate(videos):
                                score = video.get('viralScore', 'N/A')
                                duration = video.get('videoMsDuration', 0) / 1000  # Convert to seconds
                                logger.info(f"Clip {i+1}: Viral Score {score}, Duration: {duration:.1f}s")
                            
                            return videos
                        elif status in ['completed', 'finished', 'done', 'exported']:
                            logger.info(f"✅ Vizard processing completed (status: {status})")
                            # Even if no videos in response, try to return what we have
                            return result.get('videos', result.get('clips', []))
                        else:
                            # Still processing
                            logger.info(f"🔄 Vizard processing: attempt {attempt + 1}/{max_attempts} (status: {status})")
                    else:
                        logger.warning(f"Vizard API returned status {response.status}")
                        error_text = await response.text()
                        logger.warning(f"Response: {error_text}")
                
                # Add a safety check - if we've been polling for too long, break out
                if attempt >= max_attempts - 1:
                    logger.warning("⚠️ Vizard polling timeout approaching, attempting final check...")
                    break
                
                await asyncio.sleep(30)  # 30-second intervals as recommended
                attempt += 1
                
            except Exception as e:
                logger.error(f"Error polling Vizard status: {e}")
                await asyncio.sleep(30)
                attempt += 1
        
        logger.error("Vizard processing timed out")
        raise Exception("Vizard processing timed out after 30 minutes")
    
    async def _wait_for_webhook_completion(self, session: aiohttp.ClientSession, headers: Dict, project_id: str) -> Optional[List[Dict]]:
        """Wait for webhook notification with immediate error detection"""
        try:
            logger.info(f"⏳ Waiting for webhook notification for project {project_id}")
            
            # First, do a quick status check to see if it failed immediately
            try:
                async with session.get(
                    f"https://elb-api.vizard.ai/hvizard-server-front/open-api/v1/project/query/{project_id}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('code') == 4008:
                            logger.error(f"❌ Vizard failed immediately: {result.get('errMsg', 'Failed to download video')}")
                            raise Exception(f"Vizard failed: {result.get('errMsg', 'Failed to download video')}")
            except Exception as e:
                if "Vizard failed" in str(e):
                    raise e
                # Continue if it's just a connection error
                pass
            
            # Use config timeout values
            max_wait_time = self.config.VIZARD_WEBHOOK_TIMEOUT
            check_interval = 5    # Check every 5 seconds
            elapsed_time = 0
            
            while elapsed_time < max_wait_time:
                # Check webhook status
                try:
                    async with session.get(f"http://localhost:5001/vizard/status/{project_id}") as response:
                        if response.status == 200:
                            webhook_data = await response.json()
                            
                            # Check if processing completed
                            code = webhook_data.get('code')
                            status = webhook_data.get('status')
                            
                            if code == 4008:
                                # Failed to download video
                                error_msg = webhook_data.get('error_msg', 'Failed to download video')
                                logger.error(f"❌ Vizard webhook: {error_msg}")
                                raise Exception(f"Vizard failed: {error_msg}")
                            
                            elif code == 200 or status == 'completed':
                                # Success - get the clips
                                logger.info(f"✅ Webhook notification: Processing completed")
                                return await self._get_project_clips(session, headers, project_id)
                            
                            else:
                                logger.info(f"📊 Webhook status: {status} (code: {code})")
                        
                        elif response.status == 404:
                            # No webhook notification yet, check Vizard API directly
                            async with session.get(
                                f"https://elb-api.vizard.ai/hvizard-server-front/open-api/v1/project/query/{project_id}",
                                headers=headers
                            ) as viz_response:
                                if viz_response.status == 200:
                                    result = await viz_response.json()
                                    if result.get('code') == 4008:
                                        logger.error(f"❌ Vizard API check: {result.get('errMsg', 'Failed to download video')}")
                                        raise Exception(f"Vizard failed: {result.get('errMsg', 'Failed to download video')}")
                            
                except Exception as webhook_error:
                    if "Vizard failed" in str(webhook_error):
                        raise webhook_error
                    # Webhook server might not be running, continue with API checks
                    logger.warning(f"⚠️ Webhook check failed: {webhook_error}")
                
                # Wait before next check
                await asyncio.sleep(check_interval)
                elapsed_time += check_interval
                
                if elapsed_time % 15 == 0:  # Log every 15 seconds
                    logger.info(f"⏳ Still waiting for webhook... ({elapsed_time}s elapsed)")
            
            # Timeout - webhook didn't work, raise error to trigger retry
            logger.warning(f"⚠️ Webhook timeout after {max_wait_time}s, no response received")
            raise Exception("Webhook timeout - no response from Vizard")
            
        except Exception as e:
            logger.error(f"Error in webhook waiting: {e}")
            raise e
    
    async def _get_project_clips(self, session: aiohttp.ClientSession, headers: Dict, project_id: str) -> Optional[List[Dict]]:
        """Get clips from completed project"""
        try:
            async with session.get(
                f"https://elb-api.vizard.ai/hvizard-server-front/open-api/v1/project/query/{project_id}",
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    videos = result.get('videos', [])
                    if videos:
                        logger.info(f"✅ Retrieved {len(videos)} clips from project {project_id}")
                        return videos
                    else:
                        logger.warning(f"⚠️ No videos found in completed project {project_id}")
                        return None
                else:
                    logger.error(f"❌ Failed to get clips: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting project clips: {e}")
            return None
    
    async def _download_best_clip(self, session: aiohttp.ClientSession, clips_data: List[Dict], game_title: str) -> Optional[str]:
        """Download the highest-rated clip and upload to Cloudinary"""
        try:
            if not clips_data:
                logger.error("No clips available for download")
                raise Exception("No clips available for download")
            
            # Sort clips by viral score (highest first)
            sorted_clips = sorted(clips_data, key=lambda x: float(x.get('viralScore', 0)), reverse=True)
            best_clip = sorted_clips[0]
            
            video_url = best_clip.get('videoUrl')
            viral_score = best_clip.get('viralScore', 'N/A')
            duration = best_clip.get('videoMsDuration', 0) / 1000
            
            if not video_url:
                logger.error("No video URL found in best clip")
                raise Exception("No video URL found in best clip")
            
            logger.info(f"Selected best clip: Viral Score {viral_score}, Duration: {duration:.1f}s")
            
            # Clean filename
            safe_title = "".join(c for c in game_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title}_vizard.mp4"
            # Use a simpler path that doesn't require docker permissions
            output_path = Path("assets") / "vizard" / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download the video
            logger.info(f"Downloading clip: {video_url}")
            async with session.get(video_url) as response:
                if response.status == 200:
                    # Ensure directory exists
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(output_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                    
                    logger.info(f"Downloaded Vizard video: {output_path}")
                    
                    # Upload to Cloudinary
                    cloudinary_url = await self._upload_to_cloudinary(str(output_path), f"vizard_{safe_title}")
                    return cloudinary_url
                else:
                    logger.error(f"Failed to download Vizard video: {response.status}")
                    raise Exception(f"Failed to download Vizard video: HTTP {response.status}")
                    
        except Exception as e:
            logger.error(f"Error downloading Vizard video: {e}")
            raise Exception(f"Vizard video download failed: {e}")
    
    
    async def _upload_to_cloudinary(self, file_path: str, public_id: str) -> str:
        """Upload video to Cloudinary and return URL"""
        try:
            logger.info(f"Uploading to Cloudinary: {file_path}")
            
            # Upload to Cloudinary with public access settings
            safe_title = "".join(c for c in public_id if c.isalnum() or c in (' ', '-', '_')).rstrip()
            clean_public_id = f"vizard_{safe_title}".replace(" ", "_").replace(":", "").replace("'", "").replace("%", "")
            result = cloudinary.uploader.upload(
                file_path,
                resource_type="video",
                public_id=clean_public_id,
                folder="youtube_reels",
                overwrite=True,
                type="upload",
                access_mode="public",
                use_filename=False,
                unique_filename=True
            )
            
            cloudinary_url = result['secure_url']
            logger.info(f"✅ Uploaded to Cloudinary: {cloudinary_url}")
            return cloudinary_url
        except Exception as e:
            logger.error(f"Error uploading to Cloudinary: {e}")
            raise Exception(f"Cloudinary upload failed: {e}")
    
    async def process_gameplay_clip(self, game_title: str, game_details: Dict = None) -> Optional[str]:
        """Main method to process gameplay clip with 2-attempt fallback system"""
        max_retries = 2
        retry_count = 0
        
        # Special handling for Sonic games to ensure full screen coverage
        is_sonic_game = 'sonic' in game_title.lower()
        if is_sonic_game:
            logger.info(f"🔵 SPECIAL HANDLING: {game_title} detected as Sonic game - using optimized full-screen settings")
            # For Sonic games, try our specific sources first
            try:
                # Find best Sonic video source first
                video_url = await self.search_youtube_gameplay(game_title)
                if video_url:
                    logger.info(f"✅ Using special Sonic gameplay source: {video_url}")
                    processed_path = await self.submit_to_vizard(video_url, game_title)
                    logger.info(f"✅ Sonic gameplay clip processed successfully: {processed_path}")
                    return processed_path
            except Exception as e:
                logger.warning(f"⚠️ Special Sonic handling failed: {e}, falling back to standard process")
                # Continue with standard processing if special handling fails
        
        while retry_count < max_retries:
            try:
                logger.info(f"Processing gameplay clip for {game_title} (attempt {retry_count + 1}/{max_retries})")
                
                # Find video URL - try different sources on retries
                if retry_count == 0:
                    video_url = await self.find_game_video_url(game_title, game_details)
                elif retry_count == 1:
                    # Try YouTube search fallback
                    video_url = await self.search_youtube_gameplay(game_title)
                
                if not video_url:
                    logger.warning(f"No video URL found for {game_title} on attempt {retry_count + 1}")
                    retry_count += 1
                    continue
                
                # Submit to Vizard for processing
                processed_path = await self.submit_to_vizard(video_url, game_title)
                
                logger.info(f"✅ Gameplay clip processed successfully: {processed_path}")
                return processed_path
                    
            except Exception as e:
                retry_count += 1
                if "Failed to download video" in str(e) or "4008" in str(e):
                    logger.warning(f"⚠️ Vizard download failed on attempt {retry_count}")
                    if retry_count < max_retries:
                        logger.info(f"🔄 Trying alternative source...")
                        continue
                    else:
                        logger.error(f"❌ All Vizard attempts failed after {max_retries} tries")
                        raise Exception(f"Vizard processing failed for {game_title} after {max_retries} attempts: {e}")
                else:
                    logger.error(f"❌ Error processing gameplay clip: {e}")
                    raise Exception(f"Gameplay clip processing failed: {e}")
        
        # If we reach here, all attempts failed
        logger.error(f"❌ All {max_retries} attempts failed for {game_title}")
        raise Exception(f"Gameplay clip processing failed for {game_title} after {max_retries} attempts")
    
    async def search_youtube_gameplay(self, game_title: str) -> Optional[str]:
        """Search for alternative YouTube gameplay videos, prioritizing pure gameplay without text overlays"""
        try:
            logger.info(f"🔍 Searching YouTube for text-free {game_title} gameplay")
            
            # Alternative gameplay video searches - prioritizing pure gameplay without text
            search_terms = [
                f"{game_title} raw gameplay no commentary",
                f"{game_title} pure gameplay footage",
                f"{game_title} gameplay no commentary",
                f"{game_title} gameplay walkthrough no commentary",
                f"{game_title} in-game footage"
            ]
            
            # Updated backup video database with text-free gameplay footage URLs
            backup_videos = {
                # Raw gameplay videos without commentary or text overlays
                "cyberpunk": "https://www.youtube.com/watch?v=hvoD7ehZPcM", # Pure gameplay
                "elden ring": "https://www.youtube.com/watch?v=WqFMwJtjMcY", # No commentary gameplay
                "starfield": "https://www.youtube.com/watch?v=F_zAoby0UYk", # No HUD gameplay
                "baldur": "https://www.youtube.com/watch?v=JD9TXK632-s", # Pure gameplay
                "witcher": "https://www.youtube.com/watch?v=uFLCrscZgmw", # No commentary
                "hades": "https://www.youtube.com/watch?v=VKepf4jln4M", # Pure gameplay
                "minecraft": "https://www.youtube.com/watch?v=LxcY1Dq-TDw", # No commentary
                "fortnite": "https://www.youtube.com/watch?v=QhQZ6QXD-yw", # Raw gameplay
                "diablo": "https://www.youtube.com/watch?v=LOD5L4-YVCs", # Pure gameplay
                "call of duty": "https://www.youtube.com/watch?v=UjRrGZCM48k", # No commentary
                # Special fullscreen-optimized sources for Sonic games
                "sonic": "https://www.youtube.com/watch?v=RXlJT5j6g-w", # Sonic Frontiers no commentary
                "sonic rumble": "https://www.youtube.com/watch?v=pvsYsXwmgVQ", # Sonic gameplay that fills screen better
                "sonic frontiers": "https://www.youtube.com/watch?v=Pn5jMkAZWdo", # No commentary footage
                "sonic superstars": "https://www.youtube.com/watch?v=wh3S5luujAw" # High quality full screen footage
            }
            
            # Check for partial matches in backup videos
            game_lower = game_title.lower()
            for key, url in backup_videos.items():
                if key in game_lower or any(word in game_lower for word in key.split()):
                    logger.info(f"✅ Found backup video for {game_title}: {url}")
                    return url
            
            # PRODUCTION: No fallback URLs - require real gameplay footage
            logger.error(f"❌ No gameplay videos found for {game_title} in production")
            raise Exception(f"No gameplay videos found for {game_title}. Please provide custom_video_url or ensure Steam game has available footage.")
            
        except Exception as e:
            logger.error(f"Error in YouTube search: {e}")
            raise Exception(f"YouTube search failed for {game_title}: {e}")
    
    
    async def get_multiple_clips(self, game_title: str, count: int = 3) -> List[str]:
        """Get multiple clips for variety"""
        try:
            logger.info(f"Getting {count} clips for {game_title}")
            
            clips = []
            for i in range(count):
                clip_path = await self.process_gameplay_clip(f"{game_title}_clip_{i+1}")
                if clip_path:
                    clips.append(clip_path)
            
            return clips
            
        except Exception as e:
            logger.error(f"Error getting multiple clips: {e}")
            return []
    
    async def test_vizard_connection(self) -> bool:
        """Test Vizard API connection"""
        try:
            logger.info("Testing Vizard API connection...")
            
            headers = {
                'VIZARDAI_API_KEY': Config.VIZARD_API_KEY,
                'content-type': 'application/json'
            }
            
            # Test with template ID 73952796 as requested with full-screen settings (no distortion)
            test_payload = {
                "lang": "en",
                "preferLength": [2],  # 2 = 60-90 second clips 
                "videoType": 2,
                "videoUrl": "https://www.youtube.com/watch?v=hvoD7ehZPcM",  # Cyberpunk pure gameplay, no commentary
                "ext": "mp4",
                "maxClipNumber": 2,  # Limit to 2 clips
                "minDuration": 60,  # Minimum 60 seconds
                "maxDuration": 90,  # Maximum 90 seconds
                "textDetection": True,  # Enable text detection
                "templateId": 73952796,  # Using the requested template ID
                "cropMode": 4,  # Value 4 = Maximum fill (fills the entire screen)
                "fillScreen": True,  # Ensure video fills the entire screen
                "smartCrop": True,  # Use smart crop to focus on important content
                "scaleMode": "fit",  # Maintain aspect ratio while maximizing screen usage
                "fillFramesVertically": True,  # Force vertical fill mode
                "aspectRatio": "9:16",  # Fixed vertical aspect ratio for mobile
                "filterOptions": {
                    "minTextFreeArea": 0.9,  # Require mostly text-free frames
                    "avoidTextFrames": True,  # Actively avoid frames with text
                    "preferGameplay": True,  # Prefer pure gameplay footage
                    "preferFullScreen": True  # Prioritize footage that fills the screen
                }
            }
            
            # Create SSL context that doesn't verify certificates (for development)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    "https://elb-api.vizard.ai/hvizard-server-front/open-api/v1/project/create",
                    headers=headers,
                    json=test_payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        project_id = result.get('projectId')
                        if project_id:
                            logger.info(f"✅ Vizard API connection successful! Project ID: {project_id}")
                            return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Vizard API connection failed: {response.status} - {error_text}")
                        return False
            
        except Exception as e:
            logger.error(f"❌ Vizard API connection test failed: {e}")
            return False
