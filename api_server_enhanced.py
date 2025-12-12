import asyncio
import json
import uuid
import re
import traceback
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
from loguru import logger
import uvicorn
import aiohttp
import ssl
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import your existing automation system
from main import YouTubeReelsAutomation

app = FastAPI(title="YouTube Reels Automation API", version="1.0.0")

# Add CORS middleware - works for both local and Railway deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:3001", 
        "http://localhost:3002",
        "https://*.railway.app",  # Railway frontend domains
        "*"  # Allow all origins for Railway deployment
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state management
automation_jobs: Dict[str, Dict] = {}
active_connections: List[WebSocket] = []

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
                raise ValueError(f"Steam API request timed out when validating App ID {app_id}. Please try again later.")
            
            except Exception as e:
                logger.error(f"Error connecting to Steam API: {e}")
                raise ValueError(f"Error connecting to Steam API: {str(e)}")
    
    except ValueError as e:
        logger.warning(f"Steam App ID validation error: {e}")
        raise  # Re-raise validation errors
    except Exception as e:
        logger.error(f"Unexpected error validating Steam App ID {app_id}: {e}")
        raise ValueError(f"Failed to validate Steam App ID {app_id}: {str(e)}")

def validate_youtube_url(url: str) -> bool:
    """Validate YouTube URL format"""
    if not url or not url.strip():
        return True  # Empty URL is valid (optional parameter)
    
    url = url.strip()
    
    # Common video platforms
    video_patterns = [
        r'youtube\.com\/watch\?v=[\w-]+',  # YouTube standard
        r'youtu\.be\/[\w-]+',              # YouTube short
        r'youtube\.com\/shorts\/[\w-]+',    # YouTube shorts
        r'steamstatic\.com\/',              # Steam videos
        r'steampowered\.com\/',             # Steam videos
        r'vimeo\.com\/\d+',                # Vimeo
        r'twitch\.tv\/',                    # Twitch
        r'dailymotion\.com\/video\/',       # Dailymotion
    ]
    
    # Check if URL matches any of the patterns
    for pattern in video_patterns:
        if re.search(pattern, url):
            return True
    
    # If no match found
    return False

# Pydantic Models
class SteamAutomationRequest(BaseModel):
    mode: str = "steam"
    steam_app_id: str
    custom_video_url: Optional[str] = None
    
    @validator('steam_app_id')
    def valid_app_id_format(cls, v):
        if not v or not v.strip():
            raise ValueError("Steam App ID is required")
        
        v = v.strip()
        if not re.match(r'^\d+$', v):
            raise ValueError("Steam App ID must be numeric")
        
        return v
    
    @validator('custom_video_url')
    def valid_video_url(cls, v):
        if v and not validate_youtube_url(v):
            raise ValueError("Invalid video URL format. Please provide a valid YouTube, Steam, or other video platform URL.")
        return v

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
    online_url: Optional[str] = None
    error_message: Optional[str] = None
    request: Optional[Dict] = None

# Global API key validation
def validate_required_api_keys():
    """Validate required API keys are present in environment variables"""
    required_keys = {
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'HEYGEN_API_KEY': os.getenv('HEYGEN_API_KEY'),
        'VIZARD_API_KEY': os.getenv('VIZARD_API_KEY'),
        'CREATOMATE_API_KEY': os.getenv('CREATOMATE_API_KEY')
    }
    
    missing_keys = [key for key, value in required_keys.items() if not value]
    
    if missing_keys:
        logger.error(f"❌ Missing required API keys: {', '.join(missing_keys)}")
        return False, f"Missing API keys: {', '.join(missing_keys)}"
    
    return True, "All API keys present"

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

manager = ConnectionManager()

async def update_job_progress(job_id: str, step: int, step_name: str, status: str = "running"):
    """Update job progress and broadcast to connected clients"""
    if job_id in automation_jobs:
        job = automation_jobs[job_id]
        job['current_step'] = step
        job['step_name'] = step_name
        job['status'] = status
        job['progress'] = int((step / job['total_steps']) * 100) if step > 0 else 0
        
        # Broadcast update to all connected clients
        await manager.broadcast(json.dumps({
            'type': 'progress_update',
            'job_id': job_id,
            'data': job
        }))

async def send_backend_error(error_message: str, error_type: str = "general_error"):
    """Send a backend error notification to all connected clients"""
    await manager.broadcast(json.dumps({
        'type': 'backend_error',
        'error_type': error_type,
        'error': error_message,
        'timestamp': datetime.now().isoformat()
    }))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send current job statuses on connection
        for job_id, job in automation_jobs.items():
            await manager.send_personal_message(json.dumps({
                'type': 'progress_update',
                'job_id': job_id,
                'data': job
            }), websocket)
        
        while True:
            # Wait for any messages (mostly for ping/pong to keep connection alive)
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get('type') == 'ping':
                    await manager.send_personal_message(json.dumps({'type': 'pong'}), websocket)
            except:
                pass  # Ignore malformed messages
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

async def process_automation_job(job_id: str, request: SteamAutomationRequest):
    """Process automation job in the background"""
    automation = YouTubeReelsAutomation()
    
    # Update job to running status
    automation_jobs[job_id]['status'] = 'running'
    await update_job_progress(job_id, 0, "Initializing automation pipeline")
    
    try:
        # Start with the Steam App ID
        app_id = request.steam_app_id
        custom_video_url = request.custom_video_url if request.custom_video_url else None
        
        # Fetch game data from Steam
        await update_job_progress(job_id, 1, "Fetching game data")
        
        # Get game data using the app_id
        game_dict = await automation.get_game_data(app_id=app_id, custom_video_url=custom_video_url)
        
        if not game_dict:
            raise Exception(f"Failed to fetch game data for Steam App ID: {app_id}")
        
        game_title = game_dict.get('title') or game_dict.get('name')
        logger.info(f"🎮 Starting automation for: {game_title}")
        
        # Module 1: Intro
        await update_job_progress(job_id, 1, "Creating intro video with HeyGen")
        intro_path = await automation.intro_generator.create_intro(game_title, game_dict)
        
        if not intro_path:
            raise Exception("Module 1 (Intro) failed: HeyGen did not return a valid video path")
        
        # Module 2: Gameplay
        await update_job_progress(job_id, 2, "Processing gameplay clip with Vizard")
        vizard_path = await automation.vizard_processor.process_gameplay_clip(game_title, game_dict)
        
        if not vizard_path:
            raise Exception("Module 2 (Vizard) failed: Could not process gameplay clip")
        
        # Module 3: Game Banner
        await update_job_progress(job_id, 3, "Creating game banner with price comparison")
        outro_path = await automation.image_generator.create_outro(game_title, game_dict)
        
        if not outro_path:
            raise Exception("Module 3 (Game Banner) failed: Could not generate a valid banner")
        
        # Module 4: Compilation
        await update_job_progress(job_id, 4, "Compiling final reel with Creatomate")
        result = await automation.compiler.compile_reel(intro_path, vizard_path, outro_path, game_title)
        
        if not result:
            raise Exception("Module 4 (Compilation) failed: Creatomate did not return a valid compiled video")
        
        # Update job with completed status
        automation_jobs[job_id]['status'] = 'completed'
        automation_jobs[job_id]['completed_at'] = datetime.now().isoformat()
        
        # Handle both dict and string results
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
            'data': automation_jobs[job_id],
            'online_url': automation_jobs[job_id].get('online_url')
        }))
        
    except Exception as e:
        logger.error(f"Automation job {job_id} failed: {e}")
        
        # Get module name that failed
        module_name = "Unknown"
        current_step = automation_jobs[job_id].get('current_step', 0)
        
        if current_step == 1:
            module_name = "Intro Generation (HeyGen)"
        elif current_step == 2:
            module_name = "Gameplay Processing (Vizard)"
        elif current_step == 3:
            module_name = "Game Banner Generation"
        elif current_step == 4:
            module_name = "Final Compilation (Creatomate)"
            
        # Get stack trace for detailed error reporting
        tb = traceback.format_exc()
        logger.debug(f"Stack trace: {tb}")
        
        detailed_error = f"Module {current_step} ({module_name}) failed: {str(e)}"
        
        # Update job with failure status and detailed error
        automation_jobs[job_id]['status'] = 'failed'
        automation_jobs[job_id]['error_message'] = detailed_error
        automation_jobs[job_id]['completed_at'] = datetime.now().isoformat()
        
        await manager.broadcast(json.dumps({
            'type': 'job_failed',
            'job_id': job_id,
            'error': detailed_error,
            'data': automation_jobs[job_id]
        }))

# Exception handler for detailed API errors
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # Log the error with traceback
    logger.error(f"Unhandled API error: {exc}")
    logger.error(traceback.format_exc())
    
    # Broadcast to connected clients
    await send_backend_error(f"Server error: {str(exc)}")
    
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )

@app.post("/api/automation/start", response_model=Dict)
async def start_automation(request: SteamAutomationRequest, background_tasks: BackgroundTasks):
    """Start an automation job with Steam App ID"""
    try:
        # Validate API keys before starting
        keys_valid, keys_message = validate_required_api_keys()
        if not keys_valid:
            raise HTTPException(
                status_code=500,
                detail=f"Server configuration error: {keys_message}. Please contact the administrator."
            )
        
        # Validate Steam App ID
        if request.steam_app_id:
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
        if request.custom_video_url and not validate_youtube_url(request.custom_video_url):
            logger.error(f"❌ Invalid video URL: {request.custom_video_url}")
            raise HTTPException(
                status_code=400,
                detail="Invalid video URL format. Please provide a valid YouTube, Steam, or other video platform URL."
            )
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Create job entry
        automation_jobs[job_id] = {
            'job_id': job_id,
            'status': 'queued',
            'progress': 0,
            'current_step': 0,
            'total_steps': 4,
            'step_name': 'Initializing',
            'created_at': datetime.now().isoformat(),
            'request': request.dict()
        }
        
        # Start the job in the background
        background_tasks.add_task(process_automation_job, job_id, request)
        
        return {
            'job_id': job_id,
            'status': 'queued'
        }
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"❌ Failed to start automation: {e}")
        await send_backend_error(f"Failed to start automation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start automation: {str(e)}"
        )

@app.get("/api/automation/status/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a job"""
    if job_id not in automation_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = automation_jobs[job_id]
    
    # If job is completed but frontend might have missed the WebSocket message, broadcast again
    if job['status'] == 'completed' and job.get('result_path'):
        await manager.broadcast(json.dumps({
            'type': 'job_completed',
            'job_id': job_id,
            'result_path': job['result_path'],
            'online_url': job.get('online_url'),
            'data': job
        }))
    elif job['status'] == 'failed' and job.get('error_message'):
        await manager.broadcast(json.dumps({
            'type': 'job_failed',
            'job_id': job_id,
            'error': job['error_message'],
            'data': job
        }))
    
    return job

@app.delete("/api/automation/stop/{job_id}")
async def stop_job(job_id: str):
    """Stop a running job"""
    if job_id not in automation_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = automation_jobs[job_id]
    if job['status'] not in ['completed', 'failed']:
        job['status'] = 'cancelled'
        job['completed_at'] = datetime.now().isoformat()
        
        await manager.broadcast(json.dumps({
            'type': 'job_cancelled',
            'job_id': job_id,
            'data': job
        }))
    
    return {"status": "stopped"}

@app.get("/api/automation/jobs")
async def list_jobs():
    """List all jobs"""
    # Return jobs sorted by creation date (newest first)
    sorted_jobs = sorted(
        list(automation_jobs.values()),
        key=lambda job: job.get('created_at', ''),
        reverse=True
    )
    return sorted_jobs

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    # Check API keys
    api_keys_valid, api_keys_message = validate_required_api_keys()
    
    return {
        "status": "healthy",
        "api_keys_valid": api_keys_valid,
        "api_keys_message": api_keys_message,
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "jobs_count": len(automation_jobs),
        "active_connections": len(manager.active_connections),
        "simulation": False,
        "mode": "PRODUCTION"
    }

@app.post("/api/validation/steam-app-id")
async def validate_app_id(request: dict):
    """Validate a Steam App ID"""
    try:
        app_id = request.get('steam_app_id')
        if not app_id:
            raise HTTPException(status_code=400, detail="Steam App ID is required")
        
        result = await validate_steam_app_id(app_id)
        return {
            "valid": True,
            "app_id": app_id,
            "name": result.get('name'),
            "message": f"Valid Steam App ID: {result.get('name')}"
        }
    except ValueError as e:
        return {
            "valid": False,
            "app_id": request.get('steam_app_id'),
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"Error validating Steam App ID: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error validating Steam App ID: {str(e)}"
        )

if __name__ == "__main__":
    # Validate API keys at startup
    keys_valid, keys_message = validate_required_api_keys()
    if not keys_valid:
        logger.error(f"❌ {keys_message}")
        logger.error("🛑 Cannot start server with missing API keys.")
        exit(1)
        
    logger.info("✅ All API keys are present.")
    logger.info("🚀 Starting YouTube Reels Automation API server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
