# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Run all tests
uv run pytest tests/

# Run unit tests only
uv run pytest tests/unit/

# Run a single test
uv run pytest tests/unit/test_config.py::TestNetskopeConfig::test_explicit_params

# Run with coverage
uv run pytest --cov=netskope --cov-report=html

# Skip integration tests (require live API credentials)
uv run pytest -m "not integration"

# Lint and format
uv run ruff check . --fix
uv run ruff format .

# Type check
uv run mypy
```

Dev tools live in `[dependency-groups] dev`, which uv installs by default, so
`uv run <cmd>` needs no extra flags. With pip: `pip install -e . --group dev`.

## Releasing

The version is a literal in both `pyproject.toml` and `src/netskope/_version.py`;
`tests/unit/test_version.py` fails if the two drift. `_version.__version__` also
builds the `User-Agent` the SDK sends, so a stale literal misreports the SDK to
the API.

Before tagging:

- Drop the `.dev0` suffix in both files.
- Remove the "unpublished" and "development version" wording:
  `grep -rn 'unpublished\|\.dev0' README.md CHANGELOG.md docs/`.
- Update `docs/index.html`: the nav badge, the footer, and the version strings
  in the "Verify Installation" and "Client Properties" samples.
- Update the CLI's `netskope-py-sdk==` pin to the released version and re-run
  `uv lock` there. A `.dev0` pin does not match the final release.

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
- **`exceptions.py`** — Hierarchy: `NetskopeError` → `APIError` (with `status_code`, `request_id`) → specific errors (401→`AuthenticationError`, 429→`RateLimitError`, etc.). Non-HTTP failures are `NetskopeError` siblings of `APIError`: `ValidationError`, `ResponseValidationError`, `PaginationError`, and `ClientClosedError` (a request made after the client is closed).

**Sync/Async pattern:** Every resource, transport, and paginator has both sync and async variants. They share models but have separate class implementations (no shared async base).

### Typed CLI contracts

The development release is `1.2.0.dev0`, currently unpublished. The CLI
repository's `docs/typed-sdk-development.md` describes the local artifact
workflow that builds both packages from clean wheels.

- `pagination.Page[T]` retains validated totals, offsets, limits, and continuation evidence.
  Build one through `_pagination.build_page()` (or `_make_page`/`parse_object_page`, which
  wrap it) rather than constructing `Page` directly: it applies the requested-limit ceiling,
  the reported-offset check, and the total check in one place. Pass `echoed_offset` whenever
  the envelope reports the offset it served.
- `response.ApiResponse[T]` wraps one buffered response. Its cached `parse()` is typed;
  `json()` and `content` preserve original values without another request. Typed response
  errors contain request/field context but not response values.
- Add operation-specific request and response models. Keep legacy raw-returning resource
  methods compatible; corrected typed contracts are additive accessors or named methods.
- New AICC endpoint handles expose typed queries, pages, and bounded traversal. They own
  total retention, duplicate/offset checks, and pagination limits for the CLI.
- GET/HEAD/OPTIONS can retry by default. Explicitly safe read POSTs may opt in;
  mutations do not automatically replay. Preserve omitted versus null/empty request fields.

## Conventions

- Tenant domains must end in `.goskope.com`, `.netskope.com`, or `.boomskope.com` (bypass with `allow_custom_tenant=True`, accepted by `NetskopeConfig.resolve()` and by both client constructors; IP addresses are rejected either way)
- Resource IDs are validated against `^[a-zA-Z0-9_\-]+$` before use in URL paths (`_extract.validate_id`); a batch of IDs for a bulk write goes through `_extract.id_strings`, which also rejects an empty batch
- Response envelopes vary by endpoint — resources use custom `extract` callables or `data_key` to locate items in response JSON (common keys: `data`, `result`, `Resources`, `urllists`)
- Time parameters use `is not None` checks (epoch `0` is a valid value)
- Pagination max safety limit: 1000 pages
- `retry_on_status=frozenset()` disables status-based retries; `None` selects the
  defaults (`_config.py` distinguishes the two with `is not None`)
- ruff line-length: 100, target: py311
- mypy strict mode with pydantic v2 plugin
- Tests use `respx` for HTTP mocking, `pytest-asyncio` (auto mode) for async tests
