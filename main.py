import asyncio
import sys
import time
import aiohttp
import json
from pathlib import Path
from loguru import logger
from config import Config
from typing import Dict, List, Optional
import os
from utils.steam_scraper import SteamScraper
from modules.module1_intro import IntroGenerator
from modules.module2_vizard import VizardProcessor
from modules.module0_price import PriceComparisonGenerator
from modules.module4_compilation import CreatorMateCompiler
from datetime import datetime

class YouTubeReelsAutomation:
    def __init__(self):
        self.config = Config
        self.steam_scraper = SteamScraper()
        self.intro_generator = IntroGenerator()
        self.vizard_processor = VizardProcessor()
        self.image_generator = PriceComparisonGenerator()
        self.compiler = CreatorMateCompiler()
        
        # Progress tracking
        self.current_step = 0
        self.total_steps = 4
        self.start_time = None
        
        # Setup logging
        logger.add("logs/automation_{time}.log", rotation="1 day", retention="7 days")
        
        # Ensure directories exist
        Config.ensure_directories()
    
    async def get_game_data(self, game_title: str = None, app_id: str = None, custom_video_url: str = None) -> Dict:
        """Get game data either from Steam App ID, title, or return a basic entry
        
        Args:
            game_title: Optional game title (used for backward compatibility)
            app_id: Steam App ID (primary input method)
            custom_video_url: Optional URL for custom gameplay video
        """
        try:
            # Priority 1: If Steam App ID is provided, fetch data directly from Steam API
            if app_id:
                logger.info(f"Using provided Steam App ID: {app_id}")
                from utils.steam_api_scraper import get_steam_game_details
                
                game_data = await get_steam_game_details(app_id)
                
                # Add custom video URL if provided
                if custom_video_url and custom_video_url.strip():
                    if 'custom_videos' not in game_data:
                        game_data['custom_videos'] = []
                    game_data['custom_videos'].append(custom_video_url)
                    logger.info(f"Added custom video URL: {custom_video_url}")
                
                # Ensure title is available
                if game_data and 'name' in game_data:
                    game_data['title'] = game_data['name']
                
                return game_data
                
            # Priority 2: If game title is provided (for backward compatibility)
            elif game_title:
                logger.info(f"Using provided game title: {game_title}")
                
                # Create basic entry with provided title
                return {
                    'title': game_title,
                    'name': game_title,  # For compatibility with both formats
                    'url': '',
                    'release_date': 'TBA',
                    'image_url': '',
                    'source': 'manual',
                    'description': f'Game: {game_title}',
                    'tags': ['Gaming'],
                    'developer': 'Unknown'
                }
                
            # Priority 3: No input provided (fallback)
            else:
                logger.warning("No game title or app_id provided")
                raise Exception("No game title or Steam App ID provided")
                    
        except Exception as e:
            logger.error(f"Error getting game data: {e}")
            return None
    
    def show_loading_animation(self, message: str, duration: float = 2.0):
        """Show loading animation with dots"""
        chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        end_time = time.time() + duration
        i = 0
        while time.time() < end_time:
            print(f"\r{chars[i % len(chars)]} {message}", end="", flush=True)
            time.sleep(0.1)
            i += 1
        print(f"\r✅ {message} - Complete!")
    
    def update_progress(self, step: int, step_name: str):
        """Update and display progress"""
        self.current_step = step
        progress = (step / self.total_steps) * 100
        bar_length = 30
        filled_length = int(bar_length * step // self.total_steps)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        elapsed = time.time() - self.start_time if self.start_time else 0
        elapsed_str = f"{elapsed:.1f}s"
        print(f"📊 Current: {step_name} - Elapsed: {elapsed_str}")
        logger.info(f"Progress: {progress:.1f}% - {step_name}")
    
    async def create_reel_for_game(self, game_data: Dict) -> Optional[str]:
        """Create complete reel for a single game with progress tracking"""
        game_title = game_data['title']
        self.start_time = time.time()
        
        try:
            print(f"\n🎮 Creating reel for: {game_title}")
            print("=" * 60)
            
            # Check if AllKeyShop URL is missing and construct one from game title
            if 'allkeyshop_url' not in game_data or not game_data.get('allkeyshop_url'):
                # Format game title for URL (replace spaces with hyphens, lowercase)
                formatted_title = game_title.lower().replace(' ', '-')
                # Create a likely AllKeyShop URL format
                constructed_url = f"https://www.allkeyshop.com/blog/buy-{formatted_title}-cd-key-compare-prices/"
                game_data['allkeyshop_url'] = constructed_url
                print(f"\n🔎 No AllKeyShop URL provided, constructed URL: {constructed_url}")
                logger.info(f"Constructed AllKeyShop URL from title: {constructed_url}")
            else:
                # Validate and potentially correct the provided URL
                from modules.module0_price import PriceComparisonGenerator
                price_gen = PriceComparisonGenerator()
                original_url = game_data.get('allkeyshop_url')
                
                # Use the generic correction method
                corrected_url = price_gen._correct_url_if_needed(original_url, game_title)
                # If URL was corrected, update it
                if corrected_url != original_url:
                    game_data['allkeyshop_url'] = corrected_url
                    print(f"\n🔧 URL corrected for better matching: {corrected_url}")
                    logger.info(f"Corrected AllKeyShop URL: {corrected_url}")
                else:
                    print(f"\n🔗 Using provided AllKeyShop URL: {original_url}")
            
            # Module 1: Create Intro
            self.update_progress(1, "Creating intro video with HeyGen")
            self.show_loading_animation("Generating intro script with OpenAI", 2)
            intro_path = await self.intro_generator.create_intro(game_title, game_data)
            
            # Check if Module 1 succeeded
            if not intro_path or intro_path == "None" or intro_path is None:
                error_msg = "Module 1 (Intro) failed - no valid video path returned"
                logger.error(error_msg)
                print(f"\n❌ {error_msg}")
                print("🛑 Stopping pipeline - Module 1 must succeed before proceeding")
                raise Exception(error_msg)
            
            print(f"📹 Intro created: {intro_path}")
            print(f"✅ Module 1 completed successfully - proceeding with full pipeline")
            
            # Module 2: Process Gameplay Clip
            self.update_progress(2, "Processing gameplay clip with Vizard")
            self.show_loading_animation("Searching and processing gameplay footage", 3)
            vizard_path = await self.vizard_processor.process_gameplay_clip(game_title, game_data)
            
            # Check if Module 2 succeeded
            if not vizard_path or vizard_path == "None" or vizard_path is None:
                error_msg = "Module 2 (Vizard) failed - no valid video path returned"
                logger.error(error_msg)
                print(f"\n❌ {error_msg}")
                print("🛑 Stopping pipeline - Module 2 must succeed before proceeding")
                raise Exception(error_msg)
            
            print(f"🎮 Gameplay clip processed: {vizard_path}")
            
            # Module 3: Generate price comparison banner
            self.update_progress(3, "Creating price comparison banner")
            self.show_loading_animation("Generating price comparison banner with game info", 2)
            
            # Use separate variables for price banner and outro image
            price_banner_url = None
            # Static fallback URLs
            static_outro_path = "https://res.cloudinary.com/dodod8s0v/image/upload/v1759926961/outro_2_crwy4x.png"
            
            try:
                # Ensure steam_app_id is included in game_data
                if 'app_id' in game_data and 'steam_app_id' not in game_data:
                    # Copy app_id to steam_app_id to ensure it's used by the price comparison module
                    game_data['steam_app_id'] = game_data['app_id']
                    logger.info(f"Added steam_app_id from app_id: {game_data['app_id']}")
                
                # Generate price comparison banner with current pricing info
                # This will be used ONLY for the "coverphoto" element on track 2
                price_banner_url = await self.image_generator.create_outro(game_title, game_data)
                
                # Check if Module 3 succeeded
                if not price_banner_url or price_banner_url == "None" or price_banner_url is None:
                    logger.warning("⚠️⚠️⚠️ Price comparison banner generation FAILED!")
                    price_banner_url = static_outro_path
                    print(f"\n⚠️⚠️⚠️ Using fallback static image for price banner: {price_banner_url}")
                else:     
                    logger.info(f"🔴🔴🔴 MODULE 3 SUCCESS: PRICE BANNER URL: {price_banner_url}")
                    print(f"\n💰💰💰 MODULE 3 SUCCESS: Price comparison banner created: {price_banner_url}")
                
                # Log this prominently to ensure visibility
                print(f"\n=== MODULE 3 PRICE BANNER URL ===")
                print(f"🔵 {price_banner_url}")
                print(f"==============================\n")
                    
                # For backward compatibility, keep outro_path too (used for "outro-image" on track 3)
                outro_path = static_outro_path
                print(f"🎬 Using standard outro image: {outro_path}")
                
            except Exception as e:
                logger.warning(f"Price comparison banner generation error: {e}")
                # Fallback to static images
                price_banner_url = static_outro_path
                outro_path = static_outro_path
                print(f"🎬 Using fallback static images due to error: {static_outro_path}")
            
            # Module 4: Compile Final Reel
            self.update_progress(4, "Compiling final reel with Creatomate")
            self.show_loading_animation("Combining all segments into final video", 4)
            
            # Generate video pipeline with all elements
            logger.info("Generating video pipeline with price comparison banner")
            pipeline = None
            
            try:
                # No need to generate price banner again, we already have it from Module 3
                logger.info(f"Using price banner from Module 3: {price_banner_url}")
                # Make sure we log this important URL clearly in the logs
                logger.info(f"✅ COVERPHOTO URL: {price_banner_url}")
                    
                # Now generate the complete pipeline with all 5 elements
                pipeline = await self.image_generator.generate_video_pipeline(
                    game_title=game_title,
                    game_details=game_data,
                    gameplay_url=vizard_path,
                    intro_url=intro_path,
                    price_banner_url=price_banner_url  # Pass the price banner URL explicitly
                )
                
                # Double check and log the first element with coverphoto
                if pipeline and 'elements' in pipeline:
                    coverphoto_elements = [e for e in pipeline['elements'] if e.get('name') == 'coverphoto']
                    if coverphoto_elements:
                        logger.info(f"COVERPHOTO ELEMENT SOURCE URL: {coverphoto_elements[0].get('source')}")
                        print(f"💳 Final coverphoto URL: {coverphoto_elements[0].get('source')}")
                    else:
                        logger.warning("No coverphoto element found in pipeline!")
                
                if pipeline:
                    logger.info("Successfully created video pipeline structure with all elements")
                    # For debugging, save the pipeline structure
                    pipeline_file = Path(f"pipeline_{game_title.replace(' ', '_')}.json")
                    try:
                        with open(pipeline_file, 'w') as f:
                            json.dump(pipeline, f, indent=2)
                        logger.info(f"Saved pipeline structure to {pipeline_file}")
                    except Exception as e:
                        logger.warning(f"Could not save pipeline structure: {e}")
            except Exception as e:
                logger.warning(f"Could not generate video pipeline: {e}, falling back to standard compilation")
                pipeline = None
            
            # Use the compiler with either the pipeline or standard compilation
            if pipeline and isinstance(pipeline, dict) and "elements" in pipeline:
                # Use the compiler with the generated pipeline, passing the fresh price_banner_url
                logger.info("Using generated pipeline structure with all elements including coverphoto")
                compilation_result = await self.compiler.compile_reel(
                    intro_url=intro_path, 
                    vizard_url=vizard_path, 
                    outro_url=outro_path,
                    game_title=game_title,
                    price_banner_url=price_banner_url  # Use the fresh price comparison banner URL
                )
            else:
                # Fall back to standard compilation if pipeline generation failed
                logger.warning("Falling back to standard compilation method")
                compilation_result = await self.compiler.compile_reel(
                    intro_url=intro_path, 
                    vizard_url=vizard_path, 
                    outro_url=outro_path,
                    game_title=game_title,
                    price_banner_url=price_banner_url or outro_path  # Use the fresh price banner if available
                )
            
            # Handle both old string format and new dict format
            if isinstance(compilation_result, dict):
                final_reel_path = compilation_result.get('local_path')
                online_url = compilation_result.get('online_url')
                logger.info(f"📺 Online video URL: {online_url}")
            else:
                # Backward compatibility - old string return format
                final_reel_path = compilation_result
                online_url = None
            
            # Success notification
            total_time = time.time() - self.start_time
            print(f"\n🎉 SUCCESS! Reel created in {total_time:.1f} seconds")
            print(f"📁 Final reel: {final_reel_path}")      
            if online_url:
                print(f"🌐 Online URL: {online_url}")
            
            # Webhook notification removed
            
            logger.info(f"✅ Successfully created reel: {final_reel_path}")
            
            # Return the result in a format the API can use
            return {
                'local_path': final_reel_path,
                'online_url': online_url,
                'display_path': final_reel_path  # For backward compatibility
            } if online_url else final_reel_path
            
        except Exception as e:
            error_msg = f"Error creating reel for {game_title}: {e}"
            logger.error(error_msg)
            
            # Webhook notification removed
            
            print(f"\n❌ FAILED: {error_msg}")
            raise Exception(f"Reel creation failed: {e}")
    
    async def create_multiple_reels(self, count: int = 3) -> List[str]:
        """Create multiple reels from trending games"""
        try:
            logger.info(f"Creating {count} reels from trending games")
            
            # Code for getting games from Steam has been removed
            # The system now uses Steam App ID directly
            unique_games = []
            
            # Since we're not getting games from Steam anymore, this function
            # should be refactored to use Steam App IDs directly.
            # Leaving unique_games as an empty list will result in no reels created.
            
            # Create reels
            created_reels = []
            for game in unique_games[:count]:
                # Get additional details
                details = self.steam_scraper.get_game_details(game['url'])
                game.update(details)
                
                reel_path = await self.create_reel_for_game(game)
                if reel_path:
                    created_reels.append(reel_path)
            
            logger.info(f"Successfully created {len(created_reels)} reels")
            return created_reels
            
        except Exception as e:
            logger.error(f"Error creating multiple reels: {e}")
            return []
    
    async def run_automation(self, game_title: str = None, count: int = 1, game_details: Dict = None, app_id: str = None, custom_video_url: str = None) -> List[str]:
        """Main automation runner
        
        Args:
            game_title: Optional game title (legacy input method)
            count: Number of reels to create in multiple game mode
            game_details: Optional additional game details to merge
            app_id: Steam App ID (primary input method)
            custom_video_url: Optional URL for custom gameplay video
        """
        try:
            logger.info("🚀 Starting YouTube Reels Automation")
            
            if app_id or game_title:
                # Single game mode
                game_data = await self.get_game_data(game_title=game_title, app_id=app_id, custom_video_url=custom_video_url)
                if not game_data:
                    logger.error(f"Could not find data for game: {game_title or f'App ID {app_id}'}")
                    return []
                
                # Merge provided game_details with scraped game_data
                if game_details:
                    game_data.update(game_details)
                
                reel_path = await self.create_reel_for_game(game_data)
                return [reel_path] if reel_path else []
            else:
                # Multiple games mode
                return await self.create_multiple_reels(count)
                
        except Exception as e:
            logger.error(f"Error in automation: {e}")
            return []
            
    def print_summary(self, created_reels):
        """Print summary of created reels"""
        print("\n" + "="*60)
        print("🎬 YOUTUBE REELS AUTOMATION SUMMARY")
        print("="*60)
        
        if created_reels:
            print(f"✅ Successfully created {len(created_reels)} reel(s):")
            for i, reel_item in enumerate(created_reels, 1):
                # Handle both string paths and dictionary results
                if isinstance(reel_item, dict):
                    reel_path = reel_item.get('display_path') or reel_item.get('local_path') or reel_item.get('online_url')
                    online_url = reel_item.get('online_url')
                else:
                    reel_path = reel_item
                    online_url = None
                    
                if reel_path:
                    try:
                        filename = Path(reel_path).name
                        print(f"   {i}. {filename}")
                        print(f"      📁 {reel_path}")
                        if online_url and online_url != reel_path:
                            print(f"      🌐 {online_url}")
                    except (TypeError, ValueError):
                        # If path can't be processed, just show the raw value
                        print(f"   {i}. Output: {reel_path}")
                        
            print(f"\n📂 Output directory: {Config.OUTPUTS_PATH / 'final_reels'}")
            print("\n🎯 Next steps:")
            print("   1. Review the generated reels")
            print("   2. Upload to YouTube Shorts")
            print("   3. Add relevant hashtags and descriptions")
            print("   4. Schedule for optimal posting times")
        else:
            print("❌ No reels were created successfully")
            print("\n🔍 Check the logs for error details:")
            print("   📄 logs/automation_*.log")
        
        print("="*60)

def show_startup_banner():
    """Show startup banner"""
    print("\n" + "="*80)
    print("🎬 YOUTUBE REELS AUTOMATION SYSTEM - NEW PIPELINE")
    print("="*80)
    print("🚀 Enhanced 4-Module Gaming Content Creation Pipeline")
    print("📹 Module 1: Intro Generation (OpenAI + HeyGen with new template)")
    print("     - Template ID: 9f7cd606790b4a61a241bcafd4b67df0")
    print("     - Green screen for chroma key overlay")
    print("🎮 Module 2: Gameplay Clips (Vizard - no text/subtitles)")
    print("     - Text detection disabled")
    print("     - Focus on highlighted gameplay footage only")
    print("🎬 Module 3: Price Comparison Banner")
    print("     - Game cover with blurred background")
    print("     - Steam vs AllKeyShop price comparison")
    print("     - Prominent 'SAVE X%' discount display")
    print("🎞️ Module 4: Layered Compilation (Creatomate)")
    print("     - HeyGen intro on top with chroma key")
    print("     - Vizard gameplay footage as background")
    print("     - Price comparison banner on track 2")
    print("📱 Target: Vertical 9:16 format for YouTube Shorts")
    print("="*80)

async def run_individual_module(automation, module_num: int, input_value: str, allkeyshop_url: str = None):
    """Run individual modules for testing
    
    Args:
        automation: The automation instance
        module_num: Module number (1-4)
        input_value: Either a game title or Steam App ID
        allkeyshop_url: Optional AllKeyShop URL for price comparison
    """
    # Determine if input is an App ID or game title
    if input_value.isdigit():
        # It's likely a Steam App ID
        game_data = await automation.get_game_data(app_id=input_value)
        print(f"\n🌟 Using Steam App ID: {input_value}")
    else:
        # Treat as a game title
        game_data = await automation.get_game_data(game_title=input_value)
        print(f"\n🌟 Using game title: {input_value}")

    if not game_data:
        print(f"❌ Could not find data for game: {input_value}")
        return None

    print(f"\n🌟 Game: {game_data.get('title') or game_data.get('name')}")
    print("="*60)

    try:
        if module_num == 1:
            print("📹 MODULE 1: INTRO GENERATION")
            print(f"🔧 Generating intro with HeyGen")
            
            # Generate intro normally through the pipeline
            result = await automation.intro_generator.create_intro(game_data['title'], game_data)
            print(f"✅ Intro Cloudinary URL: {result}")
            
        elif module_num == 2:
            print("🎮 MODULE 2: VIZARD GAMEPLAY PROCESSING")
            result = await automation.vizard_processor.process_gameplay_clip(game_data['title'], game_data)
            print(f"✅ Gameplay clip processed: {result}")
            
        elif module_num == 3:
            print("\n\n🔴🔴🔴 MODULE 3: PRICE COMPARISON BANNER GENERATION 🔴🔴🔴")
            print("\n============================================")
            print(f"🔧 Creating price comparison banner with game pricing data for: {game_data['title']}")
            
            # Show if using AllKeyShop URL
            if allkeyshop_url:
                print(f"✅ Using provided AllKeyShop URL: {allkeyshop_url}")
                # Add the AllKeyShop URL to the game data
                game_data['allkeyshop_url'] = allkeyshop_url
            else:
                print("ℹ️ No AllKeyShop URL provided, will attempt to construct one from game title")
            print("============================================")
            
            try:
                # Generate actual price comparison banner with extra debugging
                print("\n1️⃣ STEP 1: Generating fresh price comparison banner...")
                
                # Ensure steam_app_id is included in game_data
                if 'app_id' in game_data and 'steam_app_id' not in game_data:
                    # Copy app_id to steam_app_id to ensure it's used by the price comparison module
                    game_data['steam_app_id'] = game_data['app_id']
                    print(f"Added steam_app_id from app_id: {game_data['app_id']}")
                
                result = await automation.image_generator.create_outro(game_data['title'], game_data)
                
                if result and result != "None":
                    print(f"\n💰💰💰 PRICE BANNER SUCCESS: {result}")
                    print("\n=== PRICE BANNER URL ====")
                    print(f"{result}")
                    print("=========================")
                else:
                    print(f"\n⚠️⚠️⚠️ FAILED TO CREATE PRICE BANNER")
                
                # Also test the video pipeline generation
                print("\n2️⃣ STEP 2: Testing video pipeline generation with price banner...")
                pipeline = await automation.image_generator.generate_video_pipeline(
                    game_title=game_data['title'],
                    game_details=game_data,
                    price_banner_url=result  # Pass the price banner URL explicitly
                )
                
                if pipeline and 'elements' in pipeline:
                    # Verify the coverphoto element exists and has the correct URL
                    coverphoto_elements = [e for e in pipeline['elements'] if e.get('name') == 'coverphoto']
                    if coverphoto_elements:
                        coverphoto = coverphoto_elements[0]
                        print(f"\n💰 VERIFICATION - PIPELINE COVERPHOTO URL: {coverphoto['source']}")
                        
                        # Compare with the generated price banner URL
                        if coverphoto['source'] == result:
                            print(f"\n✅✅✅ SUCCESS: Pipeline is using the freshly generated price banner")
                        else:
                            print(f"\n⚠️⚠️⚠️ WARNING: Pipeline coverphoto URL doesn't match generated price banner!")
                    else:
                        print(f"\n⚠️⚠️⚠️ WARNING: No coverphoto element found in pipeline!")
                    
                    # Save the pipeline to a JSON file for reference
                    import json
                    pipeline_file = 'test_pipeline_output.json'
                    with open(pipeline_file, 'w') as f:
                        json.dump(pipeline, f, indent=2)
                        
                    # Print detailed pipeline info
                    print(f"\n✅ Video pipeline JSON saved to: {pipeline_file}")
                    print(f"🌟 Contains {len(pipeline['elements'])} elements across {max([elem['track'] for elem in pipeline['elements']])} tracks")
                    print("\n== Elements in pipeline: ==")
                    for i, elem in enumerate(pipeline['elements']):
                        print(f"{i+1}. {elem.get('name')} (track {elem.get('track')})")
                else:
                    print(f"\n⚠️⚠️⚠️ ERROR: Failed to generate pipeline")
                    
            except Exception as e:
                print(f"\n❌ ERROR: Failed to create price comparison banner: {str(e)}")
                # Create a fallback Cloudinary URL using the working format pattern
                result = "https://res.cloudinary.com/dodod8s0v/image/upload/v1759926961/outro_2_crwy4x.png"
                print(f"\n⚠️ Using fallback static image: {result}")
            
        elif module_num == 4:
            print("🎞️ MODULE 4: FINAL COMPILATION")
            print("🔄 Getting URLs for complete compilation...")
            
            # First try to get a real price comparison banner
            print("\n\n🔴🔴🔴 MODULE 4 TEST - STEP 1: GENERATING PRICE BANNER 🔴🔴🔴")
            try:
                print("\n1️⃣ STEP 1: Generating fresh price comparison banner...")
                
                # Ensure steam_app_id is included in game_data
                if 'app_id' in game_data and 'steam_app_id' not in game_data:
                    # Copy app_id to steam_app_id to ensure it's used by the price comparison module
                    game_data['steam_app_id'] = game_data['app_id']
                    print(f"Added steam_app_id from app_id: {game_data['app_id']}")
                
                price_banner_url = await automation.image_generator.create_outro(game_data['title'], game_data)
                
                if price_banner_url and price_banner_url != "None":
                    print(f"\n💰💰💰 PRICE BANNER SUCCESS: {price_banner_url}")
                    print("\n=== PRICE BANNER URL ====")
                    print(f"{price_banner_url}")
                    print("=========================")
                    
                    # Make sure to use separate outro_url for the outro image
                    outro_url = "https://res.cloudinary.com/dodod8s0v/image/upload/v1759926961/outro_2_crwy4x.png"  # Static outro
                    print(f"\n🎬 Using static image for outro-image: {outro_url}")
                else:
                    print(f"\n⚠️⚠️⚠️ FAILED TO CREATE PRICE BANNER")
                    price_banner_url = "https://res.cloudinary.com/dodod8s0v/image/upload/v1759926961/outro_2_crwy4x.png"  # Fallback
                    outro_url = price_banner_url  # Use same fallback for outro
                    print(f"\n⚠️ Using fallback static image: {price_banner_url}")
            except Exception as e:
                print(f"\n❌ ERROR: Failed to create price comparison banner: {str(e)}")
                price_banner_url = "https://res.cloudinary.com/dodod8s0v/image/upload/v1759926961/outro_2_crwy4x.png"  # Fallback
                outro_url = price_banner_url  # Use same fallback for outro
                print(f"\n⚠️ Using fallback static image: {price_banner_url}")
            
            # Use sample URLs for intro and gameplay if needed
            vizard_url = "https://res.cloudinary.com/dodod8s0v/video/upload/v1759232292/youtube_reels/vizard_vizard_The_Elder_Scrolls_VI.mp4"
            intro_url = "http://res.cloudinary.com/dodod8s0v/video/upload/v1761635613/youtube_reels/intro_Gothic_1_Remake.mp4"
            
            print(f"📹 Intro URL: {intro_url}")
            print(f"🎮 Vizard URL: {vizard_url}")
            print(f"🎬 Outro URL: {outro_url}")
            print(f"💳 Price Banner URL: {price_banner_url}")
            
            # First try to create the compilation with our new pipeline structure
            print("\n🔴🔴🔴 MODULE 4 TEST - STEP 2: GENERATING PIPELINE 🔴🔴🔴")
            try:
                print("\n2️⃣ STEP 2: Testing video pipeline generation with price banner...")
                pipeline = await automation.image_generator.generate_video_pipeline(
                    game_title=game_data['title'],
                    game_details=game_data,
                    gameplay_url=vizard_url,
                    intro_url=intro_url,
                    price_banner_url=price_banner_url  # Pass the price banner URL explicitly
                )
                
                # Double check and log the first element with coverphoto
                if pipeline and 'elements' in pipeline:
                    coverphoto_elements = [e for e in pipeline['elements'] if e.get('name') == 'coverphoto']
                    if coverphoto_elements:
                        print(f"💳 Module 4 Test - Coverphoto URL: {coverphoto_elements[0].get('source')}")
                    else:
                        print("⚠️ Warning: No coverphoto element found in pipeline!")
                
                # Save the pipeline for reference (this could be used with the compiler)
                import json
                with open('module4_pipeline_output.json', 'w') as f:
                    json.dump(pipeline, f, indent=2)
                print(f"✅ Video pipeline JSON created and saved to module4_pipeline_output.json")
            except Exception as e:
                print(f"❌ Pipeline generation error: {e}")
            
            # Now proceed with standard compilation
            print("\n🔴🔴🔴 MODULE 4 TEST - STEP 3: FINAL COMPILATION 🔴🔴🔴")
            print("\n3️⃣ STEP 3: Proceeding to standard compilation...")
            
            # Verify again all URLs are correct
            print(f"\n=== COMPILATION URLS ===")
            print(f"Intro URL: {intro_url}")
            print(f"Gameplay URL: {vizard_url}")
            print(f"Outro URL: {outro_url}")
            print(f"💰💰💰 PRICE BANNER URL: {price_banner_url}")
            print(f"======================")
            
            result = await automation.compiler.compile_reel(
                intro_url=intro_url, 
                vizard_url=vizard_url, 
                outro_url=outro_url, 
                game_title=game_data['title'],
                price_banner_url=price_banner_url  # Pass the price comparison banner URL separately for track 2
            )
            print(f"✅ Final compilation created: {result}")
            return result
            
        return result
        
    except Exception as e:
        print(f"❌ Module {module_num} failed: {e}")
        logger.error(f"Module {module_num} error: {e}")
        return None

async def main():
    """Main function to test the new pipeline approach with layered videos"""
    show_startup_banner()
    
    print("\n🧪 TESTING NEW PIPELINE APPROACH")
    print("=" * 60)
    print("📋 New Pipeline Components:")
    print("1. HeyGen Intro - Updated template: 9f7cd606790b4a61a241bcafd4b67df0")
    print("2. Vizard Gameplay - No text/subtitles, only highlighted footage")
    print("3. New Compilation - HeyGen on top with chroma key + Vizard footage beneath")
    print("=" * 60)
    
    # Initialize the automation system
    automation = YouTubeReelsAutomation()
    
    # Ask for a game title or Steam App ID for testing
    print("\n🎮 Enter a game title or Steam App ID to test:")
    print("   Example game titles: 'Elden Ring', 'Cyberpunk 2077'")
    print("   Example Steam App IDs: '1245620' (Elden Ring), '1091500' (Cyberpunk 2077)")
    
    input_value = input("\n🎯 Enter game title or Steam App ID: ").strip()
    
    if not input_value:
        print("❌ No input provided. Using 'Elden Ring' as a test.")
        input_value = "Elden Ring"
    
    # Determine if it's an App ID or a game title
    if input_value.isdigit():
        print(f"\n🎯 Using Steam App ID: {input_value}")
        
        # Get game data from Steam API
        try:
            from utils.steam_api_scraper import get_steam_game_details
            game_data = await get_steam_game_details(input_value)
            
            if not game_data:
                print(f"❌ Could not find Steam game with App ID: {input_value}")
                print("🔄 Using basic game data instead.")
                game_data = {
                    'title': f"Steam Game {input_value}",
                    'name': f"Steam Game {input_value}",
                    'release_date': "2023",
                    'developer': "Unknown Developer",
                    'price': "$29.99",
                    'allkeyshop_price': "$19.99",
                    'editions': ["Standard Edition", "Deluxe Edition"],
                    'platforms': ["Windows", "Mac", "Linux"],
                    'updates': "Latest update adds new content and fixes bugs."
                }
            else:
                # Add test data for fields that might not be in the Steam API response
                game_data['price'] = game_data.get('price', "$29.99")
                game_data['allkeyshop_price'] = "$19.99"  # AllKeyShop price for testing
                game_data['editions'] = game_data.get('editions', ["Standard Edition", "Deluxe Edition"])
                game_data['platforms'] = game_data.get('platforms', ["Windows", "Mac", "Linux"])
                game_data['updates'] = game_data.get('updates', "Latest update adds new content and fixes bugs.")
                
                print(f"✅ Found game: {game_data.get('name')}")
            
        except Exception as e:
            print(f"❌ Error getting game data: {e}")
            print("🔄 Using basic game data instead.")
            game_data = {
                'title': f"Steam Game {input_value}",
                'name': f"Steam Game {input_value}",
                'release_date': "2023",
                'developer': "Unknown Developer",
                'price': "$29.99",
                'allkeyshop_price': "$19.99",
                'editions': ["Standard Edition", "Deluxe Edition"],
                'platforms': ["Windows", "Mac", "Linux"],
                'updates': "Latest update adds new content and fixes bugs."
            }
    else:
        # Using game title
        print(f"\n🎯 Using game title: {input_value}")
        game_data = {
            'title': input_value,
            'name': input_value,
            'release_date': "2023",
            'developer': "Unknown Developer",
            'price': "$29.99",
            'allkeyshop_price': "$19.99",
            'editions': ["Standard Edition", "Deluxe Edition"],
            'platforms': ["Windows", "Mac", "Linux"],
            'updates': "Latest update adds new content and fixes bugs."
        }
    
    # Extract game title safely for testing
    game_title = game_data.get('title') or game_data.get('name') or "Unknown Game"
    
    # Test the entire pipeline with the new approach
    print("\n🚀 RUNNING COMPLETE PIPELINE WITH NEW APPROACH")
    print("=" * 60)
    
    try:
        # Module 1: Generate Intro with HeyGen (new template with chroma key)
        print("\n📹 MODULE 1: GENERATING INTRO WITH HEYGEN")
        print("🧪 Using new HeyGen template: 9f7cd606790b4a61a241bcafd4b67df0")
        
        try:
            # Generate intro script with timeout handling
            print("Generating intro script with OpenAI...")
            script = await asyncio.wait_for(
                automation.intro_generator.generate_intro_script(game_title, game_data),
                timeout=60  # 60 second timeout
            )
            print("✅ Intro script generated successfully")
            
            # Generate intro video with HeyGen - with better error handling
            print("Submitting to HeyGen API - this may take a few minutes...")
            intro_url = await automation.intro_generator.generate_heygen_video(script, game_title)
            
            if not intro_url or "error" in str(intro_url).lower():
                raise Exception(f"HeyGen failed to generate video: {intro_url}")
                
            print(f"✅ HeyGen intro video created: {intro_url}")
        except Exception as e:
            print(f"❌ MODULE 1 FAILED: {e}")
            logger.error(f"Module 1 (Intro) error: {e}")
            raise Exception(f"Module 1 failed: {e}")
        
        # Module 2: Process gameplay with Vizard.ai (no text/subtitles)
        print("\n🎮 MODULE 2: PROCESSING GAMEPLAY WITH VIZARD")
        print("🧪 Vizard configured for no text/subtitles, only highlighted footage")
        
        try:
            # Add custom video URL if provided
            custom_video_url = input("\n🎬 Enter a custom YouTube URL for gameplay (or press Enter to skip): ").strip()
            if custom_video_url:
                if 'custom_videos' not in game_data:
                    game_data['custom_videos'] = []
                game_data['custom_videos'].append(custom_video_url)
                print(f"✅ Using custom video URL: {custom_video_url}")
            
            # Process gameplay with Vizard - with improved error handling
            print("Submitting to Vizard AI - this may take a few minutes...")
            vizard_url = await automation.vizard_processor.process_gameplay_clip(game_title, game_data)
            
            if not vizard_url or "error" in str(vizard_url).lower():
                raise Exception(f"Vizard failed to process gameplay: {vizard_url}")
                
            print(f"✅ Vizard gameplay processed: {vizard_url}")
        except Exception as e:
            print(f"❌ MODULE 2 FAILED: {e}")
            logger.error(f"Module 2 (Vizard) error: {e}")
            raise Exception(f"Module 2 failed: {e}")
        
        # Module 3: Generate Price Comparison Banner
        print("\n🎥 MODULE 3: GENERATING PRICE COMPARISON BANNER")
        
        # Ask for an optional AllKeyShop URL for more precise price comparison
        aks_url = input("\n💳 Enter AllKeyShop URL (or press Enter to generate one from game title): ").strip()
        
        if aks_url:
            # Add the AllKeyShop URL to the game data
            game_data['allkeyshop_url'] = aks_url
            print(f"✅ Using provided AllKeyShop URL: {aks_url}")
        else:
            print("ℹ️ Will generate AllKeyShop URL from game title")
        
        try:
            # Ensure steam_app_id is included in game_data
            if 'app_id' in game_data and 'steam_app_id' not in game_data:
                # Copy app_id to steam_app_id to ensure it's used by the price comparison module
                game_data['steam_app_id'] = game_data['app_id']
                logger.info(f"Added steam_app_id from app_id: {game_data['app_id']}")
            
            # Generate the price comparison banner
            price_banner_url = await automation.image_generator.create_outro(game_title, game_data)
            
            if not price_banner_url or "error" in str(price_banner_url).lower():
                raise Exception(f"Failed to generate price comparison banner: {price_banner_url}")
                
            print(f"✅ Price comparison banner generated: {price_banner_url}")
            
            # For backward compatibility, use a standard outro image
            outro_url = "https://res.cloudinary.com/dodod8s0v/image/upload/v1759926961/outro_2_crwy4x.png"
            print(f"🎥 Using standard outro image: {outro_url}")
        except Exception as e:
            print(f"❌ MODULE 3 FAILED: {e}")
            logger.error(f"Module 3 (Price Comparison Banner) error: {e}")
            raise Exception(f"Module 3 failed: {e}")
        
        # Module 4: Create compilation with new layered approach
        print("\n🎞️ MODULE 4: CREATING FINAL COMPILATION")
        print("🧪 Using new layered approach:")
        print("  - HeyGen intro on top with chroma key to preserve captions")
        print("  - Vizard gameplay footage beneath as background")
        
        try:
            # Verify all URLs before starting compilation
            print("Verifying media URLs before compilation...")
            for url_name, url in {"Intro": intro_url, "Vizard": vizard_url, "Outro": outro_url}.items():
                if not url or not isinstance(url, str) or not url.startswith("http"):
                    raise Exception(f"Invalid {url_name} URL: {url}")
            
            # Compile the final reel
            print("Starting Creatomate compilation - this may take several minutes...")
            result = await automation.compiler.compile_reel(intro_url, vizard_url, outro_url, game_title)
            
            # Display result
            print("\n🎉 PIPELINE COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            
            if isinstance(result, dict):
                output_path = result.get('local_path')
                online_url = result.get('online_url')
                print(f"📁 Local path: {output_path}")
                print(f"🌐 Online URL: {online_url}")
            else:
                print(f"📁 Output: {result}")
        except Exception as e:
            print(f"❌ MODULE 4 FAILED: {e}")
            logger.error(f"Module 4 (Compilation) error: {e}")
            raise Exception(f"Module 4 failed: {e}")
        
    except Exception as e:
        print(f"\n❌ Pipeline test failed: {e}")
        logger.error(f"Pipeline test error: {e}")
    
    print("\n🏁 TEST COMPLETE")
    return

if __name__ == "__main__":
    import argparse
    
    # Set up command line argument parser
    parser = argparse.ArgumentParser(description='YouTube Reels Automation System - New Pipeline')
    parser.add_argument('--module', type=int, choices=[1, 2, 3, 4], help='Run a specific module (1-4)')
    parser.add_argument('--game', help='Game title or Steam App ID')
    parser.add_argument('--video', help='Custom YouTube URL for gameplay')
    parser.add_argument('--new-pipeline', action='store_true', help='Use the new pipeline with layered videos')
    parser.add_argument('--aks-url', help='AllKeyShop URL for price comparison banner generation')
    args = parser.parse_args()
    
    if args.module and args.game:
        # Run a specific module
        automation = YouTubeReelsAutomation()
        asyncio.run(run_individual_module(automation, args.module, args.game, args.aks_url))
    elif args.game:
        # Run full pipeline with specified game
        automation = YouTubeReelsAutomation()
        game_data = asyncio.run(automation.get_game_data(game_title=args.game if not args.game.isdigit() else None, 
                                                     app_id=args.game if args.game.isdigit() else None,
                                                     custom_video_url=args.video))
        if game_data:
            # Add AllKeyShop URL to game data if provided
            if args.aks_url:
                game_data['allkeyshop_url'] = args.aks_url
                print(f"✅ Using provided AllKeyShop URL: {args.aks_url}")
            
            asyncio.run(automation.create_reel_for_game(game_data))
    else:
        # Run the interactive mode
        asyncio.run(main())
    
    # Example usage:
    # python3 main.py                                  # Interactive mode with new pipeline
    # python3 main.py --game 1091500                   # Full pipeline with Steam App ID
    # python3 main.py --game "Cyberpunk 2077"          # Full pipeline with game title
    # python3 main.py --game 1091500 --video "https://www.youtube.com/watch?v=xxxxx"  # With custom video
    # python3 main.py --game 1091500 --aks-url "https://www.allkeyshop.com/blog/buy-game-name-cd-key-compare-prices/"  # With AllKeyShop URL
    # python3 main.py --module 1 --game 1091500        # Run only intro module
    # python3 main.py --module 2 --game "Elden Ring"   # Run only Vizard module
    # python3 main.py --module 3 --game 1091500 --aks-url "https://www.allkeyshop.com/blog/buy-game-name-cd-key-compare-prices/"  # Run price comparison module with custom URL
    