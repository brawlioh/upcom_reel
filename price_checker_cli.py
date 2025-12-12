#!/usr/bin/env python3
import asyncio
import argparse
import sys
from loguru import logger
from modules.module0_price import PriceComparisonGenerator
from config import Config

# Configure logger
logger.add("logs/price_checker_{time}.log", rotation="1 day", retention="3 days")

async def check_allkeyshop_price(url: str):
    """Check the price of a game from an AllKeyShop URL and generate a price comparison banner"""
    try:
        print("\n💰 ALLKEYSHOP PRICE COMPARISON")
        print("=" * 60)
        
        if not url or not url.startswith("https://www.allkeyshop.com/"):
            print("❌ Invalid URL. Please provide a valid AllKeyShop URL.")
            print("Example: https://www.allkeyshop.com/blog/buy-assetto-corsa-rally-cd-key-compare-prices/")
            return None
        
        # Extract game title from URL
        game_title = "Unknown Game"
        try:
            # Format: https://www.allkeyshop.com/blog/buy-[game-name]-cd-key-compare-prices/
            url_parts = url.split("/")
            for part in url_parts:
                if part.startswith("buy-") and part.endswith("-cd-key-compare-prices"):
                    game_title = part.replace("buy-", "").replace("-cd-key-compare-prices", "")
                    game_title = game_title.replace("-", " ").title()
                    break
        except Exception as e:
            logger.warning(f"Couldn't extract game title from URL: {e}")
            
        print(f"🎮 Game: {game_title}")
        print(f"🔗 URL: {url}")
        
        # Initialize price comparison generator
        price_gen = PriceComparisonGenerator()
        
        # First fetch just the price data
        print("\n🔍 Fetching price data...")
        allkeyshop_price = await price_gen.fetch_allkeyshop_price(game_title, None, url)
        
        # Create minimal game details dict
        game_details = {
            "title": game_title,
            "name": game_title,
            "allkeyshop_url": url,
            "allkeyshop_price": allkeyshop_price
        }
        
        print(f"\n💰 AllKeyShop Price: {allkeyshop_price}")
        
        # Generate price comparison banner
        print("\n🖼️ Creating price comparison banner...")
        banner_url = await price_gen.create_price_comparison(game_title, game_details, url)
        
        print("\n✅ Price comparison completed")
        print(f"🖼️ Banner URL: {banner_url}")
        
        return {
            "game": game_title,
            "url": url,
            "price": allkeyshop_price,
            "banner_url": banner_url
        }
        
    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"\n❌ Error: {e}")
        return None

def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate price comparison banners from AllKeyShop URLs")
    parser.add_argument("--url", type=str, help="AllKeyShop URL for the game")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    return parser.parse_args()

async def main():
    # Ensure required directories exist
    Config.ensure_directories()
    
    # Parse arguments
    args = parse_arguments()
    
    if args.url:
        url = args.url
    else:
        # Prompt for input
        print("\n💰 ALLKEYSHOP PRICE CHECKER")
        print("=" * 60)
        print("Enter an AllKeyShop URL (e.g., https://www.allkeyshop.com/blog/buy-assetto-corsa-rally-cd-key-compare-prices/)")
        url = input("URL: ").strip()
    
    # Run the price checker
    result = await check_allkeyshop_price(url)
    
    # Output as JSON if requested
    if args.json and result:
        import json
        # Print JSON result to stdout
        print(json.dumps(result, indent=2))
        
        # Also save to a file with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"price_data_{timestamp}.json"
        
        with open(filename, "w") as f:
            json.dump(result, f, indent=2)
            
        # Only in non-JSON output mode do we print this message
        if not args.json:
            print(f"\nJSON data saved to {filename}")
    
    # Exit with appropriate code
    sys.exit(0 if result else 1)

if __name__ == "__main__":
    asyncio.run(main())
