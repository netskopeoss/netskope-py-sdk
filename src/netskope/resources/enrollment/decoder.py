"""Canonical enrollment token-set responses, without undocumented paging."""

from __future__ import annotations

from netskope.core.resource import AsyncResource, SyncResource
from netskope.core.response_list import parse_response_list
from netskope.models.enrollment import EnrollmentTokenSet
from netskope.resources.shared.admin import item
from netskope.response import ApiResponse

# TokensetController_getTokenSets is declared `access: rw`
# (enrollment/enrollment-service-configuration.yaml:50-52, :81); the same
# level as the sibling create POST (:47). A declared write is not replayable
# whatever its HTTP verb, so the GET opts out of the transport's method-based
# retry default rather than inheriting it.
_TOKENSET_LIST_RETRY_SAFE = False


class EnrollmentResponses(SyncResource):
    def list_token_sets(self) -> ApiResponse[list[EnrollmentTokenSet]]:
        response = self._transport.request(
            "GET", "/api/v2/enrollment/tokenset", retry_safe=_TOKENSET_LIST_RETRY_SAFE
        )
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), EnrollmentTokenSet)
        )

    def create_token_set(self) -> ApiResponse[EnrollmentTokenSet]:
        """Create a token set using the gateway's bodyless POST contract."""
        response = self._transport.request("POST", "/api/v2/enrollment/tokenset")
        return ApiResponse(response, lambda raw: item(raw, EnrollmentTokenSet))


class AsyncEnrollmentResponses(AsyncResource):
    async def list_token_sets(self) -> ApiResponse[list[EnrollmentTokenSet]]:
        response = await self._transport.request(
            "GET", "/api/v2/enrollment/tokenset", retry_safe=_TOKENSET_LIST_RETRY_SAFE
        )
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), EnrollmentTokenSet)
        )

    async def create_token_set(self) -> ApiResponse[EnrollmentTokenSet]:
        """Create a token set using the gateway's bodyless POST contract."""
        response = await self._transport.request("POST", "/api/v2/enrollment/tokenset")
        return ApiResponse(response, lambda raw: item(raw, EnrollmentTokenSet))
