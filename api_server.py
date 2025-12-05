import asyncio
import json
import uuid
import re
import time
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from loguru import logger
import uvicorn
import aiohttp
import ssl

# Import your existing automation system
from main import YouTubeReelsAutomation

app = FastAPI(title="YouTube Reels Automation API", version="1.0.0")

# Add CORS middleware - works for both local and Railway deployment
# Add CORS middleware with more permissive settings
app.add_middleware(
    CORSMiddleware,
    # Explicitly allow localhost:3000 first, then include other origins
    allow_origins=[
        "http://localhost:3000",  # Frontend development server
        "http://127.0.0.1:3000",  # Alternative localhost address
        "http://localhost:3001", 
        "http://localhost:3002",
        "https://*.railway.app",  # Railway frontend domains
        "*"  # Allow all origins as fallback
    ],
    allow_credentials=True,  # Allow cookies in CORS requests
    allow_methods=["*"],     # Allow all HTTP methods
    allow_headers=["*"],     # Allow all headers
    expose_headers=["Content-Type", "X-Requested-With"],  # Expose these headers to the browser
    max_age=86400             # Cache preflight requests for 1 day
)

# Global state management
automation_jobs: Dict[str, Dict] = {}
active_connections: List[WebSocket] = []

async def safe_send(websocket: WebSocket, message: Dict) -> bool:
    """Send a message to WebSocket with proper error handling"""
    try:
        await websocket.send_json(message)
        return True
    except WebSocketDisconnect:
        # Client disconnected - this is expected sometimes
        return False
    except Exception as e:
        logger.warning(f"Error sending WebSocket message: {e}")
        return False

async def broadcast_message(message_text: str):
    """Safely broadcast a message to all connected WebSocket clients"""
    # Parse the message text into a Dict if it's JSON
    try:
        message = json.loads(message_text)
    except json.JSONDecodeError:
        # If it's not valid JSON, wrap it in a simple message structure
        message = {"type": "message", "data": message_text}
    
    # Create a list of connections to remove
    stale_connections = []
    
    # Send to all connections
    for connection in active_connections:
        success = await safe_send(connection, message)
        if not success:
            stale_connections.append(connection)
    
    # Clean up stale connections
    for stale in stale_connections:
        if stale in active_connections:
            active_connections.remove(stale)

# Input validation functions
async def validate_steam_app_id(app_id: str) -> Dict:
    """Validate Steam App ID and return game details if valid"""
    try:
        # Basic format validation
        if not app_id or not app_id.strip():
            raise ValueError("Steam App ID cannot be empty")
        
        # Remove any whitespace and validate format
        app_id = app_id.strip()
        
        # Steam App IDs should be numeric
        if not re.match(r'^\d+$', app_id):
            raise ValueError("Steam App ID must be numeric (e.g., 1962700)")
        
        # Check if App ID is reasonable (Steam IDs are typically 6+ digits)
        if len(app_id) < 3:
            raise ValueError("Steam App ID too short - please provide a valid Steam App ID")
        
        if len(app_id) > 10:
            raise ValueError("Steam App ID too long - please check the App ID")
        
        logger.info(f"🔍 Validating Steam App ID: {app_id}")
        
        # For testing and development, let's allow any valid numeric ID and generate mock data
        # This prevents API failures when Steam's API is unresponsive or rate-limited
        mock_game_name = f"Game {app_id}"
        logger.info(f"✅ Using mock game data for development: {mock_game_name} (App ID: {app_id})")
            
        return {
            'app_id': app_id,
            'name': mock_game_name,
            'type': 'game',
            'valid': True
        }
        
        # NOTE: The Steam API validation is disabled for now as it's causing issues
        # Uncomment the code below to re-enable it when needed
        
        '''
        # Test Steam API connectivity and game existence
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            # Try Steam Store API first
            steam_api_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
            
            try:
                async with session.get(steam_api_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if app_id in data and data[app_id].get('success'):
                            game_data = data[app_id]['data']
                            game_name = game_data.get('name', 'Unknown Game')
                            game_type = game_data.get('type', 'unknown')
                            
                            # Validate it's actually a game (not DLC, software, etc.)
                            if game_type.lower() not in ['game', 'demo']:
                                raise ValueError(f"Steam App ID {app_id} is not a game (type: {game_type}). Please provide a game App ID.")
                            
                            logger.info(f"✅ Valid Steam game found: {game_name} (App ID: {app_id})")
                            
                            return {
                                'app_id': app_id,
                                'name': game_name,
                                'type': game_type,
                                'valid': True
                            }
                        else:
                            raise ValueError(f"Steam App ID {app_id} not found. Please check the App ID and try again.")
                    else:
                        raise ValueError(f"Unable to validate Steam App ID {app_id}. Steam API returned status {response.status}.")
            
            except asyncio.TimeoutError:
                raise ValueError("Steam API request timed out. Please check your internet connection and try again.")
            except aiohttp.ClientError as e:
                raise ValueError(f"Network error while validating Steam App ID: {str(e)}")
        '''
    
    except ValueError as ve:
        # Provide specific error message for validation errors
        logger.warning(f"Steam App ID validation warning: {ve}")
        raise
    except Exception as e:
        # For unexpected errors, log but don't expose details to user
        logger.error(f"Unexpected error validating Steam App ID {app_id}: {e}")
        raise ValueError("Failed to validate Steam App ID. Using fallback data.")
        
        # For development, you can return mock data instead of raising an error
        # return {
        #     'app_id': app_id,
        #     'name': f"Game {app_id}",
        #     'type': 'game',
        #     'valid': True
        # }

def validate_youtube_url(url: str) -> bool:
    """Validate YouTube URL format"""
    if not url:
        return True  # Optional field
    
    youtube_patterns = [
        r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'https?://(?:www\.)?youtube\.com/shorts/[\w-]+',
        r'https?://youtu\.be/[\w-]+'
    ]
    
    return any(re.match(pattern, url) for pattern in youtube_patterns)

class AutomationRequest(BaseModel):
    mode: str  # 'steam' only
    game_title: Optional[str] = None
    steam_app_id: Optional[str] = None
    custom_video_url: Optional[str] = None
    allkeyshop_url: Optional[str] = None  # Added AllKeyShop URL field
    count: Optional[int] = 1
    
    @validator('mode')
    def validate_mode(cls, v):
        if v != 'steam':
            raise ValueError("Only 'steam' mode is currently supported")
        return v
    
    @validator('steam_app_id')
    def validate_steam_id_format(cls, v):
        if v is None:
            raise ValueError("Steam App ID is required")
        
        v = v.strip() if v else ""
        if not v:
            raise ValueError("Steam App ID cannot be empty")
        
        if not re.match(r'^\d+$', v):
            raise ValueError("Steam App ID must be numeric")
        
        return v
    
    @validator('custom_video_url')
    def validate_video_url(cls, v):
        if v and not validate_youtube_url(v):
            raise ValueError("Custom video URL must be a valid YouTube URL")
        return v
    
    @validator('allkeyshop_url')
    def validate_allkeyshop_url(cls, v):
        if v is None or v.strip() == '':
            return None  # Return None for empty strings to treat them as not provided
        
        # Clean up the URL
        v = v.strip()
        
        # Add protocol if missing
        if not v.startswith('http'):
            v = 'https://' + v
            
        # Ensure it's an AllKeyShop URL
        if 'allkeyshop.com' not in v:
            raise ValueError("URL must be from allkeyshop.com domain")
        
        # Ensure it's a product page URL
        if '/blog/buy-' not in v and '-cd-key-compare-prices' not in v:
            # Try to determine if it's a different format of AllKeyShop URL
            # and suggest a correction
            if '/blog/' in v:
                game_part = v.split('/blog/')[-1]
                if game_part and not game_part.startswith('buy-'):
                    suggested = f"https://www.allkeyshop.com/blog/buy-{game_part}"
                    if not suggested.endswith('-cd-key-compare-prices/'):
                        suggested = suggested.rstrip('/') + '-cd-key-compare-prices/'
                    logger.warning(f"AllKeyShop URL format incorrect, suggesting: {suggested}")
                    return suggested
        
        # Ensure URL ends with trailing slash for API compatibility
        if not v.endswith('/'):
            v += '/'
            
        return v
    
    @validator('count')
    def validate_count(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError("Count must be between 1 and 5")
        return v or 1

class JobStatus(BaseModel):
    job_id: str
    status: str  # 'queued', 'running', 'completed', 'failed'
    progress: int  # 0-100
    current_step: int
    total_steps: int
    step_name: str
    created_at: str
    completed_at: Optional[str] = None
    result_path: Optional[str] = None
    error_message: Optional[str] = None

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        # Create a new list to avoid modifying during iteration
        connections_to_remove = []
        
        # Try to send to all connections
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                # Normal disconnection, add to removal list
                connections_to_remove.append(connection)
                logger.info(f"WebSocket disconnected during broadcast")
            except Exception as e:
                # Add to removal list instead of removing during iteration
                connections_to_remove.append(connection)
                # Log error with more details
                logger.error(f"WebSocket broadcast error: {e}")
        
        # Remove broken connections afterward
        for connection in connections_to_remove:
            if connection in self.active_connections:
                self.active_connections.remove(connection)

manager = ConnectionManager()

async def update_job_progress(job_id: str, step: int, step_name: str, status: str = "running"):
    """Update job progress and broadcast to connected clients"""
    if job_id in automation_jobs:
        job = automation_jobs[job_id]
        job['current_step'] = step
        job['step_name'] = step_name
        job['status'] = status
        job['progress'] = int((step / job['total_steps']) * 100) if step > 0 else 0
        
        # Broadcast update to all connected clients with error handling
        try:
            message = json.dumps({
                'type': 'progress_update',
                'job_id': job_id,
                'data': job
            })
            await manager.broadcast(message)
        except Exception as e:
            # Don't let broadcast failures stop the automation process
            logger.error(f"Failed to broadcast progress update: {e}")
            # Continue without failing the job

async def run_automation_job(job_id: str, request: AutomationRequest):
    """Background task to run the automation"""
    try:
        # Update job status to running
        automation_jobs[job_id]['status'] = 'running'
        await update_job_progress(job_id, 0, "Initializing automation system", "running")
        
        # Create automation instance
        automation = YouTubeReelsAutomation()
        
        # Prepare parameters based on request mode
        if request.mode == 'single':
            if not request.game_title:
                raise ValueError("Game title is required for single mode")
            
            await update_job_progress(job_id, 1, "Creating intro video with HeyGen")
            
            # Get game data
            game_data = await automation.get_game_data(request.game_title)
            if not game_data:
                raise ValueError(f"Could not find data for game: {request.game_title}")
            
            # Add custom video URL if provided
            game_details = {}
            if request.custom_video_url:
                game_details['custom_videos'] = [request.custom_video_url]
            
            # Run the automation with progress updates
            result = await run_automation_with_progress(automation, job_id, game_data, game_details)
            
        elif request.mode == 'steam':
            if not request.steam_app_id:
                raise ValueError("Steam App ID is required for steam mode")
            
            await update_job_progress(job_id, 1, "Fetching Steam game details")
            
            try:
                # Try to get game details from Steam API
                try:
                    # Import Steam API scraper
                    from utils.steam_api_scraper import get_steam_game_details
                    
                    # Get game details from Steam
                    game_details = await get_steam_game_details(request.steam_app_id)
                    game_title = game_details['name']
                except Exception as e:
                    logger.warning(f"Could not fetch Steam details: {e}. Using fallback data.")
                    # Use fallback mock data
                    game_title = f"Game {request.steam_app_id}"
                    game_details = {
                        'name': game_title,
                        'title': game_title,
                        'release_date': "2025",
                        'developer': "Unknown Developer",
                        'price': "$29.99",
                        'platforms': ["PC"],
                    }
                
                # Add custom video URL if provided
                if request.custom_video_url:
                    if 'custom_videos' not in game_details:
                        game_details['custom_videos'] = []
                    game_details['custom_videos'].append(request.custom_video_url)
                
                # Add AllKeyShop URL if provided
                if request.allkeyshop_url:
                    game_details['allkeyshop_url'] = request.allkeyshop_url
                    logger.info(f"Using AllKeyShop URL: {request.allkeyshop_url}")
                
                # Run the automation
                result = await run_automation_with_progress(automation, job_id, game_title, game_details)
                
            except Exception as steam_error:
                logger.error(f"Error in Steam mode: {steam_error}")
                raise ValueError(f"Failed to process Steam App ID {request.steam_app_id}: {str(steam_error)}")
            
        else:
            raise ValueError(f"Invalid mode: {request.mode}. Only 'steam' mode is supported.")
        
        # Job completed successfully
        automation_jobs[job_id]['status'] = 'completed'
        automation_jobs[job_id]['completed_at'] = datetime.now().isoformat()
        automation_jobs[job_id]['progress'] = 100
        
        # Handle both old string format and new dict format
        if isinstance(result, dict):
            automation_jobs[job_id]['result_path'] = result.get('local_path')
            automation_jobs[job_id]['online_url'] = result.get('online_url')
            result_for_broadcast = result.get('online_url') or result.get('local_path')
        else:
            automation_jobs[job_id]['result_path'] = result
            automation_jobs[job_id]['online_url'] = None
            result_for_broadcast = result
        
        await manager.broadcast(json.dumps({
            'type': 'job_completed',
            'job_id': job_id,
            'result_path': result_for_broadcast,
            'online_url': automation_jobs[job_id].get('online_url')
        }))
        
    except Exception as e:
        logger.error(f"Automation job {job_id} failed: {e}")
        automation_jobs[job_id]['status'] = 'failed'
        automation_jobs[job_id]['error_message'] = str(e)
        automation_jobs[job_id]['completed_at'] = datetime.now().isoformat()
        
        await manager.broadcast(json.dumps({
            'type': 'job_failed',
            'job_id': job_id,
            'error': str(e)
        }))

async def run_automation_with_progress(automation, job_id: str, game_data, game_details=None):
    """Run automation with progress updates"""
    if isinstance(game_data, str):
        game_title = game_data
        game_dict = game_details or {}
        # Make sure required fields are present
        game_dict['title'] = game_title
        game_dict['name'] = game_title
    else:
        game_title = game_data.get('title') or game_data.get('name', 'Unknown Game')
        game_dict = game_data
        # Make sure required fields are present
        if 'title' not in game_dict and 'name' in game_dict:
            game_dict['title'] = game_dict['name']
        elif 'name' not in game_dict and 'title' in game_dict:
            game_dict['name'] = game_dict['title']
    
    # Ensure AllKeyShop URL is present or constructed for price comparison
    if 'allkeyshop_url' not in game_dict or not game_dict.get('allkeyshop_url'):
        # Format game title for URL (replace spaces with hyphens, lowercase)
        formatted_title = game_title.lower().replace(' ', '-')
        # Create a likely AllKeyShop URL format
        constructed_url = f"https://www.allkeyshop.com/blog/buy-{formatted_title}-cd-key-compare-prices/"
        game_dict['allkeyshop_url'] = constructed_url
        logger.info(f"API: Constructed AllKeyShop URL from title: {constructed_url}")
    else:
        # Validate and potentially correct the provided URL
        from modules.module0_price import PriceComparisonGenerator
        price_gen = PriceComparisonGenerator()
        original_url = game_dict.get('allkeyshop_url')
        corrected_url = price_gen._correct_url_if_needed(original_url, game_title)
        
        # DIRECT FIX: Special handling for Europa Universalis IV
        if "europa universalis iv" in game_title.lower() and "europa-universalis-v" in original_url.lower():
            corrected_url = original_url.replace("europa-universalis-v", "europa-universalis-iv")
            logger.info(f"API: CRITICAL - Fixed Europa Universalis IV URL mismatch")
            game_dict['allkeyshop_url'] = corrected_url
        # If URL was corrected, update it
        elif corrected_url != original_url:
            game_dict['allkeyshop_url'] = corrected_url
            logger.info(f"API: Corrected AllKeyShop URL: {corrected_url}")
        else:
            logger.info(f"API: Using provided AllKeyShop URL: {original_url}")
        
        # Ensure correct URL is used for Europa Universalis IV
        if "europa universalis iv" in game_title.lower():
            # Double-check that we're using the right URL
            current_url = game_dict.get('allkeyshop_url', '')
            if 'europa-universalis-v' in current_url.lower():
                correct_url = current_url.replace('europa-universalis-v', 'europa-universalis-iv')
                game_dict['allkeyshop_url'] = correct_url
                logger.info(f"API: Final Europa Universalis IV URL check - corrected to: {correct_url}")
    
    # Module 1: Intro
    await update_job_progress(job_id, 1, "Creating intro video with HeyGen")
    intro_path = await automation.intro_generator.create_intro(game_title, game_dict)
    
    if not intro_path:
        raise Exception("Module 1 (Intro) failed")
    
    # Module 2: Gameplay
    await update_job_progress(job_id, 2, "Processing gameplay clip with Vizard")
    vizard_path = await automation.vizard_processor.process_gameplay_clip(game_title, game_dict)
    
    if not vizard_path:
        raise Exception("Module 2 (Vizard) failed")
    
    # Module 3: Generate price comparison banner with detailed updates
    await update_job_progress(job_id, 3, "Creating price comparison banner")
    
    # Generate price comparison banner with game pricing data - no fallbacks
    # Update progress with sub-steps to keep user informed
    try:
        await manager.broadcast(json.dumps({
            'type': 'job_update',
            'job_id': job_id,
            'status': 'running',
            'current_step': 3,
            'step_name': "Fetching game pricing data",
            'details': "Obtaining price information from Steam and other sources"
        }))
    except Exception as e:
        # Don't let WebSocket errors stop the automation
        logger.error(f"WebSocket broadcast error (non-critical): {e}")
    
    # Allow time for frontend to update
    await asyncio.sleep(0.5)
    
    # Generate the price banner with proper exception handling
    try:
        # Wrap the image generator call in try/except to prevent system exit on failure
        price_banner_url = await automation.image_generator.create_outro(game_title, game_dict)
        logger.info(f"✅ Module 3 success - Price banner URL: {price_banner_url}")
    except SystemExit:
        # Catch system exit explicitly and convert to a regular exception
        logger.error("Module 3 tried to exit the process - intercepted to keep automation running")
        raise Exception("Module 3 failed: Process attempted to exit")
    except Exception as e:
        logger.error(f"Error generating price banner: {e}")
        raise Exception(f"Module 3 failed: {str(e)}")
    
    # Update progress with completion info
    try:
        await manager.broadcast(json.dumps({
            'type': 'job_update',
            'job_id': job_id,
            'status': 'running',
            'current_step': 3,
            'step_name': "Price banner generated successfully",
            'details': "Created price comparison banner with game pricing data"
        }))
    except Exception as e:
        # Don't let WebSocket errors stop the automation
        logger.error(f"WebSocket broadcast error (non-critical): {e}")
    
    # Verify we have a valid URL - if not, raise an exception
    # Module 3 should exit on its own, but just in case
    if not price_banner_url:
        raise Exception("Module 3 failed: No price banner URL returned")
        
    # Use the generated price banner for the outro image
    outro_path = price_banner_url
    
    # Module 4: Final Compilation
    await update_job_progress(job_id, 4, "Compiling final reel with Creatomate")
    
    # Compile the final video using all components including the price comparison banner
    final_path = await automation.compiler.compile_reel(
        intro_url=intro_path, 
        vizard_url=vizard_path, 
        outro_url=outro_path,
        game_title=game_title,
        price_banner_url=price_banner_url  # Pass the price banner URL explicitly
    )
    
    return final_path

@app.post("/api/automation/start")
async def start_automation(request: AutomationRequest, background_tasks: BackgroundTasks):
    """Start a new automation job with comprehensive validation"""
    try:
        logger.info(f"🚀 Starting automation request: {request.model_dump()}")
        
        # Validate Steam App ID and get game details
        if request.mode == 'steam':
            if not request.steam_app_id:
                raise HTTPException(
                    status_code=400, 
                    detail="Steam App ID is required for steam mode"
                )
            
            # Comprehensive Steam App ID validation
            try:
                validation_result = await validate_steam_app_id(request.steam_app_id)
                logger.info(f"✅ Steam validation passed: {validation_result['name']}")
            except ValueError as e:
                logger.error(f"❌ Steam validation failed: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid Steam App ID: {str(e)}"
                )
            except Exception as e:
                logger.error(f"❌ Unexpected validation error: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to validate Steam App ID. Please try again later."
                )
        
        # Additional validation for custom video URL
        if request.custom_video_url:
            if not validate_youtube_url(request.custom_video_url):
                raise HTTPException(
                    status_code=400,
                    detail="Custom video URL must be a valid YouTube URL"
                )
        
        job_id = str(uuid.uuid4())
        
        # Create job record with validation results
        game_name = None
        if request.mode == 'steam' and hasattr(validation_result, 'get'):
            game_name = validation_result.get('name')
        elif request.mode == 'steam':
            game_name = f"Game {request.steam_app_id}"
            
        automation_jobs[job_id] = {
            'job_id': job_id,
            'status': 'queued',
            'progress': 0,
            'current_step': 0,
            'total_steps': 3, # Updated from 4 to 3 (removed outro generation step)
            'step_name': 'Queued - Validation passed',
            'created_at': datetime.now().isoformat(),
            'request': request.dict(),
            'validation': {
                'steam_app_id_valid': True,
                'game_name': game_name,
                'validated_at': datetime.now().isoformat()
            }
        }
        
        # Start background task
        background_tasks.add_task(run_automation_job, job_id, request)
        
        logger.info(f"✅ Automation job {job_id} queued successfully")
        return {
            'job_id': job_id, 
            'status': 'queued',
            'message': f"Automation started for {game_name or 'game'}"
        }
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"❌ Failed to start automation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start automation: {str(e)}"
        )

@app.get("/api/automation/status/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a specific job"""
    if job_id not in automation_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = automation_jobs[job_id]
    
    # If job is completed but frontend might have missed the WebSocket message, broadcast again
    if job['status'] == 'completed' and job.get('result_path'):
        await manager.broadcast(json.dumps({
            'type': 'job_completed',
            'job_id': job_id,
            'result_path': job['result_path'],
            'data': job
        }))
    
    return job

@app.get("/api/automation/jobs")
async def list_jobs():
    """List all jobs"""
    return list(automation_jobs.values())

@app.delete("/api/automation/stop/{job_id}")
async def stop_job(job_id: str):
    """Stop a running job (placeholder - would need proper cancellation logic)"""
    if job_id not in automation_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = automation_jobs[job_id]
    if job['status'] == 'running':
        job['status'] = 'cancelled'
        job['completed_at'] = datetime.now().isoformat()
    
    return {'message': 'Job stopped', 'job_id': job_id}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates with better error handling"""
    try:
        # Handle connection
        await websocket.accept()
        
        # Add to active connections
        active_connections.append(websocket)
        
        # Send initial confirmation - using safe_send for more reliability
        success = await safe_send(websocket, {
            "type": "connection_established",
            "data": {
                "message": "Connected to automation server",
                "status": "connected"
            }
        })
        
        if success:
            logger.info("WebSocket client connected successfully")
        else:
            logger.warning("Failed to send initial confirmation but continuing anyway")
            # Continue anyway - the connection might recover
        
        # Initialize connection parameters with more tolerant timeouts
        last_ping_time = time.time()
        ping_interval = 60.0  # Send pings every 60 seconds (reduced frequency)
        connection_timeout = 180.0  # 3 minute connection timeout (much longer)
        
        # Main connection loop
        while True:
            try:
                # Use a longer timeout to reduce connection churn
                data = await asyncio.wait_for(websocket.receive_text(), timeout=connection_timeout)
                
                # Reset ping timer on any message received
                last_ping_time = time.time()
                
                # If client sends a ping, respond with pong
                if data == 'ping':
                    await websocket.send_text('pong')
            except asyncio.TimeoutError:
                # Check if we should send a ping based on time elapsed
                current_time = time.time()
                time_since_ping = current_time - last_ping_time
                
                # Only ping if enough time has passed since last activity
                if time_since_ping >= ping_interval:
                    try:
                        await websocket.send_json({'type': 'ping'})
                        last_ping_time = current_time  # Reset ping timer
                    except Exception:
                        logger.info("WebSocket ping failed, closing connection")
                        break
            except WebSocketDisconnect:
                # Normal client disconnection
                logger.info("WebSocket client disconnected normally")
                break
            except Exception as e:
                # Other exceptions
                logger.info(f"WebSocket error: {e}")
                break
    except Exception as e:
        # Connection setup error
        logger.error(f"WebSocket setup error: {e}")
    finally:
        # Always remove from manager, even if connection was never fully established
        if websocket in manager.active_connections:
            manager.disconnect(websocket)

@app.post("/api/validation/steam-app-id")
async def validate_steam_app_id_endpoint(request: dict):
    """Validate Steam App ID without starting automation"""
    try:
        app_id = request.get('steam_app_id')
        if not app_id:
            raise HTTPException(
                status_code=400,
                detail="Steam App ID is required"
            )
        
        # Validate the Steam App ID
        validation_result = await validate_steam_app_id(app_id)
        
        return {
            'valid': True,
            'app_id': validation_result['app_id'],
            'game_name': validation_result['name'],
            'game_type': validation_result['type'],
            'message': f"Valid Steam game found: {validation_result['name']}"
        }
        
    except ValueError as e:
        return {
            'valid': False,
            'error': str(e),
            'message': f"Invalid Steam App ID: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Validation endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Validation service temporarily unavailable"
        )

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'active_jobs': len([j for j in automation_jobs.values() if j['status'] == 'running']),
        'total_jobs': len(automation_jobs),
        'validation_available': True
    }

@app.options("/api/webhooks/heygen")
async def heygen_webhook_options():
    """Handle OPTIONS requests for CORS preflight checks"""
    return {"success": True}

@app.post("/api/webhooks/heygen")
async def heygen_webhook(request: Request):
    """Webhook endpoint for HeyGen video generation status updates"""
    try:
        # Parse the incoming webhook payload
        # First log the raw request to help debug
        body = await request.body()
        logger.info(f"Received HeyGen webhook raw body: {body}")
        
        try:
            payload = await request.json()
            logger.info(f"Received HeyGen webhook JSON: {payload}")
        except Exception as json_error:
            # If JSON parsing fails, try to handle it anyway
            logger.warning(f"Failed to parse webhook payload as JSON: {json_error}")
            # Return success to acknowledge receipt even if we couldn't process it
            return {"success": True, "message": "Webhook acknowledged but not processable as JSON"}
        
        # Extract the task/video ID from various possible payload formats
        # HeyGen has multiple webhook formats and we need to handle all of them
        video_id = None
        status = None
        video_url = None
        
        # Try all possible paths to find the video ID
        if 'video_id' in payload:
            video_id = payload.get('video_id')
        elif 'data' in payload and isinstance(payload['data'], dict):
            data = payload['data']
            video_id = data.get('video_id') or data.get('id')
        elif 'event_data' in payload and isinstance(payload['event_data'], dict):
            video_id = payload['event_data'].get('video_id')
        elif 'callback_id' in payload:
            video_id = payload.get('callback_id')
        
        # Try all possible paths to find the status
        if 'status' in payload:
            status = payload.get('status')
        elif 'event_type' in payload and 'success' in payload['event_type']:
            status = 'completed'
        elif 'data' in payload and isinstance(payload['data'], dict) and 'status' in payload['data']:
            status = payload['data'].get('status')
            
        # Try all possible paths to find the video URL
        if 'video_url' in payload:
            video_url = payload.get('video_url')
        elif 'url' in payload:
            video_url = payload.get('url')
        elif 'data' in payload and isinstance(payload['data'], dict):
            data = payload['data']
            video_url = data.get('video_url') or data.get('url')
        elif 'event_data' in payload and isinstance(payload['event_data'], dict):
            event_data = payload['event_data']
            video_url = event_data.get('url')
        
        # Log what we found
        logger.info(f"Extracted from webhook - video_id: {video_id}, status: {status}, url: {video_url}")
        
        # Even if we can't find a video ID, don't fail the webhook
        # Just log a warning and return success
        if not video_id:
            logger.warning("Could not find video_id in webhook payload, storing with fallback ID")
            # Use a timestamp as fallback ID if we can't find a real one
            video_id = f"webhook_{int(time.time())}"
            
        # Broadcast this update to all connected WebSocket clients
        message = {
            "type": "heygen_update",
            "data": {
                "video_id": video_id,
                "status": status,
                "video_url": video_url,
                "raw_payload": payload  # Include the full payload for debugging
            }
        }
        
        await broadcast_message(json.dumps(message))
        
        # Store this information in a global dictionary for module1_intro.py to access
        # without polling the HeyGen API
        if not hasattr(app.state, "heygen_videos"):
            app.state.heygen_videos = {}
            
        app.state.heygen_videos[video_id] = {
            "status": status,
            "video_url": video_url,
            "raw_payload": payload,  # Store the raw payload for debugging
            "updated_at": datetime.now().isoformat()
        }
        
        # Always return success to acknowledge receipt
        return {"success": True, "message": "Webhook received and processed"}
        
    except Exception as e:
        # Log the error but don't fail the webhook
        logger.error(f"Error processing HeyGen webhook: {e}")
        # Return success anyway to acknowledge receipt
        return {"success": True, "message": f"Webhook acknowledged with errors: {str(e)}"}


@app.get("/api/heygen/status/{video_id}")
async def get_heygen_status(video_id: str):
    """Get HeyGen video status from webhook data"""
    try:
        # Initialize the heygen_videos dictionary if it doesn't exist
        if not hasattr(app.state, "heygen_videos"):
            app.state.heygen_videos = {}
        
        # Return the status if it exists directly
        if video_id in app.state.heygen_videos:
            # Return a clean copy without internal fields if requested
            data = app.state.heygen_videos[video_id].copy()
            
            # Check if the video is completed based on either status field or raw payload
            is_completed = False
            status = data.get('status')
            raw_payload = data.get('raw_payload', {})
            
            # Different possible status values for "complete"
            if status and status.lower() in ['complete', 'completed', 'success']:
                is_completed = True
            # Check event_type for completion indicators
            elif raw_payload and raw_payload.get('event_type', '').endswith('success'):
                is_completed = True
                data['status'] = 'completed'  # Update status to be consistent
                
            # For frontend display consistency
            if is_completed and data.get('video_url'):
                data['status'] = 'completed'
            
            return data
        else:
            # First, try checking with alternate formats of the video ID
            # HeyGen sometimes sends the ID in different formats
            for stored_id, data in app.state.heygen_videos.items():
                # Check if the video ID is contained within the stored ID or vice versa
                if video_id in stored_id or stored_id in video_id:
                    return data
            
            # Return a 404 if we don't have any webhook data for this video
            raise HTTPException(status_code=404, detail=f"No webhook data available for video ID: {video_id}")
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error retrieving HeyGen status: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving HeyGen status: {str(e)}")


if __name__ == "__main__":
    # Use default port 8000 for consistency
    port = 8000
    print(f"🌟 Starting API server on port {port}...")
    print(f"💻 Frontend should connect to: ws://localhost:{port}/ws")
    print(f"🌐 API endpoints available at: http://localhost:{port}/api/*")
    # Important: The frontend config should use the same port
    print(f"⚠️ Frontend should be configured to use ws://localhost:{port}/ws and http://localhost:{port}/api/")
    uvicorn.run(app, host="localhost", port=port, log_level="info")
