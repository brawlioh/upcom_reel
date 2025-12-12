#!/usr/bin/env python3

import os
import sys
import requests
import json
from typing import Dict, Optional, List
from loguru import logger
import re
import time
import random

class SteamLookup:
    """
    Static utility class for Steam-related lookups and operations.
    """
    
    @staticmethod
    def search_steam_app_id(game_title: str) -> Optional[str]:
        """
        Search for a Steam App ID based on a game title.
        
        Args:
            game_title: The title of the game to search for
            
        Returns:
            str or None: The Steam App ID if found, None otherwise
        """
        try:
            # Use Steam store search
            search_url = f"https://store.steampowered.com/api/storesearch/?term={game_title.replace(' ', '+')}&l=english&cc=US"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            logger.info(f"Searching Steam for game: {game_title}")
            response = requests.get(search_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if we got any results
                if data.get('total') > 0 and 'items' in data:
                    # Return the first match's app_id
                    first_match = data['items'][0]
                    app_id = str(first_match.get('id'))
                    
                    if app_id:
                        logger.info(f"Found Steam App ID: {app_id} for game: {game_title}")
                        return app_id
            
            logger.warning(f"No Steam App ID found for: {game_title}")
            return None
            
        except Exception as e:
            logger.error(f"Error searching Steam App ID: {e}")
            return None

    @staticmethod
    def get_game_details(app_id: str) -> Dict:
        """
        Get game details from Steam API based on App ID.
        
        Args:
            app_id: The Steam App ID
            
        Returns:
            Dict: Game details including pricing information
        """
        try:
            # Build the Steam Store API URL
            api_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=us&l=english"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data and app_id in data and data[app_id].get('success'):
                    game_data = data[app_id]['data']
                    
                    # Extract relevant information
                    result = {
                        'name': game_data.get('name', ''),
                        'steam_app_id': app_id
                    }
                    
                    # Extract pricing
                    if 'price_overview' in game_data:
                        price_info = game_data['price_overview']
                        result['steam_price'] = price_info.get('final_formatted', 'N/A')
                        
                        # Extract discount percentage if available
                        if 'discount_percent' in price_info:
                            result['discount_percentage'] = price_info.get('discount_percent', 0)
                    
                    # Get header image
                    if 'header_image' in game_data:
                        result['image_url'] = game_data['header_image']
                    
                    logger.info(f"Got game details for App ID: {app_id} - {result.get('name')}")
                    return result
            
            logger.warning(f"Failed to get game details for App ID: {app_id}")
            return {'steam_app_id': app_id, 'name': '', 'steam_price': 'N/A'}
            
        except Exception as e:
            logger.error(f"Error getting game details: {e}")
            return {'steam_app_id': app_id, 'name': '', 'steam_price': 'N/A'}
