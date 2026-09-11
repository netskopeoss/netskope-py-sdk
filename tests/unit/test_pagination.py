"""Tests for the pagination system."""

from __future__ import annotations

import logging

import httpx
import pytest
import respx
from pydantic import SecretStr

from netskope._config import NetskopeConfig
from netskope._pagination import build_page, coerce_total, select_total
from netskope._transport import AsyncTransport, SyncTransport
from netskope.exceptions import PaginationError, ResponseValidationError
from netskope.models.alerts import Alert
from netskope.pagination import AsyncPaginatedResponse, Page, SyncPaginatedResponse
from netskope.resources._admin_response import page as admin_page

URL = "https://test.goskope.com/api/v2/test"


def _config() -> NetskopeConfig:
    return NetskopeConfig(
        tenant="test.goskope.com",
        api_token=SecretStr("test-token"),
        timeout=5.0,
        max_retries=0,
        backoff_factor=0.01,
    )


@pytest.fixture
def transport() -> SyncTransport:
    return SyncTransport(_config())


@pytest.fixture
def paginators(transport: SyncTransport):
    """Build either legacy paginator over the same route and page size."""

    def build(
        kind: str, page_size: int, extract=None
    ) -> SyncPaginatedResponse | AsyncPaginatedResponse:
        if kind == "async":
            return AsyncPaginatedResponse(
                transport=AsyncTransport(_config()),
                method="GET",
                path="/api/v2/test",
                params={},
                model=Alert,
                page_size=page_size,
                extract=extract or _extract,
            )
        return SyncPaginatedResponse(
            transport=transport,
            method="GET",
            path="/api/v2/test",
            params={},
            model=Alert,
            page_size=page_size,
            extract=extract or _extract,
        )

    return build


async def take_pages(paginator, count: int | None = None) -> list[Page]:
    """Pull *count* pages, or every page when ``count`` is ``None``."""
    pages: list[Page] = []
    if isinstance(paginator, AsyncPaginatedResponse):
        iterator = paginator.pages()
        while count is None or len(pages) < count:
            try:
                pages.append(await iterator.__anext__())
            except StopAsyncIteration:
                break
        return pages
    iterator = paginator.pages()
    while count is None or len(pages) < count:
        try:
            pages.append(next(iterator))
        except StopIteration:
            break
    return pages


def _extract(body: dict) -> list[dict]:
    return body.get("result", [])


class TestSyncPaginatedResponse:
    """Tests for the synchronous pagination iterator."""

    @respx.mock
    def test_iterates_all_items(self, transport: SyncTransport) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test")
        route.side_effect = [
            httpx.Response(
                200,
                json={
                    "result": [{"_id": "1"}, {"_id": "2"}],
                    "status": {"total": 3},
                },
            ),
            httpx.Response(
                200,
                json={
                    "result": [{"_id": "3"}],
                    "status": {"total": 3},
                },
            ),
        ]
        paginator = SyncPaginatedResponse(
            transport=transport,
            method="GET",
            path="/api/v2/test",
            params={},
            model=Alert,
            page_size=2,
            extract=_extract,
        )
        items = list(paginator)
        assert len(items) == 3
        assert items[0].id == "1"
        assert items[2].id == "3"

    @respx.mock
    def test_pages_yields_page_objects(self, transport: SyncTransport) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test")
        route.side_effect = [
            httpx.Response(
                200,
                json={
                    "result": [{"_id": "1"}, {"_id": "2"}],
                    "status": {"total": 4},
                },
            ),
            httpx.Response(
                200,
                json={
                    "result": [{"_id": "3"}, {"_id": "4"}],
                    "status": {"total": 4},
                },
            ),
        ]
        paginator = SyncPaginatedResponse(
            transport=transport,
            method="GET",
            path="/api/v2/test",
            params={},
            model=Alert,
            page_size=2,
            extract=_extract,
        )
        pages = list(paginator.pages())
        assert len(pages) == 2
        assert isinstance(pages[0], Page)
        assert pages[0].total == 4
        assert len(pages[0].items) == 2

    @respx.mock
    def test_empty_response(self, transport: SyncTransport) -> None:
        respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(200, json={"result": [], "status": {"total": 0}})
        )
        paginator = SyncPaginatedResponse(
            transport=transport,
            method="GET",
            path="/api/v2/test",
            params={},
            model=Alert,
            page_size=100,
            extract=_extract,
        )
        items = list(paginator)
        assert len(items) == 0

    @respx.mock
    def test_to_list_with_limit(self, transport: SyncTransport) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test")
        route.side_effect = [
            httpx.Response(
                200,
                json={
                    "result": [{"_id": str(i)} for i in range(100)],
                    "status": {"total": 500},
                },
            ),
        ]
        paginator = SyncPaginatedResponse(
            transport=transport,
            method="GET",
            path="/api/v2/test",
            params={},
            model=Alert,
            page_size=100,
            extract=_extract,
        )
        items = paginator.to_list(max_items=50)
        assert len(items) == 50

    @respx.mock
    def test_first(self, transport: SyncTransport) -> None:
        respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": [{"_id": "first"}],
                    "status": {"total": 1},
                },
            )
        )
        paginator = SyncPaginatedResponse(
            transport=transport,
            method="GET",
            path="/api/v2/test",
            params={},
            model=Alert,
            page_size=100,
            extract=_extract,
        )
        item = paginator.first()
        assert item is not None
        assert item.id == "first"

    @respx.mock
    def test_first_empty(self, transport: SyncTransport) -> None:
        respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(200, json={"result": []})
        )
        paginator = SyncPaginatedResponse(
            transport=transport,
            method="GET",
            path="/api/v2/test",
            params={},
            model=Alert,
            page_size=100,
            extract=_extract,
        )
        assert paginator.first() is None

    @respx.mock
    def test_params_include_offset_and_limit(self, transport: SyncTransport) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test")
        route.mock(return_value=httpx.Response(200, json={"result": []}))
        paginator = SyncPaginatedResponse(
            transport=transport,
            method="GET",
            path="/api/v2/test",
            params={"query": "test"},
            model=Alert,
            page_size=50,
            extract=_extract,
        )
        list(paginator)
        url = str(route.calls[0].request.url)
        assert "limit=50" in url
        assert "offset=0" in url
        assert "query=test" in url


class TestTotalCoercion:
    """The single total policy shared by every offset decoder."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (3, 3),
            ("3", 3),
            (0, 0),
            ("0", 0),
            (True, None),
            (False, None),
            (-1, None),
            ("-1", None),
            (1.5, None),
            ("1.5", None),
            ("", None),
            ("many", None),
            (None, None),
            ([3], None),
        ],
    )
    def test_coerce_total(self, value: object, expected: int | None) -> None:
        assert coerce_total(value) == expected

    @pytest.mark.parametrize(
        ("metadata", "expected"),
        [
            ({"status": {"total": "12"}}, 12),
            ({"total": 7}, 7),
            ({"totalResults": "7"}, 7),
            ({"status": {"total": "invalid"}, "total": 3}, 3),
            ({"status": {"total": -1}, "totalResults": 4}, 4),
            ({"status": {"count": 10_000}}, None),
            ({}, None),
        ],
    )
    def test_select_total_prefers_the_first_usable_field(
        self, metadata: dict, expected: int | None
    ) -> None:
        assert select_total(metadata) == expected


class TestBuildPage:
    """Continuation evidence and metadata retention on a built page."""

    def _items(self, count: int) -> list[Alert]:
        return [Alert.model_validate({"_id": str(index)}) for index in range(count)]

    def test_metadata_and_has_more_come_from_the_stated_total(self) -> None:
        metadata = {"status": {"total": 5}, "warnings": ["partial"]}
        page = build_page(self._items(2), offset=0, limit=2, total=5, metadata=metadata)
        assert page.metadata == metadata
        assert (page.total, page.offset, page.limit, page.has_more) == (5, 0, 2, True)

    def test_last_page_has_no_more(self) -> None:
        page = build_page(self._items(2), offset=3, limit=2, total=5, metadata={})
        assert page.has_more is False

    def test_unknown_total_leaves_continuation_unestablished(self) -> None:
        page = build_page(self._items(2), offset=0, limit=2, total=None)
        assert page.total is None
        assert page.has_more is None
        assert page.metadata == {}

    def test_records_past_the_stated_total_are_rejected(self) -> None:
        metadata = {"status": {"total": 1}}
        with pytest.raises(PaginationError, match="stated total") as caught:
            build_page(self._items(3), offset=0, limit=3, total=1, metadata=metadata)
        assert caught.value.offset == 0
        # The refused records travel with the error so an iterator that has
        # delivered nothing yet can keep them instead of discarding a page.
        assert [item.id for item in caught.value.records] == ["0", "1", "2"]
        assert caught.value.metadata == metadata

    def test_empty_page_past_the_total_is_accepted(self) -> None:
        page = build_page([], offset=40, limit=2, total=10, metadata={})
        assert page.items == []
        assert page.has_more is False

    def test_more_records_than_requested_are_rejected(self) -> None:
        with pytest.raises(PaginationError, match="exceeded the requested page size") as caught:
            build_page(self._items(3), offset=20, limit=2, total=None)
        assert caught.value.offset == 20

    def test_a_requested_page_size_of_zero_still_bounds_the_page(self) -> None:
        assert build_page([], offset=0, limit=0, total=None).items == []
        with pytest.raises(PaginationError, match="exceeded the requested page size"):
            build_page(self._items(1), offset=0, limit=0, total=None)

    @pytest.mark.parametrize("echoed", [None, 20])
    def test_a_matching_or_absent_offset_echo_builds_the_page(self, echoed: int | None) -> None:
        page = build_page(self._items(1), offset=20, limit=2, total=None, echoed_offset=echoed)
        assert page.offset == 20

    @pytest.mark.parametrize(
        "echoed",
        [0, True, 20.0, "20", [20]],
        ids=["other-page", "boolean", "float", "string", "list"],
    )
    def test_an_offset_echo_that_cannot_identify_the_page_is_rejected(self, echoed: object) -> None:
        with pytest.raises(PaginationError, match="offset does not match") as caught:
            build_page(self._items(1), offset=20, limit=2, total=None, echoed_offset=echoed)
        assert caught.value.offset == 20


class TestAdminPageOffsetEcho:
    """The shared administrative decoder reads an offset echo as received."""

    def _response(self, echoed: object) -> httpx.Response:
        return httpx.Response(200, json={"roles": [{"_id": "1"}], "total": 9, "offset": echoed})

    @pytest.mark.parametrize(
        "echoed",
        [1, "0", -1, True, 0.0, "nought", [0]],
        ids=["other-page", "string", "negative", "boolean", "float", "unparsable", "list"],
    )
    def test_an_echo_that_cannot_identify_the_page_is_rejected(self, echoed: object) -> None:
        with pytest.raises(PaginationError, match="offset does not match"):
            admin_page(self._response(echoed), Alert, "roles", offset=0, limit=2)

    def test_a_matching_echo_builds_the_page(self) -> None:
        page = admin_page(self._response(0), Alert, "roles", offset=0, limit=2)
        assert (page.offset, page.total, page.has_more) == (0, 9, True)


@pytest.mark.parametrize("kind", ["sync", "async"])
class TestLegacyPageTotals:
    """The general iterator validates totals instead of trusting raw values."""

    @respx.mock
    async def test_string_total_is_coerced_and_drives_continuation(self, paginators, kind) -> None:
        route = respx.get(URL)
        route.side_effect = [
            httpx.Response(200, json={"result": [{"_id": "1"}], "status": {"total": "250"}}),
            httpx.Response(200, json={"result": [{"_id": "2"}], "status": {"total": "250"}}),
        ]
        pages = await take_pages(paginators(kind, 1), 2)
        assert [page.total for page in pages] == [250, 250]
        assert [page.has_more for page in pages] == [True, True]
        assert pages[0].metadata == {"status": {"total": "250"}}
        assert route.call_count == 2

    @respx.mock
    async def test_unusable_total_does_not_establish_continuation(self, paginators, kind) -> None:
        respx.get(URL).mock(
            return_value=httpx.Response(
                200, json={"result": [{"_id": "1"}], "status": {"total": True}}
            )
        )
        page = (await take_pages(paginators(kind, 1), 1))[0]
        assert page.total is None
        assert page.has_more is None

    @respx.mock
    async def test_a_total_the_records_outrun_stops_the_iterator(
        self, paginators, kind, caplog
    ) -> None:
        """A total that shrinks once rows have shipped ends the traversal loudly."""
        route = respx.get(URL)
        route.side_effect = [
            httpx.Response(200, json={"result": [{"_id": "1"}], "status": {"total": 10}}),
            httpx.Response(200, json={"result": [{"_id": "2"}], "status": {"total": 1}}),
        ]
        with caplog.at_level(logging.DEBUG, logger="netskope"):
            pages = await take_pages(paginators(kind, 1))
        assert [item.id for page in pages for item in page.items] == ["1"]
        assert route.call_count == 2
        dropped = [record for record in caplog.records if "reported total" in record.getMessage()]
        assert [record.levelno for record in dropped] == [logging.WARNING]
        assert "1 records from that page were dropped" in caplog.text

    @respx.mock
    async def test_a_page_larger_than_requested_still_raises(self, paginators, kind) -> None:
        respx.get(URL).mock(
            return_value=httpx.Response(200, json={"result": [{"_id": "1"}, {"_id": "2"}]})
        )
        with pytest.raises(PaginationError, match="exceeded the requested page size") as caught:
            await take_pages(paginators(kind, 1))
        assert caught.value.offset == 0

    @respx.mock
    async def test_a_completed_total_stops_before_another_request(self, paginators, kind) -> None:
        route = respx.get(URL).mock(
            return_value=httpx.Response(
                200, json={"result": [{"_id": "1"}], "status": {"total": 1}}
            )
        )
        pages = await take_pages(paginators(kind, 1))
        assert [page.has_more for page in pages] == [False]
        assert route.call_count == 1

    @respx.mock
    async def test_a_malformed_record_stays_inside_the_error_hierarchy(
        self, paginators, kind
    ) -> None:
        respx.get(URL).mock(
            return_value=httpx.Response(
                200, json={"result": [{"_id": ["not-an-id"]}]}, headers={"x-request-id": "page-1"}
            )
        )
        with pytest.raises(ResponseValidationError) as caught:
            await take_pages(paginators(kind, 1))
        assert caught.value.request_method == "GET"
        assert caught.value.request_path == "/api/v2/test"
        assert caught.value.request_id == "page-1"
        assert caught.value.field_errors == ((("_id",), "string_type"),)
        assert "not-an-id" not in str(caught.value)

    @respx.mock
    async def test_an_undecodable_envelope_stays_inside_the_error_hierarchy(
        self, paginators, kind
    ) -> None:
        """A decoder's own diagnostic reaches the caller as an SDK error."""

        def refuse(body: dict) -> list[dict]:
            raise ValueError("Expected a list of records.")

        respx.get(URL).mock(return_value=httpx.Response(200, json={"result": "garbage"}))
        with pytest.raises(ResponseValidationError, match="Expected a list of records") as caught:
            await take_pages(paginators(kind, 1, refuse))
        assert caught.value.request_path == "/api/v2/test"
