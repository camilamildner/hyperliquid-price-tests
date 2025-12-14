# HyperLiquid Price Client – Test Suite

This repository contains a Python test suite designed to validate the behavior of the function:

get_hyperliquid_price(symbol: str) -> float

The focus of this test suite is to ensure safe and predictable behavior when retrieving price data that directly affects trading and rebalance operations.

Because price data impacts user funds, the system must behave conservatively under failures and block trading whenever a reliable price cannot be guaranteed.

---

## Project Scope

This project focuses on:

- Unit-level tests using pytest
- Deterministic behavior using mocked API responses
- Error handling under realistic failure scenarios
- Retry and timeout handling
- Severity classification based on financial risk
- CI-ready tests designed to act as quality gates

Out of scope:

- Real API calls
- Manual testing
- Integration tests
- End-to-end UI tests

---

## Implemented Scenarios

The test suite covers the following scenarios:

- Successful price retrieval (200 OK)
- API down with retry (500 errors)
- Retry exhaustion after repeated failures
- Invalid price data (negative, null, missing)
- Rate limiting (429)
- Network timeouts
- Invalid JSON responses

Each scenario defines explicit behavior and severity based on its impact on trading safety.

---

## How to Run the Tests

1. Create and activate a virtual environment

2. Install dependencies:

pip install -r requirements.txt

3. Run the test suite:

pytest -v

All tests are isolated, fast, and do not rely on external services.

---

## Severity Rationale

Severity is defined based on financial risk:

- Critical – must immediately block trading or rebalance
- High – should alert and fail safe
- Low – log and continue

Any scenario where the price cannot be trusted is treated as Critical.

---

## CI Readiness

The tests are designed to be:

- Deterministic
- Isolated using mocks
- Fast enough to run on every pull request

They are suitable for use as merge-blocking quality gates in CI pipelines such as GitHub Actions.

---

## AI Usage Disclosure

AI was used as an assistant for:

- Boilerplate generation
- Formatting and documentation structure

All testing logic, severity decisions, failure handling strategies, and design reasoning were defined and validated by me.

---

## Notes

Postman can be useful for exploratory API testing, but for this assignment the focus is on automated, deterministic tests using pytest and mocks, ensuring CI readiness and safe trading behavior.

The detailed Test Plan is available in the file: 
test-plan-hyperliquid-price-client.pdf