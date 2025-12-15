import pytest
import requests
import time
from unittest.mock import patch, Mock, MagicMock
from src.price_client import (
    get_hyperliquid_price,
    HyperLiquidAPIError,
    RateLimitError,
    InvalidPriceDataError,
    RetryExhaustedError,
)


class TestNormalCase:
    """TC01: Normal Case (200 OK)"""
    
    @patch("src.price_client.requests.get")
    def test_normal_case_valid_price(self, mock_get):
        """TC01: Valid positive price should return float"""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"price": 45000.75}
        mock_get.return_value = mock_response
        
        # Act
        result = get_hyperliquid_price("BTC")
        
        # Assert
        assert result == 45000.75
        assert isinstance(result, float)
    
    @patch("src.price_client.requests.get")
    def test_symbol_passed_to_api(self, mock_get):
        """Verify symbol parameter is included in API call"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"price": 45000.75}
        mock_get.return_value = mock_response
        
        get_hyperliquid_price("ETH")
        
        # Verify API call includes symbol parameter
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "params" in call_args[1]
        assert call_args[1]["params"]["symbol"] == "ETH"


class TestServerErrors:
    """TC02: API Down (500 Error) and TC07: Retry Exhaustion"""
    
    @patch("src.price_client.requests.get")
    @patch("src.price_client.time.sleep")
    def test_server_error_retries_then_fails(self, mock_sleep, mock_get):
        """TC02: Server errors should retry N times then raise"""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 502
        mock_get.return_value = mock_response
        
        # Act & Assert
        with pytest.raises(RetryExhaustedError, match="Failed to get price"):
            get_hyperliquid_price("BTC")
        
        # Should retry MAX_RETRIES times
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries
    
    @patch("src.price_client.requests.get")
    def test_immediate_failure_on_client_error(self, mock_get):
        """Client errors (400-499) should fail immediately without retry"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with pytest.raises(HyperLiquidAPIError, match="Client error"):
            get_hyperliquid_price("BTC")
        
        assert mock_get.call_count == 1  # No retry on client errors


class TestInvalidPriceData:
    """TC03: Invalid Price Data (negative, null, missing)"""
    
    @patch("src.price_client.requests.get")
    @pytest.mark.parametrize("test_input,expected_error", [
        # Negative price - CRITICAL
        ({"price": -100.0}, "Invalid price value"),
        # Zero price - CRITICAL
        ({"price": 0}, "Invalid price value"),
        # Non-numeric price - CRITICAL
        ({"price": "invalid"}, "Price not numeric"),
        # Missing price field - CRITICAL without fallback
        ({}, "Missing price field"),
    ])
    def test_invalid_price_data_critical(self, mock_get, test_input, expected_error):
        """TC03: Invalid data should raise exception (block trading)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = test_input
        mock_get.return_value = mock_response
        
        with pytest.raises(InvalidPriceDataError, match=expected_error):
            get_hyperliquid_price("BTC", use_fallback=False)
    
    @patch("src.price_client.requests.get")
    def test_missing_price_with_fallback(self, mock_get):
        """Missing price with fallback enabled should use last known price"""
        # First call - valid price
        mock_response1 = Mock()
        mock_response1.status_code = 200
        mock_response1.json.return_value = {"price": 50000.0}
        
        # Second call - missing price
        mock_response2 = Mock()
        mock_response2.status_code = 200
        mock_response2.json.return_value = {}  # Missing price field
        
        mock_get.side_effect = [mock_response1, mock_response2]
        
        # First call sets last known price
        result1 = get_hyperliquid_price("BTC", use_fallback=True)
        assert result1 == 50000.0
        
        # Second call uses fallback
        result2 = get_hyperliquid_price("BTC", use_fallback=True)
        assert result2 == 50000.0  # Uses cached price


class TestRateLimiting:
    """TC04: Rate Limiting (429)"""
    
    @patch("src.price_client.requests.get")
    def test_rate_limit_with_retry_after(self, mock_get):
        """TC04: Rate limit should raise immediately with retry info"""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}
        mock_get.return_value = mock_response
        
        with pytest.raises(RateLimitError) as exc_info:
            get_hyperliquid_price("BTC")
        
        assert exc_info.value.retry_after == 30
        assert "Rate limited" in str(exc_info.value)
        assert mock_get.call_count == 1  # No retry on rate limit
    
    @patch("src.price_client.requests.get")
    def test_rate_limit_without_retry_after(self, mock_get):
        """Rate limit without Retry-After header"""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_get.return_value = mock_response
        
        with pytest.raises(RateLimitError) as exc_info:
            get_hyperliquid_price("BTC")
        
        assert exc_info.value.retry_after is None


class TestNetworkTimeout:
    """TC05: Network Timeout"""
    
    @patch("src.price_client.requests.get")
    @patch("src.price_client.time.sleep")
    def test_timeout_retry_exhausted(self, mock_sleep, mock_get):
        """TC05: Timeout should retry then fail"""
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")
        
        with pytest.raises(RetryExhaustedError, match="Failed to get price"):
            get_hyperliquid_price("BTC")
        
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2
    
    @patch("src.price_client.requests.get")
    @patch("src.price_client.time.sleep")
    def test_timeout_recovery_on_second_attempt(self, mock_sleep, mock_get):
        """Timeout on first attempt, success on second"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"price": 45000.0}
        
        mock_get.side_effect = [
            requests.exceptions.Timeout("First attempt timeout"),
            mock_response
        ]
        
        result = get_hyperliquid_price("BTC")
        assert result == 45000.0
        assert mock_get.call_count == 2


class TestInvalidJSON:
    """TC06: Invalid JSON Response"""
    
    @patch("src.price_client.requests.get")
    def test_invalid_json_response(self, mock_get):
        """TC06: Malformed JSON should raise immediately"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response
        
        with pytest.raises(InvalidPriceDataError, match="Invalid JSON response"):
            get_hyperliquid_price("BTC")


class TestRetryExhaustion:
    """TC07: Retry Exhaustion"""
    
    @patch("src.price_client.requests.get")
    @patch("src.price_client.time.sleep")
    def test_all_retries_exhausted_server_error(self, mock_sleep, mock_get):
        """TC07: All retries exhausted on persistent server errors"""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_get.return_value = mock_response
        
        with pytest.raises(RetryExhaustedError, match="after 3 attempts"):
            get_hyperliquid_price("BTC")
        
        assert mock_get.call_count == 3
    
    @patch("src.price_client.requests.get")
    @patch("src.price_client.time.sleep")
    def test_retry_exhaustion_mixed_errors(self, mock_sleep, mock_get):
        """Retry exhaustion with different error types"""
        mock_get.side_effect = [
            requests.exceptions.Timeout("Timeout 1"),
            requests.exceptions.ConnectionError("Connection lost"),
            Mock(status_code=500)  # Server error
        ]
        
        with pytest.raises(RetryExhaustedError):
            get_hyperliquid_price("BTC")


class TestEdgeCases:
    """Additional edge cases"""
    
    @patch("src.price_client.requests.get")
    def test_large_price_value(self, mock_get):
        """Handle very large price values"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"price": 1e6}  # 1 million
        mock_get.return_value = mock_response
        
        result = get_hyperliquid_price("BTC")
        assert result == 1000000.0
    
    @patch("src.price_client.requests.get")
    def test_multiple_symbols_caching(self, mock_get):
        """Test caching works independently for different symbols"""
        # Mock BTC price
        mock_response_btc = Mock()
        mock_response_btc.status_code = 200
        mock_response_btc.json.return_value = {"price": 50000.0}
        
        # Mock ETH price
        mock_response_eth = Mock()
        mock_response_eth.status_code = 200
        mock_response_eth.json.return_value = {"price": 3000.0}
        
        mock_get.side_effect = [mock_response_btc, mock_response_eth]
        
        # Get BTC price
        btc_price = get_hyperliquid_price("BTC", use_fallback=True)
        assert btc_price == 50000.0
        
        # Get ETH price
        eth_price = get_hyperliquid_price("ETH", use_fallback=True)
        assert eth_price == 3000.0
        
        # Each symbol should have independent cache
        assert mock_get.call_count == 2