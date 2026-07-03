"""Steering resource — traffic steering, IPSec tunnels, and managed devices.

Example::

    # Get NPA steering config
    config = client.steering.get_config("npa")

    # List PoPs
    for pop in client.steering.list_pops():
        print(f"{pop.name} — {pop.region}")

    # Create an IPSec tunnel
    tunnel = client.steering.create_tunnel(
        site="NYC-Office",
        pops=["US-East1"],
        psk="...",
        srcidentity="vpn@example.com",
    )
"""

from __future__ import annotations

from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.exceptions import ValidationError
from netskope.models.devices import Device
from netskope.models.infrastructure import IPSecTunnel, Pop
from netskope.models.steering import SteeringConfig
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list

_CLIENT_CONFIG_PATH = "/api/v2/steering/globalconfig/clientconfiguration"

# Each config scope has its own endpoint.  Note that ``publishers`` does NOT
# live under ``clientconfiguration`` — it has a dedicated globalconfig path.
_SCOPE_PATHS: dict[str, str] = {
    "npa": f"{_CLIENT_CONFIG_PATH}/npa",
    "nsc": f"{_CLIENT_CONFIG_PATH}/nsc",
    "ztna": f"{_CLIENT_CONFIG_PATH}/ztna",
    "publishers": "/api/v2/steering/globalconfig/publishers",
}

_POPS_PATH = "/api/v2/steering/ipsec/pops"
_TUNNELS_PATH = "/api/v2/steering/ipsec/tunnels"
_DEVICES_PATH = "/api/v2/steering/devices"

TUNNEL_BANDWIDTHS = (50, 100, 150, 200, 250, 1000)
TUNNEL_ENCRYPTIONS = ("AES128-CBC", "AES256-CBC", "AES256-GCM")
_TUNNEL_STATUSES = ("up", "down")


def _extract_pops(body: dict[str, Any]) -> list[dict[str, Any]]:
    return extract_list(body, "pops")


def _extract_tunnels(body: dict[str, Any]) -> list[dict[str, Any]]:
    return extract_list(body, "tunnels")


def _extract_devices(body: dict[str, Any]) -> list[dict[str, Any]]:
    return extract_list(body, "devices")


def _scope_path(scope: str) -> str:
    path = _SCOPE_PATHS.get(scope)
    if path is None:
        raise ValidationError(
            f"Invalid scope {scope!r}. Must be one of: {', '.join(sorted(_SCOPE_PATHS))}"
        )
    return path


def _validate_bandwidth(bandwidth: int) -> None:
    if bandwidth not in TUNNEL_BANDWIDTHS:
        raise ValidationError(
            f"Invalid bandwidth {bandwidth!r}. "
            f"Must be one of: {', '.join(str(b) for b in TUNNEL_BANDWIDTHS)}"
        )


def _validate_encryption(encryption: str) -> None:
    if encryption not in TUNNEL_ENCRYPTIONS:
        raise ValidationError(
            f"Invalid encryption {encryption!r}. Must be one of: {', '.join(TUNNEL_ENCRYPTIONS)}"
        )


def _build_pops_params(
    name: str | None,
    region: str | None,
    country: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if name is not None:
        params["name"] = name
    if region is not None:
        params["region"] = region
    if country is not None:
        params["country"] = country
    return params


def _build_tunnels_params(
    status: str | None,
    site: str | None,
    pop: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if status is not None:
        normalized = status.lower()
        if normalized not in _TUNNEL_STATUSES:
            raise ValidationError(
                f"Invalid status {status!r}. Must be one of: {', '.join(_TUNNEL_STATUSES)}"
            )
        params["status"] = normalized
    if site is not None:
        params["site"] = site
    if pop is not None:
        params["pop"] = pop
    return params


def _build_create_tunnel_payload(
    site: str,
    pops: list[str],
    psk: str,
    srcidentity: str,
    bandwidth: int,
    encryption: str,
    enabled: bool,
    vendor: str | None,
    notes: str | None,
) -> dict[str, Any]:
    _validate_bandwidth(bandwidth)
    _validate_encryption(encryption)
    if not pops:
        raise ValidationError("pops must contain at least one PoP name.")
    payload: dict[str, Any] = {
        "site": site,
        "pops": list(pops),
        "psk": psk,
        "srcidentity": srcidentity,
        "bandwidth": bandwidth,
        "encryption": encryption,
        "enabled": enabled,
    }
    if vendor is not None:
        payload["vendor"] = vendor
    if notes is not None:
        payload["notes"] = notes
    return payload


def _build_update_tunnel_payload(
    site: str | None,
    pops: list[str] | None,
    psk: str | None,
    bandwidth: int | None,
    encryption: str | None,
    enabled: bool | None,
    notes: str | None,
) -> dict[str, Any]:
    if bandwidth is not None:
        _validate_bandwidth(bandwidth)
    if encryption is not None:
        _validate_encryption(encryption)
    payload: dict[str, Any] = {}
    if site is not None:
        payload["site"] = site
    if pops is not None:
        if not pops:
            raise ValidationError("pops must contain at least one PoP name.")
        payload["pops"] = list(pops)
    if psk is not None:
        payload["psk"] = psk
    if bandwidth is not None:
        payload["bandwidth"] = bandwidth
    if encryption is not None:
        payload["encryption"] = encryption
    if enabled is not None:
        payload["enabled"] = enabled
    if notes is not None:
        payload["notes"] = notes
    if not payload:
        raise ValidationError(
            "No update fields provided. Specify at least one of: site, pops, psk, "
            "bandwidth, encryption, enabled, notes."
        )
    return payload


class SteeringResource(SyncResource):
    """Synchronous interface to steering configuration, IPSec, and device APIs."""

    def get_config(self, scope: str = "npa") -> SteeringConfig:
        """Get global steering configuration.

        Args:
            scope: Configuration scope (``"npa"``, ``"nsc"``, ``"ztna"``, or
                ``"publishers"``).  Client-configuration scopes route to
                ``/steering/globalconfig/clientconfiguration/{scope}``;
                ``"publishers"`` routes to ``/steering/globalconfig/publishers``.
        """
        body = self._get(_scope_path(scope))
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
        body = self._patch(_scope_path(scope), json=settings)
        return SteeringConfig.model_validate(body)

    def list_pops(
        self,
        *,
        name: str | None = None,
        region: str | None = None,
        country: str | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[Pop]:
        """List Points of Presence (PoPs) where IPSec tunnels can terminate.

        Args:
            name: Filter PoPs by (partial) name.
            region: Filter PoPs by ISO-3166 region code (e.g. ``"US"``).
            country: Filter PoPs by ISO-3166 country code (e.g. ``"DE"``).
            page_size: Results per page.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_POPS_PATH,
            params=_build_pops_params(name, region, country),
            model=Pop,
            page_size=page_size,
            extract=_extract_pops,
        )

    def list_tunnels(
        self,
        *,
        status: str | None = None,
        site: str | None = None,
        pop: str | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[IPSecTunnel]:
        """List IPSec tunnels with optional filtering.

        Args:
            status: Filter by operational status — ``"up"`` or ``"down"``.
            site: Filter by site (tunnel) name.
            pop: Filter by the PoP the tunnel terminates at.
            page_size: Results per page.

        Raises:
            netskope.exceptions.ValidationError: If *status* is not
                ``"up"`` or ``"down"``.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_TUNNELS_PATH,
            params=_build_tunnels_params(status, site, pop),
            model=IPSecTunnel,
            page_size=page_size,
            extract=_extract_tunnels,
        )

    def get_tunnel(self, tunnel_id: int) -> IPSecTunnel:
        """Get an IPSec tunnel by ID."""
        body = self._get(f"{_TUNNELS_PATH}/{tunnel_id}")
        return IPSecTunnel.model_validate(extract_item(body))

    def create_tunnel(
        self,
        site: str,
        pops: list[str],
        psk: str,
        srcidentity: str,
        *,
        bandwidth: int = 100,
        encryption: str = "AES256-CBC",
        enabled: bool = True,
        vendor: str | None = None,
        notes: str | None = None,
    ) -> IPSecTunnel:
        """Create an IPSec tunnel (POST).

        Args:
            site: Unique tunnel/site name (e.g. ``"NYC-Office-Primary"``).
            pops: PoP names where the tunnel terminates (at least one).
            psk: Pre-shared key for IKE authentication.
            srcidentity: IKE source identity presented by the CPE device.
            bandwidth: Maximum bandwidth in Mbps — one of 50, 100, 150, 200,
                250, 1000 (default 100).
            encryption: One of ``AES128-CBC``, ``AES256-CBC``, ``AES256-GCM``
                (default ``AES256-CBC``).
            enabled: Whether the tunnel is enabled after creation.
            vendor: Optional CPE vendor name.
            notes: Optional free-text notes.

        Raises:
            netskope.exceptions.ValidationError: If *bandwidth*,
                *encryption*, or *pops* is invalid.
        """
        payload = _build_create_tunnel_payload(
            site, pops, psk, srcidentity, bandwidth, encryption, enabled, vendor, notes
        )
        body = self._post(_TUNNELS_PATH, json=payload)
        return IPSecTunnel.model_validate(extract_item(body))

    def update_tunnel(
        self,
        tunnel_id: int,
        *,
        site: str | None = None,
        pops: list[str] | None = None,
        psk: str | None = None,
        bandwidth: int | None = None,
        encryption: str | None = None,
        enabled: bool | None = None,
        notes: str | None = None,
    ) -> IPSecTunnel:
        """Update an IPSec tunnel (PATCH) — only provided fields are sent.

        Args:
            tunnel_id: Numeric ID of the tunnel to update.
            site: New tunnel/site name.
            pops: New PoP assignment (at least one name).
            psk: New pre-shared key.
            bandwidth: New bandwidth in Mbps (50/100/150/200/250/1000).
            encryption: New encryption algorithm.
            enabled: Enable or disable the tunnel.
            notes: New free-text notes.

        Raises:
            netskope.exceptions.ValidationError: If a value is invalid or
                no update fields were provided.
        """
        payload = _build_update_tunnel_payload(
            site, pops, psk, bandwidth, encryption, enabled, notes
        )
        body = self._patch(f"{_TUNNELS_PATH}/{tunnel_id}", json=payload)
        return IPSecTunnel.model_validate(extract_item(body))

    def delete_tunnel(self, tunnel_id: int) -> None:
        """Delete an IPSec tunnel.  Irreversible — traffic is disrupted immediately.

        Args:
            tunnel_id: Numeric ID of the tunnel to delete.
        """
        self._delete(f"{_TUNNELS_PATH}/{tunnel_id}")

    def list_devices(self, *, page_size: int = 100) -> SyncPaginatedResponse[Device]:
        """List managed devices enrolled in the tenant.

        Queries ``GET /api/v2/steering/devices``.  Not every tenant exposes
        this endpoint; when unavailable the API returns 404 and a
        :class:`~netskope.exceptions.NotFoundError` propagates.  For those
        tenants, client status data is available via ``client.events``
        (the ``clientstatus`` event type) instead.

        Args:
            page_size: Results per page.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_DEVICES_PATH,
            params={},
            model=Device,
            page_size=page_size,
            extract=_extract_devices,
        )


class AsyncSteeringResource(AsyncResource):
    """Asynchronous interface to steering configuration, IPSec, and device APIs."""

    async def get_config(self, scope: str = "npa") -> SteeringConfig:
        """Get global steering configuration.

        See :meth:`SteeringResource.get_config`.
        """
        body = await self._get(_scope_path(scope))
        return SteeringConfig.model_validate(body)

    async def update_config(
        self,
        scope: str = "npa",
        *,
        settings: dict[str, Any],
    ) -> SteeringConfig:
        """Update global steering configuration (PATCH)."""
        body = await self._patch(_scope_path(scope), json=settings)
        return SteeringConfig.model_validate(body)

    def list_pops(
        self,
        *,
        name: str | None = None,
        region: str | None = None,
        country: str | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[Pop]:
        """List Points of Presence (PoPs).  See :meth:`SteeringResource.list_pops`."""
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_POPS_PATH,
            params=_build_pops_params(name, region, country),
            model=Pop,
            page_size=page_size,
            extract=_extract_pops,
        )

    def list_tunnels(
        self,
        *,
        status: str | None = None,
        site: str | None = None,
        pop: str | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[IPSecTunnel]:
        """List IPSec tunnels.  See :meth:`SteeringResource.list_tunnels`."""
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_TUNNELS_PATH,
            params=_build_tunnels_params(status, site, pop),
            model=IPSecTunnel,
            page_size=page_size,
            extract=_extract_tunnels,
        )

    async def get_tunnel(self, tunnel_id: int) -> IPSecTunnel:
        """Get an IPSec tunnel by ID."""
        body = await self._get(f"{_TUNNELS_PATH}/{tunnel_id}")
        return IPSecTunnel.model_validate(extract_item(body))

    async def create_tunnel(
        self,
        site: str,
        pops: list[str],
        psk: str,
        srcidentity: str,
        *,
        bandwidth: int = 100,
        encryption: str = "AES256-CBC",
        enabled: bool = True,
        vendor: str | None = None,
        notes: str | None = None,
    ) -> IPSecTunnel:
        """Create an IPSec tunnel.  See :meth:`SteeringResource.create_tunnel`."""
        payload = _build_create_tunnel_payload(
            site, pops, psk, srcidentity, bandwidth, encryption, enabled, vendor, notes
        )
        body = await self._post(_TUNNELS_PATH, json=payload)
        return IPSecTunnel.model_validate(extract_item(body))

    async def update_tunnel(
        self,
        tunnel_id: int,
        *,
        site: str | None = None,
        pops: list[str] | None = None,
        psk: str | None = None,
        bandwidth: int | None = None,
        encryption: str | None = None,
        enabled: bool | None = None,
        notes: str | None = None,
    ) -> IPSecTunnel:
        """Update an IPSec tunnel (PATCH).  See :meth:`SteeringResource.update_tunnel`."""
        payload = _build_update_tunnel_payload(
            site, pops, psk, bandwidth, encryption, enabled, notes
        )
        body = await self._patch(f"{_TUNNELS_PATH}/{tunnel_id}", json=payload)
        return IPSecTunnel.model_validate(extract_item(body))

    async def delete_tunnel(self, tunnel_id: int) -> None:
        """Delete an IPSec tunnel.  Irreversible."""
        await self._delete(f"{_TUNNELS_PATH}/{tunnel_id}")

    def list_devices(self, *, page_size: int = 100) -> AsyncPaginatedResponse[Device]:
        """List managed devices.  See :meth:`SteeringResource.list_devices`."""
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_DEVICES_PATH,
            params={},
            model=Device,
            page_size=page_size,
            extract=_extract_devices,
        )
