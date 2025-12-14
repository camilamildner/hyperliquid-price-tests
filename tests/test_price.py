import pytest
import requests
from unittest.mock import patch
from src.price_client import (
    get_hyperliquid_price,
    HyperLiquidAPIError,
    RateLimitError,
)


@patch("src.price_client.requests.get")
def test_price_normal_case(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"price": 123.45}

    result = get_hyperliquid_price("BTC")

    assert result == 123.45


@patch("src.price_client.requests.get")
def test_price_api_down(mock_get):
    mock_get.return_value.status_code = 500

    with pytest.raises(HyperLiquidAPIError):
        get_hyperliquid_price("BTC")


@patch("src.price_client.requests.get")
@pytest.mark.parametrize(
    "bad_payload",
    [
        {"price": -100},
        {"price": None},
        {},
    ],
)
def test_price_bad_data(mock_get, bad_payload):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = bad_payload

    with pytest.raises(HyperLiquidAPIError):
        get_hyperliquid_price("BTC")


@patch("src.price_client.requests.get")
def test_price_rate_limit(mock_get):
    mock_get.return_value.status_code = 429

    with pytest.raises(RateLimitError):
        get_hyperliquid_price("BTC")


@patch("src.price_client.requests.get")
def test_price_timeout_retry_exhausted(mock_get):
    mock_get.side_effect = requests.exceptions.Timeout

    with pytest.raises(HyperLiquidAPIError):
        get_hyperliquid_price("BTC")

    assert mock_get.call_count == 3


@patch("src.price_client.requests.get")
def test_price_invalid_json(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.side_effect = ValueError("Invalid JSON")

    with pytest.raises(HyperLiquidAPIError):
        get_hyperliquid_price("BTC")


@patch("src.price_client.requests.get")
def test_price_retry_exhausted_on_server_error(mock_get):
    mock_get.return_value.status_code = 500

    with pytest.raises(HyperLiquidAPIError):
        get_hyperliquid_price("BTC")

    assert mock_get.call_count == 3