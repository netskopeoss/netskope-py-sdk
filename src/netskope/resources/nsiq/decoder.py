"""Typed NSIQ operations without guessing legacy false-positive payloads."""

from __future__ import annotations

from netskope.core.resource import AsyncResource, SyncResource
from netskope.core.response_list import parse_response_list
from netskope.models.nsiq import (
    FalsePositiveReceipt,
    RecategorizationReceipt,
    RecategorizationRequest,
    UrlFalsePositiveRequest,
    UrlLookup,
    UrlLookupReport,
)
from netskope.resources.shared.admin import item, request_payload
from netskope.response import ApiResponse


class NsiqResponses(SyncResource):
    def url_lookup(self, request: UrlLookup) -> ApiResponse[list[UrlLookupReport]]:
        response = self._transport.request(
            "POST",
            "/api/v2/nsiq/urllookup",
            json={"query": request_payload(request, UrlLookup)},
            retry_safe=True,
        )
        return ApiResponse(response, lambda raw: parse_response_list(raw.json(), UrlLookupReport))

    def recategorize(
        self, request: RecategorizationRequest
    ) -> ApiResponse[RecategorizationReceipt]:
        response = self._transport.request(
            "POST",
            "/api/v2/nsiq/url/recategorizations",
            json=request_payload(request, RecategorizationRequest),
        )
        return ApiResponse(response, lambda raw: item(raw, RecategorizationReceipt))

    def report_url_false_positive(
        self, request: UrlFalsePositiveRequest
    ) -> ApiResponse[list[FalsePositiveReceipt]]:
        response = self._transport.request(
            "POST",
            "/api/v2/nsiq/falsepositives/url",
            json=request_payload(request, UrlFalsePositiveRequest),
        )
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), FalsePositiveReceipt)
        )


class AsyncNsiqResponses(AsyncResource):
    async def url_lookup(self, request: UrlLookup) -> ApiResponse[list[UrlLookupReport]]:
        response = await self._transport.request(
            "POST",
            "/api/v2/nsiq/urllookup",
            json={"query": request_payload(request, UrlLookup)},
            retry_safe=True,
        )
        return ApiResponse(response, lambda raw: parse_response_list(raw.json(), UrlLookupReport))

    async def recategorize(
        self, request: RecategorizationRequest
    ) -> ApiResponse[RecategorizationReceipt]:
        response = await self._transport.request(
            "POST",
            "/api/v2/nsiq/url/recategorizations",
            json=request_payload(request, RecategorizationRequest),
        )
        return ApiResponse(response, lambda raw: item(raw, RecategorizationReceipt))

    async def report_url_false_positive(
        self, request: UrlFalsePositiveRequest
    ) -> ApiResponse[list[FalsePositiveReceipt]]:
        response = await self._transport.request(
            "POST",
            "/api/v2/nsiq/falsepositives/url",
            json=request_payload(request, UrlFalsePositiveRequest),
        )
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), FalsePositiveReceipt)
        )
