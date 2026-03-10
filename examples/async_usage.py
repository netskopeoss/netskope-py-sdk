"""Netskope SDK — Async Usage Example.

Demonstrates how to use the async client for high-throughput operations.

Usage:
    export NETSKOPE_TENANT="mycompany.goskope.com"
    export NETSKOPE_API_TOKEN="your-v2-token"
    python async_usage.py
"""

from __future__ import annotations

import asyncio

from netskope import AsyncNetskopeClient


async def main() -> None:
    async with AsyncNetskopeClient() as client:
        print(f"Connected to {client.tenant}")

        # Async iteration — pages fetched on demand
        count = 0
        async for alert in client.alerts.list(page_size=10):
            print(f"Alert: {alert.alert_name} — {alert.severity}")
            count += 1
            if count >= 10:
                break

        # Fetch all at once (async)
        publishers = await client.publishers.list(page_size=50).to_list(max_items=50)
        print(f"\nPublishers: {len(publishers)}")
        for pub in publishers:
            print(f"  {pub.publisher_name}: {pub.status}")


if __name__ == "__main__":
    asyncio.run(main())
