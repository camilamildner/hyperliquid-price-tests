# HyperLiquid Price Client – Test Suite

This repository contains a Python test suite designed to validate the behavior of the function:

get_hyperliquid_price(symbol: str, use_fallback: bool = False) -> float

The focus of this test suite is to ensure safe and predictable behavior when retrieving price data that directly affects trading and rebalance operations.

Because price data impacts user funds, the system must behave conservatively under failures and block trading whenever a reliable price cannot be guaranteed.

---

## Project Scope

This project focuses on:

- Unit-level tests using pytest
- Deterministic behavior using mocked API responses
- Error handling under realistic failure scenarios
- Retry and timeout handling with exponential backoff
- Severity classification based on financial risk
- Configurable fallback strategies for graceful degradation
- Production-ready logging and monitoring
- CI-ready tests designed to act as quality gates

Out of scope:

- Real API calls
- Manual testing
- Integration tests
- End-to-end UI tests

---

## Implemented Scenarios

The test suite covers the following scenarios:

- Successful price retrieval (200 OK) – Returns valid float price
- API down with retry (500 errors) – Retries 3 times with backoff, then blocks
- Retry exhaustion after repeated failures – Raises specific exception
- Invalid price data (negative, null, missing) – Immediate block or fallback
- Rate limiting (429) – Fails fast with Retry-After information
- Network timeouts – Retries with increasing delays
- Invalid JSON responses – Immediate block, cannot parse
- Client errors (400-499) – Immediate block, no retry
- Mixed failure scenarios – Real-world complex error sequences

Each scenario defines explicit behavior and severity based on its impact on trading safety.

---

## How to Run the Tests

1. Create and activate a virtual environment

# Create virtual environment
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on macOS/Linux
source venv/bin/activate

2. Install dependencies:

pip install -r requirements.txt

3. Run the test suite:

# Basic test run
pytest

# Verbose output
pytest -v

# Specific test class
pytest tests/test_price.py::TestNormalCase -v

# With coverage report
pytest --cov=src --cov-report=html

All tests are isolated, fast, and do not rely on external services.

---

## Severity Rationale

Severity is defined based on financial risk:

- Critical – must immediately block trading or rebalance
Negative or zero prices
Invalid JSON responses
Persistent failures after retries
Client configuration errors (4xx)
- High – should alert and fail safe
Server errors (5xx) after retries
Rate limiting at capacity
Network timeouts after retries
Missing price without fallback
- Low – log and continue
Missing price with fallback enabled
Temporary network glitches
Non-critical API warnings

Any scenario where the price cannot be trusted is treated as Critical.

---

## CI Readiness

The tests are designed to be:

- Deterministic – Same results every run
- Isolated – Using mocks, no external dependencies
- Fast – Runs in under 2 seconds
- Reliable – No flaky tests

They are suitable for use as merge-blocking quality gates in CI pipelines such as GitHub Actions.
Critical test failures blocking PR merge
Coverage requirements enforced
Performance benchmarks tracked

---

## AI Usage Disclosure

AI was used as an assistant for:

- Boilerplate generation
- Formatting and documentation structure
- Error message standardization

All testing logic, severity decisions, failure handling strategies, and design reasoning were defined and validated by me. The business logic, safety considerations, and production-readiness decisions are entirely human-designed.

---

## Notes

Postman can be useful for exploratory API testing, but for this assignment the focus is on automated, deterministic tests using pytest and mocks, ensuring CI readiness and safe trading behavior.

The detailed Test Plan is available in the file: 
test-plan-hyperliquid-price-client.pdf