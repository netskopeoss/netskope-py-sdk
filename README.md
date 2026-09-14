# Netskope Python SDK

**[Read the documentation](https://netskopeoss.github.io/netskope-py-sdk/)**

The official Netskope Python SDK — a modern, typed, and intuitive interface to the Netskope REST API v2.

[![PyPI](https://img.shields.io/pypi/v/netskope_py_sdk)](https://pypi.org/project/netskope-py-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/netskope_py_sdk)](https://pypi.org/project/netskope-py-sdk/)
[![License](https://img.shields.io/pypi/l/netskope_py_sdk)](https://github.com/netSkopeoss/netskope-py-sdk/blob/main/LICENSE)

## Why This SDK?

- **Broad API coverage** — 25 resource namespaces spanning alerts, events, incidents, SCIM, publishers, private apps, steering, URL lists, NPA policy, DNS, CCI, devices, enrollment, RBAC, user management, API tokens, notifications, IPS, DEM/ADEM, AI/agent activity (AICC), and the ATP/NSIQ/RBI/DSPM/SPM security services
- **Hierarchical namespaces** — `client.alerts.list()`, `client.scim.users.create()` — explore the entire API through autocomplete
- **Automatic pagination** — just iterate, no page loops needed
- **Full type safety** — Pydantic v2 models with complete type annotations
- **Sync + Async** — choose the right client for your use case
- **Automatic retries**: exponential backoff with jitter for safe operations
- **Rich exceptions** — specific error types with request IDs for support escalation
- **Minimal dependencies** — only `httpx` + `pydantic`
- **Python 3.11+** — modern Python, no legacy baggage

## Installation

```bash
pip install netskope-py-sdk
```

## Quick Start

```python
from netskope import NetskopeClient

# Create a client (or set NETSKOPE_TENANT and NETSKOPE_API_TOKEN env vars)
client = NetskopeClient(
    tenant="mycompany.goskope.com",
    api_token="your-v2-api-token",
)

# List high-severity alerts — pagination is automatic
for alert in client.alerts.list(query='severity eq "high"'):
    print(f"{alert.alert_name} — {alert.user} — {alert.severity}")

# Query network events
for event in client.events.list("network", query='user eq "alice@example.com"'):
    print(f"{event.src_ip} → {event.dst_ip}")

# Manage URL allow/block lists
blocklist = client.url_lists.create("threat-iocs", ["malware.example.com"])
client.url_lists.deploy()  # deploy pending changes

# List publishers
for pub in client.publishers.list():
    print(f"{pub.publisher_name} — {pub.status}")

# SCIM user provisioning
for user in client.scim.users.list():
    print(f"{user.user_name} active={user.active}")
```

## Async Usage

```python
from netskope import AsyncNetskopeClient

async with AsyncNetskopeClient(tenant="...", api_token="...") as client:
    async for alert in client.alerts.list():
        print(alert.alert_name)
```

## Configuration

### Typed CLI integration (development)

The unpublished `1.2.0.dev0` development version adds bounded pages and optional
access to the original response alongside a typed result:

```python
with NetskopeClient(tenant="mycompany.goskope.com", api_token="...") as client:
    response = client.publishers.with_response.list_page(limit=25)
    page = response.parse()
    for publisher in page.items:
        print(publisher.publisher_name)
    print(page.total, page.has_more)
    original_json = response.json()
```

Both `parse()` and `json()` inspect the same completed request. Ordinary
`publishers.list_page()` returns a typed page directly. Unknown response fields
remain available through Pydantic models; original JSON access is for callers
that need the API's exact envelope and scalar representations.

Publisher and URL-list collection endpoints return one complete collection.
Their page methods apply `offset` and `limit` locally, and their iterators fetch
once. `publishers.list(filter_expr=...)` raises `ValidationError`; filter the
returned records in Python. A local page retains the server's total and reports
whether more records remain in the fetched collection.

The same pattern now covers RBAC role summaries/details, SCIM admins, alerts,
and device-tag reads. Alerts have a distinct `aggregate_page()` result type,
and bounded scans expose why they stopped:

```python
from netskope import DatasearchWindow

with NetskopeClient(tenant="mycompany.goskope.com", api_token="...") as client:
    scan = client.alerts.scan_pages(
        window=DatasearchWindow(start_time=1_700_000_000, end_time=1_700_003_600),
        max_records=200_000,
    )
    for page in scan:
        for alert in page.items:
            print(alert.id)
    print(scan.summary)  # Absent until the iterator is fully consumed.

    for tag in client.devices.tags.iter_all():
        print(tag.id, tag.name)
```

A record/page limit is not evidence of complete traversal. Alert scan summaries
distinguish caller limits from endpoint exhaustion. A page the SDK cannot
continue from safely is an error, not a result: a page longer than the requested
limit, an offset or `startIndex` the server ignored, or a total that contradicts
the records returned raises `PaginationError`, with request context and the
requested offset. Three reads sit outside that rule: the bounded RBAC role page
and the datasearch aggregate page, which report no total of their own, and the
SCIM `list()` iterators, which follow their own `startIndex` walk. The legacy
offset `list()` iterators apply it with one relaxation: when a page reaches past
the reported total they stop and log that at `WARNING` instead of raising,
because rows have already been yielded. The records on that page are dropped. A malformed envelope raises
`ResponseValidationError`. Both are importable from `netskope`. Neither promises
a transactional snapshot while tenant data changes.

RBAC writes can use a strict request and return only the mutation receipt:

```python
from netskope.models import ApiGroupGrant, RoleCreate, RolePatch

with NetskopeClient(tenant="mycompany.goskope.com", api_token="...") as client:
    receipt = client.rbac.roles.create_receipt(
        RoleCreate(
            name="SOC-Analyst",
            description="Read access to the selected API group",
            api_groups=[ApiGroupGrant(api_group_id=1, permission="r")],
        )
    )
    client.rbac.roles.update_receipt(receipt.id, RolePatch(description="Updated description"))
```

Choose API-group IDs for your tenant. These methods send one POST or PATCH and
do not fetch details afterward. Omitted patch fields stay absent; unknown
fields, explicit nulls, and duplicate grants fail validation. Device-tag
create/update convenience methods also validate their name/description input,
with original response access through `client.devices.tags.with_response`.

Typed response access reaches the remaining resource families while preserving
the existing raw-returning SDK methods. The new AICC namespace exposes
operation-specific query types and owns collection traversal:

```python
from netskope.models import AiccApplicationQuery

query = AiccApplicationQuery(
    start_time="2026-09-01T00:00:00Z",
    end_time="2026-09-08T00:00:00Z",
)
with NetskopeClient(tenant="mycompany.goskope.com", api_token="...") as client:
    for page in client.aicc.applications.iter_pages(query, page_size=100):
        for application in page.items:
            print(application.name, application.sessions)
```

Use `with_response.iter_pages()` when an exporter needs original wire values.
Repeated records, contradictory totals, ignored offsets, and incomplete safety
limits raise `PaginationError`; a malformed page raises
`ResponseValidationError`. A streaming consumer must check for errors after
earlier pages have been emitted. No traversal promises a transactional snapshot.

### Environment Variables

| Variable | Description |
|---|---|
| `NETSKOPE_TENANT` | Tenant hostname (e.g. `mycompany.goskope.com`) |
| `NETSKOPE_API_TOKEN` | REST API v2 token |
| `NETSKOPE_CA_BUNDLE` | Path to a CA bundle (PEM) for TLS verification |

### Client Options

```python
client = NetskopeClient(
    tenant="mycompany.goskope.com",
    api_token="...",
    timeout=60.0,  # request timeout (seconds)
    max_retries=5,  # retry count for transient errors
    backoff_factor=1.0,  # exponential backoff base
    allow_custom_tenant=False,  # True skips the tenant domain check
    verify=True,  # TLS verification (see below)
)
```

`allow_custom_tenant=True` accepts a private or preproduction hostname that does
not end in `.goskope.com`, `.netskope.com`, or `.boomskope.com`. IP addresses
are still rejected.

Pass `ci_session="..."` in place of `api_token` to use a browser session cookie.
The two explicit credentials are mutually exclusive, and an explicit session
suppresses environment-token fallback. Browser login and session refresh belong
to the application using the SDK.

The SDK closes HTTPX clients it creates. If you pass `http_client=...`, the
client stays caller-owned and open when the SDK closes. Configure TLS on that
injected client; the SDK supplies its own tenant, credentials, and request timeout.

`client.closed` reports whether the client has been closed. A request made after
`close()` raises `ClientClosedError`.

GET, HEAD, and OPTIONS retry transient failures by default. Every other request
is sent once unless it explicitly declares safe replay through `retry_safe=True`.
Read-only POST queries opt in, among them UCI lookups, UBA anomaly search, User
Management queries, device-tag reads, and the DEM/ADEM query endpoints. Creates,
updates, deletes, scan submissions, and registration-token generation do not.
Streaming request bodies are sent once. `Retry-After: 0` falls through to the
jittered backoff, and an HTTP-date `Retry-After` is honored. The public
`client.request()` and its async counterpart use the same authentication,
retries, and error handling as typed resources.

`retry_on_status` selects which status codes retry. Left at `None` it means the
defaults, `{429, 500, 502, 503, 504}`; an empty `frozenset()` turns status-based
retries off. Connection errors and timeouts retry independently of it, so use
`max_retries=0` to stop retrying altogether.

### TLS Verification

The `verify` option controls how the client validates the tenant's TLS
certificate:

- `True` (default) — verify against the system trust store
- `False` — disable verification (not recommended)
- a path string — verify against a custom CA bundle (PEM) file

When `verify` is left at its default, the SDK resolves a CA bundle from the
first environment variable that is set: `NETSKOPE_CA_BUNDLE`,
`REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, or `CURL_CA_BUNDLE`. The helper
`find_netskope_ca_cert()` performs this lookup and returns the resolved path
(or `None`), so you can pass it explicitly:

```python
from netskope import NetskopeClient, find_netskope_ca_cert

client = NetskopeClient(
    tenant="mycompany.goskope.com",
    api_token="...",
    verify=find_netskope_ca_cert() or True,
)
```

### Multiple Tenants

```python
prod = NetskopeClient(tenant="prod.goskope.com", api_token=prod_token)
staging = NetskopeClient(tenant="staging.goskope.com", api_token=staging_token)
```

## API Reference

### Alerts

```python
# List with JQL filtering
alerts = client.alerts.list(query='alert_type eq "DLP"')
for alert in alerts:
    print(alert.alert_name, alert.severity, alert.user)

# Get a single alert
alert = client.alerts.get("alert-id-123")

# Page-level access
for page in client.alerts.list().pages():
    print(f"Page: {len(page.items)} items, {page.total} total")

# Collect all at once (with safety limit)
all_alerts = client.alerts.list().to_list(max_items=5000)
```

### Events

```python
from datetime import datetime

# Query by event type
for event in client.events.list("application"):
    print(event.user, event.app, event.activity)

# Network events with time range
for event in client.events.list(
    "network",
    start_time=datetime(2026, 1, 1),
    end_time=datetime(2026, 3, 1),
):
    print(event.src_ip, event.dst_ip)

# Audit events take a JQL query too; audit_type is folded into it as a
# `type eq "admin"` clause.
for event in client.events.list("audit", audit_type="admin"):
    print(event.user, event.activity)

# Supported types: alert, application, network, page, incident,
#   audit, infrastructure, clientstatus, epdlp
# "transaction" is not a record endpoint — list() rejects it. Its hourly
# backlog metrics come from transaction_metrics():
metrics = client.events.transaction_metrics(hours=24)
```

### URL Lists

```python
# CRUD operations
url_list = client.url_lists.create("blocklist", ["bad.com", "evil.org"])

# Partial updates are merged over the current list — pass only what you want to change.
# (The Netskope API requires the full payload on every PUT, so update() GETs first
# and preserves the fields you don't supply.)
url_list = client.url_lists.update(url_list.id, urls=["bad.com", "evil.org", "new.bad.com"])

client.url_lists.delete(url_list.id)

# Deploy all pending changes
client.url_lists.deploy()
```

If that preparatory read is missing `name`, `urls`, or `type`, or identifies a
different list, `update()` raises `ResponseValidationError` instead of sending a
PUT that would erase the list's URLs. A `list_type` other than `exact` or
`regex`, and an `update()` with nothing to change, raise `ValidationError`
before any request is built. A response that carries no single URL list raises
`ResponseValidationError` rather than decoding into a blank record.

### Publishers

```python
# List all publishers
for pub in client.publishers.list():
    print(f"{pub.publisher_name}: {pub.status} ({pub.apps_count} apps)")

# Create a publisher. lbroker_connect goes out as the API's `lbrokerconnect`.
new_pub = client.publishers.create(name="aws-us-east-1", lbroker_connect=True)

# Get by ID
pub = client.publishers.get(publisher_id=42)

# Registration token, apps, and upgrades
token = client.publishers.create_registration_token(publisher_id=42)
apps = client.publishers.list_apps(publisher_id=42)
client.publishers.bulk_upgrade([42, 43])

# Publisher releases and alert configuration
for rel in client.publishers.list_releases():
    print(rel)
config = client.publishers.get_alerts_configuration()
```

Publisher updates require `name`. Updating alert configuration requires all
three fields: `admin_users`, `event_types`, and `selected_users`. Its result is
an acknowledgment; call `get_alerts_configuration()` to read the configuration.

### Private Apps (ZTNA)

```python
# List private apps. Each filter argument becomes one term of the single
# `query` expression the endpoint takes, joined with `and`, so this is sent
# as query=name sw dash and in_policy eq yes.
for app in client.private_apps.list(app_name="dash", in_policy=True):
    print(f"{app.app_name} → {app.host}:{app.port}")

# Create a private app. protocols is required: the API carries the port inside
# each protocol entry, so this sends protocols=[{"type": "tcp", "port": "443"}].
# port may be an int, and "TCP/UDP" expands into one entry per transport.
app = client.private_apps.create(
    name="internal-dashboard",
    host="10.0.0.5",
    port=443,
    protocols=["TCP"],
    publisher_ids=[1, 2],
)

# Update (PATCH) and manage the app's publishers. update() takes the fields to
# change as extra_fields; it has no per-field keyword arguments.
client.private_apps.update(app.app_id, extra_fields={"host": "10.0.0.6"})
client.private_apps.add_publishers([app.app_id], [3])

# Tags
for tag in client.private_apps.tags.list():
    print(tag.tag_name)
new_tags = client.private_apps.tags.create(app.app_id, ["prod"])
```

App, publisher, and tag IDs go out as strings, as the API expects. Bulk delete,
publisher association, policy-in-use, and the tag writes reject an empty ID list
or a blank tag name before the request is built.

### SCIM (Users & Groups)

```python
# Users
for user in client.scim.users.list():
    print(user.user_name, user.active)

user = client.scim.users.create(
    user_name="alice@example.com",
    email="alice@example.com",
    display_name="Alice Smith",
)

# Groups. Members are excluded unless you ask for them by name.
for group in client.scim.groups.list():
    print(group.display_name)

group = client.scim.groups.get("group-id", attributes="members")
print(f"{group.display_name}: {len(group.members)} members")
```

`page_size` on these iterators, and on `client.rbac.admins.list()`, must be
between 1 and 1000, the ceiling the SCIM `count` parameter already had.
`client.rbac.admins` yields `AdminUser`, which carries the platform admin's
`record_type`, `provisioned_by`, and `role`; the SCIM profile fields it
inherits (`display_name`, `emails`, `name`, `groups`) stay empty for an admin.
A SCIM user `update()` returns `None` for the documented 204.

### Incidents

```python
# List incidents
for incident in client.incidents.list(query='severity eq "critical"'):
    print(incident.incident_id, incident.severity, incident.status)

# Get user risk score
uci = client.incidents.get_uci("user@example.com")
latest = uci.confidences[-1] if uci.confidences else None
print(f"Latest confidence: {latest.confidence_score if latest else 'n/a'}")

# Get UBA anomalies. The endpoint has no server-side severity filter, so
# passing severity= is rejected rather than silently dropped.
anomalies = client.incidents.get_anomalies(["user@example.com"])

# Incident notes
notes = client.incidents.list_notes("dlp-incident-id")
note = client.incidents.add_note("dlp-incident-id", "Investigated — false positive")
client.incidents.delete_note("dlp-incident-id", note.note_id)
```

### Steering & Infrastructure

```python
# Get steering config. The only scopes with an endpoint are "npa" and
# "publishers"; anything else is rejected before a request is built.
config = client.steering.get_config("npa")

# List PoPs
for pop in client.steering.list_pops():
    print(f"{pop.name} — {pop.region} ({pop.location})")

# List IPSec tunnels. The record is keyed by site, and reports `enabled`
# even though create_tunnel()/update_tunnel() write the API's `enable`.
for tunnel in client.steering.list_tunnels():
    print(f"{tunnel.site}: enabled={tunnel.enabled}")
```

### NPA Policy & Infrastructure

```python
# Policy rules and groups
for rule in client.npa.policy.rules.list():
    print(rule.rule_name)
rule = client.npa.policy.rules.get(rule_id=123)
for group in client.npa.policy.groups.list():
    print(group.group_name)

# Publisher upgrade profiles and local brokers
for profile in client.npa.upgrade_profiles.list():
    print(profile.name)
for broker in client.npa.local_brokers.list():
    print(broker.name)

# Validate a name or search resources
client.npa.validate_name("private_app", "internal-dashboard")
client.npa.search("private_apps", "name sw prod")
```

### DNS Security Profiles

```python
# DNS profiles (paginated)
for profile in client.dns.list():
    print(profile.name)
profile = client.dns.get(profile_id="uuid-here")

# Creates and updates default to interactive=True, so the change waits in a Pending-*
# state. Pass interactive=False to deploy on write instead.
profile = client.dns.create("corp-dns")
client.dns.update(profile.id, description="Corporate resolver")

# Deploying by ID requires a change_note; deploy(all=True) does not.
client.dns.deploy(ids=[profile.id], change_note="quarterly update")

# Domain inheritance groups and reference data
for group in client.dns.inheritance_groups.list():
    print(group.name)
client.dns.inheritance_groups.deploy(all=True)
categories = client.dns.list_domain_categories()
record_types = client.dns.list_record_types()
```

DNS deletes default to `interactive=False`; pass `interactive=True` to stage
a deletion. Typed deploy responses parse into a `Page` of profiles or inheritance
groups, preserving the returned records and total.

### CCI (Cloud Confidence Index)

```python
# Look up risk data for an exact app name
data = client.cci.lookup_app("Dropbox", ccl="high")

# Custom app tags. list() returns the API envelope, not a list
catalog = client.cci.tags.list()
for name in catalog["data"]["tags"]:
    print(name)

# The typed accessor returns a Page of tag names instead
for tag in client.cci.tags.with_response.list_names_page().parse().items:
    print(tag.root)

client.cci.tags.create("finance-approved", apps=["Dropbox"])

attributes = client.cci.tags.supported_attributes()
```

### Devices

```python
# List managed devices (paginated)
for device in client.devices.list():
    print(device)

# Device tags
for tag in client.devices.tags.list():
    print(tag.name)
tag = client.devices.tags.create("kiosk", description="Kiosk devices")

client.devices.supported_os()
```

### Enrollment

```python
# Client enrollment token sets. Neither call takes arguments: the list
# operation declares no parameters and the create operation no body, so
# name/max_devices/limit/offset warn and are not sent.
for token_set in client.enrollment.list_token_sets():
    print(token_set.id, token_set.enforce_status)
new_set = client.enrollment.create_token_set()
```

### RBAC (Roles & Admins)

```python
# Roles
for role in client.rbac.roles.list():
    print(role.name)
role = client.rbac.roles.create(
    "read-only-analyst",
    description="Read-only access",
    api_groups=[{"apiGroupId": 1, "permission": "r"}],
)

# Admin users (SCIM-paginated)
for admin in client.rbac.admins.list():
    print(admin.user_name)
```

### User Management

The read-only User Management API returns richer data than SCIM, including
per-account group membership. For user provisioning CRUD, use
`client.scim.users`.

```python
# Users
for user in client.users.list(filter={"accounts.active": {"eq": True}}):
    print(user.id, user.emails)
user = client.users.get("alice@example.com")

# Groups and membership
for group in client.users.groups.list():
    print(group.display_name)
members = client.users.groups.members("Engineering")
```

### API Tokens

```python
from datetime import datetime

for token in client.tokens.list():
    print(token.name)

# The secret is returned exactly once — store it securely
new_token = client.tokens.create(
    "ci-pipeline",
    [{"endpoint": "/api/v2/events", "permissions": "r"}],
    expires=datetime(2027, 1, 1),
)
client.tokens.reissue(new_token.id)  # rotate the secret
client.tokens.revoke(new_token.id)  # PATCH {"operation": "revoke"} — the record stays
client.tokens.delete(new_token.id)  # DELETE — a separate operation
```

### Notification Templates

```python
for template in client.notifications.list_templates():
    print(template.name)

template = client.notifications.create_template(
    "dlp-block",
    title="Action Blocked",
    message="This action violates policy.",
    ack_button_text="OK",
)
```

Both template creation and update require `name`, `title`, and `message`.
Template type, button rules, and field lengths are validated before the request.

### IPS (Intrusion Prevention)

```python
status = client.ips.status()
signatures = client.ips.list_signatures()
hits = client.ips.search_signatures(cvss_severity=["critical"], limit=50)
mode = client.ips.get_alert_only_mode()
client.ips.update_allowlist(domain=["intranet.example.com"])
```

### DEM / ADEM (Digital Experience Monitoring)

```python
from datetime import datetime

# Application probes. An app probe follows an app named by app_name
# (predefined) or app_id (custom); frequency is in minutes. There is no
# target, protocol, or interval — passing one raises ValidationError.
for probe in client.dem.probes.list().get("data", []):
    print(probe)

client.dem.probes.create(
    "slack-probe",
    frequency=5,
    entity={"user": ["alice@example.com"], "group": [], "ou": []},
    os=["windows", "mac"],
    device_classification=["managed"],
    app_name="Slack",
)

# Alert-rule reads. Creation criteria need service-specific validation because
# the contract's threshold alternatives overlap. The SDK retains criteria= and
# metric/threshold for compatibility, but cannot certify those threshold shapes.
rules = client.dem.alert_rules.list(category="User Experience", enabled=True)

# DEM alerts
alerts = client.dem.alerts.search(severity=["high"], limit=50)

# Ad-hoc query. begin/end go out as {"absolute": "<RFC 3339>"} objects; a
# bare int is read as epoch milliseconds. agent_status and client_status
# are state sources — read them with get_states(), not get_data().
data = client.dem.query.get_data(
    "ux_score",
    select=["user", "exp_score"],
    begin=datetime(2026, 1, 1),
    end=datetime(2026, 1, 2),
)

# ADEM per-user experience (epoch seconds on the wire)
info = client.dem.users.info(
    "alice@example.com",
    start_time=datetime(2026, 1, 1),
    end_time=datetime(2026, 1, 2),
)
```

### Security Services (ATP, NSIQ, RBI, DSPM, SPM)

```python
# Advanced Threat Protection. The sandbox upload is multipart with a
# required scantype; the file must be a ZipCrypto archive (password
# "infected") holding one exe/pdf/doc/xls/ppt/rtf member of at most 16 MB.
result = client.atp.scan_url("http://example.com")
job = client.atp.scan_file_path("/path/to/sample.zip")
report = client.atp.get_report(job["jobid"])

# NSIQ — URL categorization, recategorization, IOC lookup
client.nsiq.url_lookup("http://example.com")
client.nsiq.lookup_iocs(["<sha256>"])

# Remote Browser Isolation — templates and CDR config. restore_cdr() is a
# PUT that empties the CDR config; test_cdr_config() is a GET whose
# settings travel as query values, with an inline api_key sent as the
# X-CDR-Api-Key header.
client.rbi.list_templates(limit=10)
client.rbi.test_cdr_config(vendor="votiro", endpoint_url="https://votiro.example.com")
client.rbi.restore_cdr()

# Data Security Posture Management. list_resources() routes by the resource
# names DspmResource.supported_resource_types() reports. There is no bulk
# connect-by-id: connect_datastore() sends one DataStoreRequest, and
# scan_datastores() loops the single-datastore start-scan operation.
client.dspm.list_resources("databases")
client.dspm.scan_datastores(["datastore-id"])

# SaaS Security Posture Management. recent_changes requires a time range.
client.spm.list_apps()
client.spm.recent_changes(start=1758127874, end=1759127874)
```

## Error Handling

```python
from netskope import (
    NetskopeError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ForbiddenError,
)

try:
    alert = client.alerts.get("nonexistent")
except NotFoundError as e:
    print(f"Not found: {e.message}")
    print(f"Request ID: {e.request_id}")  # for support escalation
except RateLimitError as e:
    print(f"Rate limited — retry after {e.retry_after}s")
except AuthenticationError:
    print("Invalid or expired API token")
except ForbiddenError:
    print("Token lacks required scope")
except NetskopeError as e:
    print(f"SDK error: {e}")
```

An HTTP 2xx is not automatically a success. The SDK raises `APIError` for a
response body that reports failure: `ok: 0` (which covers `ok: false`),
`success: false`, or datasearch's `execution: "FAILED"`, whether that field sits
at the top level or under `status`. A method returning a raw `dict` raises
rather than handing back an envelope the caller has to check.

Not every error comes from an HTTP status. `ValidationError` rejects bad input
before a request is built, `ResponseValidationError` reports a response the SDK
cannot decode, `PaginationError` reports a page it cannot continue from, and
`ClientClosedError` is raised when the client is already closed. All of them
derive from `NetskopeError` and import from `netskope` or `netskope.exceptions`.

## Contract Source

Request and response shapes in this SDK are checked against a pinned revision
of the Netskope API gateway contract — the internal OpenAPI definitions the
gateway is built from. Those definitions are not public, so this repository
carries neither a copy nor a link to them.

The conformance checks live in `tests/unit/resources/test_spec_*.py`
(`test_spec_events.py`, `test_spec_identity.py`, `test_spec_infra.py`,
`test_spec_services.py`). Each assertion cites the contract file and line the
shape comes from, for example:

```python
def test_transaction_metrics_sends_only_hours(client: NetskopeClient) -> None:
    """transaction_metrics.yaml:74-83 declares `hours` as the only parameter."""
```

Those citations are the record of why a parameter is spelled the way it is, why
a field was removed from a model, and why an argument is rejected before a
request is built. Response fixtures use the contract's own example values
wherever it publishes them. Every test runs against `respx` mocks on
`example.goskope.com`; none of them reaches a live tenant.

## Context Managers

```python
# Sync
with NetskopeClient(tenant="...", api_token="...") as client:
    alerts = client.alerts.list().to_list()

# Async
async with AsyncNetskopeClient(tenant="...", api_token="...") as client:
    alerts = await client.alerts.list().to_list()
```

## Logging

```python
import logging

# See all requests at INFO level
logging.getLogger("netskope").setLevel(logging.INFO)

# Full request/response debug (tokens redacted)
logging.getLogger("netskope").setLevel(logging.DEBUG)
```

## Requirements

- Python 3.11+
- `httpx` >= 0.27
- `pydantic` >= 2.0

## Development

The repository is managed with [uv](https://docs.astral.sh/uv/) and ships a
committed `uv.lock`, so every environment resolves to the same versions.

```bash
uv sync                              # Create .venv with runtime + dev dependencies
uv run pytest                        # Run the test suite
uv run ruff check . --fix            # Lint
uv run ruff format .                 # Format
uv run ty check                      # Type check src/
uv build && ./scripts/smoke-dist.sh  # Build the wheel and sdist, install each into a clean venv
```

CI runs the same checks on Python 3.11 and 3.14 for every pull request. Without
uv, `pip install -e . --group dev` installs the same dependency group.

## License

MIT
