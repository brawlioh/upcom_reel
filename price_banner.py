#!/usr/bin/env python3
"""
AllKeyShop Price Banner Generator
--------------------------------

This script generates price comparison banners from AllKeyShop URLs.

Usage:
  ./price_banner.py <allkeyshop-url>
  ./price_banner.py --json <allkeyshop-url>
  ./price_banner.py (interactive mode)

Examples:
  ./price_banner.py https://www.allkeyshop.com/blog/buy-assetto-corsa-rally-cd-key-compare-prices/
  ./price_banner.py --json https://www.allkeyshop.com/blog/buy-assetto-corsa-rally-cd-key-compare-prices/
"""

import sys
import os
from price_checker_cli import main
import asyncio

if __name__ == "__main__":
    # Call the main function from price_checker_cli.py
    asyncio.run(main())
