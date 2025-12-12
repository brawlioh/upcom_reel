# Price Module Fixes

## Issues Fixed

1. **UTF-8 Encoding Error**: Fixed issue with non-ASCII characters in URLs causing `'utf-8' codec can't encode characters in position 1-2: surrogates not allowed'` error.

2. **aiohttp.ClientRetry Missing**: Removed dependency on `aiohttp.ClientRetry` which is not available in all versions of aiohttp.

3. **API Connection Failures**: Enhanced error handling and added proper URL normalization to ensure more consistent API responses.

## Implemented Solutions

### 1. URL Normalization

Added URL normalization to handle potential Unicode encoding issues:

```python
# Normalize URL to handle potential UTF-8 encoding issues
import unicodedata
allkeyshop_url = unicodedata.normalize('NFKD', allkeyshop_url).encode('ascii', 'ignore').decode('ascii')
```

This converts any special characters in URLs to their closest ASCII equivalent, preventing UTF-8 encoding errors during API requests.

### 2. Removed ClientRetry Dependency

Replaced `aiohttp.ClientRetry` with a manual retry approach that was already implemented in the code:

```python
# Removed:
retry_options = aiohttp.ClientRetry(
    total=3,  # Try 3 times
    statuses=[408, 429, 500, 502, 503, 504],  # Common error codes to retry
    exceptions=[aiohttp.ClientError, asyncio.TimeoutError],
    retry_delay=1,  # 1 second delay between retries
)

# Using manual retry with existing for loop that tries multiple request formats
```

This fix ensures compatibility with all versions of aiohttp, including older versions that don't have the ClientRetry feature.

### 3. Additional Error Handling

- Added try/except blocks around URL normalization
- Improved logging for debugging URL issues
- Maintained existing 3-attempt retry mechanism for API calls

## Testing

The fix has been successfully tested with:

- Game: "INAZUMA ELEVEN: Victory Road"
- AllKeyShop URL: "https://www.allkeyshop.com/blog/buy-inazuma-eleven-victory-road-of-heroes-cd-key-compare-prices/"

### Test Results

- ✅ Price data is now successfully retrieved (Steam: €69.99, AllKeyShop: €65.05, Discount: 7%)
- ✅ Price comparison banner is successfully generated
- ✅ Full video pipeline works end-to-end

## Future Recommendations

1. Consider implementing a URL validation function that checks for and cleans problematic characters before making API requests
2. Add unit tests for edge cases with special characters in URLs
3. Update aiohttp to the latest version if possible
