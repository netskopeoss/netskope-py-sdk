"""Response access for IPS status, allowlist, and signature references."""

from __future__ import annotations

from pydantic import TypeAdapter

from netskope.models.ips import IpsAllowlist, IpsAllowlistPatch, IpsStatus
from netskope.resources._admin_response import item, page_params, request_payload
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._typed_response import decode_body
from netskope.response import ApiResponse

_REFERENCES = TypeAdapter(list[str])


class IpsResponses(SyncResource):
    def update_allowlist(self, request: IpsAllowlistPatch) -> ApiResponse[IpsAllowlist]:
        response = self._transport.request(
            "PATCH", "/api/v2/ips/allowlist", json=request_payload(request, IpsAllowlistPatch)
        )
        return ApiResponse(response, lambda raw: item(raw, IpsAllowlist))

    def status(self) -> ApiResponse[IpsStatus]:
        response = self._transport.request("GET", "/api/v2/ips/status")
        return ApiResponse(response, lambda raw: item(raw, IpsStatus))

    def list_allowlist(self) -> ApiResponse[IpsAllowlist]:
        response = self._transport.request("GET", "/api/v2/ips/allowlist")
        return ApiResponse(response, lambda raw: item(raw, IpsAllowlist))

    def list_signatures(
        self, *, limit: int | None = None, offset: int | None = None, reference: str | None = None
    ) -> ApiResponse[list[str]]:
        params = page_params(limit, offset)
        if reference is not None:
            params["reference"] = reference
        response = self._transport.request(
            "GET", "/api/v2/ips/signaturereferencelist", params=params or None
        )
        return ApiResponse(response, lambda raw: decode_body(raw, _REFERENCES, envelope="data"))


class AsyncIpsResponses(AsyncResource):
    async def update_allowlist(self, request: IpsAllowlistPatch) -> ApiResponse[IpsAllowlist]:
        response = await self._transport.request(
            "PATCH", "/api/v2/ips/allowlist", json=request_payload(request, IpsAllowlistPatch)
        )
        return ApiResponse(response, lambda raw: item(raw, IpsAllowlist))

    async def status(self) -> ApiResponse[IpsStatus]:
        response = await self._transport.request("GET", "/api/v2/ips/status")
        return ApiResponse(response, lambda raw: item(raw, IpsStatus))

    async def list_allowlist(self) -> ApiResponse[IpsAllowlist]:
        response = await self._transport.request("GET", "/api/v2/ips/allowlist")
        return ApiResponse(response, lambda raw: item(raw, IpsAllowlist))

    async def list_signatures(
        self, *, limit: int | None = None, offset: int | None = None, reference: str | None = None
    ) -> ApiResponse[list[str]]:
        params = page_params(limit, offset)
        if reference is not None:
            params["reference"] = reference
        response = await self._transport.request(
            "GET", "/api/v2/ips/signaturereferencelist", params=params or None
        )
        return ApiResponse(response, lambda raw: decode_body(raw, _REFERENCES, envelope="data"))
