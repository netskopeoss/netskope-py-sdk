"""Canonical enrollment token-set responses, without undocumented paging."""

from __future__ import annotations

from netskope.models.enrollment import EnrollmentTokenSet
from netskope.resources._admin_response import item
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._response_list import parse_response_list
from netskope.response import ApiResponse


class EnrollmentResponses(SyncResource):
    def list_token_sets(self) -> ApiResponse[list[EnrollmentTokenSet]]:
        response = self._transport.request("GET", "/api/v2/enrollment/tokenset")
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), EnrollmentTokenSet)
        )

    def create_token_set(self) -> ApiResponse[EnrollmentTokenSet]:
        """Create a token set using the gateway's bodyless POST contract."""
        response = self._transport.request("POST", "/api/v2/enrollment/tokenset")
        return ApiResponse(response, lambda raw: item(raw, EnrollmentTokenSet))


class AsyncEnrollmentResponses(AsyncResource):
    async def list_token_sets(self) -> ApiResponse[list[EnrollmentTokenSet]]:
        response = await self._transport.request("GET", "/api/v2/enrollment/tokenset")
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), EnrollmentTokenSet)
        )

    async def create_token_set(self) -> ApiResponse[EnrollmentTokenSet]:
        """Create a token set using the gateway's bodyless POST contract."""
        response = await self._transport.request("POST", "/api/v2/enrollment/tokenset")
        return ApiResponse(response, lambda raw: item(raw, EnrollmentTokenSet))
