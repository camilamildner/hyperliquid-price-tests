import requests
import time
import logging
from requests.exceptions import Timeout, RequestException
from typing import Optional

# Configuration
MAX_RETRIES = 3
TIMEOUT_SECONDS = 2
BASE_URL = "https://api.hyperliquid.xyz/info"

# Logger setup
logger = logging.getLogger(__name__)

# Global cache for last known prices (simple implementation)
_last_known_prices = {}


class HyperLiquidAPIError(Exception):
    """Base exception for API errors."""
    pass


class RateLimitError(HyperLiquidAPIError):
    """Rate limit exception with retry-after information."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class InvalidPriceDataError(HyperLiquidAPIError):
    """Invalid price data (negative, zero, non-numeric, missing)."""
    pass


class RetryExhaustedError(HyperLiquidAPIError):
    """All retry attempts have been exhausted."""
    pass


def get_hyperliquid_price(symbol: str, use_fallback: bool = False) -> float:
    """
    Fetch price from Hyperliquid API with robust error handling.
    
    Args:
        symbol: Trading symbol (e.g., 'BTC', 'ETH')
        use_fallback: If True, use last known price on invalid data (non-critical mode)
                     If False, raise exception on invalid data (critical mode)
    
    Returns:
        float: Current price for the symbol
    
    Raises:
        RateLimitError: When rate limited (429)
        InvalidPriceDataError: When price data is invalid
        RetryExhaustedError: When all retry attempts fail
        HyperLiquidAPIError: For other API errors
    """
    global _last_known_prices
    last_exception = None
    
    logger.info(f"Fetching price for {symbol} (fallback enabled: {use_fallback})")
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Make API request
            response = requests.get(
                BASE_URL,
                params={"symbol": symbol, "type": "spotPrice"},
                timeout=TIMEOUT_SECONDS,
                headers={"User-Agent": "HyperLiquid-Price-Client/1.0"}
            )
            
            logger.debug(f"Attempt {attempt}/{MAX_RETRIES}: Status {response.status_code}")
            
            # === RATE LIMIT (429) - TC04 ===
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                retry_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
                
                error_msg = f"Rate limited for {symbol}"
                if retry_seconds:
                    error_msg += f". Retry after {retry_seconds} seconds"
                
                logger.warning(f"{error_msg}. Blocking trading.")
                raise RateLimitError(error_msg, retry_after=retry_seconds)
            
            # === SUCCESS (200) - TC01 ===
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError as e:
                    # === INVALID JSON - TC06 ===
                    logger.error(f"CRITICAL: Invalid JSON response for {symbol}. Blocking trading.")
                    raise InvalidPriceDataError(f"Invalid JSON response for {symbol}: {e}")
                
                # Extract price field
                price = data.get("price")
                
                # === MISSING PRICE FIELD - TC03 ===
                if price is None:
                    logger.warning(f"Missing price field in response for {symbol}")
                    
                    if use_fallback and symbol in _last_known_prices:
                        fallback_price = _last_known_prices[symbol]
                        logger.info(f"Using fallback price for {symbol}: {fallback_price}")
                        return fallback_price
                    else:
                        logger.error(f"CRITICAL: No price data for {symbol}. Blocking trading.")
                        raise InvalidPriceDataError(f"Missing price field for {symbol}")
                
                # === NON-NUMERIC PRICE - TC03 ===
                if not isinstance(price, (int, float)):
                    logger.error(f"CRITICAL: Price not numeric for {symbol}: {type(price)}. Blocking trading.")
                    raise InvalidPriceDataError(f"Price not numeric for {symbol}: {price}")
                
                # === NEGATIVE OR ZERO PRICE - TC03 ===
                if price <= 0:
                    logger.error(f"CRITICAL: Invalid price value for {symbol}: {price}. Blocking trading.")
                    raise InvalidPriceDataError(f"Invalid price value for {symbol}: {price}")
                
                # Valid price - update cache and return
                price_float = float(price)
                _last_known_prices[symbol] = price_float
                logger.info(f"Successfully fetched price for {symbol}: {price_float}")
                return price_float
            
            # === SERVER ERROR (500-599) - TC02 ===
            if 500 <= response.status_code < 600:
                logger.warning(f"Server error {response.status_code} for {symbol} (attempt {attempt}/{MAX_RETRIES})")
                
                if attempt < MAX_RETRIES:
                    # Wait before retry (exponential backoff simplified)
                    wait_time = attempt * 0.5
                    time.sleep(wait_time)
                    continue
                else:
                    # === RETRY EXHAUSTION - TC07 ===
                    last_exception = HyperLiquidAPIError(
                        f"Server error {response.status_code} after {MAX_RETRIES} retries"
                    )
                    break
            
            # === CLIENT ERROR (400-499) ===
            if 400 <= response.status_code < 500:
                logger.error(f"Client error {response.status_code} for {symbol}. Blocking trading.")
                raise HyperLiquidAPIError(f"Client error {response.status_code} for {symbol}")
            
            # === UNEXPECTED STATUS CODE ===
            logger.error(f"Unexpected status code {response.status_code} for {symbol}")
            raise HyperLiquidAPIError(f"Unexpected status code: {response.status_code}")
        
        # === NETWORK TIMEOUT - TC05 ===
        except Timeout as e:
            logger.warning(f"Timeout for {symbol} (attempt {attempt}/{MAX_RETRIES})")
            last_exception = e
            
            if attempt < MAX_RETRIES:
                wait_time = attempt * 0.5
                time.sleep(wait_time)
                continue
            break
        
        # === OTHER NETWORK ERRORS ===
        except RequestException as e:
            logger.warning(f"Network error for {symbol}: {e} (attempt {attempt}/{MAX_RETRIES})")
            last_exception = e
            
            if attempt < MAX_RETRIES:
                wait_time = attempt * 0.5
                time.sleep(wait_time)
                continue
            break
        
        # === RATE LIMIT ERROR (bubble up immediately) ===
        except RateLimitError:
            raise  # Re-raise immediately, no retry for rate limits
    
    # === ALL RETRIES EXHAUSTED - TC02, TC05, TC07 ===
    logger.error(f"CRITICAL: All {MAX_RETRIES} retries exhausted for {symbol}. Blocking trading.")
    raise RetryExhaustedError(
        f"Failed to get price for {symbol} after {MAX_RETRIES} attempts"
    ) from last_exception