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

from functools import cached_property
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from netskope.core.ids import extract_item, extract_list, validate_id
from netskope.core.pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.core.resource import AsyncResource, SyncResource
from netskope.exceptions import ValidationError
from netskope.models._npa_requests import request_payload
from netskope.models.devices import Device
from netskope.models.infrastructure import IPSecTunnel, Pop
from netskope.models.steering import (
    IPSecTunnelCreate,
    IPSecTunnelPatch,
    SteeringConfig,
    SteeringConfigStatus,
    SteeringSettings,
)
from netskope.resources.shared.npa import parse_item
from netskope.resources.steering.decoder import AsyncSteeringResponses, SteeringResponses
from netskope.resources.steering.paths import (
    _POPS_PATH,
    _TUNNELS_PATH,
    IPSEC_MAX_LIMIT,
    _build_pops_params,
    _build_tunnels_params,
    _scope_path,
)

# Each config scope has its own endpoint.  Note that ``publishers`` does NOT
# live under ``clientconfiguration`` — it has a dedicated globalconfig path.
# ``npa_global_config.yaml`` declares exactly these two configurable scopes
# (``/globalconfig/clientconfiguration/npa`` at :218, ``/globalconfig/publishers``
# at :352); the SDK's former ``nsc`` and ``ztna`` scopes had no path behind them
# and every call on them was a 404.

_DEVICES_PATH = "/api/v2/steering/devices"

# The tiers and ciphers Netskope commonly provisions.  Neither
# ``ipsec_tunnel_request_post`` nor ``_patch`` puts an enum on ``bandwidth``
# (steering/ipsec.yaml:237-238) or ``encryption`` (:241-242), so these name the
# usual values without shutting a tenant out of an unusual one.
TUNNEL_BANDWIDTHS = (50, 100, 150, 200, 250, 1000)
TUNNEL_ENCRYPTIONS = ("AES128-CBC", "AES256-CBC", "AES256-GCM")

# ``GET /ipsec/pops`` and ``GET /ipsec/tunnels`` both declare ``limit`` with
# ``minimum: 0, maximum: 100`` (steering/ipsec.yaml:478-486 and :672-680), the
# only formal bounds in this area.  The accessors admit the whole declared
# range; an iterator needs a positive stride, so 0 would never advance.


def _steering_settings_payload(settings: dict[str, Any]) -> dict[str, Any]:
    """Validate the flag mapping the global-config PATCH declares, then serialize it.

    ``global_config_data_request`` is ``type: object`` whose
    ``additionalProperties`` are ``oneOf`` a ``^[01]$`` string and an integer in
    ``enum: [0, 1]`` (steering/npa_global_config.yaml:43-52), so no other value
    describes a flag.  :class:`~netskope.models.steering.SteeringSettings` is
    the one place that domain is expressed.
    """
    try:
        validated = SteeringSettings(settings)
    except PydanticValidationError as exc:
        reasons = " ".join(
            error["msg"].removeprefix("Value error, ").rstrip(".") + "." for error in exc.errors()
        )
        raise ValidationError(reasons) from None
    return request_payload(validated, SteeringSettings)


def _ipsec_page_size(page_size: int) -> int:
    """Clamp an iterator page size into the declared ``limit`` range."""
    if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size < 1:
        raise ValidationError(
            f"Invalid page_size {page_size!r}. Must be an integer between 1 and "
            f"{IPSEC_MAX_LIMIT} (steering/ipsec.yaml:478-486)."
        )
    return min(page_size, IPSEC_MAX_LIMIT)


def _extract_pops(body: dict[str, Any]) -> list[dict[str, Any]]:
    return extract_list(body, "pops")


def _extract_tunnels(body: dict[str, Any]) -> list[dict[str, Any]]:
    return extract_list(body, "tunnels")


def _extract_devices(body: dict[str, Any]) -> list[dict[str, Any]]:
    return extract_list(body, "devices")


def _validate_bandwidth(bandwidth: int) -> None:
    if isinstance(bandwidth, bool) or not isinstance(bandwidth, int) or bandwidth <= 0:
        raise ValidationError(
            f"Invalid bandwidth {bandwidth!r}. Must be a positive integer in Mbps; "
            f"Netskope commonly provisions {', '.join(str(b) for b in TUNNEL_BANDWIDTHS)}."
        )


def _validate_encryption(encryption: str) -> None:
    if not isinstance(encryption, str) or not encryption.strip():
        raise ValidationError(
            f"Invalid encryption {encryption!r}. Must be a cipher name; "
            f"Netskope commonly provisions {', '.join(TUNNEL_ENCRYPTIONS)}."
        )


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
    fields: dict[str, Any] = {
        "site": site,
        "pops": list(pops),
        "psk": psk,
        "srcidentity": srcidentity,
        "bandwidth": bandwidth,
        "encryption": encryption,
        "enabled": enabled,
    }
    if vendor is not None:
        fields["vendor"] = vendor
    if notes is not None:
        fields["notes"] = notes
    return request_payload(fields, IPSecTunnelCreate)


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
    if pops is not None and not pops:
        raise ValidationError("pops must contain at least one PoP name.")
    fields: dict[str, Any] = {
        name: value
        for name, value in (
            ("site", site),
            ("pops", list(pops) if pops is not None else None),
            ("psk", psk),
            ("bandwidth", bandwidth),
            ("encryption", encryption),
            ("enabled", enabled),
            ("notes", notes),
        )
        if value is not None
    }
    if not fields:
        raise ValidationError(
            "No update fields provided. Specify at least one of: site, pops, psk, "
            "bandwidth, encryption, enabled, notes."
        )
    return request_payload(fields, IPSecTunnelPatch)


class SteeringResource(SyncResource):
    """Synchronous interface to steering configuration, IPSec, and device APIs."""

    @cached_property
    def with_response(self) -> SteeringResponses:
        """Opt into typed, same-request response access."""

        return SteeringResponses(self._transport)

    def get_config(self, scope: str = "npa") -> SteeringConfig:
        """Get global steering configuration.

        Args:
            scope: Configuration scope — ``"npa"`` or ``"publishers"``.
                ``"npa"`` routes to
                ``/steering/globalconfig/clientconfiguration/npa``;
                ``"publishers"`` routes to ``/steering/globalconfig/publishers``.

        Raises:
            netskope.exceptions.ValidationError: If *scope* is not one the
                gateway publishes a path for.
        """
        body = self._get(_scope_path(scope))
        return SteeringConfig.model_validate(body)

    def update_config(
        self,
        scope: str = "npa",
        *,
        settings: dict[str, Any],
    ) -> SteeringConfigStatus:
        """Update global steering configuration (PATCH).

        ``global_config_data_request`` admits only the flag values ``0`` and
        ``1``, as an integer or as the matching ``^[01]$`` string
        (``steering/npa_global_config.yaml:43-52``), so anything else is
        refused before the request leaves the process.

        The 200 body declares one property, ``status``
        (``:274-283`` for ``npa``, ``:408-417`` for ``publishers``), and does
        not echo the stored flags, so the return value is that acknowledgment.
        Call :meth:`get_config` to read the configuration back.

        Args:
            scope: Configuration scope.
            settings: Feature flags to update, each value ``0`` or ``1``.

        Raises:
            netskope.exceptions.ValidationError: If *scope* has no path, or a
                setting value is not ``0``/``1``.
        """
        path = _scope_path(scope)
        body = self._patch(path, json=_steering_settings_payload(settings))
        return SteeringConfigStatus.model_validate(body)

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
            page_size: Results per page, 1..100; values above the declared
                ``maximum: 100`` (``steering/ipsec.yaml:478-486``) are clamped.

        Raises:
            netskope.exceptions.ValidationError: If *page_size* is not a
                positive integer.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_POPS_PATH,
            params=_build_pops_params(name, region, country),
            model=Pop,
            page_size=_ipsec_page_size(page_size),
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
            page_size: Results per page, 1..100; values above the declared
                ``maximum: 100`` (``steering/ipsec.yaml:672-680``) are clamped.

        Raises:
            netskope.exceptions.ValidationError: If *status* is not
                ``"up"`` or ``"down"``, or *page_size* is not a positive
                integer.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_TUNNELS_PATH,
            params=_build_tunnels_params(status, site, pop),
            model=IPSecTunnel,
            page_size=_ipsec_page_size(page_size),
            extract=_extract_tunnels,
        )

    def get_tunnel(self, tunnel_id: int) -> IPSecTunnel:
        """Get an IPSec tunnel by ID.

        The single-tunnel read answers ``{result: [item], status, total}``
        (steering/ipsec.yaml:305-317), unlike the create and update responses,
        which key the record under ``data``. ``parse_item`` accepts both.
        """
        body = self._get(f"{_TUNNELS_PATH}/{validate_id(tunnel_id, 'tunnel_id')}")
        return parse_item(body, IPSecTunnel)

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
            bandwidth: Maximum bandwidth in Mbps, a positive integer
                (default 100).  Netskope commonly provisions 50, 100, 150,
                200, 250 or 1000.
            encryption: Cipher name (default ``AES256-CBC``).  Netskope
                commonly provisions ``AES128-CBC``, ``AES256-CBC`` or
                ``AES256-GCM``.
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
            bandwidth: New bandwidth in Mbps, a positive integer.
            encryption: New cipher name.
            enabled: Enable or disable the tunnel.
            notes: New free-text notes.

        Raises:
            netskope.exceptions.ValidationError: If a value is invalid or
                no update fields were provided.
        """
        payload = _build_update_tunnel_payload(
            site, pops, psk, bandwidth, encryption, enabled, notes
        )
        body = self._patch(f"{_TUNNELS_PATH}/{validate_id(tunnel_id, 'tunnel_id')}", json=payload)
        return IPSecTunnel.model_validate(extract_item(body))

    def delete_tunnel(self, tunnel_id: int) -> None:
        """Delete an IPSec tunnel.  Irreversible — traffic is disrupted immediately.

        Args:
            tunnel_id: Numeric ID of the tunnel to delete.
        """
        self._delete(f"{_TUNNELS_PATH}/{validate_id(tunnel_id, 'tunnel_id')}")

    def list_devices(self, *, page_size: int = 100) -> SyncPaginatedResponse[Device]:
        """List managed devices enrolled in the tenant.

        Queries ``GET /api/v2/steering/devices``, which no spec file declares:
        ``production/endpoints/steering/`` has no ``/devices`` path, and
        ``production/endpoints/devices/`` offers only ``/otp``,
        ``/device/tags*``, ``/supportedos``, ``/support/*`` and
        ``/getclientlogs``.  A tenant that does not expose it answers 404 and a
        :class:`~netskope.exceptions.NotFoundError` propagates.  Client status
        data is available via ``client.events`` (the ``clientstatus`` event
        type) instead.

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

    @cached_property
    def with_response(self) -> AsyncSteeringResponses:
        """Opt into typed, same-request response access."""

        return AsyncSteeringResponses(self._transport)

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
    ) -> SteeringConfigStatus:
        """Update global steering configuration (PATCH).

        See :meth:`SteeringResource.update_config`.
        """
        path = _scope_path(scope)
        body = await self._patch(path, json=_steering_settings_payload(settings))
        return SteeringConfigStatus.model_validate(body)

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
            page_size=_ipsec_page_size(page_size),
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
            page_size=_ipsec_page_size(page_size),
            extract=_extract_tunnels,
        )

    async def get_tunnel(self, tunnel_id: int) -> IPSecTunnel:
        """Get an IPSec tunnel by ID.

        See :meth:`SteeringResource.get_tunnel` for the envelope difference.
        """
        body = await self._get(f"{_TUNNELS_PATH}/{validate_id(tunnel_id, 'tunnel_id')}")
        return parse_item(body, IPSecTunnel)

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
        body = await self._patch(
            f"{_TUNNELS_PATH}/{validate_id(tunnel_id, 'tunnel_id')}", json=payload
        )
        return IPSecTunnel.model_validate(extract_item(body))

    async def delete_tunnel(self, tunnel_id: int) -> None:
        """Delete an IPSec tunnel.  Irreversible."""
        await self._delete(f"{_TUNNELS_PATH}/{validate_id(tunnel_id, 'tunnel_id')}")

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
