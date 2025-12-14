import requests
from requests.exceptions import Timeout, RequestException

MAX_RETRIES = 3
TIMEOUT_SECONDS = 2


class HyperLiquidAPIError(Exception):
    pass


class RateLimitError(Exception):
    pass


def get_hyperliquid_price(symbol: str) -> float:
    last_exception = None

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                "https://api.hyperliquid.xyz",
                timeout=TIMEOUT_SECONDS
            )

            # ---- SUCCESS ----
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    raise HyperLiquidAPIError("Invalid JSON response")

                price = data.get("price")

                if price is None or not isinstance(price, (int, float)) or price <= 0:
                    raise HyperLiquidAPIError("Invalid price data")

                return float(price)

            # ---- RATE LIMIT ----
            if response.status_code == 429:
                raise RateLimitError("Rate limited")

            # ---- SERVER ERROR (RETRYABLE) ----
            if response.status_code >= 500:
                last_exception = HyperLiquidAPIError("Server error")
                continue

            # ---- UNEXPECTED STATUS ----
            last_exception = HyperLiquidAPIError(
                f"Unexpected status code: {response.status_code}"
            )
            continue

        except Timeout as e:
            last_exception = e
            continue

        except RequestException as e:
            last_exception = e
            continue

    # ---- RETRY EXHAUSTED ----
    raise HyperLiquidAPIError("Retry exhausted") from last_exception