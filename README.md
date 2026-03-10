# Netskope Python SDK

The official Netskope Python SDK — a modern, typed, and intuitive interface to the Netskope REST API v2.

[![PyPI](https://img.shields.io/pypi/v/netskope-py-sdk)](https://pypi.org/project/netskope-py-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/netskope-py-sdk)](https://pypi.org/project/netskope-py-sdk/)
[![License](https://img.shields.io/pypi/l/netskope-py-sdk)](https://github.com/netSkopeoss/netskope-py-sdk/blob/main/LICENSE)

## Why This SDK?

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

### Client Options

```python
client = NetskopeClient(
    tenant="mycompany.goskope.com",
    api_token="...",
    timeout=60.0,           # request timeout (seconds)
    max_retries=5,          # retry count for transient errors
    backoff_factor=1.0,     # exponential backoff base
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
