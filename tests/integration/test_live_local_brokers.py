"""Live integration tests for the local brokers API.

Read-only coverage per the safety checklist in
``tests/integration/conftest.py``: no broker create/update/delete, no config
mutation, and no registration tokens are exercised against live tenants.
Credentials come from environment variables only.

Run with: pytest tests/integration/test_live_local_brokers.py -m integration -v
"""

from __future__ import annotations

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.models.infrastructure import LocalBroker, LocalBrokerConfig

from .conftest import skip_if_unavailable


@pytest.mark.integration
class TestLocalBrokersIntegration:
    """Live, read-only tests for the local brokers API."""

    def test_list_local_brokers(self, client: NetskopeClient) -> None:
        """List local brokers and get typed responses."""
        try:
            brokers = client.npa.local_brokers.list()
        except APIError as exc:
            skip_if_unavailable(exc, "Local brokers API")
            return
        assert isinstance(brokers, list)
        if brokers:
            assert isinstance(brokers[0], LocalBroker)
            assert brokers[0].id is not None

    def test_get_local_broker(self, client: NetskopeClient) -> None:
        """Fetch the first listed broker by id (read-only)."""
        try:
            brokers = client.npa.local_brokers.list()
        except APIError as exc:
            skip_if_unavailable(exc, "Local brokers API")
            return
        if not brokers or brokers[0].id is None:
            pytest.skip("No local brokers configured on this tenant")
        broker = client.npa.local_brokers.get(brokers[0].id)
        assert isinstance(broker, LocalBroker)
        assert broker.id == brokers[0].id

    def test_get_config(self, client: NetskopeClient) -> None:
        """Fetch the tenant-wide broker configuration (read-only)."""
        try:
            config = client.npa.local_brokers.get_config()
        except APIError as exc:
            skip_if_unavailable(exc, "Local broker config API")
            return
        assert isinstance(config, LocalBrokerConfig)
