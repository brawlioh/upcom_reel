#!/usr/bin/env python3

import asyncio
import sys
import os
from typing import Dict, Optional
from loguru import logger

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import required modules
from modules.module0_price import PriceComparisonGenerator

async def generate_coverphoto_for_video(game_title: str, game_details: Dict = None, allkeyshop_url: Optional[str] = None) -> str:
    """
    Generate a price comparison banner to use as coverphoto for a game video
    
    Args:
        game_title: Title of the game
        game_details: Optional dictionary with game details
        allkeyshop_url: Optional AllKeyShop URL
        
    Returns:
        URL of the generated coverphoto on Cloudinary
    """
    logger.info(f"Generating coverphoto for {game_title}")
    
    # Initialize the price comparison generator
    price_gen = PriceComparisonGenerator()
    
    # Get the coverphoto URL using the dedicated method
    try:
        coverphoto_url = await price_gen.get_coverphoto_url(
            game_title=game_title,
            game_details=game_details,
            allkeyshop_url=allkeyshop_url
        )
        logger.info(f"Successfully generated coverphoto: {coverphoto_url}")
        return coverphoto_url
    except Exception as e:
        logger.error(f"Error generating coverphoto: {e}")
        raise

async def integrate_with_creatomate(game_title: str, allkeyshop_url: Optional[str] = None) -> Dict:
    """
    Example of integrating the price comparison coverphoto with Creatomate
    
    Args:
        game_title: Title of the game
        allkeyshop_url: Optional AllKeyShop URL
        
    Returns:
        Dictionary with video creation parameters including the coverphoto URL
    """
    # Generate the coverphoto first
    coverphoto_url = await generate_coverphoto_for_video(game_title, None, allkeyshop_url)
    
    # Prepare Creatomate video creation parameters with the coverphoto
    video_params = {
        "title": game_title,
        "elements": [
            {
                "id": "coverphoto",
                "name": "coverphoto",
                "type": "image",
                "track": 2,
                "time": 0,
                "duration": 4,  # 4 seconds display time
                "source": coverphoto_url,
                "animations": [
                    {
                        "time": "end",
                        "duration": 3,
                        "easing": "quadratic-out",
                        "reversed": True,
                        "type": "fade"
                    }
                ]
            }
            # Add other video elements as needed
        ]
    }
    
    logger.info(f"Prepared video parameters with coverphoto for {game_title}")
    return video_params

# Example usage when run directly
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate price comparison coverphoto for video")
    parser.add_argument("game_title", help="Title of the game")
    parser.add_argument("--url", help="AllKeyShop URL (optional)")
    
    args = parser.parse_args()
    
    async def main():
        try:
            # Generate coverphoto
            coverphoto_url = await generate_coverphoto_for_video(args.game_title, None, args.url)
            print(f"Coverphoto URL: {coverphoto_url}")
            
            # Example of preparing Creatomate parameters
            video_params = await integrate_with_creatomate(args.game_title, args.url)
            print("\nCreatomate Video Parameters:")
            for key, value in video_params.items():
                if key != "elements":
                    print(f"{key}: {value}")
                else:
                    print("elements: [...]")  # Don't print the full elements array
        except Exception as e:
            print(f"Error: {e}")
    
    # Run the async main function
    asyncio.run(main())
