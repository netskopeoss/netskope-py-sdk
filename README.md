# Netskope Python SDK

**[Read the documentation](https://netskopeoss.github.io/netskope-py-sdk/)**

The official Netskope Python SDK — a modern, typed, and intuitive interface to the Netskope REST API v2.

[![PyPI](https://img.shields.io/pypi/v/netskope_py_sdk)](https://pypi.org/project/netskope-py-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/netskope_py_sdk)](https://pypi.org/project/netskope-py-sdk/)
[![License](https://img.shields.io/pypi/l/netskope_py_sdk)](https://github.com/netSkopeoss/netskope-py-sdk/blob/main/LICENSE)

## Why This SDK?

- **Broad API coverage** — 24 resource namespaces spanning alerts, events, incidents, SCIM, publishers, private apps, steering, URL lists, NPA policy, DNS, CCI, devices, enrollment, RBAC, user management, API tokens, notifications, IPS, DEM/ADEM, and the ATP/NSIQ/RBI/DSPM/SPM security services
- **Hierarchical namespaces** — `client.alerts.list()`, `client.scim.users.create()` — explore the entire API through autocomplete
- **Automatic pagination** — just iterate, no page loops needed
- **Full type safety** — Pydantic v2 models with complete type annotations
- **Sync + Async** — choose the right client for your use case
- **Automatic retries** — exponential backoff with jitter for transient errors
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
    timeout=60.0,           # request timeout (seconds)
    max_retries=5,          # retry count for transient errors
    backoff_factor=1.0,     # exponential backoff base
    verify=True,            # TLS verification (see below)
)
```

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

# Supported types: alert, application, network, page, incident,
#   audit, infrastructure, clientstatus, epdlp, transaction
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

### Publishers

```python
# List all publishers
for pub in client.publishers.list():
    print(f"{pub.publisher_name}: {pub.status} ({pub.apps_count} apps)")

# Create a publisher
new_pub = client.publishers.create(name="aws-us-east-1")

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

### Private Apps (ZTNA)

```python
# List private apps
for app in client.private_apps.list():
    print(f"{app.app_name} → {app.host}:{app.port}")

# Create a private app
app = client.private_apps.create(
    name="internal-dashboard",
    host="10.0.0.5",
    port="443",
    protocols=["TCP"],
    publisher_ids=[1, 2],
)

# Update (PATCH) and manage the app's publishers
client.private_apps.update(app.id, host="10.0.0.6")
client.private_apps.add_publishers([app.id], [3])

# Tags
for tag in client.private_apps.tags.list():
    print(tag.tag_name)
new_tags = client.private_apps.tags.create(app.id, ["prod"])
```

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

# Groups
for group in client.scim.groups.list():
    print(f"{group.display_name}: {len(group.members)} members")
```

### Incidents

```python
# List incidents
for incident in client.incidents.list(query='severity eq "critical"'):
    print(incident.incident_id, incident.severity, incident.status)

# Get user risk score
uci = client.incidents.get_uci("user@example.com")
print(f"Risk score: {uci.score}")

# Get UBA anomalies
anomalies = client.incidents.get_anomalies(["user@example.com"])

# Incident notes
notes = client.incidents.list_notes("dlp-incident-id")
note = client.incidents.add_note("dlp-incident-id", "Investigated — false positive")
client.incidents.delete_note("dlp-incident-id", note.note_id)
```

### Steering & Infrastructure

```python
# Get steering config
config = client.steering.get_config("npa")

# List PoPs
for pop in client.steering.list_pops():
    print(f"{pop.name} — {pop.region}")

# List IPSec tunnels
for tunnel in client.steering.list_tunnels():
    print(f"{tunnel.name}: {tunnel.status}")
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

# Domain inheritance groups and reference data
for group in client.dns.inheritance_groups.list():
    print(group.name)
categories = client.dns.list_domain_categories()
record_types = client.dns.list_record_types()
```

### CCI (Cloud Confidence Index)

```python
# Look up risk data for an exact app name
data = client.cci.lookup_app("Dropbox", ccl="high")

# Custom app tags
for tag in client.cci.tags.list():
    print(tag)
client.cci.tags.create(...)

attributes = client.cci.supported_attributes()
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
# Client enrollment token sets
for token_set in client.enrollment.list_token_sets():
    print(token_set)
new_set = client.enrollment.create_token_set(...)
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

### IPS (Intrusion Prevention)

```python
status = client.ips.status()
signatures = client.ips.list_signatures()
mode = client.ips.get_alert_only_mode()
client.ips.update_allowlist(...)
```

### DEM / ADEM (Digital Experience Monitoring)

```python
from datetime import datetime

# Synthetic and network probes
for probe in client.dem.probes.list().get("data", []):
    print(probe)

# ADEM per-user experience
info = client.dem.users.info(
    "alice@example.com",
    start_time=datetime(2026, 1, 1),
    end_time=datetime(2026, 1, 2),
)

# DEM alerts and rules
alerts = client.dem.alerts.search(...)
rules = client.dem.alert_rules.list()
```

### Security Services (ATP, NSIQ, RBI, DSPM, SPM)

```python
# Advanced Threat Protection — file/URL scanning
result = client.atp.scan_url("http://example.com")
client.atp.scan_file_path("/path/to/sample.exe")

# NSIQ — URL categorization, recategorization, IOC lookup
client.nsiq.url_lookup("http://example.com")
client.nsiq.lookup_iocs(["<sha256>"])

# Remote Browser Isolation — templates and CDR config
client.rbi.list_templates()

# Data Security Posture Management — resource inventory
client.dspm.list_resources("databases")

# SaaS Security Posture Management — app posture
client.spm.list_apps()
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

## License

MIT
