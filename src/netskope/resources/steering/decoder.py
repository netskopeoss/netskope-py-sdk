"""Explicit, bounded steering responses for synchronous and asynchronous clients."""

from __future__ import annotations

from netskope.core.ids import validate_id
from netskope.core.pagination import Page
from netskope.core.resource import AsyncResource, SyncResource
from netskope.models._npa_requests import request_payload
from netskope.models.infrastructure import IPSecTunnel, Pop
from netskope.models.steering import (
    IPSecTunnelCreate,
    IPSecTunnelPatch,
    SteeringConfig,
    SteeringConfigStatus,
    SteeringSettings,
)
from netskope.resources.shared.npa import page_params, parse_item, parse_page
from netskope.resources.steering.paths import (
    _POPS_PATH,
    _TUNNELS_PATH,
    IPSEC_MAX_LIMIT,
    _build_pops_params,
    _build_tunnels_params,
    _scope_path,
)
from netskope.response import ApiResponse


class SteeringResponses(SyncResource):
    """Completed steering responses, retaining original wire values."""

    def create_tunnel_request(self, request: IPSecTunnelCreate) -> ApiResponse[IPSecTunnel]:
        payload = request_payload(request, IPSecTunnelCreate)
        response = self._transport.request("POST", _TUNNELS_PATH, json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), IPSecTunnel))

    def update_tunnel_request(
        self, tunnel_id: int, request: IPSecTunnelPatch
    ) -> ApiResponse[IPSecTunnel]:
        payload = request_payload(request, IPSecTunnelPatch)
        response = self._transport.request(
            "PATCH", f"{_TUNNELS_PATH}/{validate_id(tunnel_id)}", json=payload
        )
        return ApiResponse(response, lambda raw: parse_item(raw.json(), IPSecTunnel))

    def update_config_request(
        self, scope: str, settings: SteeringSettings
    ) -> ApiResponse[SteeringConfigStatus | None]:
        """Update global steering flags; parses the status acknowledgment.

        The 200 body declares one property, ``status``
        (``steering/npa_global_config.yaml:274-283`` for ``npa``, ``:408-417``
        for ``publishers``) and does not echo the stored flags.  A body-less
        response parses to ``None``; call :meth:`get_config` to read the
        configuration back.
        """
        payload = request_payload(settings, SteeringSettings)
        response = self._transport.request("PATCH", _scope_path(scope), json=payload)
        return ApiResponse(
            response,
            lambda raw: SteeringConfigStatus.model_validate(raw.json()) if raw.content else None,
        )

    def get_config(self, scope: str = "npa") -> ApiResponse[SteeringConfig]:
        response = self._transport.request("GET", _scope_path(scope))
        return ApiResponse(response, lambda raw: SteeringConfig.model_validate(raw.json()))

    def list_pops_page(
        self,
        *,
        name: str | None = None,
        region: str | None = None,
        country: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[Pop]]:
        params = {
            **_build_pops_params(name, region, country),
            # ``limit`` declares minimum 0, maximum 100 (steering/ipsec.yaml:478-486).
            **page_params(limit, offset, limit_minimum=0, limit_maximum=IPSEC_MAX_LIMIT),
        }
        response = self._transport.request("GET", _POPS_PATH, params=params or None)
        return ApiResponse(response, lambda raw: parse_page(raw.json(), Pop, limit, offset, "pops"))

    def list_tunnels_page(
        self,
        *,
        status: str | None = None,
        site: str | None = None,
        pop: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[IPSecTunnel]]:
        params = {
            **_build_tunnels_params(status, site, pop),
            # ``limit`` declares minimum 0, maximum 100 (steering/ipsec.yaml:672-680).
            **page_params(limit, offset, limit_minimum=0, limit_maximum=IPSEC_MAX_LIMIT),
        }
        response = self._transport.request("GET", _TUNNELS_PATH, params=params or None)
        return ApiResponse(
            response, lambda raw: parse_page(raw.json(), IPSecTunnel, limit, offset, "tunnels")
        )

    def get_tunnel(self, tunnel_id: int) -> ApiResponse[IPSecTunnel]:
        response = self._transport.request("GET", f"{_TUNNELS_PATH}/{validate_id(tunnel_id)}")
        return ApiResponse(response, lambda raw: parse_item(raw.json(), IPSecTunnel))


class AsyncSteeringResponses(AsyncResource):
    """Completed steering responses, retaining original wire values."""

    async def create_tunnel_request(self, request: IPSecTunnelCreate) -> ApiResponse[IPSecTunnel]:
        payload = request_payload(request, IPSecTunnelCreate)
        response = await self._transport.request("POST", _TUNNELS_PATH, json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), IPSecTunnel))

    async def update_tunnel_request(
        self, tunnel_id: int, request: IPSecTunnelPatch
    ) -> ApiResponse[IPSecTunnel]:
        payload = request_payload(request, IPSecTunnelPatch)
        response = await self._transport.request(
            "PATCH", f"{_TUNNELS_PATH}/{validate_id(tunnel_id)}", json=payload
        )
        return ApiResponse(response, lambda raw: parse_item(raw.json(), IPSecTunnel))

    async def update_config_request(
        self, scope: str, settings: SteeringSettings
    ) -> ApiResponse[SteeringConfigStatus | None]:
        """Update global steering flags.  See :meth:`SteeringResponses.update_config_request`."""
        payload = request_payload(settings, SteeringSettings)
        response = await self._transport.request("PATCH", _scope_path(scope), json=payload)
        return ApiResponse(
            response,
            lambda raw: SteeringConfigStatus.model_validate(raw.json()) if raw.content else None,
        )

    async def get_config(self, scope: str = "npa") -> ApiResponse[SteeringConfig]:
        response = await self._transport.request("GET", _scope_path(scope))
        return ApiResponse(response, lambda raw: SteeringConfig.model_validate(raw.json()))

    async def list_pops_page(
        self,
        *,
        name: str | None = None,
        region: str | None = None,
        country: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[Pop]]:
        params = {
            **_build_pops_params(name, region, country),
            # ``limit`` declares minimum 0, maximum 100 (steering/ipsec.yaml:478-486).
            **page_params(limit, offset, limit_minimum=0, limit_maximum=IPSEC_MAX_LIMIT),
        }
        response = await self._transport.request("GET", _POPS_PATH, params=params or None)
        return ApiResponse(response, lambda raw: parse_page(raw.json(), Pop, limit, offset, "pops"))

    async def list_tunnels_page(
        self,
        *,
        status: str | None = None,
        site: str | None = None,
        pop: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[IPSecTunnel]]:
        params = {
            **_build_tunnels_params(status, site, pop),
            # ``limit`` declares minimum 0, maximum 100 (steering/ipsec.yaml:672-680).
            **page_params(limit, offset, limit_minimum=0, limit_maximum=IPSEC_MAX_LIMIT),
        }
        response = await self._transport.request("GET", _TUNNELS_PATH, params=params or None)
        return ApiResponse(
            response, lambda raw: parse_page(raw.json(), IPSecTunnel, limit, offset, "tunnels")
        )

    async def get_tunnel(self, tunnel_id: int) -> ApiResponse[IPSecTunnel]:
        response = await self._transport.request("GET", f"{_TUNNELS_PATH}/{validate_id(tunnel_id)}")
        return ApiResponse(response, lambda raw: parse_item(raw.json(), IPSecTunnel))
