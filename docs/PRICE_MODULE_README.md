# Price Comparison Module

This module enables fetching game price data from AllKeyShop and generating price comparison banners.

## Features

- Direct input of AllKeyShop URLs
- Automatic game title extraction from URLs
- Real-time price fetching from AllKeyShop API
- Generation of price comparison banners between Steam and AllKeyShop prices
- Discount percentage calculation
- Cloudinary integration for banner hosting

## Usage

### Command Line Interface

The easiest way to use this module is through the command-line interface:

```bash
# Run with URL argument
python3 price_checker_cli.py --url "https://www.allkeyshop.com/blog/buy-assetto-corsa-rally-cd-key-compare-prices/"

# Run with interactive prompt
python3 price_checker_cli.py
```

### API Usage

You can also import and use the module programmatically in your Python code:

```python
import asyncio
from modules.module0_price import PriceComparisonGenerator

async def generate_price_banner():
    # Initialize the price comparison generator
    price_gen = PriceComparisonGenerator()
    
    # Define your AllKeyShop URL
    allkeyshop_url = "https://www.allkeyshop.com/blog/buy-assetto-corsa-rally-cd-key-compare-prices/"
    
    # Extract game title (or provide it directly)
    game_title = "Assetto Corsa Rally"
    
    # Create minimal game details dict
    game_details = {
        "title": game_title,
        "name": game_title,
        "allkeyshop_url": allkeyshop_url
    }
    
    # Generate price comparison banner
    banner_url = await price_gen.create_price_comparison(game_title, game_details, allkeyshop_url)
    
    return banner_url

# Run the async function
banner_url = asyncio.run(generate_price_banner())
print(f"Banner URL: {banner_url}")
```

## Direct Module Execution

You can also run the price module directly:

```bash
python3 -m modules.module0_price "https://www.allkeyshop.com/blog/buy-assetto-corsa-rally-cd-key-compare-prices/"
```

## API Reference

### `PriceComparisonGenerator` Class

The main class for price comparison operations.

#### Methods:

- `create_price_comparison(game_title, game_details=None, allkeyshop_url=None)`: Creates a price comparison banner
- `extract_prices(game_title, game_details=None, steam_app_id=None, allkeyshop_url=None)`: Extracts prices from Steam and AllKeyShop
- `fetch_steam_price(game_title, steam_app_id=None)`: Fetches price from Steam Store API
- `fetch_allkeyshop_price(game_title, game_details=None, direct_url=None)`: Fetches price from AllKeyShop API
- `calculate_discount(steam_price, allkeyshop_price)`: Calculates discount percentage
- `create_price_comparison_banner(game_title, prices)`: Creates the visual banner image

## Example Output

When the script runs successfully, it will output something like:

```
💰 ALLKEYSHOP PRICE COMPARISON
============================================================
🎮 Game: Assetto Corsa Rally
🔗 URL: https://www.allkeyshop.com/blog/buy-assetto-corsa-rally-cd-key-compare-prices/

🔍 Fetching price data...
💰 AllKeyShop Price: €30.99

🖼️ Creating price comparison banner...
✅ Price comparison completed
🖼️ Banner URL: http://res.cloudinary.com/dodod8s0v/image/upload/v1763557111/youtube_reels/price_comparison_Assetto%20Corsa%20Rally.png
```

The generated banner will be uploaded to Cloudinary and accessible via the provided URL.

## Requirements

- Python 3.7+
- aiohttp
- Pillow (PIL)
- cloudinary
- loguru
