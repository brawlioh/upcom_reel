import requests
from bs4 import BeautifulSoup
from loguru import logger
import time
import re
from typing import List, Dict, Optional

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    _SELENIUM_AVAILABLE = True
except ModuleNotFoundError:
    webdriver = None
    Options = None
    By = None
    WebDriverWait = None
    EC = None
    ChromeDriverManager = None
    _SELENIUM_AVAILABLE = False

class SteamScraper:
    def __init__(self):
        if not _SELENIUM_AVAILABLE:
            raise ModuleNotFoundError(
                "SteamScraper requires 'selenium' and 'webdriver_manager'. "
                "Install them to enable browser-based Steam scraping."
            )
        self.setup_driver()
    
    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        try:
            if not _SELENIUM_AVAILABLE:
                raise ModuleNotFoundError(
                    "SteamScraper requires 'selenium' and 'webdriver_manager'. "
                    "Install them to enable browser-based Steam scraping."
                )
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-logging")
            chrome_options.add_argument("--disable-dev-tools")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
            
            from selenium.webdriver.chrome.service import Service
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(30)  # 30 second timeout
            logger.info("Chrome driver setup successful")
        except Exception as e:
            logger.error(f"Failed to setup Chrome driver: {e}")
            raise Exception(f"Chrome driver setup failed: {e}")
    
    def get_upcoming_games(self, limit: int = 20) -> List[Dict[str, str]]:
        """Scrape upcoming popular games from Steam"""
        try:
            logger.info("Fetching upcoming games from Steam...")
            self.driver.get("https://store.steampowered.com/search/?filter=popularcomingsoon&os=win")
            
            # Wait for games to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "search_result_row"))
            )
            
            games = []
            game_elements = self.driver.find_elements(By.CLASS_NAME, "search_result_row")[:limit]
            
            for element in game_elements:
                try:
                    title_elem = element.find_element(By.CLASS_NAME, "title")
                    title = title_elem.text.strip()
                    
                    # Get game URL
                    game_url = element.get_attribute("href")
                    
                    # Get release date if available
                    release_date = "TBA"
                    try:
                        release_elem = element.find_element(By.CLASS_NAME, "search_released")
                        release_date = release_elem.text.strip()
                    except:
                        pass
                    
                    # Get game image
                    img_url = ""
                    try:
                        img_elem = element.find_element(By.TAG_NAME, "img")
                        img_url = img_elem.get_attribute("src")
                    except:
                        pass
                    
                    games.append({
                        "title": title,
                        "url": game_url,
                        "release_date": release_date,
                        "image_url": img_url,
                        "source": "steam_upcoming"
                    })
                    
                except Exception as e:
                    logger.warning(f"Error parsing game element: {e}")
                    continue
            
            logger.info(f"Found {len(games)} upcoming games")
            return games
            
        except Exception as e:
            logger.error(f"Error fetching upcoming games: {e}")
            raise Exception(f"Steam scraping failed: {e}")
    
    def get_most_wished_games(self, limit: int = 20) -> List[Dict[str, str]]:
        """Scrape most wished games from SteamDB"""
        try:
            logger.info("Fetching most wished games from SteamDB...")
            
            # Use requests for SteamDB as it's simpler
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get("https://steamdb.info/stats/mostwished/", headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            games = []
            table = soup.find('table', class_='table-responsive')
            
            if table:
                rows = table.find_all('tr')[1:limit+1]  # Skip header row
                
                for row in rows:
                    try:
                        cells = row.find_all('td')
                        if len(cells) >= 3:
                            # Game title is usually in the second cell
                            title_cell = cells[1]
                            title_link = title_cell.find('a')
                            
                            if title_link:
                                title = title_link.text.strip()
                                steam_url = f"https://store.steampowered.com/app/{title_link.get('href', '').split('/')[-2]}/"
                                
                                games.append({
                                    "title": title,
                                    "url": steam_url,
                                    "release_date": "TBA",
                                    "image_url": "",
                                    "source": "steam_wishlist"
                                })
                    
                    except Exception as e:
                        logger.warning(f"Error parsing wishlist row: {e}")
                        continue
            
            logger.info(f"Found {len(games)} most wished games")
            return games
            
        except Exception as e:
            logger.error(f"Error fetching most wished games: {e}")
            return []
    
    def get_game_details(self, game_url: str) -> Dict[str, str]:
        """Get additional details for a specific game"""
        try:
            self.driver.get(game_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "apphub_AppName"))
            )
            
            details = {}
            
            # Get description
            try:
                desc_elem = self.driver.find_element(By.CLASS_NAME, "game_description_snippet")
                details["description"] = desc_elem.text.strip()
            except:
                details["description"] = ""
            
            # Get tags
            try:
                tag_elements = self.driver.find_elements(By.CSS_SELECTOR, ".app_tag")
                details["tags"] = [tag.text.strip() for tag in tag_elements[:5]]
            except:
                details["tags"] = []
            
            # Get developer
            try:
                dev_elem = self.driver.find_element(By.CSS_SELECTOR, ".developer_name a")
                details["developer"] = dev_elem.text.strip()
            except:
                details["developer"] = ""
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting game details: {e}")
            return {}
    
    def search_game_videos(self, game_title: str) -> List[str]:
        """Search for gameplay videos of a specific game"""
        try:
            # Clean game title for search
            clean_title = re.sub(r'[^\w\s]', '', game_title)
            search_query = f"{clean_title} gameplay trailer"
            
            # This would typically search YouTube or other video platforms
            # For now, return placeholder URLs that would be replaced with actual video URLs
            video_urls = [
                f"https://example.com/gameplay/{clean_title.replace(' ', '_')}_1.mp4",
                f"https://example.com/gameplay/{clean_title.replace(' ', '_')}_2.mp4"
            ]
            
            logger.info(f"Found {len(video_urls)} video URLs for {game_title}")
            return video_urls
            
        except Exception as e:
            logger.error(f"Error searching videos for {game_title}: {e}")
            return []
    
    def close(self):
        """Close the browser driver"""
        if hasattr(self, 'driver'):
            self.driver.quit()
    
    def get_fallback_games(self, limit: int = 20) -> List[Dict[str, str]]:
        """Fallback list of popular upcoming games when scraping fails"""
        fallback_games = [
            {
                "title": "Cyberpunk 2077: Phantom Liberty",
                "url": "https://store.steampowered.com/app/2138330/Cyberpunk_2077_Phantom_Liberty/",
                "release_date": "2023",
                "image_url": "",
                "source": "fallback",
                "description": "The highly anticipated expansion to Cyberpunk 2077",
                "tags": ["RPG", "Open World", "Cyberpunk"],
                "developer": "CD PROJEKT RED"
            },
            {
                "title": "The Elder Scrolls VI",
                "url": "https://elderscrolls.bethesda.net/en/tes6",
                "release_date": "TBA",
                "image_url": "",
                "source": "fallback",
                "description": "The next chapter in the Elder Scrolls saga",
                "tags": ["RPG", "Fantasy", "Open World"],
                "developer": "Bethesda Game Studios"
            },
            {
                "title": "Grand Theft Auto VI",
                "url": "https://www.rockstargames.com/",
                "release_date": "TBA",
                "image_url": "",
                "source": "fallback",
                "description": "The next installment in the GTA series",
                "tags": ["Action", "Open World", "Crime"],
                "developer": "Rockstar Games"
            },
            {
                "title": "Starfield",
                "url": "https://bethesda.net/en/game/starfield",
                "release_date": "2023",
                "image_url": "",
                "source": "fallback",
                "description": "Bethesda's new space exploration RPG",
                "tags": ["RPG", "Space", "Sci-Fi"],
                "developer": "Bethesda Game Studios"
            },
            {
                "title": "Diablo IV",
                "url": "https://diablo4.blizzard.com/",
                "release_date": "2023",
                "image_url": "",
                "source": "fallback",
                "description": "The next chapter in the Diablo saga",
                "tags": ["Action RPG", "Dark Fantasy", "Multiplayer"],
                "developer": "Blizzard Entertainment"
            },
            {
                "title": "Halo Infinite",
                "url": "https://www.halowaypoint.com/",
                "release_date": "2021",
                "image_url": "",
                "source": "fallback",
                "description": "Master Chief's latest adventure",
                "tags": ["FPS", "Sci-Fi", "Multiplayer"],
                "developer": "343 Industries"
            }
        ]
        
        logger.info(f"Using fallback game list with {min(len(fallback_games), limit)} games")
        return fallback_games[:limit]
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        self.close()
