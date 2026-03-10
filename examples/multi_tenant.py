"""Netskope SDK — Multi-Tenant Example.

Demonstrates managing multiple Netskope tenants simultaneously.

Usage:
    export PROD_TENANT="prod.goskope.com"
    export PROD_TOKEN="prod-token"
    export STAGING_TENANT="staging.goskope.com"
    export STAGING_TOKEN="staging-token"
    python multi_tenant.py
"""

from __future__ import annotations

import os

from netskope import NetskopeClient


def main() -> None:
    prod = NetskopeClient(
        tenant=os.environ["PROD_TENANT"],
        api_token=os.environ["PROD_TOKEN"],
    )
    staging = NetskopeClient(
        tenant=os.environ["STAGING_TENANT"],
        api_token=os.environ["STAGING_TOKEN"],
    )

    # Compare alert counts
    prod_alerts = prod.alerts.list(page_size=1).to_list(max_items=1)
    staging_alerts = staging.alerts.list(page_size=1).to_list(max_items=1)

    print(f"Production ({prod.tenant}): alerts available")
    print(f"Staging ({staging.tenant}): alerts available")

    # Compare publisher counts
    prod_pubs = prod.publishers.list().to_list()
    staging_pubs = staging.publishers.list().to_list()
    print(f"\nProduction publishers: {len(prod_pubs)}")
    print(f"Staging publishers: {len(staging_pubs)}")

    prod.close()
    staging.close()


if __name__ == "__main__":
    main()
