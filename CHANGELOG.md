# Changelog

All notable changes to the Netskope Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

The next published release is `1.2.0`. The development version is `1.2.0.dev0`,
which has not been published.

The behaviors listed first change for code written against `1.1.0`, most of
them by raising where the SDK used to return a value. `1.1.0` was itself never
published: PyPI serves `1.0.3` as the latest version, and the repository carries
no `v1.1.0` tag or GitHub release. Anyone upgrading from the last published
version therefore gets the 1.1.0 entry below in the same step, including its
expansion from 8 to 24 resource namespaces.

### Behavior changes

- **Breaking:** the package is laid out in three layers: `netskope/core/` holds the
  plumbing no API area owns, `netskope/resources/<area>/` is one package per API
  namespace (`resource.py`, `decoder.py`, `paths.py`), and
  `netskope/resources/shared/` holds what several areas share. The package root is
  unchanged — `netskope`, `netskope.exceptions`, `netskope.response`,
  `netskope.datasearch` and `netskope.models.*` all resolve exactly as before.
  **Every other import path moved, and nothing re-exports to soften it.**
  `from netskope.resources.dspm import DspmResource` becomes
  `from netskope.resources.dspm.resource import DspmResource`; `AiccResource` and
  `DemResource` come from `netskope.resources.{aicc,dem}.namespace`; the AICC endpoint
  types from `netskope.resources.shared.aicc_endpoint`. `netskope.pagination` is
  **removed** — import `Page` from `netskope.core.pagination`. Private paths moved too:
  `netskope._pagination` is `netskope.core.pagination` and
  `netskope.resources._alert_query` is `netskope.resources.shared.datasearch_query`.
- The package now imports acyclically. Each area's path constants and payload
  builders live in `paths.py`, which both `resource.py` and `decoder.py` import,
  replacing 14 resource/decoder cycles that were held open by 53 imports hidden
  inside method bodies. `dem` and `aicc`, previously the two largest modules at
  2,120 and 984 lines, are packages of one module per sub-namespace.

- Publisher and URL-list collections are fetched once, with page windows applied locally; publisher server-side filters are rejected. Local pages derive continuation from the fetched records and report the collection total as received, even when it contradicts them: the service counted rows the client cannot. Such a page is never refused for that disagreement, and `Page.windowed_locally` marks it, so a caller comparing the envelope against the page can tell an ordinary local window from a shape mismatch.
- Publisher PATCH requires `name`, publisher alert-configuration PUT requires all three configuration fields, and notification template POST and PATCH require complete valid bodies. Invalid request bounds and enums now fail before HTTP across DEM, RBI, IPS, NSIQ, RBAC roles, and user management; CCI lookups require one selector.
- Enrollment token-set GETs and private-app or tag policy-usage POSTs no longer retry, following their declared write access.
- Typed DNS deploys return pages of deployed objects; publisher alert-configuration and steering updates return acknowledgments. Private-app publisher removal returns applications, and publisher action results retain publisher lists.
- A string `timestamp` on `Alert`, `Event`, `Incident`, and `Anomaly` (and their
  subclasses) decoded to `None` in 1.1.0, which read epoch numbers and nothing
  else. It now decodes to a timezone-aware `datetime`; a string carrying no UTC
  offset is read as UTC, which is what the API reports. A value that cannot be
  read at all is still `None`, so one unreadable row does not reject the page it
  arrived in. Booleans are among those unreadable values: 1.1.0 turned `True`
  into `1970-01-01T00:00:01Z` through `bool`'s integer behavior.
- The legacy `list()` iterators yielded every record a page returned in 1.1.0,
  including records past the total the envelope had already reported. They now
  stop at that page and log the stop at `WARNING` on the `netskope` logger; the
  records on that page are not yielded.
- `retry_on_status=frozenset()` fell back to the default `{429, 500, 502, 503,
  504}` in 1.1.0. An empty set now means what it says and disables status-based
  retries. Pass `max_retries=0` for the same effect on connection errors too.
- An HTTP 2xx response whose body reports failure now raises `APIError` instead
  of being returned as a `dict`. Three envelopes are recognized: `ok: 0` (which
  also matches `ok: false`), `success: false`, and datasearch's
  `execution: "FAILED"`, at the top level or nested under `status`. Callers that
  inspected the returned body for these flags will see the exception first.
- `url_lists.update()` with no fields to change raised a bare `ValueError` in
  1.1.0. It now raises `netskope.exceptions.ValidationError`, which is not a
  `ValueError` subclass, so `except ValueError` around it stops catching.
- `private_apps.create()` sent whatever it was given in 1.1.0, including a body
  with no `protocols` and a top-level `port` that the API gateway rejected. It
  now requires `protocols` and raises `ValidationError` before the request is
  built. The port rides inside each protocol entry
  (`{"type": "tcp", "port": "443"}`).
- `incidents.get_anomalies(severity=...)` sent the value as `severity_filter` in
  1.1.0. The endpoint has no server-side severity filter, so the argument is now
  rejected with `ValidationError`. Filter the returned `Anomaly` records instead.
- `scim.users.list()`, `scim.groups.list()`, and `rbac.admins.list()` passed any
  `page_size` straight through in 1.1.0, including values above the SCIM maximum.
  A `page_size` outside 1 through 1000 now raises `ValidationError`. `count=0`
  remains the RFC 7644 totals-only probe.
- A page longer than the requested limit returned its records in 1.1.0. It now
  raises `PaginationError`, as do a reported `offset` that does not identify the
  requested page and a total contradicted by the records already returned.
- A response that fails model validation raises
  `netskope.exceptions.ResponseValidationError` rather than letting
  `pydantic.ValidationError` escape the SDK's error hierarchy. Code catching
  `pydantic.ValidationError` around SDK calls no longer matches.
- `steering.create_tunnel()` and `update_tunnel()` send the API's `enable` key.
  1.1.0 sent `enabled`, which the endpoint ignored.

### Added

- `DemAlertEntity`, `DemAlertMetricValue`, `RbiWatermark`, `PublisherAlertsConfigurationStatus`, and `SteeringConfigStatus` are public model exports. DNS profile and inheritance-group deletes accept `interactive`, defaulting to `False`.
- Typed sync/async response access across event, incident, DEM/ADEM,
  administrative, NPA, steering, CCI, ATP/NSIQ, RBI, DSPM, and SPM operations.
  Operation-specific request models validate supported writes before HTTP;
  legacy raw-returning SDK methods remain available for compatibility.
- `client.aicc` inventory, entity detail, analytics, and data-protection
  resources with typed queries and responses. SDK-owned pagination retains
  totals and rejects ignored offsets, repeated rows, contradictory totals,
  and incomplete safety-limit stops. Explicit prefixes support bounded reports.
- Public model exports support offline JSON Schema discovery in the CLI.
  New canonical DSPM reads cover 16 resource names and single-datastore scan
  submissions expose a typed HTTP 202 acknowledgment.
- Strict `RoleCreate`/`RolePatch` requests with typed API-group grants and
  nested settings, plus single-write `create_receipt()`/`update_receipt()`
  methods. Sync/async response accessors preserve the receipt without a detail
  GET; legacy convenience methods retain their existing follow-up behavior.
- `DeviceTagCreate`/`DeviceTagPatch` validate tag names and descriptions,
  preserving omitted patch fields. Sync/async tag write response accessors
  retain the original response and verify the returned tag identity.
- Operation-specific RBAC summary/detail models and bounded role/admin reads;
  alert record/aggregate pages and fixed-window scan summaries; device-tag
  body-pagination iterators. New reads have sync/async response accessors.
- `PaginationError` reports request context for unsafe continuation without
  exposing record identities. Tag traversal retains totals across pages and
  rejects ignored offsets, duplicate records, and incomplete page-budget stops.
- Cookie authentication through `ci_session`, public sync/async `request()`
  methods, and injected HTTPX clients with explicit borrowed ownership.
- Public `Page[T]` and one-request `publishers.list_page()`, preserving
  envelope metadata, server totals, and unknown continuation state.
- Typed publisher write validation and publisher application/action models.
- Opt-in `ApiResponse[T]` accessors for publisher operations and related
  upgrade-profile/local-broker lists. Parsing and inspecting an original
  response never repeats the request. Response validation errors carry
  payload-free field locations and request context; API errors now also carry
  request method/path metadata.
- `ClientClosedError` for a request made after the client is closed, plus a
  `closed` property on `NetskopeClient` and `AsyncNetskopeClient`. It is
  exported from the package root, so `from netskope import ClientClosedError`
  works alongside `netskope.exceptions.ClientClosedError`.
- Both clients accept `allow_custom_tenant`, which previously only reached
  the configuration layer.
- `IncidentUpdateOutcome.count` reports the entry count an acknowledgment
  carried, or `None` when the service returned only a message.
- Typed event pages accept the audit endpoint's `audit_type` filter, which
  the legacy iterator already supported. Every other category rejects it. On
  audit it folds into the same `query` expression as a `type eq` clause, so a
  caller supplying both gets one combined filter rather than a conflict.

### Changed

- DEM queries accept the declared zero limits and equal or mixed time bounds, reject out-of-range inputs without clamping, and require positive entity-query epochs. Entity queries no longer inherit the dataset endpoint's two-day window cap.
- Audit and infrastructure event reads enforce their 5000-record ceiling and supported query features; datasearch reads send the required default timeout when callers pass `None`. Single-event lookups request one row and verify the returned identity.
- SCIM requests accept both SCIM success bodies and JSON error bodies while preserving the SCIM request Content-Type.
- New alert query methods use canonical `orderbys`; legacy `list()` keeps
  its existing ordering parameter. Existing one-page tag lists and legacy RBAC
  return types remain supported.
- Automatic retries now default to GET, HEAD, and OPTIONS. Explicitly marked
  read-only POST operations can retry. Mutations and streaming request bodies
  are sent once unless a buffered operation explicitly opts into safe replay.
- `retry_on_status=frozenset()` disables status-based retries. It previously
  fell back to the default `{429, 500, 502, 503, 504}`, so there was no way to
  turn status retries off without also setting `max_retries=0`. `None` still
  selects the defaults.
- `raise_for_status()` rejects an HTTP-success body that reports failure:
  `ok: 0` (which matches `ok: false` as well), `success: false`, and datasearch's
  `execution: "FAILED"` at the top level or under `status`. Methods that return a
  raw `dict`, among them `nsiq.get_ioc()`, raise `APIError` for those bodies
  instead of handing the envelope back.
- `incidents.get_anomalies()` sends `limit`, `offset`, `sortby`, and
  `sortorder` as query parameters and keeps only `users` and `timeframe` in the
  request body. The `severity` argument is now rejected instead of being sent as
  `severity_filter`; the endpoint has no server-side severity filter.
- `private_apps.create()` requires `protocols` and carries the port inside
  each protocol entry (`{"type": "tcp", "port": "443"}`) instead of a top-level
  `port`, and sends publisher IDs as strings. `port` may be an integer as well
  as a string, `"TCP/UDP"` expands into the two entries the API carries, and a
  ready-made `{"type": ..., "port": ...}` mapping keeps its own port. An
  unsupported protocol error names the values the SDK accepts.
- Private-app publisher association, policy-in-use, and bulk delete send
  string identifiers on both the legacy and typed paths, and reject an empty ID
  list instead of sending one.
- Legacy `steering.create_tunnel()` and `update_tunnel()` send the API's
  `enable` key rather than `enabled`, matching the typed IPsec request models.
- `events.list("clientstatus")` and `events.list("incident")` decode into
  `ClientStatusEvent` and `IncidentEvent`. An infrastructure `events.get()` now
  reads `/api/v2/events/data/infrastructure` instead of the datasearch path.
- Typed incident and DEM/ADEM helpers no longer mark every request as safe
  to replay. Read-only POST queries opt in explicitly; everything else follows
  the GET/HEAD/OPTIONS default and is sent once.
- One total policy across the decoders. Integers and numeric strings are
  used; booleans, negatives, floats, and unparsable values mean "no total"
  rather than an error. CCI pages and DSPM inventory pages now read an unusable
  `total_query_count`, `tags_count`, or `total` that way instead of failing. A
  CCI tag catalog contradicted by a usable `tags_count` raises `PaginationError`
  rather than a decoding error. Device-tag paging keeps its stricter reading,
  because its schema states `total_count`, `offset`, and `limit` as numbers.
- The legacy `list()` iterators stop, logging the stop at `WARNING`, when a
  page reaches past the total the envelope reported, rather than raising after
  they have already yielded rows. The records on that page are not yielded. A page longer than the requested size still raises
  `PaginationError`, and bounded page reads still treat an outrun total as an
  error.
- RBI template operations (`get_template`, `get_template_diffs`,
  `update_template`, `delete_template`, `restore_template`) accept an integer or
  a string `template_id` on both the sync and async resources, matching
  `rbi.with_response`. A numeric `id` in a template response decodes as text.
- `client.scim.users.list()`, `client.scim.groups.list()`, and
  `client.rbac.admins.list()` bound `page_size` to 1 through 1000, the ceiling a
  single `count` already had. `admins.list_page(count=...)` is capped at 1000,
  and `count=0` remains the totals-only probe.
- `url_lists.create()` and `url_lists.update()` raise
  `netskope.exceptions.ValidationError` for a missing or unusable input.
  `update()` previously raised a bare `ValueError` when given nothing to change,
  and `create()` sent an unrecognized `list_type` to the API unchecked.
- `ClientStatusEvent` and `IncidentEvent` accept integers in the identity,
  version, status, assignee, and DLP fields that some tenants report as numbers.
  `EventQueryCapabilities.jql` defaults to `True`, and no category overrides it:
  audit declares the same `query` filter as the rest (`events/audit.yaml:12-18`).
  What audit lacks is field projection, grouping, and ordering.
- `IncidentUpdateResult.accepted` requires a positive reported count. A negative count no longer claims that updates were applied; `accepted_entries` still reports the sum the service returned.
- Resource identifiers reject negative integers before the request is sent, alongside the existing rejection of booleans and of strings outside `^[a-zA-Z0-9_\-]+$`. `url_lists.get(-3)` raises rather than spending a round trip on `/api/v2/policy/urllist/-3`. Zero remains a usable identifier.
- The legacy SCIM resources accept the same identifiers as the typed accessors: an id is percent-encoded into the path by the shared `quote_id` rule (non-empty, no whitespace or control characters, not a dot-only segment) instead of being rejected by a `^[a-zA-Z0-9_\-]+$` pattern. `scim.users.get("user@example.com")` now sends `GET /api/v2/scim/Users/user%40example.com`.
- The legacy SCIM iterators build their pages through the same checks as every other decoder: a page longer than `count`, records past `totalResults`, and a `startIndex` echo naming another page are rejected. `Page.offset` on those pages is the zero-based offset (it was the one-based `startIndex`), matching `rbac.admins.list_page()`.
- An empty page whose envelope establishes that the collection is complete ends iteration immediately instead of costing one more request.
- `pages()` documents that a page contradicting its own request raises `PaginationError` mid-iteration, after earlier pages have been yielded.
- An HTTP 200 response whose body reports `ok: 0` (or `ok: false`, which compares equal), `success: false`, `status: "error"`, or `execution: "FAILED"` raises an API error rather than being returned as data. `success: 0` is not treated as a failure: only the boolean `false` is. The raised error keeps the body's own `status_code` when it states one, and the HTTP status otherwise.
- `UserConfidenceIndex` declares only `user_id` and `confidences`; the `user`, `score`, `severity`, and `sources` fields were never returned by the endpoint and always read as empty.
- `incidents.get_anomalies()` no longer caps `timeframe` at 90 days; any value of at least 1 day is accepted.
- `events.list()` and `events.list_page()` accept `insertion_start_time` and `insertion_end_time` for the audit and infrastructure event types, the only endpoints that define an ingestion-time window.
- The transport accepts per-request `headers` for operation-specific values; the API token header cannot be overridden that way.
- `scim.groups.get()` accepts `attributes` and `excluded_attributes`; group members are excluded by default and are returned only with `attributes="members"`.
- `rbac.admins` returns `AdminUser`, which types the platform admin record (`metadata`, the Netskope SCIM extension, `record_type`, `provisioned_by`, and `role`). It subclasses `ScimUser`, whose `display_name`, `emails`, `name`, and `groups` fields are never populated for an admin.
- `enrollment.create_token_set()` and `enrollment.list_token_sets()` warn with a `DeprecationWarning` when passed `name`, `max_devices`, `limit`, or `offset`; the values are no longer sent.
- The SCIM page-size ceiling of 1000 is documented as an SDK guard rail rather than a gateway rule; the gateway declares `count` and `startIndex` as unbounded integers.
- DNS profile and inheritance-group writes default to `interactive=True`, leaving the change pending until `deploy()` applies it; pass `interactive=False` to deploy on write as before. DNS profile deployment by ID requires a `change_note`, which the API declares required.
- `private_apps.list()` composes its filter arguments into the single `query` expression the API documents; the arguments remain, and the previously ignored `filter_expr` joins the same expression.
- Steering configuration accepts only the `npa` and `publishers` scopes; `nsc` and `ztna` have no endpoint and are rejected before any request.
- IPsec tunnel bandwidth and encryption accept any positive integer and any cipher name, matching the API, instead of a fixed client-side list. Upgrade profile `timezone` is validated against the zone names the API accepts, exported as `PUBLISHER_UPGRADE_TIMEZONES`.
- `url_lists.list()` accepts the `pending` and `field` filters the API declares.
- `PublisherStatus.NOT_CONNECTED` is replaced by `NOT_REGISTERED`, the value the API returns. Fields absent from every API response were removed from `Publisher`, `PublisherRelease`, `LocalBroker`, `UrlList`, `PrivateApp`, `IPSecTunnel` and `Pop`; unmodelled keys remain reachable through each model's extras.
- DEM `probes.create` requires the fields the API requires (`frequency`, `entity`, `os`, `device_classification`, `status`, an app selector and `move`); `target`, `protocol` and `interval` have no counterpart in the API and raise a message naming the fields to use instead. DEM `alert_rules.create` builds the nested `criteria` the API expects from `metric` and `threshold`; `probe_id` has no counterpart and raises.
- DEM `alert_rules.list` sends the `category`, `type`, `enabled` and `severity` filters the API declares; `limit` and `offset` slice the result in the SDK, as do `limit`/`offset` on `notifications.list_templates`.
- DEM `get_data` rejects `agent_status` and `client_status` and points at `get_states`; DEM `get_entities` gained `sort_by` and `user_location`; IPS `list_signature_overrides` and `search_signatures` gained `sort_by` and `sort_order`. DEM probe and alert-rule records expose the fields the API returns; fields that were always empty were removed.
- SPM `inventory` takes the aggregation the API requires; its `filter` argument is a deprecated alias for the operation's own `ngl_query`. DSPM has no bulk connect-by-id operation, so `connect_datastores` explains that and the new `connect_datastore` sends a single datastore request.
- NSIQ `lookup_iocs` is no longer replayed after a network failure, because the operation is declared read-write.
- AICC queries validate the risk-level, extension-type, model-deployment and violation-severity enumerations before sending, including inside array parameters.
- The repository is built and tested with uv and now commits `uv.lock`, so every environment resolves to the same versions; `ruff` is pinned to 0.15.5, and `ty` 0.0.79 replaces mypy and its pydantic plugin as the type checker (scoped to `src/` through `[tool.ty.src]`).
- CI (`.github/workflows/ci.yml`) runs lint, format, type check and the test suite on Python 3.11 and 3.14 with `uv sync --locked`, then builds the wheel and sdist and installs each into a clean environment through `scripts/smoke-dist.sh`.
- A `v*` tag now drives the release (`.github/workflows/release.yml`): it verifies the tag matches the project version and is on `main`, repeats the CI checks, smoke-tests the artifacts, publishes to PyPI through Trusted Publishing with no stored token, and creates the GitHub Release from that version's CHANGELOG section.

### Fixed

- Typed `url_lists.deploy()` accepts the status-only acknowledgment its model
  documents. Reading records out of a `{data: [...], status}` envelope was
  applied to every object response, so an acknowledgment carrying no collection
  was refused. A collection that is present but malformed still raises.
- `events.get()` converts a record that fails model validation into
  `ResponseValidationError`. It read a body directly with no `parse()` boundary
  behind it, so `pydantic.ValidationError` reached the caller from this one
  accessor while every sibling converted it.
- `netskope.core.decoding.decoded()` keeps response values out of the error it
  raises. `pydantic.ValidationError` is itself a `ValueError`, so its rendered
  input was being interpolated into a message documented as payload-free; it now
  reduces to `(location, error_type)` pairs the way `ApiResponse.parse()` does.
- Event `insertion_start_time`/`insertion_end_time` reject a naive datetime and
  a non-epoch value, matching the sibling `start_time`/`end_time` bounds.
  `int(naive.timestamp())` silently read the caller's local zone, and a value
  that was neither a datetime nor an integer reached the query string unchecked.
- `users.groups.with_response.members_page()` raises `ValidationError` for a
  `limit` or `offset` outside the declared bounds, as its legacy twin does,
  rather than letting `pydantic.ValidationError` escape.
- Private-app convenience filters refuse a value carrying whitespace or a quote.
  Each becomes a term of one `query` expression that has no documented quoting,
  so `app_name="My App"` silently filtered on something else. Pass the whole
  expression through `query` for such a value.
- `spm.inventory()` raises when `ngl_query` is supplied together with its
  deprecated alias `filter`, instead of silently sending the deprecated value
  and dropping the current one.
- Publisher request validation names the offending fields instead of echoing
  pydantic's rendered message, which included the caller's input and a docs URL.
- Legacy `url_lists.deploy()` is annotated `list[dict] | dict`. The endpoint
  answers with an array (`policy/urllist.yaml:209-217`), which the previous
  `dict[str, Any]` excluded.
- `dem.query` time bounds that cannot be converted to the RFC 3339 shape the
  operation declares raise `ValidationError` instead of a bare `ValueError` from
  `datetime.fromtimestamp`. The usual cause is passing epoch seconds or
  microseconds where the surface takes milliseconds.
- `AiccMcpQuery` no longer offers `first_seen_after`. Four inventory list
  operations declare that parameter and `/inventory/mcp-servers` does not, so it
  moved from the shared base onto the four query models whose endpoints take it;
  it was previously accepted by the model and then refused before the request.
- A SCIM search matching nothing decodes as an empty page. `Resources` is
  required only once `totalResults` is non-zero (RFC 7644 3.4.2), so
  `scim.users.list_page()`, `scim.groups.list_page()` and `rbac.admins.list_page()`
  no longer reject a conformant empty `ListResponse`. A non-zero total with no
  collection is still an error.
- `rbac.roles.list()`, `rbac.roles.get()` and `steering.get_tunnel()` raise
  `ResponseValidationError` rather than a bare `ValueError` when a 200 body carries
  no recognisable record. Those six call sites decoded outside the `ApiResponse`
  boundary that performs the conversion, so `except NetskopeError` missed them.
- `dem.alert_rules.list()` and `notifications.list_templates()` refuse a negative
  `limit` or `offset` instead of slicing from the wrong end of the collection. Both
  windows are applied to records the client already holds, where `rows[-3:]` is the
  last three rows and not "page -3".
- `dspm.analytics()` raises `ValidationError` for an unrecognised `sort_order`
  instead of a bare `ValueError`, and reports the "takes no query parameters" error
  for a report that accepts none rather than failing on the parameter first.
- `ClientStatusEvent` keeps `host_info` and `last_seen_device_event` as fields. A
  resolving `AliasPath` marks its container consumed, so flattening `hostname`,
  `os` and `status` was discarding those objects and every sibling key with them.
- The typed `url_lists.deploy()` result carries each deployed record's `urls` and
  `type`, which were left nested under `data` and stranded in `model_extra`. A
  `{data: [...], status}` response populates `urllists` as well.
- The typed RBI template page accepts `limit=0`, which `list_templates` documents
  as "unlimited"; it was being read as a page-size cap that rejected any non-empty
  response.
- The notifications template write reports that the API takes the complete
  template on create *and* update, and names `action_type` when its default of
  `block` is what made the button fields invalid.

- RBAC role paths accept fractional numeric identifiers without truncation; legacy role creation fetches the exact returned role ID instead of converting it to an integer first.
- Declared numeric response fields retain fractions, including incident identifiers, insertion times, event counts, RBAC identifiers, and notification timeouts. Policy aliases populate their public fields; client-status `ts` remains a raw integer because its unit is unspecified.
- Sparse SPM history, ATP acknowledgments, NSIQ receipts, ADEM graphs, RBI watermarks, and DNS references no longer fail on fields the response schema makes optional. Legacy paginators retain top-level totals, and path identifiers reject trailing newlines.
- An HTTP 200 body whose `status` is `not found` raises `NotFoundError` instead of
  decoding to an all-`None` record; the value is declared at
  `npa_publishers.yaml:871-876` and three other NPA schemas.
- Error messages reported as `error_message` (ATP), `errorMsg` (ubadatasvc) or
  `body.errors` (SPM) reach the exception instead of degrading to the HTTP reason
  phrase, and a 429 carrying `retry_after` in its body populates
  `RateLimitError.retry_after`.
- `steering.get_tunnel` reads the `result` envelope the single-tunnel operation
  declares (`ipsec.yaml:305-317`), not the `data` envelope its create and update
  siblings use; it previously returned a record with every field `None`.
- `AtpScanReport.verdict` is optional, so the documented in-progress poll decodes
  (`atpsvc.yaml:409-419`); DSPM tag lists accept the string form their sibling
  fields already used.
- `spm.inventory(past_view=True)` requires `timestamp`, and RBI accepts a single
  `status`, `fields` or `template_id` without splitting the string into
  characters; empty id lists and `all=true` alongside ids are rejected.
- Publisher-association and DNS deploy acknowledgements that carry no record
  array decode as empty rather than raising, since neither schema marks the
  array required.
- UCI lookups accept email and domain-qualified usernames on both the plain
  (`incidents.get_uci()`) and typed entry points, in sync and async clients.
  Blank and non-string usernames and naive `from_time` datetimes fail before
  HTTP; valid identities and epoch-zero time bounds are preserved unchanged.
- HTTP-success failure envelopes and FastAPI validation details produce
  contextual SDK errors. Validation messages omit echoed request input.
  New typed accessors reject malformed response fields before presentation.
- AICC `include_total=false` page counts are not treated as collection
  totals; an omitted total on a later page cannot discard earlier evidence.
- Bounded short event/alert record pages expose endpoint-specific
  exhaustion evidence. Full pages, omitted limits, and aggregates do not
  inherit that conclusion, and trusted totals remain authoritative.
- Bounded role reads validate limit/offset before HTTP, and detail reads
  reject missing, boolean, or unrelated role IDs. Role detail IP restrictions
  accept the documented timestamped IP objects as well as legacy strings.
- Alert decoding accepts both `result` and `data` collections and validates
  non-empty aggregate results.
- `TimestampMixin` reads datetime strings as well as epoch numbers, so the
  `timestamp` on `Alert`, `Event`, `Incident`, and `Anomaly` survives a tenant
  that reports it as text. A string without a UTC offset is read as UTC, so
  epoch rows and string rows in one page stay comparable. A value that cannot be
  read is still `None` rather than a decoding failure, because these models
  decode whole pages and one unreadable row must not reject the rest.
- HTTP-200 datasearch execution failures raise API errors. Detection now
  covers a top-level `execution: "FAILED"` field as well as the same field
  inside the `status` envelope, because the two datasearch endpoint families
  report execution in different places. Device-tag ID lookups reject unrelated
  or ambiguous records instead of returning the first.
- `ApiResponse.parse()` reports the decoder's own diagnostic instead of one
  generic sentence, and an SDK error raised inside a decoder now reaches the
  caller with the request method, path, and request ID filled in.
- A page that cannot be continued safely raises instead of being accepted.
  One shared page builder applies the checks for every decoder routed through
  it, which is now the NPA, URL-list, user, publisher, event, alert, incident,
  device, DNS, SCIM, device-tag, CCI, DSPM, AICC, and RBI pages plus the legacy
  offset iterators: a page longer than the requested limit, a reported `offset`
  that does not identify the requested page, and a total contradicted by the
  records returned raise `PaginationError` with request context and the
  requested offset. `admins.list_page()` keeps its own `startIndex` check ahead
  of that builder. A malformed envelope still raises `ResponseValidationError`.
  The exceptions are the bounded RBAC role page and the datasearch aggregate
  page, which report no total, and the legacy SCIM iterators, which check
  neither page size nor `startIndex`.
- A page envelope that nests `total` and `offset` under `data` beside its
  records keeps both, so a device page no longer loses the total it was given
  or skips the offset check.
- The legacy `list()` iterators report a record that fails model validation
  or an envelope they cannot decode as `ResponseValidationError`, carrying the
  request method, path, request ID, and payload-free field locations, instead of
  letting a Pydantic or `ValueError` escape the SDK's error hierarchy.
- `publishers.list()` and `publishers.list_page()` raise
  `ResponseValidationError` for a malformed envelope, so both the iterator and
  the bounded page report the same error type. `publishers.get()`, `create()`,
  `update()`, and `create_registration_token()` report a malformed response the
  same way; they previously raised the bare base `NetskopeError`.
- The legacy offset paginator no longer raises `TypeError` when the envelope
  reports `status.total` as a string, and it stops as soon as a page's own
  totals show there is nothing more to fetch.
- `extract_response_list()` prefers an operation's declared record key over
  the generic `result`/`data` envelope and rejects two competing collections as
  ambiguous, including an empty one beside a populated one. User Management
  pages select `users` or `groups` according to the operation.
- URL-list `update()` (legacy and typed, sync and async) recognizes every
  documented read envelope, and refuses the PUT with `ResponseValidationError`
  when the read lacks `name`/`urls`/`type` or identifies a different list.
  Previously an unrecognized envelope merged into a payload that erased the
  list's URLs.
- URL-list `get()`, `create()`, and `update()` raise
  `ResponseValidationError` when no single record can be extracted, rather than
  validating an empty dict into a blank `UrlList`. A record whose nested `data`
  came back empty is still recognized by its `id` and `name`, and a `urllists`
  collection is read at the top level as well as under `data`. `get()`,
  `update()`, and `delete()` validate the list ID before interpolating it into
  the request path.
- `publishers.update()` with no fields to change and
  `publishers.bulk_upgrade()` with non-integer IDs raise `ValidationError`
  before the request is built.
- `Retry-After: 0` falls through to the jittered backoff instead of retrying
  immediately, and an HTTP-date `Retry-After` is honored by retries and by
  `RateLimitError.retry_after` (`netskope.exceptions.parse_retry_after`). A
  `nan` or infinite value now reads as no delay stated, so the jittered backoff
  applies and `retry_after` is `None`.
- A response body that is not JSON reports "The API response body is not
  valid JSON." The message previously quoted the decoder's byte position and the
  bytes around it. `.content` still carries the original body.
- SCIM list `count` is bounded to 1000 on `client.scim.users` and
  `client.scim.groups`; `count=0` remains the RFC 7644 totals-only probe.
- DSPM errors name `DspmResource.supported_resource_types()` and report the
  status actually received when a scan submission is not HTTP 202.
- Typed event queries reject JQL filters and ID lookup for `audit`, which
  that endpoint does not support, instead of sending a query it ignores.
- Incident update acknowledgments accept a message or an omitted `result`,
  so `"Update Successful"` no longer fails decoding. For those acknowledgments
  `accepted` stays `False`: a success flag carried with a message
  (`{"ok": 1, "result": "no incident matched"}`) or with no `result` at all
  states no entry count, so it cannot claim an update was applied.
- `upgrade_profiles.with_response.assign()` unwraps a `data` envelope.
  `upgrade_profiles.assign()` and the private-app tag writes reject an empty or
  unsafe identifier list, and an empty or blank tag name, before the request is
  built.
- `incidents.get_anomalies()` validates `users`, `timeframe`, `limit`,
  `offset`, `sort_by`, and `sort_order` before the request is built rather than
  letting the API reject them.
- Legacy `steering.create_tunnel()` and `update_tunnel()` build their bodies
  through the strict IPsec request models, so an empty `psk` or a non-string
  `site` fails before HTTP rather than reaching the API.
- Legacy iterator pages keep the envelope's `status` block as page metadata
  and compute `has_more` from the total it reports.
- AICC application `status` accepts an optional start/end window. Its query
  model declared no window at all and, forbidding extra fields, rejected one.
  AICC list filters reject empty lists; `stop_after` validation errors name
  `stop_after`; `risk_level` is documented as the API's `reconciled_risk_level`
  query parameter.
- `rbi.with_response.get_template()` accepts integer template IDs.
- Seven resource classes regained class docstrings that a misplaced string
  literal had left as unattached expressions. The AICC sub-resources and the
  `RbiResponses`, `SpmResponses`, and `DspmResponses` accessor classes, sync and
  async, now carry docstrings as well.
- Alert and incident records accept the numeric field shapes the datasearch API returns. `Alert.severity`, `Alert.site`, `Alert.ccl`, `Event.site`, `Incident.severity`, `Incident.status`, `Incident.assignee`, `Incident.dlp_profile`, `Incident.dlp_rule` and `Anomaly.severity` take a string or a number, as `Event.severity` already did, and a single `other_categories` value sent as a bare string decodes as a one-element list. A numeric `severity_level` no longer fails every alert read.
- An unreadable `timestamp` no longer rejects the record that carries it, and with it the rest of the page. Epoch numbers still become UTC-aware datetimes and datetime strings are still parsed; an empty string, an unparsable string, a boolean, a mapping, a list, or an epoch outside the supported range reads as no timestamp rather than raising. A datetime string without a UTC offset is read as UTC, so epoch rows and string rows on the same page compare without `TypeError`.
- `nsiq.url_lookup()` and `nsiq.lookup_iocs()` retry transient failures on both the sync and async clients. They read through POST, like the UCI, UBA, user-management, device-tag and DEM query endpoints that already opted in.
- Publisher response accessors validate `publisher_id` before building the request path, matching the private-app and RBAC accessors. A caller-supplied identifier can no longer redirect the request to another endpoint.
- `PrivateAppPolicyUsage` decodes an acknowledgment that carries no policy references. `{"status": "success"}` and an explicit `"data": null` read as an empty reference list instead of failing validation.
- An HTTP-200 datasearch execution failure names itself. The error reads "The datasearch query reported execution=FAILED for <METHOD> <path>", with the API's own message appended when the body carries one, instead of "[HTTP 200] Unknown error". The status code and exception class are unchanged.
- The legacy `client.<namespace>.list()` iterators (offset and SCIM) report a 200 response whose body is not JSON, is empty, or is not a JSON object or array as `ResponseValidationError`, instead of letting `json.JSONDecodeError` or `AttributeError` escape the SDK error hierarchy. A body that cannot be decoded as text reports a fixed message that never quotes the offending bytes.
- A first page carrying more records than its stated total keeps those records instead of discarding them and returning an empty iterator: the total is treated as unusable (`Page.total` and `Page.has_more` are `None`) and the traversal continues. A total the records outrun after rows have shipped still ends the traversal, logged at WARNING with the number of records dropped.
- A page shorter than the requested page size ends the traversal instead of advancing the offset past the records the API withheld, which skipped records and stopped while the last page still reported `has_more=True`. Such a page reports `has_more=None` and logs a WARNING.
- Reaching the 1000-page safety limit raises `PaginationError` naming the offset, instead of returning a truncated result set that looks complete.
- `PaginationError` raised while decoding a page inside `list()` carries the request method, path and request id, as the typed `with_response` path does.
- The shared administrative page decoder passes the envelope's echoed `offset` as received, so a garbage, negative or boolean echo is rejected rather than read as "the envelope stated nothing".
- The request log line records the method and path only; query strings (JQL, usernames, filters) no longer reach the DEBUG log.
- Datasearch requests send the `timeout` query parameter the API marks required, defaulting to 180 seconds; `alerts`, `events`, and `incidents` read methods accept a `timeout` argument, and `timeout=None` omits it.
- Legacy `alerts.list()` and `events.list()` send the sort field as `orderbys` instead of `sortby`, which the datasearch endpoints do not define, so results were returned unordered.
- `Alert.other_categories` accepts object entries; a row such as `[{"name": "Cloud Storage"}]` no longer rejects the whole page.
- Audit events accept a JQL `query`, and `audit_type` is sent as a `type eq "..."` clause inside it rather than an undocumented `type` parameter; `events.get()` works for audit events as a result.
- `events.list()` and `events.get()` reject the `transaction` event type with a message pointing at `events.transaction_metrics(hours=...)`, instead of paginating a metrics object and yielding nothing.
- `incidents.get_anomalies()` reads records from the documented `results` key; the non-typed call previously returned an empty list for every response.
- `ConfidencePoint.start` and `ConfidencePoint.confidence_score` are optional, matching a schema that requires neither.
- A datasearch response reporting a failed execution is raised regardless of the casing the tenant uses; `Failed` and `failed` no longer decode as an empty success.
- Errors reported inside a `data.error` field on an HTTP 200 body, such as a forensics download failure, carry the server's reason instead of "Unknown error", and a missing forensic file raises `NotFoundError`.
- `IncidentUpdateResult.accepted` follows the `ok` flag, so the documented success body `{"ok": 1, "result": "Update Successful"}` reports acceptance; `accepted_entries` still reports only counted entries.
- `NetworkEvent.protocol` populates from the `ip_protocol` field network events actually return.
- `ClientStatusEvent.hostname`, `.os`, and `.status` read the nested `host_info` and `last_seen_device_event` objects the client-status endpoint returns, while still accepting the flat names.
- `scim.users.update()` and `scim.groups.update()` no longer raise a JSON decode error on the documented success: the PATCH answers 204 with an empty body, so the methods return `None` there and still decode a body when one arrives.
- SCIM requests send `application/scim+json;charset=utf-8` as `Accept` and `Content-Type`, the only media type the SCIM API declares; the platform admin SCIM route keeps plain JSON.
- SCIM group patches send `path: "displayname"`, the spelling in the gateway's `path` enum, instead of `path: "displayName"`.
- SCIM user patches send one path-scoped replace operation per attribute instead of a single operation with no `path`, matching every documented example.
- Looking a user up by username filters on `accounts.userName`; `userName` is a property of the account, not of the user, so the previous filter silently matched nothing.
- `SupportedOperatingSystems.available_os` defaults to an empty list, since the gateway schema marks no property required.
- `enrollment.create_token_set()` sends no request body and `enrollment.list_token_sets()` sends no query string, because neither operation declares one.
- RBAC role pages report the envelope's `count` as the page total, so `Page.total` and `Page.has_more` are populated for role listings.
- `tokens.revoke()` sends the API's revoke operation (`PATCH {"operation": "revoke"}`) instead of deleting the token; `tokens.delete()` is unchanged.
- URL list deployment posts to `/api/v2/policy/urllist/deploy`; the previous `/api/v2/policy/deploy` path does not exist and returned 404 on every call.
- Publisher create and update send the local-broker flag under the API's `lbrokerconnect` key, so the flag is no longer silently dropped.
- Publisher bulk upgrade sends publisher IDs as strings, matching the bulk endpoint's schema.
- Publisher alert configuration can send `selectedUsers`, and rejects an `event_types` list outside the API's one-to-five bound.
- `Publisher.publisher_id` and `publisher_name` are populated from single-object responses, which name the record `id` and `name`; `client.publishers.get()`, `.create()` and `.update()` previously returned `None` for both.
- `PublisherApp` reads the publisher-apps response, which names each record `id`, `name` and `private_app_protocol`; every record previously parsed to all-`None`.
- `PublisherUpgradeProfile.external_id` falls back to the `id` that create and update responses carry, so a newly created profile can be assigned without a second read.
- `PrivateApp.app_id` and `app_name` are populated from NPA search results, which name the record `id` and `name`; `PrivateApp.port` is read from the app's protocol entries, where the API carries it; `service_publisher_assignments` is exposed and `publishers` reads the same value.
- NPA policy rule creation sends `group_id` as the string the API declares.
- DNS deployment sends `all` as a query parameter and a body carrying the fields the API requires, instead of a body the API rejects; `dns.update(log_traffic=...)` takes the API's `"Blocked DNS"` or `"All DNS"` mode rather than a boolean.
- `npa.validate_name()` can send `tag_type`, which the API requires when validating a tag name.
- `IPSecTunnel` and `Pop` model the fields the IPsec API returns; `LocalBroker` no longer declares a status or an owning publisher; `NpaNameValidation.is_valid_name` is optional; `UrlList.pending` is read as the integer the API returns.
- SPM `recent_changes` POSTs the required `time_range` body to `/apps/recentchanges/getstats` instead of sending a bodyless GET that the API rejects.
- SPM `list_apps`, `get_app`, `inventory`, `posture_score` and `list_policy_rules` address the operations the API actually exposes (`POST /inventory/getresources`, `POST /results/getposturescores`, `GET /rules/list`); the previous paths returned 404 on every tenant.
- DSPM `list_resources` uses the same verified routes as `list_page`, and rejects the legacy resource names that have no route instead of building a 404 path; `analytics` reads the two connected-datastore reports the API declares; `scan_datastores` issues one real start-scan request per datastore.
- ATP `scan_file` and `scan_file_path` upload the file as `multipart/form-data` with the required `scantype` query parameter, instead of a base64 JSON body the service does not accept.
- RBI `restore_cdr` uses PUT, and `test_cdr_config` sends its settings as query parameters on a GET, with an inline API key in the `X-CDR-Api-Key` header.
- DEM `get_data`, `get_dataset` and `get_traceroute` send `begin` and `end` as `{"absolute": "<RFC 3339>"}` objects; integer arguments are still read as epoch milliseconds and converted.
- DEM `probes.create` and `alert_rules.create` send the request bodies the API defines, without the `data` wrapper.
- CCI `lookup_app` omits `discovered` and `connector` rather than sending a value outside their enumeration, and validates `ccl`.
- NSIQ URL-lookup reports and false-positive receipts no longer require fields the API marks optional; notification template writes accept any colour string the API accepts; `AiccDataCoverage` parses a response that omits `data_available_since`; RBI `list_applications` parses a response that omits the `applications` collection.

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
- Verified against `example.goskope.com`: list, create (`type=regex`), update with urls only (preserves `name` and `type`), update with name only (preserves `urls` and `type`), update with all fields, delete.
- Parallel to [netskopeoss/netskope-cli#10](https://github.com/netskopeoss/netskope-cli/pull/10) and the equivalent fix on the Netskope MCP server's PATCH, which hit the same class of bug.
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
