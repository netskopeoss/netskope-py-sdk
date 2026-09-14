"""How the legacy ``list()`` iterators behave on malformed and hostile pages.

Every case here is a 200 response: the transport is happy, and only the page
decoder can tell that the envelope cannot support safe continuation.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr

from netskope.core import pagination as _pagination
from netskope.core.config import NetskopeConfig
from netskope.core.pagination import (
    AsyncPaginatedResponse,
    AsyncScimPaginatedResponse,
    Page,
    SyncPaginatedResponse,
    SyncScimPaginatedResponse,
)
from netskope.core.transport import AsyncTransport, SyncTransport
from netskope.exceptions import NetskopeError, PaginationError, ResponseValidationError
from netskope.models.alerts import Alert

URL = "https://test.goskope.com/api/v2/test"
SCIM_URL = "https://test.goskope.com/api/v2/scim/Users"

KINDS = pytest.mark.parametrize("kind", ["sync", "async"])


def _config() -> NetskopeConfig:
    return NetskopeConfig(
        tenant="test.goskope.com",
        api_token=SecretStr("test-token"),
        timeout=5.0,
        max_retries=0,
        backoff_factor=0.01,
    )


def _extract(body: dict[str, Any]) -> list[dict[str, Any]]:
    """A resource decoder that assumes the envelope is an object."""
    return body.get("result", [])


def offset_paginator(
    kind: str, page_size: int = 2, extract: Any = _extract
) -> SyncPaginatedResponse[Alert] | AsyncPaginatedResponse[Alert]:
    arguments: dict[str, Any] = {
        "method": "GET",
        "path": "/api/v2/test",
        "params": {},
        "model": Alert,
        "page_size": page_size,
        "extract": extract,
    }
    if kind == "async":
        return AsyncPaginatedResponse(transport=AsyncTransport(_config()), **arguments)
    return SyncPaginatedResponse(transport=SyncTransport(_config()), **arguments)


def scim_paginator(
    kind: str, page_size: int = 2
) -> SyncScimPaginatedResponse[Alert] | AsyncScimPaginatedResponse[Alert]:
    arguments: dict[str, Any] = {
        "method": "GET",
        "path": "/api/v2/scim/Users",
        "params": {},
        "model": Alert,
        "page_size": page_size,
    }
    if kind == "async":
        return AsyncScimPaginatedResponse(transport=AsyncTransport(_config()), **arguments)
    return SyncScimPaginatedResponse(transport=SyncTransport(_config()), **arguments)


async def drain(paginator: Any) -> list[Page[Alert]]:
    """Pull every page from either iterator flavour."""
    if isinstance(paginator, (AsyncPaginatedResponse, AsyncScimPaginatedResponse)):
        return [page async for page in paginator.pages()]
    return list(paginator.pages())


async def drain_partial(paginator: Any) -> tuple[list[str | None], NetskopeError | None]:
    """Collect record ids page by page, keeping whatever ended the iteration."""
    collected: list[str | None] = []
    try:
        if isinstance(paginator, (AsyncPaginatedResponse, AsyncScimPaginatedResponse)):
            async for page in paginator.pages():
                collected.extend(item.id for item in page.items)
        else:
            for page in paginator.pages():
                collected.extend(item.id for item in page.items)
    except NetskopeError as exc:
        return collected, exc
    return collected, None


def ids(pages: list[Page[Alert]]) -> list[str | None]:
    return [item.id for page in pages for item in page.items]


def records(*rows: dict[str, Any], **envelope: Any) -> httpx.Response:
    return httpx.Response(200, json={"result": list(rows), **envelope})


def scim_records(*rows: dict[str, Any], **envelope: Any) -> httpx.Response:
    return httpx.Response(200, json={"Resources": list(rows), **envelope})


@KINDS
class TestUndecodableBodies:
    """A 200 the SDK cannot read is an SDK error, never a raw decoder crash."""

    @pytest.mark.parametrize(
        "content",
        [b"<html>maintenance</html>", b"", b"{"],
        ids=["html", "empty", "truncated"],
    )
    @respx.mock
    async def test_a_body_that_is_not_json_reaches_the_caller_as_an_sdk_error(
        self, kind: str, content: bytes
    ) -> None:
        respx.get(URL).mock(
            return_value=httpx.Response(200, content=content, headers={"x-request-id": "rq-1"})
        )
        with pytest.raises(ResponseValidationError, match="not valid JSON") as caught:
            await drain(offset_paginator(kind))
        assert caught.value.request_method == "GET"
        assert caught.value.request_path == "/api/v2/test"
        assert caught.value.request_id == "rq-1"

    @respx.mock
    async def test_undecodable_bytes_are_not_echoed_into_the_message(self, kind: str) -> None:
        """A codec failure quotes the offending bytes; the SDK message must not."""
        respx.get(URL).mock(return_value=httpx.Response(200, content=b'{"secret": "\xff\xfe"}'))
        with pytest.raises(ResponseValidationError) as caught:
            await drain(offset_paginator(kind))
        assert str(caught.value) == "The API response body is not valid JSON."
        assert "0xff" not in str(caught.value) and "secret" not in str(caught.value)

    @respx.mock
    async def test_a_scim_body_that_is_not_json_reaches_the_caller_as_an_sdk_error(
        self, kind: str
    ) -> None:
        respx.get(SCIM_URL).mock(
            return_value=httpx.Response(200, content=b"<html>maintenance</html>")
        )
        with pytest.raises(ResponseValidationError, match="not valid JSON"):
            await drain(scim_paginator(kind))

    @pytest.mark.parametrize("body", [5, "maintenance", True], ids=["int", "string", "boolean"])
    @respx.mock
    async def test_a_json_body_that_is_not_a_collection_is_rejected(
        self, kind: str, body: Any
    ) -> None:
        """The guard runs before the resource decoder, which assumes an object."""
        respx.get(URL).mock(return_value=httpx.Response(200, json=body))
        with pytest.raises(ResponseValidationError, match="Expected a JSON object or array"):
            await drain(offset_paginator(kind))

    @pytest.mark.parametrize("body", [[{"_id": "1"}], "maintenance"], ids=["list", "string"])
    @respx.mock
    async def test_a_scim_body_that_is_not_a_list_response_is_rejected(
        self, kind: str, body: Any
    ) -> None:
        respx.get(SCIM_URL).mock(return_value=httpx.Response(200, json=body))
        with pytest.raises(ResponseValidationError, match="SCIM list response object"):
            await drain(scim_paginator(kind))


@KINDS
class TestFirstPageTotals:
    """A total too small for the very first page is unusable, not a stop signal."""

    @respx.mock
    async def test_a_first_page_its_total_cannot_account_for_keeps_its_records(
        self, kind: str, caplog
    ) -> None:
        route = respx.get(URL).mock(return_value=records({"_id": "1"}, status={"total": 0}))
        with caplog.at_level(logging.WARNING, logger="netskope"):
            pages = await drain(offset_paginator(kind))
        assert ids(pages) == ["1"]
        assert (pages[0].total, pages[0].has_more) == (None, None)
        assert route.call_count == 1
        assert "cannot account for the first page" in caplog.text

    @respx.mock
    async def test_a_rescued_first_page_keeps_the_envelope_status(self, kind: str) -> None:
        respx.get(URL).side_effect = [
            records({"_id": "1"}, {"_id": "2"}, status={"total": 0}),
            records(status={"total": 0}),
            records(status={"total": 0}),
        ]
        pages = await drain(offset_paginator(kind))
        assert ids(pages) == ["1", "2"]
        assert pages[0].metadata == {"status": {"total": 0}}

    @respx.mock
    async def test_a_scim_first_page_its_total_cannot_account_for_keeps_its_records(
        self, kind: str
    ) -> None:
        route = respx.get(SCIM_URL).mock(return_value=scim_records({"_id": "1"}, totalResults=0))
        pages = await drain(scim_paginator(kind))
        assert ids(pages) == ["1"]
        assert (pages[0].total, pages[0].has_more) == (None, None)
        assert route.call_count == 1


@KINDS
class TestShortPages:
    """Offset traversal cannot continue past a page the API cut short."""

    @respx.mock
    async def test_a_short_page_stops_without_claiming_completeness(
        self, kind: str, caplog
    ) -> None:
        route = respx.get(URL).mock(return_value=records({"_id": "a"}, status={"total": 6}))
        with caplog.at_level(logging.WARNING, logger="netskope"):
            pages = await drain(offset_paginator(kind))
        assert ids(pages) == ["a"]
        assert (pages[0].total, pages[0].has_more) == (6, None)
        assert route.call_count == 1
        assert "continuing would skip records" in caplog.text

    @respx.mock
    async def test_a_short_page_mid_stream_stops_after_the_pages_it_delivered(
        self, kind: str
    ) -> None:
        route = respx.get(URL)
        route.side_effect = [
            records({"_id": "a"}, {"_id": "b"}, status={"total": 6}),
            records({"_id": "c"}, status={"total": 6}),
        ]
        pages = await drain(offset_paginator(kind))
        assert ids(pages) == ["a", "b", "c"]
        assert [page.has_more for page in pages] == [True, None]
        assert route.call_count == 2

    @respx.mock
    async def test_a_final_short_page_that_completes_the_total_reports_completion(
        self, kind: str, caplog
    ) -> None:
        route = respx.get(URL)
        route.side_effect = [
            records({"_id": "a"}, {"_id": "b"}, status={"total": 3}),
            records({"_id": "c"}, status={"total": 3}),
        ]
        with caplog.at_level(logging.WARNING, logger="netskope"):
            pages = await drain(offset_paginator(kind))
        assert ids(pages) == ["a", "b", "c"]
        assert [page.has_more for page in pages] == [True, False]
        assert route.call_count == 2
        assert [record.getMessage() for record in caplog.records if record.name == "netskope"] == []

    @respx.mock
    async def test_an_empty_page_that_completes_the_total_stops_at_once(self, kind: str) -> None:
        route = respx.get(URL).mock(return_value=records(status={"total": 0}))
        assert await drain(offset_paginator(kind)) == []
        assert route.call_count == 1


@KINDS
class TestPageCeiling:
    """Reaching the safety limit is reported, never returned as a complete set."""

    @respx.mock
    async def test_the_ceiling_raises_instead_of_truncating_silently(
        self, kind: str, monkeypatch
    ) -> None:
        monkeypatch.setattr(_pagination, "_MAX_PAGES", 3)
        route = respx.get(URL).mock(return_value=records({"_id": "1"}, {"_id": "2"}))
        with pytest.raises(PaginationError, match="safety limit") as caught:
            await drain(offset_paginator(kind))
        assert route.call_count == 3
        assert caught.value.offset == 6
        assert "offset 6" in str(caught.value)
        assert caught.value.request_method == "GET"
        assert caught.value.request_path == "/api/v2/test"

    @respx.mock
    async def test_the_scim_ceiling_raises_instead_of_truncating_silently(
        self, kind: str, monkeypatch
    ) -> None:
        monkeypatch.setattr(_pagination, "_MAX_PAGES", 3)
        route = respx.get(SCIM_URL).mock(return_value=scim_records({"_id": "1"}, {"_id": "2"}))
        with pytest.raises(PaginationError, match="safety limit") as caught:
            await drain(scim_paginator(kind))
        assert route.call_count == 3
        assert caught.value.offset == 6


@KINDS
class TestRequestContext:
    """A refused page names the request it came from, as the typed path does."""

    @respx.mock
    async def test_a_page_larger_than_requested_carries_the_request_context(
        self, kind: str
    ) -> None:
        respx.get(URL).mock(
            return_value=httpx.Response(
                200,
                json={"result": [{"_id": "1"}, {"_id": "2"}, {"_id": "3"}]},
                headers={"x-request-id": "rq-legacy"},
            )
        )
        with pytest.raises(PaginationError, match="exceeded the requested page size") as caught:
            await drain(offset_paginator(kind))
        assert caught.value.request_method == "GET"
        assert caught.value.request_path == "/api/v2/test"
        assert caught.value.request_id == "rq-legacy"
        assert caught.value.offset == 0

    @respx.mock
    async def test_a_refusal_after_delivered_pages_still_carries_the_context(
        self, kind: str
    ) -> None:
        route = respx.get(URL)
        route.side_effect = [
            records({"_id": "1"}, {"_id": "2"}, status={"total": 99}),
            httpx.Response(
                200,
                json={"result": [{"_id": "3"}, {"_id": "4"}, {"_id": "5"}]},
                headers={"x-request-id": "rq-2"},
            ),
        ]
        delivered, error = await drain_partial(offset_paginator(kind))
        assert delivered == ["1", "2"]
        assert isinstance(error, PaginationError)
        assert error.request_id == "rq-2"
        assert error.request_path == "/api/v2/test"
        assert error.offset == 2


@KINDS
class TestScimPageChecks:
    """SCIM pages answer to the same checks every other page decoder applies."""

    @respx.mock
    async def test_more_records_than_the_requested_count_are_rejected(self, kind: str) -> None:
        respx.get(SCIM_URL).mock(
            return_value=scim_records(*({"_id": str(i)} for i in range(5)), totalResults=2)
        )
        with pytest.raises(PaginationError, match="exceeded the requested page size") as caught:
            await drain(scim_paginator(kind))
        assert caught.value.offset == 0

    @respx.mock
    async def test_a_start_index_naming_another_page_is_rejected(self, kind: str) -> None:
        respx.get(SCIM_URL).mock(
            return_value=scim_records({"_id": "1"}, startIndex=5, totalResults=9)
        )
        with pytest.raises(PaginationError, match="startIndex does not match") as caught:
            await drain(scim_paginator(kind))
        assert caught.value.request_path == "/api/v2/scim/Users"
        assert caught.value.offset == 0

    @respx.mock
    async def test_a_matching_start_index_echo_is_accepted(self, kind: str) -> None:
        route = respx.get(SCIM_URL)
        route.side_effect = [
            scim_records({"_id": "1"}, {"_id": "2"}, startIndex=1, totalResults=3),
            scim_records({"_id": "3"}, startIndex="3", totalResults=3),
        ]
        pages = await drain(scim_paginator(kind))
        assert ids(pages) == ["1", "2", "3"]
        assert [page.offset for page in pages] == [0, 2]
        assert [page.has_more for page in pages] == [True, False]
        assert dict(route.calls[1].request.url.params)["startIndex"] == "3"

    @respx.mock
    async def test_records_past_total_results_stop_the_traversal(self, kind: str, caplog) -> None:
        route = respx.get(SCIM_URL)
        route.side_effect = [
            scim_records({"_id": "1"}, totalResults=10),
            scim_records({"_id": "2"}, totalResults=1),
        ]
        with caplog.at_level(logging.WARNING, logger="netskope"):
            pages = await drain(scim_paginator(kind, page_size=1))
        assert ids(pages) == ["1"]
        assert route.call_count == 2
        assert "1 records from that page were dropped" in caplog.text
