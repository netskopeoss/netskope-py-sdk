"""Netskope SDK — URL List Management Example.

Demonstrates CRUD operations on URL allow/block lists and policy deployment.

Usage:
    export NETSKOPE_TENANT="mycompany.goskope.com"
    export NETSKOPE_API_TOKEN="your-v2-token"
    python url_list_management.py
"""

from __future__ import annotations

from netskope import NetskopeClient
from netskope.exceptions import APIError


def main() -> None:
    client = NetskopeClient()

    # List existing URL lists
    print("Current URL Lists:")
    for url_list in client.url_lists.list():
        print(f"  [{url_list.id}] {url_list.name} — {len(url_list.urls)} URLs ({url_list.type})")

    # Create a new URL list (uncomment to run)
    # new_list = client.url_lists.create(
    #     name="sdk-test-blocklist",
    #     urls=["malware.example.com", "phishing.bad.org"],
    #     list_type="exact",
    # )
    # print(f"\nCreated: {new_list.name} (id={new_list.id})")

    # Update (uncomment to run)
    # updated = client.url_lists.update(
    #     new_list.id,
    #     urls=["malware.example.com", "phishing.bad.org", "new-threat.evil.net"],
    # )
    # print(f"Updated: {updated.name} — now {len(updated.urls)} URLs")

    # Deploy pending changes (uncomment to run)
    # result = client.url_lists.deploy()
    # print(f"Deployed: {result}")

    # Cleanup (uncomment to run)
    # client.url_lists.delete(new_list.id)
    # print("Deleted test list")

    client.close()


if __name__ == "__main__":
    main()
