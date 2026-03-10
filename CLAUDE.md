# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Run all tests
pytest tests/

# Run unit tests only
pytest tests/unit/

# Run a single test
pytest tests/unit/test_config.py::TestNetskopeConfig::test_explicit_params

# Run with coverage
pytest --cov=netskope --cov-report=html

# Skip integration tests (require live API credentials)
pytest -m "not integration"

# Lint and format
ruff check . --fix
ruff format .

# Type check
mypy
```

## Architecture

This is a Python SDK for the Netskope REST API v2 with sync and async support. Python 3.11+, built on httpx + Pydantic v2.

**Request flow:** `NetskopeClient` → resource (e.g. `AlertsResource`) → `SyncTransport.request()` → `send_with_retries()` → httpx → `raise_for_status()` → response/pagination

**Key layers:**

- **`_client.py`** — `NetskopeClient` / `AsyncNetskopeClient` entry points. Instantiates transport and exposes resource namespaces as properties (e.g. `client.alerts`, `client.scim.users`).
- **`_config.py`** — `NetskopeConfig.resolve()` implements a boto3-style credential chain: explicit params → env vars (`NETSKOPE_TENANT`, `NETSKOPE_API_TOKEN`). Validates tenant domain, blocks IP addresses (SSRF prevention), stores token as `SecretStr`.
- **`_transport.py`** — `SyncTransport` / `AsyncTransport` wrap httpx with token injection, logging, and retry delegation. All HTTP flows through here.
- **`_retry.py`** — Exponential backoff with jitter, respects `Retry-After` headers. Rebuilds request before each retry to avoid consumed stream issues.
- **`_pagination.py`** — `SyncPaginatedResponse` / `AsyncPaginatedResponse` for offset-based pagination; `SyncScimPaginatedResponse` / `AsyncScimPaginatedResponse` for RFC 7644 SCIM pagination (`startIndex`/`count`). All return lazy iterators yielding typed Pydantic models.
- **`resources/`** — Each API namespace (alerts, events, incidents, scim, publishers, private_apps, steering, url_lists) has sync + async resource classes inheriting from `_base.py`. Resources use `_build_params()` helpers and `_extract()` functions to handle response envelope variations.
- **`models/`** — Pydantic v2 models. `NetskopeModel` base uses `extra="allow"` (forward-compatible), `frozen=True` (immutable). `TimestampMixin` auto-converts epoch ints to UTC datetime. Field aliases map API names to Pythonic names (e.g. `_id` → `id`, `severity_level` → `severity`).
- **`exceptions.py`** — Hierarchy: `NetskopeError` → `APIError` (with `status_code`, `request_id`) → specific errors (401→`AuthenticationError`, 429→`RateLimitError`, etc.).

**Sync/Async pattern:** Every resource, transport, and paginator has both sync and async variants. They share models but have separate class implementations (no shared async base).

## Conventions

- Tenant domains must end in `.goskope.com`, `.netskope.com`, or `.boomskope.com` (bypass with `allow_custom_tenant=True`)
- Resource IDs are validated against `^[a-zA-Z0-9_\-]+$` before use in URL paths
- Response envelopes vary by endpoint — resources use custom `extract` callables or `data_key` to locate items in response JSON (common keys: `data`, `result`, `Resources`, `urllists`)
- Time parameters use `is not None` checks (epoch `0` is a valid value)
- Pagination max safety limit: 1000 pages
- ruff line-length: 100, target: py311
- mypy strict mode with pydantic v2 plugin
- Tests use `respx` for HTTP mocking, `pytest-asyncio` (auto mode) for async tests
