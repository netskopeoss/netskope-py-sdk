"""Netskope SDK — Quick Start Example.

This example demonstrates the core features of the Netskope Python SDK:
- Client initialization
- Listing alerts with automatic pagination
- Querying events by type
- Managing URL lists
- Listing publishers
- Error handling

Prerequisites:
    pip install netskope-py-sdk

Usage:
    export NETSKOPE_TENANT="mycompany.goskope.com"
    export NETSKOPE_API_TOKEN="your-v2-token"
    python quickstart.py
"""

from __future__ import annotations

from netskope import NetskopeClient
from netskope.exceptions import AuthenticationError, NotFoundError, RateLimitError


def main() -> None:
    # Create a client — reads from env vars by default
    client = NetskopeClient()
    print(f"Connected to {client.tenant} (SDK v{client.version})")

    # ── Alerts ──────────────────────────────────────────────────
    print("\n📋 Recent Alerts:")
    for alert in client.alerts.list(page_size=5).to_list(max_items=5):
        print(f"  {alert.alert_name} | {alert.severity} | {alert.user}")

    # ── Events ──────────────────────────────────────────────────
    print("\n📊 Recent Application Events:")
    for event in client.events.list("application", page_size=5).to_list(max_items=5):
        print(f"  {event.user} → {event.app} ({event.activity})")

    # ── Publishers ──────────────────────────────────────────────
    print("\n🏢 Publishers:")
    for pub in client.publishers.list(page_size=5).to_list(max_items=5):
        print(f"  {pub.publisher_name}: {pub.status} ({pub.apps_count} apps)")

    # ── URL Lists ───────────────────────────────────────────────
    print("\n🔗 URL Lists:")
    for url_list in client.url_lists.list(page_size=5).to_list(max_items=5):
        print(f"  {url_list.name}: {len(url_list.urls)} entries")

    # ── Error Handling ──────────────────────────────────────────
    print("\n🛡️ Error Handling Demo:")
    try:
        client.alerts.get("nonexistent-id")
    except NotFoundError as e:
        print(f"  NotFoundError caught: {e.message}")
    except AuthenticationError as e:
        print(f"  AuthenticationError: {e.message}")
    except RateLimitError as e:
        print(f"  RateLimitError: retry after {e.retry_after}s")

    client.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
