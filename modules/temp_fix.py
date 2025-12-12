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
                        logger.info(f"Steam API response structure: {list(data.keys()) if isinstance(data, dict) else 'Not a dictionary'}")
                        
                        # Process the response
                        if 'products' in data and len(data['products']) > 0:
                            product = data['products'][0]
                            logger.info(f"Found product for Steam price: {product.get('name', 'Unknown')}")
                            logger.info(f"Steam product keys: {list(product.keys()) if isinstance(product, dict) else 'Not a dictionary'}")
                            
                            if 'offers' in product and len(product['offers']) > 0:
                                logger.info(f"Found {len(product['offers'])} Steam offers")
                                
                                # Look for Steam price in the offers
                                for offer in product['offers']:
                                    if 'price' in offer and offer.get('merchant', {}).get('name', '') == 'Steam':
                                        steam_price = offer.get('price')
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
