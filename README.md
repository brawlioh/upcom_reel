# UPCOM Reels Automation Core

This repository contains the core Python files for the YouTube Reels Automation pipeline.

## Overview

The pipeline automates the creation of YouTube Reels by:

1. Generating intro videos with HeyGen
2. Processing gameplay footage with Vizard
3. Creating price comparison banners for games
4. Compiling all elements into a final video

## Key Components

- `main.py`: Main entry point and pipeline orchestration
- `api_server.py`: FastAPI server for web interface
- `config.py`: Configuration management

### Modules
- `module0_price.py`: Price comparison banner generation
- `module1_intro.py`: Intro video creation with HeyGen
- `module2_vizard.py`: Gameplay processing with Vizard
- `module4_compilation.py`: Final video compilation

### Utils
- `steam_api_scraper.py`: Scrape game details from Steam
- `steam_scraper.py`: Additional Steam data scraping
- `youtube_scraper.py`: YouTube data utilities

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Configure API keys in `.env`
3. Run the server: `python api_server.py`

## License

All rights reserved.
