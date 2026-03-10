"""Steering resource — traffic steering and IPSec configuration.

Example::

    # Get NPA steering config
    config = client.steering.get_config("npa")

    # List PoPs
    for pop in client.steering.list_pops():
        print(f"{pop.name} — {pop.region}")
"""

from __future__ import annotations

from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.models.infrastructure import IPSecTunnel, Pop
from netskope.models.steering import SteeringConfig
from netskope.resources._base import AsyncResource, SyncResource

_CONFIG_PATH = "/api/v2/steering/globalconfig/clientconfiguration"
_POPS_PATH = "/api/v2/steering/ipsec/pops"
_TUNNELS_PATH = "/api/v2/steering/ipsec/tunnels"


def _extract_pops(body: dict[str, Any]) -> list[dict[str, Any]]:
    data = body.get("data", [])
    if isinstance(data, dict):
        pops = data.get("pops", [])
        if isinstance(pops, list):
            return pops
    if isinstance(data, list):
        return data
    return []


def _extract_tunnels(body: dict[str, Any]) -> list[dict[str, Any]]:
    data = body.get("data", [])
    if isinstance(data, dict):
        tunnels = data.get("tunnels", [])
        if isinstance(tunnels, list):
            return tunnels
    if isinstance(data, list):
        return data
    return []


_VALID_SCOPES = frozenset({"npa", "nsc", "ztna", "publishers"})


def _validate_scope(scope: str) -> None:
    if scope not in _VALID_SCOPES:
        from netskope.exceptions import ValidationError

        raise ValidationError(
            f"Invalid scope {scope!r}. Must be one of: {', '.join(sorted(_VALID_SCOPES))}"
        )


class SteeringResource(SyncResource):
    """Synchronous interface to steering configuration and IPSec APIs."""

    def get_config(self, scope: str = "npa") -> SteeringConfig:
        """Get global steering configuration.

        Args:
            scope: Configuration scope (``"npa"``, ``"nsc"``, ``"ztna"``, or ``"publishers"``).
        """
        _validate_scope(scope)
        body = self._get(f"{_CONFIG_PATH}/{scope}")
        return SteeringConfig.model_validate(body)

    def update_config(
        self,
        scope: str = "npa",
        *,
        settings: dict[str, Any],
    ) -> SteeringConfig:
        """Update global steering configuration (PATCH).

        Args:
            scope: Configuration scope.
            settings: Key-value settings to update.
        """
        _validate_scope(scope)
        body = self._patch(f"{_CONFIG_PATH}/{scope}", json=settings)
        return SteeringConfig.model_validate(body)

    def list_pops(self, *, page_size: int = 100) -> SyncPaginatedResponse[Pop]:
        """List all Points of Presence (PoPs)."""
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_POPS_PATH,
            params={},
            model=Pop,
            page_size=page_size,
            extract=_extract_pops,
        )

    def list_tunnels(self, *, page_size: int = 100) -> SyncPaginatedResponse[IPSecTunnel]:
        """List all IPSec tunnels."""
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_TUNNELS_PATH,
            params={},
            model=IPSecTunnel,
            page_size=page_size,
            extract=_extract_tunnels,
        )

    def get_tunnel(self, tunnel_id: int) -> IPSecTunnel:
        """Get an IPSec tunnel by ID."""
        body = self._get(f"{_TUNNELS_PATH}/{tunnel_id}")
        data = body.get("data", body)
        return IPSecTunnel.model_validate(data)


class AsyncSteeringResource(AsyncResource):
    """Asynchronous interface to steering and IPSec APIs."""

    async def get_config(self, scope: str = "npa") -> SteeringConfig:
        _validate_scope(scope)
        body = await self._get(f"{_CONFIG_PATH}/{scope}")
        return SteeringConfig.model_validate(body)

    async def update_config(
        self,
        scope: str = "npa",
        *,
        settings: dict[str, Any],
    ) -> SteeringConfig:
        _validate_scope(scope)
        body = await self._patch(f"{_CONFIG_PATH}/{scope}", json=settings)
        return SteeringConfig.model_validate(body)

    def list_pops(self, *, page_size: int = 100) -> AsyncPaginatedResponse[Pop]:
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_POPS_PATH,
            params={},
            model=Pop,
            page_size=page_size,
            extract=_extract_pops,
        )

    def list_tunnels(self, *, page_size: int = 100) -> AsyncPaginatedResponse[IPSecTunnel]:
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_TUNNELS_PATH,
            params={},
            model=IPSecTunnel,
            page_size=page_size,
            extract=_extract_tunnels,
        )

    async def get_tunnel(self, tunnel_id: int) -> IPSecTunnel:
        body = await self._get(f"{_TUNNELS_PATH}/{tunnel_id}")
        data = body.get("data", body)
        return IPSecTunnel.model_validate(data)
