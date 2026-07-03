# Changelog

All notable changes to the Netskope Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-07-03

Major expansion of API coverage — from 8 to 24 resource namespaces. Every new
namespace is available on both `NetskopeClient` and `AsyncNetskopeClient`. The
SDK was validated against live tenants, and endpoint shapes were verified
against the Netskope API gateway OpenAPI specs, which corrected several
assumptions previously derived from the Netskope CLI.

### Added

- **DEM / ADEM** (`client.dem`) — Digital Experience Monitoring: synthetic and
  network probes, alert rules, alerts, the query API, apps, and per-user ADEM
  experience data (`users.info`, `users.applications`, `users.diagnose`, and more).
- **RBAC** (`client.rbac`) — roles (`roles`) and admin users (`admins`).
- **User Management** (`client.users`) — read-only User Management query API with
  per-account group membership (`list`, `get`, `groups.list`, `groups.members`),
  complementing the SCIM provisioning API.
- **API tokens** (`client.tokens`) — REST API v2 token CRUD, including `reissue`
  to rotate a token secret.
- **Notifications** (`client.notifications`) — user notification templates
  (`block` and `useralert`) and delivery settings.
- **IPS** (`client.ips`) — Intrusion Prevention status, allowlists, signatures,
  signature overrides, alert-only mode, and threat-hunting config.
- **ATP** (`client.atp`) — Advanced Threat Protection file and URL scanning with
  report retrieval.
- **NSIQ** (`client.nsiq`) — URL categorization/recategorization, IOC lookups,
  and false-positive reporting.
- **RBI** (`client.rbi`) — Remote Browser Isolation templates, CDR, and cloud
  storage configuration.
- **DSPM** (`client.dspm`) — Data Security Posture Management resource inventory,
  analytics, and datastore connect/scan.
- **SPM** (`client.spm`) — SaaS Security Posture Management app inventory, posture
  score, and policy rules.
- **DNS profiles** (`client.dns`) — DNS Security profiles and domain inheritance
  groups (`inheritance_groups`), plus tunnels, domain categories, and record types.
- **CCI** (`client.cci`) — Cloud Confidence Index app lookup, custom tags
  (`tags`), and rules.
- **Devices** (`client.devices`) — managed device listing, supported OS, and
  device tags (`tags`).
- **Enrollment** (`client.enrollment`) — client enrollment token-set management.
- **NPA policy & infrastructure** (`client.npa`) — access policy rules
  (`policy.rules`) and groups (`policy.groups`), publisher upgrade profiles
  (`upgrade_profiles`), local brokers (`local_brokers`), `validate_name`, and `search`.
- **Incident notes** — `incidents.list_notes()`, `add_note()`, and `delete_note()`.
- **Publisher extensions** — registration tokens, per-publisher app listing,
  bulk upgrade, releases, and alert configuration.
- **Private-app extensions** — private-app tags (`private_apps.tags`) and
  publisher-association management (`add_publishers`, `replace_publishers`,
  `remove_publishers`).
- **Steering extensions** — IPSec tunnel CRUD (`create_tunnel`, `update_tunnel`,
  `delete_tunnel`, `get_tunnel`, `list_tunnels`).
- **CA-bundle / TLS verification support** — new `verify` client option
  (`True` | `False` | path to a CA bundle) and `NETSKOPE_CA_BUNDLE` env var.
  The new `find_netskope_ca_cert()` helper resolves a CA bundle from
  `NETSKOPE_CA_BUNDLE`, `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, or
  `CURL_CA_BUNDLE`, in that order.

### Fixed

- `incidents.update()` now sends the `{"payload": [...]}` wrapper the API
  requires (previously a flat body that the API rejected).
- `incidents.get_uci()` now sends the correct `{"user", "fromTime"}` body.
- `incidents.get_anomalies()` now sends `severity_filter` as the API expects.
- `publishers.create()` and `publishers.update()` now send `name` (previously
  `publisher_name`, which the API rejected).
- Steering publishers-scope path corrected to
  `/steering/globalconfig/publishers`.
- `private_apps.update()` now uses PATCH instead of PUT.
- `raise_for_status()` now raises on HTTP-200 responses carrying a
  `{"status": "error"}` body (previously treated as success).
- `events.list()` now routes `audit`, `infrastructure`, and `transaction` to
  their correct endpoints, and events gained a `get()` method for single-event
  lookup by ID.
- `Event.severity` now accepts an integer (audit events report severity as an int).

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
