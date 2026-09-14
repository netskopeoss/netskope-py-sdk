# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
uv sync                                 # Create .venv and install runtime + dev dependencies
uv sync --locked                        # What CI runs; fails if uv.lock is stale

# Testing
uv run pytest                           # All tests
uv run pytest tests/unit/               # Unit tests only
uv run pytest tests/unit/test_config.py::TestNetskopeConfig::test_explicit_params  # One test
uv run pytest -m "not integration"      # Skip tests that need live API credentials
uv run pytest --cov=netskope --cov-report=html  # With coverage

# Lint, format, type-check (run before commits/PRs)
uv run ruff check .                     # Lint
uv run ruff check . --fix               # Auto-fix lint issues
uv run ruff format .                    # Format (ruff format --check . to verify only)
uv run ty check                         # Type check src/ (scope in [tool.ty.src])

# Packaging
uv build && ./scripts/smoke-dist.sh     # Build both artifacts, install each into a clean venv and import it

# CI (.github/workflows/ci.yml) runs the same four checks on Python 3.11 and 3.14 for every
# pull request and push to main, then builds the wheel and sdist and smoke-tests both from a
# clean install (scripts/smoke-dist.sh, which release.yml runs on the artifacts it publishes).
```

Dev tools live in `[dependency-groups] dev`, which uv installs by default, so
`uv run <cmd>` needs no extra flags. `uv.lock` is committed: a dependency change
edits `pyproject.toml` and then runs `uv lock`, and both files land in the same
commit. With pip: `pip install -e . --group dev`.

## Releasing to PyPI

The full runbook is `.claude/commands/release.md`. The short version:

```bash
# 1. Bump the version in BOTH literals (tests/unit/test_version.py fails if they drift),
#    then refresh the lockfile
#    - pyproject.toml           →  version = "X.Y.Z"
#    - src/netskope/_version.py →  __version__ = "X.Y.Z"
uv lock                     # uv.lock records the project version; uv sync --locked fails until this runs

# 2. docs/index.html carries the version in four places (nav badge, the
#    print(netskope.__version__) sample, the client.version sample, the footer).
#    grep -n '<old-version>' docs/index.html afterwards to confirm none survived.

# 3. Rotate CHANGELOG.md: [Unreleased] becomes [X.Y.Z] - YYYY-MM-DD, a fresh empty
#    [Unreleased] goes above it, and the compare links at the bottom are updated.

# 4. Check, commit, tag, push
uv run ruff check . --fix && uv run ruff format . && uv run ty check && uv run pytest
git add pyproject.toml uv.lock src/netskope/_version.py CHANGELOG.md docs/index.html
git commit -m "Release vX.Y.Z - <short summary>"
git push origin main
git tag -a vX.Y.Z -m "vX.Y.Z - <short summary>" && git push origin vX.Y.Z
```

`_version.__version__` builds the `User-Agent` the SDK sends, so a stale literal
misreports the SDK to the API on every request.

Pushing the tag runs `.github/workflows/release.yml`, which refuses a tag that is
not on `main` or does not match the project version, runs the same checks as CI,
builds, smoke-tests both artifacts, publishes through PyPI's Trusted Publisher
for this repository (no token is stored anywhere), and only then creates the
GitHub Release from that version's CHANGELOG section. Watch it with
`gh run watch`. The local `UV_PUBLISH_TOKEN` path is a fallback for when Actions
cannot run, and the token comes from the macOS keychain for that one command:
never echo it or commit it.

Until `1.2.0` ships, the README and CHANGELOG describe `1.2.0.dev0` as
unpublished. The release that publishes it removes that wording:
`grep -rn 'unpublished\|\.dev0' README.md CHANGELOG.md docs/`.

## Architecture

This is a Python SDK for the Netskope REST API v2 with sync and async support. Python 3.11+, built on httpx + Pydantic v2.

**Request flow:** `NetskopeClient` → resource (e.g. `AlertsResource`) → `SyncTransport.request()` → `send_with_retries()` → httpx → `raise_for_status()` → response/pagination

**Layout.** Three layers: `core/` is the plumbing no API area owns, `resources/<area>/` is one package per API namespace, `models/` is one module per area. **No module re-exports anything for convenience.** Import the module that owns the symbol: `netskope.resources.dspm.resource`, `netskope.resources.aicc.namespace`, `netskope.resources.shared.aicc_endpoint`, `netskope.core.pagination` for `Page`. `netskope`, `netskope.exceptions`, `netskope.response`, `netskope.datasearch` and `netskope.models.*` are the exception — they are the declared public API and export deliberately. `tests/unit/test_cli_public_surface.py` pins the 86 symbols netskope-cli imports as a deliberate coupling check between two repos that ship together — when a path moves, move the CLI and regenerate that table rather than adding a re-export to satisfy it.

```
netskope/
├── __init__.py  exceptions.py  pagination.py  response.py  datasearch.py   public surface
├── core/        client  config  transport  retry  pagination  resource  ids  decoding  response_list
├── resources/
│   ├── shared/  npa  admin  datasearch_query  aicc_contract  aicc_endpoint
│   └── <area>/  resource.py  decoder.py  paths.py        (dem/ and aicc/ add sub-namespace modules)
└── models/      <area>.py
```

**Each area package holds three files.** `resource.py` is the public namespace class; `decoder.py` holds the `with_response` accessors that keep the original HTTP response; `paths.py` holds the path constants and payload builders **both** of the others need. That third module is not optional bookkeeping — it is what keeps the package acyclic. `resource.py` imports `decoder.py` for its `with_response` accessor, so if `decoder.py` imported `resource.py` back for a path constant, the two would form a cycle. Before this split there were 14 such cycles, papered over by 53 imports hidden inside method bodies plus 14 matching `TYPE_CHECKING` blocks. `tests/unit/test_import_graph.py` fails on any cycle and on any resource import deferred into a function; **put shared paths and builders in `paths.py` rather than reaching across.**

**Key layers:**

- **`core/client.py`** — `NetskopeClient` / `AsyncNetskopeClient` entry points. Instantiates transport and exposes resource namespaces as properties (e.g. `client.alerts`, `client.scim.users`).
- **`core/config.py`** — `NetskopeConfig.resolve()` implements a boto3-style credential chain: explicit params → env vars (`NETSKOPE_TENANT`, `NETSKOPE_API_TOKEN`). Validates tenant domain, blocks IP addresses (SSRF prevention), stores token as `SecretStr`.
- **`core/transport.py`** — `SyncTransport` / `AsyncTransport` wrap httpx with token injection, logging, and retry delegation. All HTTP flows through here.
- **`core/retry.py`** — Exponential backoff with jitter, respects `Retry-After` headers. Rebuilds request before each retry to avoid consumed stream issues. A request not marked `retry_safe` gets a retry limit of **0**, which also suppresses retry on timeout and network error — so `retry_safe=True` on a read-shaped POST is load-bearing, not decoration.
- **`core/pagination.py`** — `SyncPaginatedResponse` / `AsyncPaginatedResponse` for offset-based pagination; `SyncScimPaginatedResponse` / `AsyncScimPaginatedResponse` for RFC 7644 SCIM pagination (`startIndex`/`count`). All return lazy iterators yielding typed Pydantic models. `Page` is imported from here directly; there is no `netskope.pagination` façade.
- **`core/resource.py`, `core/ids.py`, `core/decoding.py`, `core/response_list.py`** — the resource base classes, id validation and URL-segment quoting, and the shared envelope decoders.
- **`resources/<area>/`** — Each API namespace (alerts, events, incidents, scim, publishers, private_apps, steering, url_lists, …) has sync + async resource classes inheriting from `core/resource.py`.
- **`models/`** — Pydantic v2 models. `NetskopeModel` base uses `extra="allow"` (forward-compatible), `frozen=True` (immutable). `TimestampMixin` reads both epoch numbers and datetime strings into a UTC-aware datetime; a value it cannot read becomes `None` rather than rejecting the record (and with it the page). Field aliases map API names to Pythonic names (e.g. `_id` → `id`, `severity_level` → `severity`).
- **`exceptions.py`** — Hierarchy: `NetskopeError` → `APIError` (with `status_code`, `request_id`) → specific errors (401→`AuthenticationError`, 429→`RateLimitError`, etc.). Non-HTTP failures are `NetskopeError` siblings of `APIError`: `ValidationError`, `ResponseValidationError`, `PaginationError`, and `ClientClosedError` (a request made after the client is closed).

**Sync/Async pattern:** Every resource, transport, and paginator has both sync and async variants. They share models but have separate class implementations (no shared async base).

### Typed CLI contracts

The development release is `1.2.0.dev0`, currently unpublished. The CLI
repository's `docs/typed-sdk-development.md` describes the local artifact
workflow that builds both packages from clean wheels.

- `pagination.Page[T]` retains validated totals, offsets, limits, and continuation evidence.
  Build one through `core.pagination.build_page()` (or `_make_page`/`parse_object_page`, which
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
  use each operation's `rbac.access` to override that default. Enrollment token-set
  reads and private-app policy-usage POSTs are marked `rw` and must not retry.
  Preserve omitted versus null/empty request fields.
- Unpaginated publisher and URL-list collections use `paginated=False`; their
  page methods use `core.pagination.local_page()` and send no offset or limit.
- Notification template POST and PATCH share the same required name, title, and
  message fields. Validate both with `NotificationTemplateWrite`.

## Conventions

- Tenant domains must end in `.goskope.com`, `.netskope.com`, or `.boomskope.com` (bypass with `allow_custom_tenant=True`, accepted by `NetskopeConfig.resolve()` and by both client constructors; IP addresses are rejected either way)
- Resource IDs are validated against `^[a-zA-Z0-9_\-]+$` before use in URL paths (`_extract.validate_id`), which also rejects booleans and negative integers; SCIM identifiers instead go through `_extract.quote_id`, which percent-encodes any non-blank, non-dot-only segment (so `user@example.com` is a usable id); a batch of IDs for a bulk write goes through `_extract.id_strings`, which also rejects an empty batch
- Response envelopes vary by endpoint — resources use custom `extract` callables or `data_key` to locate items in response JSON (common keys: `data`, `result`, `Resources`, `urllists`)
- Time parameters use `is not None` checks (epoch `0` is a valid value)
- Pagination max safety limit: 1000 pages
- `retry_on_status=frozenset()` disables status-based retries; `None` selects the
  defaults (`core/config.py` distinguishes the two with `is not None`)
- ruff line-length: 100, target: py311
- Toolchain: uv for the environment, the lockfile and packaging; ruff for lint (rules E, W, F, I, N, UP, B, SIM, RUF) and formatting; ty for type checking `src/`. All of it is configured in `pyproject.toml`. Suppress a ty diagnostic with `# ty: ignore[rule]` and say why on the line above; bare `# type: ignore` also works. Inside a class that defines a `list` method, spell the builtin `builtins.list[...]` in annotations — the method shadows the name in class scope
- Tests use `respx` for HTTP mocking, `pytest-asyncio` (auto mode) for async tests
- Changelog: `CHANGELOG.md` follows Keep a Changelog 1.1.0 throughout. Every user-visible change lands in the same PR under `### Added` / `Changed` / `Deprecated` / `Removed` / `Fixed` / `Security` in the Unreleased section, one or two sentences per entry on one unwrapped line; the release runbook turns that section into the version entry and the GitHub Release notes. A release that removes a public method, renames a model field, or changes an existing response contract also opens with a `### Breaking` subsection listing each one, so the size of the version bump can be read off the changelog
- Wire shapes are checked against a pinned revision of the Netskope API gateway contract, whose definitions are not public. `tests/unit/resources/test_spec_*.py` holds those checks; each assertion's docstring cites the contract file and line it came from, and response fixtures use the contract's own example values. Cite the same way when adding one, and do not copy contract text into the repository
