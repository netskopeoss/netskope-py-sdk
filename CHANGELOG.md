# Changelog

All notable changes to the Netskope Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.4] - 2026-05-08

### Fixed

- Fix `url_lists.create()` and `url_lists.update()` returning HTTP 400 from the Netskope API. The endpoint requires `name` at the top level and `urls`/`type` wrapped under a `data` key — the SDK was sending a flat body that the API rejected with `property urls should not exist, ... data should not be null or undefined`.
- `url_lists.update()` now GETs the existing list and merges the provided fields over the current values before sending the PUT, so callers only need to specify what they want to change. The Netskope API requires `name`, `data.urls`, and `data.type` on every PUT, so previously calling `update(list_id, urls=[...])` would fail with `name required`.
- `url_lists.create()` now correctly handles the API's list-shaped POST response (`[{...}]`) instead of crashing on `body.get(...)`.
- `url_lists.update()` raises `ValueError` when called with no fields to change (previously sent an empty body).
- Verified against `nskp-io.goskope.com`: list, create (`type=regex`), update with urls only (preserves `name` and `type`), update with name only (preserves `urls` and `type`), update with all fields, delete.
- Parallel to [netskopeoss/netskope-cli#10](https://github.com/netskopeoss/netskope-cli/pull/10) and [netSkope/mcp-server-pilot#19](https://github.com/netSkope/mcp-server-pilot/pull/19), which fix the same class of bug on the CLI's PUT and the MCP server's PATCH respectively.
- Fix `raise_for_status()` rendering the API's list-shaped `message` field as a stringified Python list. The Netskope API returns multi-error validation responses as `"message": ["...", "..."]`; these are now joined with `; ` so the resulting `APIError` message is human-readable.
- Resolve a `mypy --strict` error in `exceptions.py` by typing the parsed error payload explicitly.

## [1.0.3] - 2026-03-10

### Fixed

- Add prominent documentation link to README
- Update docs site version references from v1.0.0 to v1.0.3
- Apply ruff formatting fixes across examples, source, and tests

## [1.0.2] - 2026-03-10

### Fixed

- Fix README badges not rendering — use normalized package name (underscores) for shields.io
- Add documentation badge linking to https://netskopeoss.github.io/netskope-py-sdk/

## [1.0.1] - 2026-03-10

### Fixed

- Fix pagination offset calculation that skipped items when iterating large result sets
- Fix falsy timestamp handling — epoch `0` is now correctly treated as a valid value
- Fix SCIM pagination parameters (`startIndex`/`count`) not being passed correctly
- Fix retry logic for streamed responses — request body is now rebuilt before each retry
- Fix tenant domain validation to properly reject IP addresses (SSRF prevention)
- Fix `_build_params()` helpers to omit `None` values instead of sending them as query params
- Fix response envelope extraction for endpoints with non-standard `data_key` paths

## [1.0.0] - 2026-03-10

### Added

- **NetskopeClient** and **AsyncNetskopeClient** — sync and async entry points
- **Hierarchical resource namespaces**: `client.alerts`, `client.events`, `client.url_lists`, `client.publishers`, `client.private_apps`, `client.scim`, `client.incidents`, `client.steering`
- **Automatic pagination** with lazy iterators, `.pages()`, `.to_list()`, and `.first()`
- **Pydantic v2 response models** for all resources: Alert, Event, Publisher, UrlList, PrivateApp, ScimUser, ScimGroup, Incident, and more
- **Rich exception hierarchy**: NetskopeError, APIError, AuthenticationError, ForbiddenError, NotFoundError, ConflictError, RateLimitError, ServerError, ValidationError, ConnectionError, TimeoutError
- **Automatic retries** with exponential backoff, jitter, and Retry-After header support
- **Credential resolution chain**: explicit params → environment variables
- **Context manager support** for both sync and async clients
- **Full type annotations** with `py.typed` marker (PEP 561)
- **Comprehensive test suite**: 80+ unit tests, 19 integration tests
- **Examples directory**: quickstart, async usage, event monitoring, URL list management, multi-tenant
- **Documentation site**: GitHub Pages with Tailwind CSS
