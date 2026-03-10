"""Netskope SDK — Event Monitoring Example.

Demonstrates querying events across multiple types with time filtering,
suitable for SIEM integration or security monitoring scripts.

Usage:
    export NETSKOPE_TENANT="mycompany.goskope.com"
    export NETSKOPE_API_TOKEN="your-v2-token"
    python event_monitoring.py
"""

from __future__ import annotations

from datetime import datetime, timedelta

from netskope import NetskopeClient
from netskope.models.events import EventType


def main() -> None:
    client = NetskopeClient()
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)

    event_types = [
        EventType.ALERT,
        EventType.APPLICATION,
        EventType.NETWORK,
        EventType.PAGE,
    ]

    for event_type in event_types:
        print(f"\n{'=' * 60}")
        print(f" {event_type.upper()} Events (last 24h)")
        print(f"{'=' * 60}")

        events = client.events.list(
            event_type,
            start_time=start_time,
            end_time=end_time,
            page_size=10,
        ).to_list(max_items=10)

        if not events:
            print("  No events found")
            continue

        for event in events:
            parts = [f"  {event.user or 'unknown'}"]
            if event.app:
                parts.append(f"app={event.app}")
            if event.activity:
                parts.append(f"activity={event.activity}")
            if event.action:
                parts.append(f"action={event.action}")
            print(" | ".join(parts))

    client.close()


if __name__ == "__main__":
    main()
