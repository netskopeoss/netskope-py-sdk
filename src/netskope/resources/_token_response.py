"""Response access for API-token operations. Writes are never replayed."""

from __future__ import annotations

from netskope.models.tokens import ApiToken, ApiTokenWrite
from netskope.resources._admin_response import item, request_payload
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import validate_id
from netskope.resources._response_list import parse_response_list
from netskope.response import ApiResponse


class TokensResponses(SyncResource):
    def create(self, request: ApiTokenWrite) -> ApiResponse[ApiToken]:
        response = self._transport.request(
            "POST", "/api/v2/auth/tokens", json=request_payload(request, ApiTokenWrite)
        )
        return ApiResponse(response, lambda raw: item(raw, ApiToken))

    def update(self, token_id: str, request: ApiTokenWrite) -> ApiResponse[ApiToken]:
        path = f"/api/v2/auth/tokens/{validate_id(token_id, 'token_id')}"
        response = self._transport.request(
            "PATCH", path, json=request_payload(request, ApiTokenWrite)
        )
        return ApiResponse(response, lambda raw: item(raw, ApiToken))

    def list(self) -> ApiResponse[list[ApiToken]]:
        response = self._transport.request("GET", "/api/v2/auth/tokens")
        return ApiResponse(response, lambda raw: parse_response_list(raw.json(), ApiToken))

    def get(self, token_id: str) -> ApiResponse[ApiToken]:
        path = f"/api/v2/auth/tokens/{validate_id(token_id, 'token_id')}"
        response = self._transport.request("GET", path)
        return ApiResponse(response, lambda raw: item(raw, ApiToken))


class AsyncTokensResponses(AsyncResource):
    async def create(self, request: ApiTokenWrite) -> ApiResponse[ApiToken]:
        response = await self._transport.request(
            "POST", "/api/v2/auth/tokens", json=request_payload(request, ApiTokenWrite)
        )
        return ApiResponse(response, lambda raw: item(raw, ApiToken))

    async def update(self, token_id: str, request: ApiTokenWrite) -> ApiResponse[ApiToken]:
        path = f"/api/v2/auth/tokens/{validate_id(token_id, 'token_id')}"
        response = await self._transport.request(
            "PATCH", path, json=request_payload(request, ApiTokenWrite)
        )
        return ApiResponse(response, lambda raw: item(raw, ApiToken))

    async def list(self) -> ApiResponse[list[ApiToken]]:
        response = await self._transport.request("GET", "/api/v2/auth/tokens")
        return ApiResponse(response, lambda raw: parse_response_list(raw.json(), ApiToken))

    async def get(self, token_id: str) -> ApiResponse[ApiToken]:
        path = f"/api/v2/auth/tokens/{validate_id(token_id, 'token_id')}"
        response = await self._transport.request("GET", path)
        return ApiResponse(response, lambda raw: item(raw, ApiToken))
