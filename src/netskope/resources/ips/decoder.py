"""Response access for IPS status, allowlist, and signature references."""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from netskope.core.decoding import decode_body
from netskope.core.resource import AsyncResource, SyncResource
from netskope.exceptions import ValidationError
from netskope.models.ips import IpsAllowlist, IpsAllowlistPatch, IpsStatus
from netskope.resources.shared.admin import item, page_params, request_payload
from netskope.response import ApiResponse

_REFERENCES = TypeAdapter(list[str])

# ``GET /signaturereferencelist`` (ips/ms-ips.yaml:583-592),
# ``POST /getsignaturelist`` (:721-727) and ``GET /signatureoverrides``
# (:1177-1186) all declare ``limit`` as ``minimum: 1, maximum: 100``.
IPS_LIMIT_RANGE = (1, 100)


def check_limit(limit: int | None) -> None:
    """Reject an IPS ``limit`` outside the declared ``[1, 100]`` range."""
    if limit is None:
        return
    low, high = IPS_LIMIT_RANGE
    if isinstance(limit, bool) or not isinstance(limit, int) or not low <= limit <= high:
        raise ValidationError(f"limit must be an integer between {low} and {high}.")


def _paging(limit: int | None, offset: int | None) -> dict[str, Any]:
    check_limit(limit)
    return page_params(limit, offset, maximum=IPS_LIMIT_RANGE[1])


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
        params = _paging(limit, offset)
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
        params = _paging(limit, offset)
        if reference is not None:
            params["reference"] = reference
        response = await self._transport.request(
            "GET", "/api/v2/ips/signaturereferencelist", params=params or None
        )
        return ApiResponse(response, lambda raw: decode_body(raw, _REFERENCES, envelope="data"))
