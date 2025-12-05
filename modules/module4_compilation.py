import asyncio
import aiohttp
import os
import re
import ssl
from pathlib import Path
from loguru import logger
from config import Config
from typing import Dict, Optional, List

class CreatorMateCompiler:
    """Handles video compilation using Creatomate API with Heygen intro and Vizard gameplay footage"""
    
    def __init__(self):
        self.config = Config
    
    async def compile_reel(self, intro_url: str, vizard_url: str, outro_url: str, game_title: str, price_banner_url: str = None) -> Optional[Dict]:
        """Main method to compile final reel using the HeyGen intro, Vizard gameplay videos, and price banner
        
        Args:
            intro_url: URL for the intro video
            vizard_url: URL for the gameplay video
            outro_url: URL for the outro image/video
            game_title: Title of the game
            price_banner_url: Optional URL for the price comparison banner (coverphoto)
                              If provided, will be placed on track 2 as "coverphoto"
        """
        try:
            logger.info(f"Compiling reel for {game_title}")
            
            # Check if outro_url is an image URL (ending with png/jpg/jpeg)
            is_image_outro = any(outro_url.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"])
            
            logger.info(f"Outro type: {'Image' if is_image_outro else 'Video'}")
            logger.info(f"Intro URL: {intro_url}")
            logger.info(f"Vizard URL: {vizard_url}")
            logger.info(f"Outro URL: {outro_url}")
            
            # CRITICAL: Use price_banner_url for coverphoto element
            # If price_banner_url is None, use outro_url as both outro and price banner
            # This maintains backward compatibility
            if price_banner_url is None:
                price_banner_url = outro_url
                logger.info("⚠️⚠️⚠️ CRITICAL ERROR: NO PRICE BANNER PROVIDED!")
                print(f"\n⚠️⚠️⚠️ CRITICAL ERROR: USING OUTRO URL FOR PRICE BANNER: {outro_url}")
            else:
                logger.info(f"🔴🔴🔴 USING DEDICATED PRICE BANNER: {price_banner_url}")
                print(f"\n💰💰💰 COMPILATION USING PRICE BANNER: {price_banner_url}")
                
            # Force log this to make it ultra clear
            print(f"\n\n🔵 FINAL PRICE BANNER URL IN COMPILATION: {price_banner_url}\n\n")
            
            result = await self.create_compilation(intro_url, vizard_url, outro_url, game_title, 
                                               is_image_outro=is_image_outro, price_banner_url=price_banner_url)
            logger.info(f"Reel compiled successfully: {result}")
            return result
        except Exception as e:
            logger.error(f"Error compiling reel: {e}")
            raise Exception(f"Reel compilation failed: {e}")
    
    async def create_compilation(self, intro_url: str, vizard_url: str, outro_url: str, game_title: str, 
                                is_image_outro: bool = False, price_banner_url: str = None) -> Optional[Dict]:
        """Create final compilation using Creatomate with HeyGen on top (chroma keyed), Vizard gameplay, and price banner
        
        Args:
            intro_url: URL for the intro video
            vizard_url: URL for the gameplay video
            outro_url: URL for the outro image/video
            game_title: Title of the game
            is_image_outro: Whether outro_url points to an image
            price_banner_url: URL for the price comparison banner (coverphoto) on track 2
        """
        try:
            logger.info(f"Creating compilation for {game_title}")
            logger.info(f"Processing URLs:")
            logger.info(f"  Intro (HeyGen): {intro_url}")
            logger.info(f"  Gameplay (Vizard): {vizard_url}")
            logger.info(f"  Outro: {outro_url}")
            
            # Store URLs in a dictionary for easy reference
            # EXPLICITLY ensure price_banner_url is used for coverphoto
            cloudinary_urls = {
                "intro": intro_url,
                "vizard": vizard_url,
                "outro": outro_url,
                "coverphoto": price_banner_url  # Explicitly use price_banner_url for coverphoto
            }
            
            # CRITICAL DEBUGGING - ensure we're using the price banner URL
            logger.info(f"🔴🔴🔴 COVERPHOTO URL IN COMPILATION: {cloudinary_urls['coverphoto']}")
            print(f"\n💰💰💰 COVERPHOTO URL IN COMPILATION: {cloudinary_urls['coverphoto']}")
            
            # Check if price banner is different from outro
            if price_banner_url and price_banner_url != outro_url:
                logger.info("🔴 GOOD: Using separate price comparison banner")
                print(f"\n🔵 VERIFICATION: Using separate price banner different from outro")
            else:
                logger.warning("⚠️⚠️⚠️ WARNING: Using outro image as price comparison banner")
                print(f"\n⚠️ WARNING: Using outro image ({outro_url}) as price comparison banner")
            
            # Create a structure that exactly matches the provided reference JSON
            # The ordering here matters - we'll create the elements in the exact order of the reference JSON
            base_elements = [
                # Track 1: Gameplay video (first element in reference)
                {
                    "id": "gameplay",
                    "name": "gameplay",
                    "type": "video",
                    "track": 1,
                    "time": 0,
                    "duration": None,  # Using null (None in Python) as in the reference
                    "source": cloudinary_urls.get("vizard"),
                    "loop": True,
                    "volume": "20%",
                    "animations": [
                        {
                            "time": "end",
                            "duration": 4,
                            "easing": "quadratic-out",
                            "reversed": True,
                            "type": "fade"
                        }
                    ]
                },
                # Track 2: Price comparison banner (coverphoto) - second element in reference
                {
                    "id": "794f5712-a44f-4cee-ab3f-82c2a5ed853c",
                    "name": "coverphoto", 
                    "type": "image",
                    "track": 2,
                    "time": 0,
                    "duration": 4,
                    "source": cloudinary_urls.get("coverphoto"),
                    "animations": [
                        {
                            "time": "end",
                            "duration": 3,
                            "easing": "quadratic-out",
                            "reversed": True,
                            "type": "fade"
                        }
                    ]
                },
                # Track 3: Intro video - third element in reference
                {
                    "id": "intro---heygen",
                    "name": "intro---heygen",
                    "type": "video",
                    "track": 3,
                    "time": 0,
                    "fit": "contain",
                    "source": cloudinary_urls.get("intro"),
                    "chroma_key_color": "rgba(0,255,0,1)",
                    "chroma_key_sensitivity": "50%"
                },
                # Track 3 (continued): Outro image - fourth element in reference
                {
                    "id": "outro-image",
                    "name": "outro-image",
                    "type": "image",
                    "track": 3,
                    "time": "auto",  # Position after intro video
                    "duration": 3,
                    "source": cloudinary_urls.get("outro"),
                    "animations": [
                        {
                            "time": 0,
                            "duration": 0.5,
                            "transition": True,
                            "type": "fade"
                        }
                    ]
                },
                # Track 4: Logo overlay - fifth element in reference
                {
                    "id": "25ee313f-f8dc-45bb-99a7-06e64dd4db9b",
                    "name": "logo-top-L3M",
                    "type": "image",
                    "track": 4,
                    "time": 0,
                    "source": "https://res.cloudinary.com/dodod8s0v/image/upload/v1759927553/logo_2_xwogmb.png",
                    "animations": [
                        {
                            "time": 0,
                            "duration": 1,
                            "transition": True,
                            "type": "fade"
                        },
                        {
                            "time": "end",
                            "duration": 3,
                            "easing": "quadratic-out",
                            "reversed": True,
                            "type": "fade"
                        }
                    ]
                }
            ]

            # All elements are now included in base_elements in the correct order
            # No need to append additional elements

            # Create Creatomate render payload
            render_payload = {
                "source": {
                    "output_format": "mp4",
                    "width": 720,
                    "height": 1280,
                    "frame_rate": "25 fps",  # Updated to match reference
                    "elements": base_elements
                }
            }
            
            # CRITICAL: Verify the coverphoto element has the correct source URL
            try:
                coverphoto_elements = [e for e in base_elements if e.get('name') == 'coverphoto']
                if coverphoto_elements:
                    coverphoto = coverphoto_elements[0]
                    logger.info(f"🔴🔴🔴 FINAL JSON COVERPHOTO SOURCE: {coverphoto['source']}")
                    print(f"\n💰💰💰 VERIFICATION - FINAL JSON COVERPHOTO SOURCE: {coverphoto['source']}")
                    
                    # EXPLICITLY output the entire coverphoto element for verification
                    import json
                    print(f"\n=== COVERPHOTO ELEMENT IN FINAL JSON ===")
                    print(json.dumps(coverphoto, indent=2))
                    print(f"=====================================\n")
                else:
                    logger.error("⚠️⚠️⚠️ CRITICAL ERROR: No coverphoto element found in final JSON!")
                    print(f"\n⚠️⚠️⚠️ CRITICAL ERROR: No coverphoto element found in final JSON!")
            except Exception as e:
                logger.error(f"Error verifying coverphoto element: {e}")
                print(f"Error verifying coverphoto element: {e}")
            
            
            # Submit to Creatomate API
            headers = {
                'Authorization': f'Bearer {Config.CREATOMATE_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            # Create SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    f"{Config.CREATOMATE_BASE_URL}/renders",
                    headers=headers,
                    json=render_payload
                ) as response:
                    if response.status in [200, 202]:  # 202 = Accepted (render queued)
                        result = await response.json()
                        # Handle both single render and array response formats
                        if isinstance(result, list) and len(result) > 0:
                            render_id = result[0].get('id')
                        else:
                            render_id = result.get('id')
                        
                        if render_id:
                            logger.info(f"Creatomate render submitted: {render_id}")
                            # Poll for completion with retry logic
                            retry_count = 0
                            max_retries = 2
                            
                            while retry_count <= max_retries:
                                try:
                                    # Try with current configuration
                                    final_url = await self._poll_creatomate_status(session, headers, render_id)
                                    
                                    if final_url:
                                        # Download final video
                                        output_path = await self._download_final_video(session, final_url, game_title)
                                        
                                        # Return result with paths
                                        result = {
                                            'local_path': output_path,
                                            'online_url': final_url
                                        }
                                        logger.info(f"✅ Compilation complete: {output_path}")
                                        return result
                                    else:
                                        # If _poll_creatomate_status returns None, it means there was an error but we should try again
                                        retry_count += 1
                                        logger.warning(f"Retrying with simplified configuration (attempt {retry_count}/{max_retries})")
                                        
                                        # Simplify the configuration for retries - modify render_payload
                                        if retry_count == 1:
                                            # First retry: Match the screenshot layout exactly
                                            render_payload["source"]["elements"] = [
                                                # Top layer (Track 3): Logo overlay with animations
                                                {
                                                    "id": "logo-top",
                                                    "name": "logo-top",
                                                    "type": "image",
                                                    "track": 3,
                                                    "time": 0,
                                                    "source": "https://res.cloudinary.com/dodod8s0v/image/upload/v1759927553/logo_2_xwogmb.png",
                                                    "animations": [
                                                        {
                                                            "time": 0,
                                                            "type": "fade",
                                                            "transition": True
                                                        },
                                                        {
                                                            "time": "end",
                                                            "duration": 3,
                                                            "easing": "quadratic-out",
                                                            "reversed": True,
                                                            "type": "fade"
                                                        }
                                                    ]
                                                },
                                                # Middle layer (Track 2): HeyGen intro video
                                                {
                                                    "id": "intro---heygen",
                                                    "name": "intro---heygen",
                                                    "type": "video",
                                                    "track": 2,
                                                    "time": 0,
                                                    "fit": "contain",
                                                    "source": cloudinary_urls.get("intro"),
                                                    "chroma_key_color": "rgba(0,255,0,1)",
                                                    "chroma_key_sensitivity": "50%"
                                                },
                                                # Bottom layer (Track 1): Gameplay footage
                                                {
                                                    "id": "gameplay",
                                                    "name": "gameplay",
                                                    "type": "video",
                                                    "track": 1,
                                                    "time": 0,
                                                    "duration": None,  # Using null (None in Python) as in the reference
                                                    "source": cloudinary_urls.get("vizard"),
                                                    "loop": True,  # Explicit loop property as in the reference
                                                    "volume": "20%",
                                                    "animations": [
                                                        {
                                                            "time": "end",
                                                            "duration": 4,  # 4 second fade out as requested
                                                            "easing": "quadratic-out",
                                                            "reversed": True,
                                                            "type": "fade"
                                                        }
                                                    ]
                                                },
                                                # Outro image at the end - on same track as intro
                                                {
                                                    "id": "outro-image",
                                                    "name": "outro-image",
                                                    "type": "image",
                                                    "track": 2,  # Same track as intro-heygen (track 2) as shown in screenshot
                                                    "time": "auto",  # Will position after the intro-heygen video
                                                    "fit": "cover",
                                                    "duration": 3,
                                                    "source": cloudinary_urls.get("outro"),
                                                    "animations": [
                                                        {
                                                            "time": 0,
                                                            "duration": 0.5,
                                                            "type": "fade",
                                                            "transition": True
                                                        }
                                                    ]
                                                }
                                            ]
                                        elif retry_count == 2:
                                            # Second retry: Simplify but keep the track arrangement from screenshot
                                            logger.info("Final attempt: Using simplified configuration but maintaining track structure")
                                            
                                            render_payload["source"]["elements"] = [
                                                # Top layer (Track 3): Logo overlay (keep this for branding)
                                                {
                                                    "id": "logo-top",
                                                    "name": "logo-top",
                                                    "type": "image",
                                                    "track": 3,  # Top track as shown in screenshot
                                                    "time": 0,
                                                    "source": "https://res.cloudinary.com/dodod8s0v/image/upload/v1759927553/logo_2_xwogmb.png",
                                                    "animations": [
                                                        {
                                                            "time": 0,
                                                            "type": "fade",
                                                            "transition": True
                                                        }
                                                    ]
                                                },
                                                # Bottom layer (Track 1): Gameplay footage
                                                {
                                                    "id": "gameplay",
                                                    "name": "gameplay",
                                                    "type": "video",
                                                    "track": 1,  # Bottom track as shown in screenshot
                                                    "time": 0,
                                                    "duration": None,  # Using null (None in Python) as in the reference
                                                    "source": cloudinary_urls.get("vizard"),
                                                    "loop": True,  # Explicit loop property as in the reference
                                                    "volume": "20%",
                                                    "animations": [
                                                        {
                                                            "time": "end",
                                                            "duration": 4,  # 4 second fade out as requested
                                                            "easing": "quadratic-out",
                                                            "reversed": True,
                                                            "type": "fade"
                                                        }
                                                    ]
                                                },
                                                # Add another element for Track 2 (minimal intro placeholder)
                                                {
                                                    "id": "intro-placeholder",
                                                    "name": "intro-placeholder",
                                                    "type": "color",  # Simple color element as placeholder
                                                    "track": 2,
                                                    "time": 0,
                                                    "width": "0%",  # Make it invisible
                                                    "height": "0%",
                                                    "color": "#00000000",  # Transparent
                                                    "duration": 1  # Very short duration
                                                },
                                                # Outro image at the end - on track 2 as in screenshot
                                                {
                                                    "id": "outro-image",
                                                    "name": "outro-image",
                                                    "type": "image",
                                                    "track": 2,  # Same track as intro (track 2) as shown in screenshot
                                                    "time": "auto",  # Will position after intro placeholder
                                                    "fit": "cover",
                                                    "duration": 3,
                                                    "source": cloudinary_urls.get("outro"),
                                                    "animations": [
                                                        {
                                                            "time": 0,
                                                            "duration": 0.5,
                                                            "type": "fade",
                                                            "transition": True
                                                        }
                                                    ]
                                                }
                                            ]
                                            
                                        # Submit the modified payload
                                        async with session.post(
                                            f"{Config.CREATOMATE_BASE_URL}/renders",
                                            headers=headers,
                                            json=render_payload
                                        ) as retry_response:
                                            if retry_response.status in [200, 202]:
                                                result = await retry_response.json()
                                                render_id = result[0].get('id') if isinstance(result, list) else result.get('id')
                                                if not render_id:
                                                    raise Exception("No render ID returned on retry")
                                            else:
                                                raise Exception(f"Retry submission failed: {retry_response.status}")
                                            
                                except Exception as retry_error:
                                    logger.error(f"Error in retry {retry_count}: {retry_error}")
                                    retry_count += 1
                            
                            # If all retries failed, return both videos for fallback handling
                            logger.warning("All Creatomate attempts failed, returning both videos for manual handling")
                            return {
                                'local_path': "fallback_direct_use",
                                'online_url': cloudinary_urls.get("intro"),
                                'gameplay_url': cloudinary_urls.get("vizard"),
                                'outro_url': cloudinary_urls.get("outro"),
                                'fallback': True
                            }
                        else:
                            logger.error("No render ID returned from Creatomate")
                            raise Exception("Creatomate API did not return a render ID")
                    else:
                        logger.error(f"Creatomate API error: {response.status}")
                        error_text = await response.text()
                        logger.error(f"Error details: {error_text}")
                        raise Exception(f"Creatomate API failed: {response.status}")
            
        except Exception as e:
            logger.error(f"Error creating compilation: {e}")
            raise Exception(f"Compilation creation failed: {e}")
    
    async def _poll_creatomate_status(self, session: aiohttp.ClientSession, headers: Dict, render_id: str) -> Optional[str]:
        """Poll Creatomate API for render completion with improved reliability"""
        max_attempts = 120  # 10 minutes with 5-second intervals
        attempt = 0
        last_logged_progress = -1
        
        while attempt < max_attempts:
            try:
                async with session.get(
                    f"{Config.CREATOMATE_BASE_URL}/renders/{render_id}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        status = result.get('status')
                        
                        if status == 'succeeded':
                            output_url = result.get('url')
                            logger.info(f"✅ Creatomate render completed: {output_url}")
                            return output_url
                        elif status == 'failed':
                            error_msg = result.get('error', 'Unknown error')
                            logger.error(f"❌ Creatomate render failed: {error_msg}")
                            
                            # Try to get more detailed error information
                            details = result.get('errorDetails', {})
                            if details:
                                logger.error(f"Error details: {details}")
                            
                            # Special error handling based on common errors
                            if "invalid input" in error_msg.lower():
                                logger.info("Attempting simplified compilation as fallback")
                                # Return None instead of raising, caller should handle
                                return None
                            else:
                                raise Exception(f"Creatomate render failed: {error_msg}")
                        else:
                            # Only log progress when it changes to avoid log spam
                            progress = int(result.get('progress', 0))
                            if progress != last_logged_progress:
                                logger.info(f"🔄 Creatomate rendering: {progress}%")
                                last_logged_progress = progress
                    elif response.status == 404:
                        logger.warning(f"Render ID not found: {render_id}")
                        await asyncio.sleep(5)  # Wait a bit before retrying
                    else:
                        error_text = await response.text()
                        logger.warning(f"Unexpected status {response.status}: {error_text}")
                
                await asyncio.sleep(5)
                attempt += 1
                
            except Exception as e:
                logger.error(f"Error polling Creatomate status: {e}")
                # More resilient error handling - wait and continue
                await asyncio.sleep(5)
                attempt += 1
                continue
        
        # If we've reached max attempts, try one last time to get any output URL
        try:
            async with session.get(
                f"{Config.CREATOMATE_BASE_URL}/renders/{render_id}",
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('status') == 'succeeded':
                        return result.get('url')
        except Exception:
            pass
            
        raise Exception("Creatomate render timed out after 10 minutes")
    
    async def _download_final_video(self, session: aiohttp.ClientSession, video_url: str, game_title: str) -> str:
        """Download final compiled video"""
        try:
            # Clean filename
            safe_title = "".join(c for c in game_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title}_final_reel.mp4"
            output_path = Config.OUTPUTS_PATH / "final_reels" / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with session.get(video_url) as response:
                if response.status == 200:
                    with open(output_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                    
                    logger.info(f"Downloaded final reel: {output_path}")
                    return str(output_path)
                else:
                    raise Exception(f"Failed to download final video: HTTP {response.status}")
                    
        except Exception as e:
            logger.error(f"Error downloading final video: {e}")
            raise Exception(f"Final video download failed: {e}")