#!/usr/bin/env python3

import asyncio
import aiohttp
import time
import os
import sys
import re
import io  # Add io for BytesIO
import random
import requests
from typing import Dict, Optional, Any, List
from pathlib import Path
from loguru import logger
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()  # This will load variables from .env file if it exists
    logger.info("Loaded environment variables from .env file")
except ImportError:
    logger.warning("Could not import dotenv, environment variables must be set manually")

# Import cloudinary with error handling
try:
    import cloudinary
    import cloudinary.uploader
    logger.info("Successfully imported cloudinary")
except ImportError:
    logger.warning("Could not import cloudinary, image upload will be disabled")
    # Create dummy cloudinary module to prevent errors
    class DummyCloudinary:
        def config(self, **kwargs):
            pass
        
        class uploader:
            @staticmethod
            def upload(file_path):
                logger.warning(f"Cloudinary upload attempted but module not available: {file_path}")
                return {"secure_url": file_path}
    
    # If cloudinary import failed, create a dummy module
    if 'cloudinary' not in globals():
        cloudinary = DummyCloudinary()

# Fix import path to find config.py in parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try importing config, but provide fallbacks if it fails
try:
    from config import Config
    logger.info("Successfully imported Config")
except ImportError:
    logger.warning("Could not import Config, using environment variables directly")
    # Define a fallback Config class
    class Config:
        # Try to get environment variables directly
        CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
        CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
        CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')
        
        # Default paths
        DATA_PATH = Path(os.getenv('STREAMGANK_DATA_PATH', './data'))
        ASSETS_PATH = DATA_PATH / 'assets'
        
        @classmethod
        def ensure_directories(cls):
            """Create necessary directories if they don't exist"""
            cls.ASSETS_PATH.mkdir(parents=True, exist_ok=True)
            (cls.ASSETS_PATH / 'price_banners').mkdir(exist_ok=True)

class PriceComparisonGenerator:
    """
    Streamlined module for generating price comparison data and banner images for games.
    
    Features:
    - Steam price fetching via AllKeyShop API
    - AllKeyShop price fetching
    - Discount calculation
    - Price comparison banner generation
    """
    def __init__(self):
        self.config = Config
        # Initialize Cloudinary with safety checks
        try:
            # Only configure if keys are available - this prevents errors in pipeline
            if Config.CLOUDINARY_CLOUD_NAME and Config.CLOUDINARY_API_KEY and Config.CLOUDINARY_API_SECRET:
                cloudinary.config(
                    cloud_name=Config.CLOUDINARY_CLOUD_NAME,
                    api_key=Config.CLOUDINARY_API_KEY,
                    api_secret=Config.CLOUDINARY_API_SECRET
                )
                logger.info("Cloudinary configured successfully")
            else:
                logger.warning("Cloudinary credentials missing, image upload will be disabled")
        except Exception as e:
            logger.error(f"Error configuring Cloudinary: {e}")
        
        # Create directories if they don't exist with proper error handling
        try:
            self.assets_path = Path(Config.ASSETS_PATH)
            self.price_banners_path = self.assets_path / "price_banners"
            self.price_banners_path.mkdir(parents=True, exist_ok=True)
            
            # Set up font paths
            self.font_path = self.assets_path / "fonts"
            self.font_path.mkdir(parents=True, exist_ok=True)
            
            # Default fonts
            self.title_font_path = str(self.font_path / "Montserrat-Bold.ttf")
            self.body_font_path = str(self.font_path / "Montserrat-Medium.ttf")
            
            # System font fallbacks
            self.system_bold_font = None
            self.system_regular_font = None
            
            # Download fonts if they don't exist
            self._ensure_fonts_exist()
            
        except Exception as e:
            logger.error(f"Error initializing PriceComparisonGenerator: {e}")
            # Initialize with fallback values
            self.system_bold_font = None
            self.system_regular_font = None
    
    def _ensure_fonts_exist(self):
        """Make sure required fonts are available or set up alternatives with strong fallbacks"""
        try:
            # First set the fallbacks to None so we have a valid state even if an exception occurs
            self.system_bold_font = None
            self.system_regular_font = None
            
            # Check if fonts directory exists, if not create it
            try:
                self.font_path.mkdir(parents=True, exist_ok=True)
            except Exception as dir_error:
                logger.warning(f"Cannot create font directory: {dir_error}, using memory-only operation")
            
            # Define a list of system fonts that are likely available on macOS
            # These are common system fonts that should be available on most Macs
            self.system_fonts = {
                "bold": [
                    "/System/Library/Fonts/SFNS.ttf",  # San Francisco (modern macOS)
                    "/System/Library/Fonts/SFNSDisplay-Bold.otf",
                    "/System/Library/Fonts/Helvetica.ttc",  # Helvetica
                    "/System/Library/Fonts/HelveticaNeue.ttc", 
                    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                    "/Library/Fonts/Arial Bold.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux fonts
                    "/Windows/Fonts/arial.ttf",  # Windows fonts
                ],
                "regular": [
                    "/System/Library/Fonts/SFNS.ttf",  # San Francisco (modern macOS)
                    "/System/Library/Fonts/SFNSDisplay-Regular.otf",
                    "/System/Library/Fonts/Helvetica.ttc",  # Helvetica
                    "/System/Library/Fonts/HelveticaNeue.ttc",
                    "/System/Library/Fonts/Supplemental/Arial.ttf",
                    "/Library/Fonts/Arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux fonts
                    "/Windows/Fonts/arial.ttf",  # Windows fonts
                ]
            }
            
            # First try to use a system font - check if any of them exist
            # Find a working bold font
            for font_path in self.system_fonts["bold"]:
                if os.path.exists(font_path):
                    try:
                        # Verify the font is usable by attempting to load it
                        test_font = ImageFont.truetype(font_path, 12)
                        self.system_bold_font = font_path
                        logger.info(f"Using system bold font: {font_path}")
                        break
                    except Exception as font_err:
                        logger.warning(f"Font exists but cannot be loaded: {font_path}, error: {font_err}")
                        continue
                    
            # Find a working regular font
            for font_path in self.system_fonts["regular"]:
                if os.path.exists(font_path):
                    try:
                        # Verify the font is usable
                        test_font = ImageFont.truetype(font_path, 12)
                        self.system_regular_font = font_path
                        logger.info(f"Using system regular font: {font_path}")
                        break
                    except Exception as font_err:
                        logger.warning(f"Font exists but cannot be loaded: {font_path}, error: {font_err}")
                        continue
            
            # If no system fonts found, try to download our preferred fonts
            if not self.system_bold_font or not self.system_regular_font:
                logger.info("No usable system fonts found, attempting to download fonts...")
                
                try:
                    font_urls = {
                        "Montserrat-Bold.ttf": "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf",
                        "Montserrat-Medium.ttf": "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Medium.ttf"
                    }
                    
                    # Download each font if it doesn't exist
                    for font_name, url in font_urls.items():
                        try:
                            font_path = self.font_path / font_name
                            if not os.path.exists(str(font_path)):
                                logger.info(f"Downloading {font_name} from {url}")
                                try:
                                    response = requests.get(url, stream=True, timeout=10)  # Add timeout
                                    if response.status_code == 200:
                                        try:
                                            with open(font_path, 'wb') as f:
                                                f.write(response.content)
                                            logger.info(f"Font {font_name} downloaded successfully")
                                            
                                            # Verify the font is usable by attempting to load it
                                            try:
                                                test_font = ImageFont.truetype(str(font_path), 12)
                                                # Set as our font if corresponding system font wasn't found
                                                if "Bold" in font_name and not self.system_bold_font:
                                                    self.system_bold_font = str(font_path)
                                                    logger.info(f"Using downloaded bold font: {font_path}")
                                                elif "Medium" in font_name and not self.system_regular_font:
                                                    self.system_regular_font = str(font_path)
                                                    logger.info(f"Using downloaded regular font: {font_path}")
                                            except Exception as font_err:
                                                logger.warning(f"Downloaded font cannot be loaded: {font_path}, error: {font_err}")
                                        except Exception as write_err:
                                            logger.warning(f"Error writing font file: {write_err}")
                                    else:
                                        logger.warning(f"Failed to download {font_name}: {response.status_code}")
                                except Exception as request_err:
                                    logger.warning(f"Error making request for font: {request_err}")
                            else:
                                # Font already exists, try to use it
                                try:
                                    test_font = ImageFont.truetype(str(font_path), 12)
                                    # Set as our font if corresponding system font wasn't found
                                    if "Bold" in font_name and not self.system_bold_font:
                                        self.system_bold_font = str(font_path)
                                        logger.info(f"Using existing downloaded bold font: {font_path}")
                                    elif "Medium" in font_name and not self.system_regular_font:
                                        self.system_regular_font = str(font_path)
                                        logger.info(f"Using existing downloaded regular font: {font_path}")
                                except Exception as font_err:
                                    logger.warning(f"Existing font cannot be loaded: {font_path}, error: {font_err}")
                        except Exception as font_err:
                            logger.warning(f"Error processing font {font_name}: {font_err}")
                except Exception as download_err:
                    logger.warning(f"Font download process failed: {download_err}")
            
            # Final check - if we still don't have any usable fonts, log a warning
            if not self.system_bold_font:
                logger.warning("No usable bold font available, will use PIL default")
            if not self.system_regular_font:
                logger.warning("No usable regular font available, will use PIL default")
                
            return True
        except Exception as e:
            logger.error(f"Font setup error: {e}, will use default font")
            # Set to None to ensure we have a valid state
            self.system_bold_font = None
            self.system_regular_font = None
            return True
            
    async def fetch_allkeyshop_price(self, allkeyshop_url: str) -> Dict[str, Any]:
        """
        Fetch price from AllKeyShop using their API
        
        Args:
            allkeyshop_url: URL to the game's AllKeyShop page
            
        Returns:
            Dictionary with best price and merchant information
        """
        try:
            logger.info(f"Fetching price from AllKeyShop for: {allkeyshop_url}")
            
            # Ensure URL ends with trailing slash
            if not allkeyshop_url.endswith('/'):
                allkeyshop_url += '/'
                logger.info(f"Added trailing slash to URL: {allkeyshop_url}")
            
            # Endpoint for best price - using the exact endpoint provided by the user
            endpoint = "https://www.allkeyshop.com/api/v2-1-250304/vaks.php"
            
            params = {
                'action': 'CatalogV2',
                'locale': 'en',
                'currency': 'EUR',
                'price_mode': 'price_card',
                'sort_order': 'desc',
                'pagenum': '1',
                'per_page': '24',
                'aks_links': allkeyshop_url,
                'fields': 'assets.cover,name,offers.price,offers.merchant.name,offers.stock_status,offers.voucher.code,offers.voucher.discount',
                '_app.version': '250415'
            }
            
            # Add browser-like headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Origin': 'https://www.allkeyshop.com',
                'Referer': 'https://www.allkeyshop.com/blog/',
                'Connection': 'keep-alive'
            }
            
            # Create a session with SSL verification disabled
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                logger.info(f"Making request to AllKeyShop API")
                async with session.get(endpoint, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Log raw data structure for debugging
                        logger.info(f"API response structure: {list(data.keys()) if isinstance(data, dict) else 'Not a dictionary'}")
                        
                        # Process the response
                        if 'products' in data and len(data['products']) > 0:
                            product = data['products'][0]
                            logger.info(f"Found product: {product.get('name', 'Unknown')}")
                            logger.info(f"Product keys: {list(product.keys()) if isinstance(product, dict) else 'Not a dictionary'}")
                            
                            if 'offers' in product and len(product['offers']) > 0:
                                logger.info(f"Found {len(product['offers'])} offers")
                                # Get in-stock offers and sort by price
                                in_stock_offers = []
                                for offer in product['offers']:
                                    if offer.get('stock_status') == 'in_stock' and 'price' in offer:
                                        in_stock_offers.append(offer)
                                
                                # If no in-stock offers, use all offers as fallback
                                if not in_stock_offers and product['offers']:
                                    logger.info("No in-stock offers found, using all offers as fallback")
                                    in_stock_offers = [offer for offer in product['offers'] if 'price' in offer]
                                
                                # Sort by price (lowest first)
                                in_stock_offers.sort(key=lambda x: float(x.get('price', 999999)))
                                
                                if in_stock_offers:
                                    best_offer = in_stock_offers[0]
                                    best_price = best_offer.get('price')
                                    merchant = best_offer.get('merchant', {}).get('name', 'Unknown')
                                    
                                    logger.info(f"Best price: €{best_price} from {merchant}")
                                    return {
                                        'price': f"€{best_price}",
                                        'merchant': merchant
                                    }
                                else:
                                    logger.warning("No offers with prices found")
                            else:
                                logger.warning("No offers found for this product")
                        else:
                            # Try to extract product info from API response even if not in expected format
                            try:
                                if isinstance(data, dict):
                                    # Search for any price information in the response
                                    for key, value in data.items():
                                        if isinstance(value, dict) and 'price' in value:
                                            price = value['price']
                                            logger.info(f"Found alternative price: €{price}")
                                            return {
                                                'price': f"€{price}",
                                                'merchant': 'AllKeyShop'
                                            }
                            except Exception as alt_err:
                                logger.debug(f"Alternative price extraction failed: {alt_err}")
                                
                            logger.warning("No products found in API response")
                    else:
                        logger.error(f"API request failed with status: {response.status}")
            
            return {'price': 'N/A', 'merchant': 'N/A'}
            
        except Exception as e:
            logger.error(f"Error fetching AllKeyShop price: {e}")
            return {'price': 'N/A', 'merchant': 'N/A'}
            
    async def fetch_steam_price(self, allkeyshop_url: str) -> Dict[str, Any]:
        """
        Fetch Steam price using AllKeyShop's API
        
        Args:
            allkeyshop_url: URL to the game's AllKeyShop page
            
        Returns:
            Dictionary with Steam price information
        """
        try:
            logger.info(f"Fetching Steam price for: {allkeyshop_url}")
            
            # Ensure URL ends with trailing slash
            if not allkeyshop_url.endswith('/'):
                allkeyshop_url += '/'
                logger.info(f"Added trailing slash to URL: {allkeyshop_url}")
            
            # Endpoint for Steam price - using the exact endpoint provided by the user
            endpoint = "https://www.allkeyshop.com/api/v2-1-250304/vaks.php"
            
            params = {
                'action': 'CatalogV2',
                'locale': 'en',
                'currency': 'EUR',
                'price_mode': 'price_card',
                'sort_order': 'desc',
                'pagenum': '1',
                'per_page': '24',
                'officialOffersOnly': '1',
                'offers.merchant.id': '1',  # This identifies Steam offers
                'aks_links': allkeyshop_url,
                'fields': 'assets.cover,name,offers.price,offers.merchant.name,offers.stock_status,offers.voucher.code,offers.voucher.discount',
                '_app.version': '250415'
            }
            
            # Add browser-like headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Origin': 'https://www.allkeyshop.com',
                'Referer': 'https://www.allkeyshop.com/blog/',
                'Connection': 'keep-alive'
            }
            
            # Create a session with SSL verification disabled
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                logger.info(f"Making request to AllKeyShop API for Steam price")
                async with session.get(endpoint, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Log raw data structure for debugging
                        logger.info(f"API response structure: {list(data.keys()) if isinstance(data, dict) else 'Not a dictionary'}")
                        
                        # Process the response
                        if 'products' in data and len(data['products']) > 0:
                            product = data['products'][0]
                            logger.info(f"Found product: {product.get('name', 'Unknown')}")
                            
                            if 'offers' in product and len(product['offers']) > 0:
                                logger.info(f"Found {len(product['offers'])} offers")
                                # Find Steam offers
                                steam_offers = []
                                for offer in product['offers']:
                                    if 'merchant' in offer and 'name' in offer['merchant'] and offer['merchant']['name'] == 'Steam' and 'price' in offer:
                                        steam_offers.append(offer)
                                
                                if steam_offers:
                                    steam_price = steam_offers[0].get('price')
                                    logger.info(f"Steam price: €{steam_price}")
                                    return {
                                        'price': f"€{steam_price}",
                                        'merchant': 'Steam'
                                    }
                                
                                # If no specific Steam offer found, use the first one
                                if len(product['offers']) > 0 and 'price' in product['offers'][0]:
                                    steam_price = product['offers'][0].get('price')
                                    merchant = product['offers'][0].get('merchant', {}).get('name', 'Official Store')
                                    logger.info(f"Using {merchant} price as Steam price: €{steam_price}")
                                    return {
                                        'price': f"€{steam_price}",
                                        'merchant': merchant
                                    }
                            else:
                                logger.warning("No offers found for Steam")
                        else:
                            logger.warning("No products found in API response for Steam price")
                    else:
                        logger.error(f"Steam price API request failed with status: {response.status}")
            
            return {'price': 'N/A', 'merchant': 'Steam'}
            
        except Exception as e:
            logger.error(f"Error fetching Steam price: {e}")
            return {'price': 'N/A', 'merchant': 'Steam'}

    def _normalize_game_title(self, game_title: str) -> str:
        """
        Normalize game title to handle unusual capitalization and formatting
        
        Args:
            game_title: Original game title
            
        Returns:
            Normalized game title
        """
        try:
            # Handle ALL CAPS titles like "INAZUMA ELEVEN: Victory Road"
            if game_title.isupper() or sum(1 for c in game_title if c.isupper()) > len(game_title) * 0.7:
                # Convert to title case
                words = game_title.split()
                normalized = []
                for word in words:
                    if len(word) <= 2:  # Keep small words lowercase
                        normalized.append(word.lower())
                    else:
                        normalized.append(word.capitalize())
                return ' '.join(normalized)
            return game_title
        except Exception as e:
            logger.warning(f"Error normalizing game title: {e}")
            return game_title
    
    def _format_title_for_url(self, text: str) -> str:
        """
        Format a title string for use in a URL
        
        Args:
            text: Title text to format
            
        Returns:
            URL-friendly formatted text
        """
        try:
            if not text or not isinstance(text, str):
                return "unknown-game"
                
            # Normalize title first
            text = self._normalize_game_title(text)
            
            # Remove special characters and replace spaces with hyphens
            text = text.lower()
            text = text.replace(':', '')
            text = text.replace("'", "")
            text = text.replace('"', '')
            text = text.replace('.', '')
            text = text.replace(',', '')
            text = text.replace('&', 'and')
            text = text.replace('(', '')
            text = text.replace(')', '')
            text = text.replace('[', '')
            text = text.replace(']', '')
            text = text.replace('!', '')
            text = text.replace('?', '')
            text = text.replace('®', '')
            text = text.replace('™', '')
            text = text.replace(' - ', '-')
            text = text.replace(' ', '-')
            
            # Replace multiple hyphens with a single hyphen
            while '--' in text:
                text = text.replace('--', '-')
                
            # Remove any non-alphanumeric characters except hyphens
            text = re.sub(r'[^a-z0-9-]', '', text)
            
            # Prevent URLs ending with a hyphen
            text = text.rstrip('-')
            
            return text
        except Exception as e:
            logger.warning(f"Error formatting title for URL: {e}")
            return "unknown-game"
    
    def _correct_url_if_needed(self, game_title: str, allkeyshop_url: str) -> str:
        """
        Correct the URL if there's a mismatch between the URL and game title
        
        Args:
            game_title: Title of the game
            allkeyshop_url: URL to the game's AllKeyShop page
            
        Returns:
            Corrected URL or the original URL if no correction is needed
        """
        try:
            logger.info(f"Checking URL: '{allkeyshop_url}' for game: '{game_title}'")
            
            # Case 1: Empty or non-string URL - generate from game title
            if not allkeyshop_url or not isinstance(allkeyshop_url, str):
                if game_title and isinstance(game_title, str):
                    formatted_title = self._format_title_for_url(game_title)
                    allkeyshop_url = f"https://www.allkeyshop.com/blog/buy-{formatted_title}-cd-key-compare-prices/"
                    logger.info(f"Generated URL from game title (case 1): {allkeyshop_url}")
                    return allkeyshop_url
                return ""
            
            # Case 2: Detect simple game name with no proper URL structure
            # Examples: "https://Battlefield 6/", "Battlefield 6", etc.
            if (allkeyshop_url.startswith("http") and "/" in allkeyshop_url and 
                not "/blog/" in allkeyshop_url and not "allkeyshop.com" in allkeyshop_url):
                
                # Extract what might be a game name
                game_name = allkeyshop_url.split("/")[-1] if "/" in allkeyshop_url else allkeyshop_url
                if not game_name:
                    game_name = allkeyshop_url.split("/")[-2] if len(allkeyshop_url.split("/")) > 2 else game_title
                
                # Remove any trailing slashes or numbers after spaces
                game_name = game_name.rstrip("/").split(" ")[0]
                
                # If it looks like a game name, use it; otherwise fall back to title
                if len(game_name) > 3 and game_name.isalpha():
                    formatted_title = self._format_title_for_url(game_name)
                else:
                    formatted_title = self._format_title_for_url(game_title)
                
                allkeyshop_url = f"https://www.allkeyshop.com/blog/buy-{formatted_title}-cd-key-compare-prices/"
                logger.info(f"Generated proper URL from malformed URL (case 2): '{allkeyshop_url}'")
                return allkeyshop_url
            
            # Case 3: Just a game name, not a URL
            if not ("http://" in allkeyshop_url.lower() or "https://" in allkeyshop_url.lower()):
                # It's just a game name, not a URL
                formatted_title = self._format_title_for_url(allkeyshop_url)
                allkeyshop_url = f"https://www.allkeyshop.com/blog/buy-{formatted_title}-cd-key-compare-prices/"
                logger.info(f"Generated URL from game name (case 3): {allkeyshop_url}")
                return allkeyshop_url
            
            # Case 4: Has http but missing allkeyshop.com domain
            if allkeyshop_url.startswith("http") and "allkeyshop.com" not in allkeyshop_url.lower():
                formatted_title = self._format_title_for_url(game_title)
                allkeyshop_url = f"https://www.allkeyshop.com/blog/buy-{formatted_title}-cd-key-compare-prices/"
                logger.info(f"Fixed URL missing allkeyshop domain (case 4): {allkeyshop_url}")
                return allkeyshop_url
                
            # Case 5: URL has allkeyshop.com but wrong format
            if "allkeyshop.com" in allkeyshop_url.lower() and "/blog/buy-" not in allkeyshop_url.lower():
                formatted_title = self._format_title_for_url(game_title)
                allkeyshop_url = f"https://www.allkeyshop.com/blog/buy-{formatted_title}-cd-key-compare-prices/"
                logger.info(f"Fixed allkeyshop URL with wrong format (case 5): {allkeyshop_url}")
                return allkeyshop_url
            
            # Ensure URL ends with a trailing slash for API compatibility
            if not allkeyshop_url.endswith('/'):
                allkeyshop_url += '/'
                logger.info(f"Added trailing slash to URL: {allkeyshop_url}")
                
            # Final validation - make sure the URL is a proper AllKeyShop URL
            if not ("allkeyshop.com" in allkeyshop_url and "/blog/buy-" in allkeyshop_url):
                # One last attempt with title
                formatted_title = self._format_title_for_url(game_title)
                proper_url = f"https://www.allkeyshop.com/blog/buy-{formatted_title}-cd-key-compare-prices/"
                logger.info(f"Final URL correction for invalid URL: {allkeyshop_url} -> {proper_url}")
                return proper_url
                
            # URL looks good
            logger.info(f"Final validated URL: {allkeyshop_url}")
            return allkeyshop_url
            
        except Exception as e:
            logger.error(f"Error correcting URL: {e}")
            # Generate a fallback URL from game title if available
            if game_title and isinstance(game_title, str):
                try:
                    formatted_title = self._format_title_for_url(game_title)
                    fallback_url = f"https://www.allkeyshop.com/blog/buy-{formatted_title}-cd-key-compare-prices/"
                    logger.info(f"Generated emergency fallback URL after error: {fallback_url}")
                    return fallback_url
                except Exception as fallback_error:
                    logger.error(f"Even fallback URL creation failed: {fallback_error}")
                    return "https://www.allkeyshop.com/blog/"
            return allkeyshop_url if allkeyshop_url else "https://www.allkeyshop.com/blog/"

    async def extract_prices(self, game_title: str, allkeyshop_url: str) -> Dict[str, Any]:
        """
        Extract prices from AllKeyShop and Steam
        
        Args:
            game_title: Title of the game
            allkeyshop_url: URL to the game's AllKeyShop page
            
        Returns:
            Dictionary with steam_price, allkeyshop_price, and discount_percentage
        """
        try:
            # Normalize game title for better matching
            normalized_title = self._normalize_game_title(game_title)
            if normalized_title != game_title:
                logger.info(f"Normalized title: '{game_title}' -> '{normalized_title}'")
                game_title = normalized_title
                
            # Correct URL if needed
            allkeyshop_url = self._correct_url_if_needed(game_title, allkeyshop_url)
            price_data = {
                'steam_price': 'N/A',
                'allkeyshop_price': 'N/A',
                'discount_percentage': 0
            }
            
            # No hardcoded prices - we'll use API response or return N/A as appropriate
            # This aligns with the user's requirement that we should return N/A when no price is available
            logger.info(f"Using API endpoints only for price data - will return N/A if not found")
            
            # First fetch AllKeyShop price
            try:
                allkeyshop_result = await self.fetch_allkeyshop_price(allkeyshop_url)
                price_data['allkeyshop_price'] = allkeyshop_result['price']
                logger.info(f"AllKeyShop price fetched: {price_data['allkeyshop_price']}")
            except Exception as aks_error:
                logger.error(f"Error fetching AllKeyShop price: {aks_error}")
                
            # Then fetch Steam price
            try:
                steam_result = await self.fetch_steam_price(allkeyshop_url)
                price_data['steam_price'] = steam_result['price']
                logger.info(f"Steam price fetched: {price_data['steam_price']}")
            except Exception as steam_error:
                logger.error(f"Error fetching Steam price: {steam_error}")
                
            # Calculate discount percentage
            try:
                if price_data['steam_price'] != 'N/A' and price_data['allkeyshop_price'] != 'N/A':
                    # Extract numeric values from price strings
                    steam_match = re.search(r'([0-9.]+)', price_data['steam_price'])
                    allkeyshop_match = re.search(r'([0-9.]+)', price_data['allkeyshop_price'])
                    
                    if steam_match and allkeyshop_match:
                        steam_value = float(steam_match.group(1))
                        allkeyshop_value = float(allkeyshop_match.group(1))
                        
                        if steam_value > 0 and allkeyshop_value > 0 and steam_value > allkeyshop_value:
                            discount = ((steam_value - allkeyshop_value) / steam_value) * 100
                            price_data['discount_percentage'] = min(int(discount), 90)  # Cap at 90%
                            logger.info(f"Calculated discount: {price_data['discount_percentage']}%")
            except Exception as calc_error:
                logger.error(f"Error calculating discount: {calc_error}")
                
            return price_data
            
        except Exception as e:
            logger.error(f"Error in extract_prices: {e}")
            return {
                'steam_price': 'N/A',
                'allkeyshop_price': 'N/A',
                'discount_percentage': 0
            }
            
    async def upload_to_cloudinary(self, image_path: str) -> str:
        """
        Upload an image to Cloudinary with enhanced error handling and fallbacks
        
        Args:
            image_path: Path to the image file
            
        Returns:
            URL of the uploaded image or local path if upload fails
        """
        try:
            # Check if Cloudinary is properly configured
            if not (hasattr(Config, 'CLOUDINARY_CLOUD_NAME') and 
                    hasattr(Config, 'CLOUDINARY_API_KEY') and 
                    hasattr(Config, 'CLOUDINARY_API_SECRET') and 
                    Config.CLOUDINARY_CLOUD_NAME and 
                    Config.CLOUDINARY_API_KEY and 
                    Config.CLOUDINARY_API_SECRET):
                logger.warning("Cloudinary not properly configured, returning local path")
                return image_path
                
            # Check if the image file exists
            if not os.path.isfile(image_path):
                logger.error(f"Image file not found: {image_path}")
                return image_path
                
            # Try to upload the image
            logger.info(f"Uploading image to Cloudinary: {image_path}")
            response = cloudinary.uploader.upload(image_path)
            
            if response and 'secure_url' in response:
                url = response['secure_url']
                logger.info(f"Image uploaded successfully: {url}")
                return url
            else:
                logger.error("Cloudinary upload failed - no secure_url in response")
                return image_path
                
        except ImportError:
            logger.error("Cloudinary package not installed properly")
            return image_path
        except Exception as e:
            logger.error(f"Error uploading to Cloudinary: {e}")
            return image_path

    async def download_game_cover(self, game_title: str, steam_app_id: str = None) -> Optional[Image.Image]:
        """
        Download game cover art from Steam or other sources with robust fallbacks
        
        Args:
            game_title: Title of the game
            steam_app_id: Steam App ID if available
            
        Returns:
            PIL Image object or None if download fails
        """
        try:
            logger.info(f"Attempting to download game cover for: {game_title} with Steam App ID: {steam_app_id}")
            
            # Normalize game title for better matching
            normalized_title = self._normalize_game_title(game_title)
            if normalized_title != game_title:
                logger.info(f"Normalized title for image search: '{game_title}' -> '{normalized_title}'")
                game_title = normalized_title
            
            # Default to None
            banner_image = None
            img_width = 0
            img_height = 0
            
            # List of potential URLs to try
            image_urls = []
            
            # We'll use the provided steam_app_id directly instead of hardcoded mappings
            # This is more maintainable and allows the pipeline to handle new games easily
            game_title_lower = game_title.lower()
            additional_app_ids = []
            
            # If steam_app_id is provided, use it directly - no need for hardcoded lists
            if steam_app_id:
                additional_app_ids.append(steam_app_id)
                logger.info(f"Using provided Steam App ID: {steam_app_id} for {game_title}")
                
                # Try variations of the App ID (sometimes adding/subtracting 1 works too)
                try:
                    app_id_int = int(steam_app_id)
                    for offset in [-1, 1, 2, -2]:
                        additional_app_ids.append(str(app_id_int + offset))
                except (ValueError, TypeError):
                    pass  # Not a numeric app ID, skip variations
            
            # Ensure steam_app_id is a string
            if steam_app_id and not isinstance(steam_app_id, str):
                steam_app_id = str(steam_app_id)
                logger.info(f"Converted Steam App ID to string: {steam_app_id}")
                
            # 1. First priority: Try Steam header image if we have an App ID
            if steam_app_id:
                # Add common Steam CDN image formats
                image_urls.extend([
                    f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/header.jpg",
                    f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/library_hero.jpg",
                    f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/capsule_616x353.jpg",
                    # Alternative CDN domain sometimes used
                    f"https://cdn.akamai.steamstatic.com/steam/apps/{steam_app_id}/header.jpg"
                ])
                
                # Add URLs from additional app IDs if we found any
                for app_id in additional_app_ids:
                    if app_id != steam_app_id:  # Don't duplicate the main app ID
                        image_urls.extend([
                            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg",
                            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/library_hero.jpg",
                        ])
                
                # 2. Second fallback: Try to fetch from Steam store API to get validated image URLs
                try:
                    logger.info(f"Trying to fetch game details from Steam Store API for App ID: {steam_app_id}")
                    api_url = f"https://store.steampowered.com/api/appdetails?appids={steam_app_id}"
                    connector = aiohttp.TCPConnector(ssl=False)  # Disable SSL verification
                    async with aiohttp.ClientSession(connector=connector) as session:
                        async with session.get(api_url, timeout=5) as response:
                            if response.status == 200:
                                data = await response.json()
                                if data and data.get(steam_app_id, {}).get('success', False):
                                    app_data = data[steam_app_id]['data']
                                    # Add header image from API if available
                                    if 'header_image' in app_data:
                                        image_urls.insert(0, app_data['header_image'])
                                        logger.info(f"Found image URL from Steam API: {app_data['header_image']}")
                except Exception as e:
                    logger.warning(f"Failed to fetch from Steam API: {e}")
                    
                # Try API calls for known additional app IDs too
                for app_id in additional_app_ids[:1]:  # Limit to first additional ID to avoid too many API calls
                    if app_id != steam_app_id:  # Don't duplicate API calls
                        try:
                            logger.info(f"Trying Steam API with additional App ID: {app_id}")
                            api_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
                            connector = aiohttp.TCPConnector(ssl=False)  # Disable SSL verification
                            async with aiohttp.ClientSession(connector=connector) as session:
                                async with session.get(api_url, timeout=5) as response:
                                    if response.status == 200:
                                        data = await response.json()
                                        if data and data.get(app_id, {}).get('success', False):
                                            app_data = data[app_id]['data']
                                            if 'header_image' in app_data:
                                                image_urls.insert(0, app_data['header_image'])
                                                logger.info(f"Found image URL from additional App ID {app_id}: {app_data['header_image']}")
                        except Exception as e:
                            logger.warning(f"Failed to fetch from Steam API for additional App ID {app_id}: {e}")
            
            # 4. Try common alternative name formats for certain games
            # Handle special cases like INAZUMA ELEVEN: Victory Road
            if ':' in game_title:
                # Try with the part before colon
                base_name = game_title.split(':')[0].strip().lower().replace(' ', '-')
                image_urls.extend([
                    f"https://cdn.cloudflare.steamstatic.com/steam/apps/{base_name}/header.jpg",
                    f"https://cdn.akamai.steamstatic.com/steam/apps/{base_name}/header.jpg"
                ])
                
                # Try with the part after colon
                sub_name = game_title.split(':')[1].strip().lower().replace(' ', '-')
                image_urls.extend([
                    f"https://cdn.cloudflare.steamstatic.com/steam/apps/{sub_name}/header.jpg",
                    f"https://cdn.akamai.steamstatic.com/steam/apps/{sub_name}/header.jpg"
                ])
                
                # Try with no spaces at all
                no_spaces = game_title.replace(' ', '').replace(':', '').lower()
                image_urls.extend([
                    f"https://cdn.cloudflare.steamstatic.com/steam/apps/{no_spaces}/header.jpg"
                ])
                
            # 8. Add a completely generic game image as last resort
            image_urls.append("https://res.cloudinary.com/dodod8s0v/image/upload/v1759926961/outro_2_crwy4x.png")  # Generic fallback banner
            
            # Log all URLs we'll try
            logger.info(f"Will try downloading images from {len(image_urls)} potential URLs")
            
            # Try all URLs until we find one that works
            for url in image_urls:
                try:
                    logger.info(f"Trying to download cover from: {url}")
                    async with aiohttp.ClientSession() as session:
                        # Add headers to mimic a browser
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                        async with session.get(url, headers=headers, timeout=10, ssl=False) as response:
                            if response.status == 200:
                                image_data = await response.read()
                                try:
                                    banner_image = Image.open(io.BytesIO(image_data))
                                    img_width, img_height = banner_image.size
                                    
                                    # Validate the image - sometimes we get a valid response but it's an error page
                                    if img_width > 50 and img_height > 20:  # Minimum reasonable size for a game image
                                        logger.info(f"Successfully downloaded cover image: {img_width}x{img_height} from {url}")
                                        # Save the successful URL for future reference
                                        self.successful_image_url = url
                                        break
                                    else:
                                        logger.warning(f"Image too small: {img_width}x{img_height}, likely an error page")
                                except Exception as img_err:
                                    logger.warning(f"Downloaded data is not a valid image: {img_err}")
                            else:
                                logger.warning(f"Failed to download image: HTTP {response.status} from {url}")
                except aiohttp.ClientError as e:
                    logger.warning(f"Connection error downloading image from {url}: {e}")
                except Exception as e:
                    logger.warning(f"Error downloading image from {url}: {e}")
            
            # Final check
            if not banner_image:
                logger.warning(f"No valid game cover found for {game_title} after trying all sources")
                
                # One last direct attempt if we have a Steam App ID
                if steam_app_id:
                    try:
                        # Try to download directly from Steam using the app_id
                        # This is the most reliable way for any game if we have the correct Steam App ID
                        direct_steam_url = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/header.jpg"
                        logger.info(f"Final attempt: Direct Steam CDN download using App ID: {direct_steam_url}")
                        
                        connector = aiohttp.TCPConnector(ssl=False)  # Disable SSL verification
                        async with aiohttp.ClientSession(connector=connector) as session:
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                            }
                            async with session.get(direct_steam_url, headers=headers, timeout=10) as response:
                                if response.status == 200:
                                    image_data = await response.read()
                                    try:
                                        banner_image = Image.open(io.BytesIO(image_data))
                                        img_width, img_height = banner_image.size
                                        if img_width > 50 and img_height > 20:
                                            logger.info(f"Successfully downloaded image using direct Steam App ID: {img_width}x{img_height}")
                                            return banner_image
                                    except Exception as img_err:
                                        logger.warning(f"Downloaded data is not a valid image in final attempt: {img_err}") 
                    except Exception as e:
                        logger.error(f"Failed direct Steam CDN download in final attempt: {e}")
            
            return banner_image
            
        except Exception as e:
            logger.error(f"Error in download_game_cover: {e}")
            return None
            
    async def download_image_with_retry(self, url: str, max_retries: int = 3) -> Optional[Image.Image]:
        """
        Helper method to download an image with retries
        
        Args:
            url: URL to download image from
            max_retries: Maximum number of retry attempts
            
        Returns:
            PIL Image object or None if download fails
        """
        retries = 0
        while retries < max_retries:
            try:
                logger.info(f"Downloading image from {url} (attempt {retries+1}/{max_retries})")
                async with aiohttp.ClientSession() as session:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                    async with session.get(url, headers=headers, timeout=10, ssl=False) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            return Image.open(io.BytesIO(image_data))
                        else:
                            logger.warning(f"Failed to download image: HTTP {response.status}")
            except Exception as e:
                logger.warning(f"Error downloading image (attempt {retries+1}): {e}")
            
            retries += 1
            await asyncio.sleep(1)  # Wait 1 second before retry
            
        return None

    async def create_price_comparison_banner(self, game_title: str, prices: Dict[str, Any], steam_app_id: str = None) -> str:
        """
        Create a price comparison banner image
        
        Args:
            game_title: Title of the game
            prices: Dictionary with steam_price, allkeyshop_price, and discount_percentage
            steam_app_id: Optional Steam App ID for fetching game cover art
            
        Returns:
            Path to the generated banner image or Cloudinary URL
        """
        try:
            # Get prices from the dictionary
            steam_price = prices.get('steam_price', 'N/A')
            allkeyshop_price = prices.get('allkeyshop_price', 'N/A')
            discount_percentage = prices.get('discount_percentage', 0)
            steam_app_id = prices.get('steam_app_id', steam_app_id)
            
            # Generate filename with timestamp
            timestamp = int(time.time())
            filename = f"price_comparison_{game_title.replace(' ', '_')}_{timestamp}.png"
            banner_path = self.price_banners_path / filename
            
            # Banner dimensions
            width, height = 1080, 1920
            
            # Try to get game cover art if we have a Steam App ID
            banner_image = None
            
            # Check if we have a Steam App ID either in the prices dict or as a separate parameter
            effective_steam_app_id = None
            
            # Check all possible sources for Steam App ID
            if steam_app_id and isinstance(steam_app_id, (str, int)) and str(steam_app_id).strip():
                effective_steam_app_id = str(steam_app_id).strip()
                logger.info(f"Using provided steam_app_id parameter: {effective_steam_app_id}")
            elif prices and isinstance(prices, dict) and prices.get('steam_app_id'):
                effective_steam_app_id = str(prices['steam_app_id']).strip()
                logger.info(f"Using steam_app_id from prices dictionary: {effective_steam_app_id}")
            
            # We'll rely only on the explicitly provided steam_app_id
            # No need for hardcoded game mappings anymore
            
            # Log what we're using
            if effective_steam_app_id:
                logger.info(f"Using provided Steam App ID: {effective_steam_app_id}")
            else:
                logger.info(f"No Steam App ID available for {game_title} - will attempt to find game cover without it")
            
            # Try to download the game cover using the effective Steam App ID
            # Pass the Steam App ID directly to download_game_cover
            if effective_steam_app_id:
                logger.info(f"Attempting to download game cover with Steam App ID: {effective_steam_app_id}")
                banner_image = await self.download_game_cover(game_title, effective_steam_app_id)
            else:
                logger.warning(f"No Steam App ID available for {game_title}, will try without it")
                banner_image = await self.download_game_cover(game_title)
                
            # Create a cinematic 9:16 portrait banner with game header and atmospheric background
            # Banner dimensions are already 1080x1920 (9:16)
            
            # Create banner base image
            banner = None
            img_width, img_height = 0, 0
            
            if banner_image:
                # Get image dimensions for the game header
                img_width, img_height = banner_image.size
                img_aspect = img_width / img_height
                logger.info(f"Original game header dimensions: {img_width}x{img_height}, aspect ratio: {img_aspect}")
                
                # Create a background by stretching and blurring the game header image as requested
                # Step 1: Resize the game image to fill the entire banner (stretching it)
                bg_image = banner_image.resize((width, height), Image.LANCZOS)
                
                # Step 2: Apply a strong blur effect
                blur_radius = 30  # Strong blur
                background = bg_image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
                
                # Step 3: Darken the background slightly for better text visibility
                darkening_factor = 0.6  # Lower is darker
                darkening_layer = Image.new('RGBA', (width, height), (0, 0, 0, int(255 * (1 - darkening_factor))))
                
                # Convert to RGBA for alpha compositing
                if background.mode != 'RGBA':
                    background = background.convert('RGBA')
                
                # Apply darkening and set as banner
                banner = background.copy()
            else:
                # No valid image - create a themed background based on game title
                logger.warning("No valid game image available, creating themed background")
                game_title_lower = game_title.lower()
                
                # Create a dynamic gradient based on game title
                import hashlib
                hash_val = int(hashlib.md5(game_title.encode()).hexdigest(), 16)
                r = (hash_val & 0xFF0000) >> 16
                g = (hash_val & 0x00FF00) >> 8
                b = hash_val & 0x0000FF
                
                # Ensure colors aren't too bright or too dark
                r = max(20, min(r, 80))
                g = max(20, min(g, 80))
                b = max(20, min(b, 80))
                
                logger.info(f"Using banner base color: rgb({r},{g},{b})")
                banner = Image.new('RGB', (width, height), (r, g, b))
            
            # Convert to RGB for further processing
            image = banner.convert('RGB')
            
            # Set up the header region for the game image
            header_height = int(height * 0.25)  # 25% of banner height for header
            header_y = int(height * 0.12)  # Position lower as per screenshot (increased from 0.04 to 0.12)
            
            # Place the game header image at the top of the banner
            if banner_image and img_width > 0 and img_height > 0:  # Ensure valid dimensions
                # Calculate dimensions to fit header while maintaining aspect ratio exactly
                original_aspect = img_width / img_height
                
                # Determine how to fit image in header area while preserving aspect ratio
                # For header images (typically wider than tall), fit by width then adjust height
                new_width = int(width * 0.95)  # Use 95% of banner width
                new_height = int(new_width / original_aspect)
                
                # If height exceeds our header area, scale down
                if new_height > header_height * 0.95:
                    new_height = int(header_height * 0.95)
                    new_width = int(new_height * original_aspect)
                
                # Create the properly sized header image
                header_image = banner_image.resize((new_width, new_height), Image.LANCZOS)
                
                # Center the header image horizontally and place at the top
                paste_x = (width - new_width) // 2
                paste_y = header_y + (header_height - new_height) // 2
                
                # Add a slight shadow behind the header for better visibility
                shadow_overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
                shadow_draw = ImageDraw.Draw(shadow_overlay)
                
                # Draw soft shadow beneath the header image
                shadow_height = int(new_height * 0.2)  # 20% of image height
                shadow_y = paste_y + new_height - shadow_height // 2
                for y in range(shadow_height):
                    opacity = int(80 * (1 - y / shadow_height))  # Fade from 80 to 0
                    shadow_draw.rectangle(
                        [paste_x, shadow_y + y, paste_x + new_width, shadow_y + y + 1],
                        fill=(0, 0, 0, opacity)
                    )
                
                # Apply shadow
                image = image.convert('RGBA')
                image = Image.alpha_composite(image, shadow_overlay)
                image = image.convert('RGB')  # Convert back for pasting
                
                # Paste the header image
                image.paste(header_image, (paste_x, paste_y))
                
                logger.info(f"Placed game header image at ({paste_x}, {paste_y}) size: {new_width}x{new_height}")
                logger.info(f"Original aspect ratio {original_aspect:.4f} maintained exactly")
            else:
                # We're using our themed background already created above
                logger.info("Using themed background for text overlay")
            draw = ImageDraw.Draw(image)
            
            # Load fonts with EVEN LARGER sizes to match reference
            # Use the system fonts we detected earlier
            try:
                # Use font sizes that match the reference image exactly
                # Bold font for emphasis
                if self.system_bold_font:
                    # No title font needed anymore since we're using the original logo
                    discount_font = ImageFont.truetype(self.system_bold_font, 150)  # Discount font size matches reference
                    price_value_font = ImageFont.truetype(self.system_bold_font, 100)  # Increased from 90 to 100 for better visibility in the green box
                else:
                    logger.warning("No bold system font found, using default")  
                    discount_font = ImageFont.load_default()
                    price_value_font = ImageFont.load_default()
                    
                # Regular font for labels
                if self.system_regular_font:
                    price_label_font = ImageFont.truetype(self.system_regular_font, 60)  # Reduced from 80 to 60 to prevent ALLKEYSHOP cropping
                else:
                    logger.warning("No regular system font found, using default")
                    price_label_font = ImageFont.load_default()
                    
                logger.info(f"Successfully loaded system fonts for banner")
                
            except Exception as font_error:
                # Detailed error logging to diagnose font issues
                logger.warning(f"Error loading fonts: {font_error}")
                logger.warning("Falling back to system default font")
                
                # Try one last approach with Arial which is very commonly available
                try:
                    arial_paths = [
                        "/Library/Fonts/Arial.ttf",
                        "/Library/Fonts/Arial Bold.ttf",
                        "/System/Library/Fonts/Supplemental/Arial.ttf",
                        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
                    ]
                    
                    # Try to find any working Arial font
                    for path in arial_paths:
                        if os.path.exists(path):
                            # No title font needed anymore since we're using the original logo
                            discount_font = ImageFont.truetype(path, 150)  # Matches reference image
                            price_label_font = ImageFont.truetype(path, 60)  # Reduced from 80 to 60 to prevent ALLKEYSHOP cropping
                            price_value_font = ImageFont.truetype(path, 100)  # Increased from 90 to 100 for better visibility in the green box
                            logger.info(f"Using Arial font at: {path}")
                            break
                    else:  # If loop completes without break
                        # Use default PIL font as last resort
                        logger.warning("Could not load any system fonts, using PIL defaults")
                        # No title font needed anymore
                        discount_font = ImageFont.load_default()
                        price_label_font = ImageFont.load_default()
                        price_value_font = ImageFont.load_default()
                        
                except Exception as final_error:
                    logger.error(f"Final font loading attempt failed: {final_error}")
                    # No title font needed anymore
                    discount_font = ImageFont.load_default()
                    price_label_font = ImageFont.load_default()
                    price_value_font = ImageFont.load_default()
            
            # Position calculations based on reference screenshot
            # No title text needed - the game image already has the title
            discount_y = height // 2 + 100  # Discount in the middle
            
            # Position prices to match the green box in the screenshot
            allkeyshop_y = int(height * 0.63)  # AllKeyShop price
            steam_y = int(height * 0.69)  # Steam price - adjusted for better spacing in the green box
            
            # Draw discount percentage if applicable - EXTREMELY LARGE & BOLD
            if discount_percentage and discount_percentage > 0:
                # Format to exactly match reference - no space between number and %
                discount_text = f"{discount_percentage}% OFF"
                
                # MUCH thicker black outline for better visibility (6 pixels instead of 4)
                # Create a more complete outline with 16 points around the text
                outline_color = (0, 0, 0)
                outline_width = 6  # Even thicker outline
                
                # Create a complete outline by drawing at multiple offset positions
                for x_offset in range(-outline_width, outline_width+1, 3):
                    for y_offset in range(-outline_width, outline_width+1, 3):
                        # Skip the center point as we'll draw the actual text there
                        if x_offset == 0 and y_offset == 0:
                            continue
                            
                        draw.text(
                            (width // 2 + x_offset, discount_y + y_offset),
                            discount_text,
                            font=discount_font,
                            fill=outline_color,
                            anchor="mm"
                        )
                
                # Draw main discount text in bright RED - exactly matching reference color
                # Use a slightly more orange-red to match the reference
                draw.text(
                    (width // 2, discount_y),
                    discount_text,
                    font=discount_font,
                    fill=(255, 30, 0),  # Bright orange-red
                    anchor="mm"
                )
            
            # Format prices (move € symbol to the end for better readability)
            formatted_aks_price = allkeyshop_price.replace('€', '') + '€' if '€' in allkeyshop_price else allkeyshop_price
            formatted_steam_price = steam_price.replace('€', '') + '€' if '€' in steam_price else steam_price
            
            # Draw AllKeyShop price - simplified labels as in reference
            # Add black outline for the label to make it more readable in green box
            outline_width = 2  # Thin outline for price labels
            outline_color = (0, 0, 0)  # Black outline
            
            # Draw outline for ALLKEYSHOP label
            for x_offset in [-outline_width, outline_width]:
                for y_offset in [-outline_width, outline_width]:
                    draw.text(
                        (width // 2 + x_offset, allkeyshop_y + y_offset),
                        "ALLKEYSHOP:",
                        font=price_label_font,
                        fill=outline_color,
                        anchor="rm"  # Right-middle alignment
                    )
            
            # Draw the actual label
            draw.text(
                (width // 2, allkeyshop_y),
                "ALLKEYSHOP:", # Changed from "ALLKEYSHOP PRICE" to match reference
                font=price_label_font,
                fill=(255, 255, 255),  # White
                anchor="rm"  # Right-middle alignment
            )
            
            # Draw price next to label (not below)
            # Add outline to price value for better readability in green box
            for x_offset in [-outline_width, outline_width]:
                for y_offset in [-outline_width, outline_width]:
                    draw.text(
                        (width // 2 + 20 + x_offset, allkeyshop_y + y_offset),
                        formatted_aks_price,
                        font=price_value_font,
                        fill=outline_color,
                        anchor="lm"  # Left-middle alignment
                    )
            
            # Draw the actual price with a brighter lime-green color to match reference
            draw.text(
                (width // 2 + 20, allkeyshop_y),  # Small space after label
                formatted_aks_price,
                font=price_value_font,
                fill=(0, 255, 40),  # Bright lime green - closely matches reference
                anchor="lm"  # Left-middle alignment
            )
            
            # Draw Steam price - simplified labels as in reference
            # Add black outline for the STEAM label
            for x_offset in [-outline_width, outline_width]:
                for y_offset in [-outline_width, outline_width]:
                    draw.text(
                        (width // 2 + x_offset, steam_y + y_offset),
                        "STEAM:",
                        font=price_label_font,
                        fill=outline_color,
                        anchor="rm"  # Right-middle alignment
                    )
                    
            # Draw the actual Steam label
            draw.text(
                (width // 2, steam_y),
                "STEAM:",  # Changed from "STEAM PRICE" to match reference
                font=price_label_font,
                fill=(255, 255, 255),  # White
                anchor="rm"  # Right-middle alignment
            )
            
            # Draw Steam price next to label with outline
            for x_offset in [-outline_width, outline_width]:
                for y_offset in [-outline_width, outline_width]:
                    draw.text(
                        (width // 2 + 20 + x_offset, steam_y + y_offset),
                        formatted_steam_price,
                        font=price_value_font,
                        fill=outline_color,
                        anchor="lm"  # Left-middle alignment
                    )
            
            # Draw the actual Steam price
            draw.text(
                (width // 2 + 20, steam_y),  # Small space after label
                formatted_steam_price,
                font=price_value_font,
                fill=(180, 180, 180),  # Slightly brighter gray for better readability
                anchor="lm"  # Left-middle alignment
            )
            
            # Save the image
            image.save(banner_path)
            logger.info(f"Banner saved to: {banner_path}")
            
            # Upload to Cloudinary if available
            cloudinary_url = await self.upload_to_cloudinary(str(banner_path))
            return cloudinary_url
            
        except Exception as e:
            logger.error(f"Error creating price comparison banner: {e}")
            return ""
            
    async def get_price_comparison(self, game_title: str, allkeyshop_url: str) -> Dict[str, Any]:
        """
        Main method to get price comparison and generate banner
        
        Args:
            game_title: Title of the game
            allkeyshop_url: URL to the game's AllKeyShop page
            
        Returns:
            Dictionary with price information and banner URL
        """
        try:
            # Extract prices
            prices = await self.extract_prices(game_title, allkeyshop_url)
            
            # Generate banner
            banner_url = await self.create_price_comparison_banner(game_title, prices)
            
            # Return combined results
            return {
                **prices,
                'banner_url': banner_url
            }
        except Exception as e:
            logger.error(f"Error in price comparison pipeline: {e}")
            return {
                'steam_price': 'N/A',
                'allkeyshop_price': 'N/A',
                'discount_percentage': 0,
                'banner_url': ''
            }
            
    async def create_outro(self, game_title: str, game_details: Dict = None) -> str:
        """
        Create banner with game information - This is a wrapper around create_price_comparison_banner
        for backward compatibility with the main.py code
        
        Args:
            game_title: Title of the game
            game_details: Additional game details (optional)
            
        Returns:
            str: URL of the generated banner or fallback URL if there's an error
        """
        # Set a fallback URL in case of any errors - this is important for pipeline integration
        # We ALWAYS want to return a valid URL, never None or empty string
        fallback_url = "https://res.cloudinary.com/dodod8s0v/image/upload/v1759926961/outro_2_crwy4x.png"
        
        try:
            # Validate game title
            if not game_title or not isinstance(game_title, str):
                logger.error(f"Invalid game title: {game_title}")
                return fallback_url
            
            # Start with logging
            logger.info(f"Creating game banner for: {game_title}")
            logger.info(f"Game details provided: {game_details}")
            
            # Use game title for logging
            game_title_lower = game_title.lower()
            
            # We'll rely on the app_id provided in game_details from main.py
            # No need for hardcoded mappings since the pipeline handles this now
            
            # If app_id is present but steam_app_id is not, copy it
            if 'app_id' in game_details and 'steam_app_id' not in game_details:
                game_details['steam_app_id'] = game_details['app_id']
                logger.info(f"Using app_id as steam_app_id: {game_details['app_id']}")
            
            # Log if we have a Steam App ID
            if 'steam_app_id' in game_details:
                logger.info(f"Using Steam App ID: {game_details['steam_app_id']} for {game_title}")
            else:
                logger.info(f"No Steam App ID found for {game_title} - will attempt to find game cover without it")
            
            # Ensure we have game details dictionary
            if game_details is None or not isinstance(game_details, dict):
                game_details = {}
                logger.warning("No game details provided or invalid format, using basic information")
            
            # For debugging
            original_url = game_details.get('allkeyshop_url', '')
            
            # Get AllKeyShop URL and correct it
            allkeyshop_url = self._correct_url_if_needed(game_title, game_details.get('allkeyshop_url'))
            
            if original_url != allkeyshop_url:
                logger.info(f"URL corrected: {original_url} -> {allkeyshop_url}")
            
            # Update game_details with corrected URL
            if allkeyshop_url:
                game_details['allkeyshop_url'] = allkeyshop_url
                logger.info(f"Using AllKeyShop URL: {allkeyshop_url}")
            else:
                logger.warning("No valid AllKeyShop URL could be generated or found")
                # Last resort fallback - ensure we always have something
                formatted_title = game_title.lower().replace(' ', '-').replace(':', '').replace("'", "").replace('.', '')
                allkeyshop_url = f"https://www.allkeyshop.com/blog/buy-{formatted_title}-cd-key-compare-prices/"
                game_details['allkeyshop_url'] = allkeyshop_url
                logger.info(f"Using last-resort fallback URL: {allkeyshop_url}")
                
            # Get Steam App ID from game_details if available
            steam_app_id = game_details.get('steam_app_id')
            logger.info(f"Using Steam App ID: {steam_app_id if steam_app_id else 'None'}")
            
            # Try to extract prices with proper error handling
            prices = None
            try:
                prices = await self.extract_prices(game_title, allkeyshop_url)
                if prices:
                    logger.info(f"Successfully extracted prices: {prices}")
            except Exception as price_error:
                logger.error(f"Error extracting prices: {price_error}")
            
            # Ensure we have a valid prices dict
            if not prices or not isinstance(prices, dict):
                prices = {
                    'steam_price': 'N/A',
                    'allkeyshop_price': 'N/A',
                    'discount_percentage': 0
                }
                logger.warning("Using default price values due to extraction failure")
            
            # Add Steam App ID to prices dict if available
            if steam_app_id:
                prices['steam_app_id'] = steam_app_id
                
            logger.info(f"Final prices: Steam: {prices.get('steam_price')}, AllKeyShop: {prices.get('allkeyshop_price')}, Discount: {prices.get('discount_percentage')}%")
            
            # Create the price comparison banner with Steam App ID and proper error handling
            banner_url = None
            try:
                banner_url = await self.create_price_comparison_banner(game_title, prices, steam_app_id)
                logger.info(f"Raw banner URL generated: {banner_url}")
            except Exception as banner_error:
                logger.error(f"Error creating banner: {banner_error}")
            
            # Validate the generated banner URL
            if banner_url and isinstance(banner_url, str) and len(banner_url) > 10 and banner_url.startswith('http'):
                logger.info(f"Valid banner URL generated: {banner_url}")
                return banner_url
            else:
                logger.warning(f"Invalid or missing banner URL: {banner_url}, using fallback")
                return fallback_url
                
        except Exception as e:
            logger.error(f"Unexpected error in create_outro: {e}")
            return fallback_url
            
    async def generate_video_pipeline(self, game_title: str, game_details: Dict = None,
                            gameplay_url: str = None, intro_url: str = None,
                            price_banner_url: str = None) -> Dict:
        """
        Generate video pipeline with all elements for Creatomate
        
        Args:
            game_title: Title of the game
            game_details: Additional game details (optional)
            gameplay_url: URL to gameplay video (optional)
            intro_url: URL to intro video (optional)
            price_banner_url: URL to price comparison banner (optional)
            
        Returns:
            Dict with video pipeline structure
        """
        try:
            # Input validation with fallbacks
            if not price_banner_url or not isinstance(price_banner_url, str):
                logger.warning(f"Invalid price_banner_url: {price_banner_url}, using fallback")
                # Use a default fallback banner URL
                price_banner_url = "https://res.cloudinary.com/dodod8s0v/image/upload/v1759926961/outro_2_crwy4x.png"
                
            if gameplay_url and not isinstance(gameplay_url, str):
                logger.warning(f"Invalid gameplay_url: {gameplay_url}, will be ignored")
                gameplay_url = None
                
            if intro_url and not isinstance(intro_url, str):
                logger.warning(f"Invalid intro_url: {intro_url}, will be ignored")
                intro_url = None
                
            # Build the video pipeline structure for Creatomate
            pipeline = {
                'output_format': 'mp4',
                'width': 1080,
                'height': 1920,
                'elements': []
            }
            
            # Track 1: Gameplay footage (background)
            if gameplay_url and gameplay_url.startswith('http'):
                pipeline['elements'].append({
                    'id': 'gameplay',
                    'name': 'gameplay',
                    'type': 'video',
                    'source': gameplay_url,
                    'track': 1,  # Base layer
                    'fit': 'cover',
                    'time': 0,
                    'duration': 60  # Default duration
                })
                logger.info(f"Added gameplay element: {gameplay_url}")
            else:
                logger.warning("No valid gameplay URL provided for pipeline")
            
            # Track 2: Price comparison banner (overlay at end)
            if price_banner_url and price_banner_url.startswith('http'):
                pipeline['elements'].append({
                    'id': 'coverphoto',
                    'name': 'coverphoto',
                    'type': 'image',
                    'source': price_banner_url,
                    'track': 2,  # Middle layer
                    'fit': 'cover',
                    'time': 30,  # Show in second half of video
                    'duration': 30,
                    'animations': [
                        {
                            'type': 'fade',
                            'fade_in': True,
                            'duration': 1
                        }
                    ]
                })
                logger.info(f"Added coverphoto element: {price_banner_url}")
            else:
                logger.warning("No valid price banner URL provided for pipeline")
            
            # Track 3: Intro with transparent background (top layer)
            if intro_url and intro_url.startswith('http'):
                pipeline['elements'].append({
                    'id': 'intro',
                    'name': 'intro',
                    'type': 'video',
                    'source': intro_url,
                    'track': 3,  # Top layer
                    'fit': 'contain',
                    'time': 0,
                    'duration': 15,  # Intro duration
                    'animations': [
                        {
                            'type': 'fade',
                            'fade_out': True,
                            'duration': 1
                        }
                    ]
                })
                logger.info(f"Added intro element: {intro_url}")
            else:
                logger.warning("No valid intro URL provided for pipeline")
            
            # Verify we have at least one element in the pipeline
            if not pipeline['elements']:
                logger.error("No valid elements for pipeline, creating basic placeholder element")
                # Add at least one element so the pipeline is not empty
                pipeline['elements'].append({
                    'id': 'placeholder',
                    'name': 'placeholder',
                    'type': 'text',
                    'text': f"Game: {game_title}",
                    'track': 1,
                    'y': "50%",
                    'time': 0,
                    'duration': 60
                })
            
            logger.info(f"Generated video pipeline with {len(pipeline['elements'])} elements")
            return pipeline
            
        except Exception as e:
            logger.error(f"Error generating video pipeline: {e}")
            # Return a minimal fallback pipeline
            return {
                'output_format': 'mp4',
                'width': 1080,
                'height': 1920,
                'elements': [
                    {
                        'id': 'placeholder',
                        'name': 'placeholder',
                        'type': 'text',
                        'text': game_title or "Video Placeholder",
                        'y': "50%",
                        'time': 0,
                        'duration': 60
                    }
                ]
            }

# User input and test function
if __name__ == "__main__":
    # Set up logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    async def test_price_comparison():
        # Initialize the generator
        generator = PriceComparisonGenerator()
        
        # Prompt user for input
        print("\nPrice Comparison Banner Generator")
        print("=============================")
        
        # Get AllKeyShop URL
        test_url = input("\nEnter AllKeyShop URL (e.g., https://www.allkeyshop.com/blog/buy-arc-raiders-cd-key-compare-prices/): ")
        
        # Default URL if empty
        if not test_url.strip():
            test_url = "https://www.allkeyshop.com/blog/buy-arc-raiders-cd-key-compare-prices/"
            print(f"Using default URL: {test_url}")
        
        # Get Steam App ID
        steam_app_id = input("\nEnter Steam App ID (e.g., 2371800): ")
        
        # Extract game title from URL
        import re
        title_match = re.search(r'buy-([^/]*)-cd-key', test_url)
        if title_match:
            # Convert hyphenated URL format to title case
            raw_title = title_match.group(1).replace('-', ' ')
            test_title = ' '.join(word.capitalize() for word in raw_title.split())
            
            # Ensure URL format matches the game title format
            expected_url_format = f"https://www.allkeyshop.com/blog/buy-{raw_title.replace(' ', '-')}-cd-key-compare-prices/"
            if test_url != expected_url_format and test_url.lower() != expected_url_format.lower():
                print(f"\nNote: URL format might not match game title.")
                print(f"Current URL: {test_url}")
                print(f"Expected format: {expected_url_format}")
                fix_url = input("\nWould you like to use the expected URL format? (y/n): ")
                if fix_url.lower() == 'y':
                    test_url = expected_url_format
                    print(f"Using corrected URL: {test_url}")
        else:
            # If we can't extract from URL, ask for a title
            test_title = input("\nEnter game title: ")
        
        # Log information
        print(f"\nGenerating price comparison for: {test_title}")
        print(f"URL: {test_url}")
        print(f"Steam App ID: {steam_app_id}\n")
        
        # Extract prices
        prices = await generator.extract_prices(test_title, test_url)
        
        # Add Steam App ID to prices dict
        if steam_app_id:
            prices['steam_app_id'] = steam_app_id
            
        # Create banner with Steam App ID
        banner_url = await generator.create_price_comparison_banner(test_title, prices, steam_app_id)
        
        # Combine results
        result = {
            **prices,
            'banner_url': banner_url
        }
        
        # Print results
        print(f"\nResults:")
        print(f"Steam Price: {result.get('steam_price', 'N/A')}")
        print(f"AllKeyShop Price: {result.get('allkeyshop_price', 'N/A')}")
        print(f"Discount: {result.get('discount_percentage', 0)}%")
        print(f"Banner URL: {result.get('banner_url', '')}")
    
    # Run the test
    asyncio.run(test_price_comparison())
    
# End of file - Fixed the unterminated string error