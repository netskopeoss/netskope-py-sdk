"""Tests for the pagination system."""

from __future__ import annotations

import logging

import httpx
import pytest
import respx
from pydantic import SecretStr

from netskope.core.config import NetskopeConfig
from netskope.core.pagination import (
    AsyncPaginatedResponse,
    Page,
    SyncPaginatedResponse,
    build_page,
    coerce_total,
    local_page,
    select_total,
)
from netskope.core.transport import AsyncTransport, SyncTransport
from netskope.exceptions import PaginationError, ResponseValidationError
from netskope.models.alerts import Alert
from netskope.resources.shared.admin import page as admin_page

URL = "https://example.goskope.coken/api/v2/test"


def _config() -> NetskopeConfig:
    return NetskopeConfig(
        tenant="example.goskope.coken",
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


@pytest.fixture
def unpaginated(transport: SyncTransport):
    """Build either paginator in the deliberately unpaginated mode."""

    def build(kind: str, page_size: int) -> SyncPaginatedResponse | AsyncPaginatedResponse:
        kwargs = {
            "method": "GET",
            "path": "/api/v2/test",
            "params": {},
            "model": Alert,
            "page_size": page_size,
            "extract": _extract,
            "paginated": False,
        }
        if kind == "async":
            return AsyncPaginatedResponse(transport=AsyncTransport(_config()), **kwargs)
        return SyncPaginatedResponse(transport=transport, **kwargs)

    return build


def _extract(body: dict) -> list[dict]:
    return body.get("result", [])


class TestSyncPaginatedResponse:
    """Tests for the synchronous pagination iterator."""

    @respx.mock
    def test_iterates_all_items(self, transport: SyncTransport) -> None:
        route = respx.get(URL)
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
        route = respx.get(URL)
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
        respx.get(URL).mock(
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
        route = respx.get(URL)
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
        respx.get(URL).mock(
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
        respx.get(URL).mock(return_value=httpx.Response(200, json={"result": []}))
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
        route = respx.get(URL)
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

    @pytest.mark.parametrize("metadata", [{"status": {"total": 1}}, {"total": 1}])
    @respx.mock
    async def test_a_completed_total_stops_before_another_request(
        self, paginators, kind, metadata
    ) -> None:
        """steering/npa_apps_private.yaml:27-30 puts total beside data."""
        route = respx.get(URL).mock(
            return_value=httpx.Response(200, json={"result": [{"_id": "1"}], **metadata})
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


@pytest.mark.parametrize("kind", ["sync", "async"])
class TestUnpaginatedCollections:
    """``paginated=False`` serves the operations that declare no offset window.

    Two operations in the contract declare neither ``offset`` nor ``limit``:
    ``GET /api/v2/infrastructure/publishers``, whose whole query is ``fields``
    (``infrastructure/npa_publishers.yaml:1024-1032``), and
    ``GET /api/v2/policy/urllist``, whose whole query is ``pending`` and
    ``field`` (``policy/urllist.yaml:132-156``).  Sending a window they do not
    declare asks the gateway to ignore it and then reasons about short pages
    that were never pages; this mode fetches the collection once instead.
    """

    @respx.mock
    async def test_no_paging_parameters_reach_the_wire(self, unpaginated, kind) -> None:
        route = respx.get(URL).mock(return_value=httpx.Response(200, json={"result": []}))
        await take_pages(unpaginated(kind, 2))
        assert route.call_count == 1
        assert not route.calls.last.request.url.params

    @respx.mock
    async def test_a_collection_larger_than_the_page_size_is_not_refused(
        self, unpaginated, kind
    ) -> None:
        """The body is the whole collection, so no requested size bounds it."""
        records = [{"_id": str(n)} for n in range(1, 6)]
        route = respx.get(URL).mock(return_value=httpx.Response(200, json={"result": records}))
        pages = await take_pages(unpaginated(kind, 2))
        assert len(pages) == 1
        assert [item.id for item in pages[0].items] == ["1", "2", "3", "4", "5"]
        assert pages[0].limit is None
        assert route.call_count == 1

    @respx.mock
    async def test_the_traversal_ends_without_refetching_the_collection(
        self, unpaginated, kind
    ) -> None:
        """A second request with the same parameters would re-deliver the same rows."""
        route = respx.get(URL).mock(
            return_value=httpx.Response(200, json={"result": [{"_id": "1"}, {"_id": "2"}]})
        )
        pages = await take_pages(unpaginated(kind, 1))
        assert [item.id for page in pages for item in page.items] == ["1", "2"]
        assert route.call_count == 1

    @respx.mock
    async def test_an_empty_collection_yields_no_page_and_one_request(
        self, unpaginated, kind
    ) -> None:
        route = respx.get(URL).mock(return_value=httpx.Response(200, json={"result": []}))
        assert await take_pages(unpaginated(kind, 2)) == []
        assert route.call_count == 1

    @respx.mock
    async def test_a_stated_total_still_reaches_the_page(self, unpaginated, kind) -> None:
        respx.get(URL).mock(
            return_value=httpx.Response(
                200, json={"result": [{"_id": "1"}], "status": {"total": 1}}
            )
        )
        page = (await take_pages(unpaginated(kind, 2)))[0]
        assert (page.total, page.offset, page.has_more) == (1, 0, False)

    async def test_an_incomplete_collection_is_not_reported_as_complete(
        self, unpaginated, kind
    ) -> None:
        """npa_publishers.yaml:877-879 declares the collection total."""
        with respx.mock(assert_all_mocked=True) as router:
            route = router.get(URL).mock(
                return_value=httpx.Response(200, json={"result": [{"_id": "1"}], "total": 2})
            )
            with pytest.raises(PaginationError, match="incomplete") as caught:
                await take_pages(unpaginated(kind, 1))
        assert route.call_count == 1
        assert caught.value.request_method == "GET"
        assert caught.value.request_path == "/api/v2/test"


class TestLocalPage:
    """:func:`local_page` windows a whole-collection response client-side."""

    def test_the_window_is_applied_to_the_records_in_hand(self) -> None:
        items = [Alert.model_validate({"_id": str(n)}) for n in range(1, 6)]
        page = local_page(items, {"total": 5}, 1, 2)
        assert [item.id for item in page.items] == ["2", "3"]
        assert (page.offset, page.limit, page.total, page.has_more) == (1, 2, 5, True)

    def test_a_window_past_the_collection_is_empty_rather_than_an_error(self) -> None:
        items = [Alert.model_validate({"_id": "1"})]
        page = local_page(items, {"total": 1}, 5, 2)
        assert page.items == []
        assert (page.offset, page.limit, page.total) == (5, 2, 1)

    def test_a_complete_array_establishes_continuation_without_inventing_a_total(self) -> None:
        """policy/urllist.yaml:157-165 returns the entire array."""
        items = [Alert.model_validate({"_id": str(n)}) for n in (1, 2)]
        page = local_page(items, {}, 0, 1)
        assert [item.id for item in page.items] == ["1"]
        assert (page.total, page.has_more) == (None, True)
        assert local_page(items, {}, 1, 1).has_more is False

    @pytest.mark.parametrize("total", [1, 3])
    def test_an_inconsistent_collection_total_is_dropped_not_reported(self, total: int) -> None:
        """npa_publishers.yaml:877-879 reports the collection total.

        The operation declares no paging parameters, so the records in hand are
        the collection by definition and a disagreeing total is the service's
        own bookkeeping. Dropping it keeps the data reachable; reporting it
        would reach the unpaginated branch of `pages()`, which refuses a
        response whose stated total exceeds the records it carries.
        """
        items = [Alert.model_validate({"_id": str(n)}) for n in (1, 2)]
        page = local_page(items, {"total": total}, 0, 1)
        assert [item.id for item in page.items] == ["1"]
        assert page.total is None
        assert page.has_more is True

    def test_no_window_returns_the_whole_collection(self) -> None:
        items = [Alert.model_validate({"_id": str(n)}) for n in (1, 2, 3)]
        page = local_page(items, {"total": 3}, 0, None)
        assert [item.id for item in page.items] == ["1", "2", "3"]
        assert (page.limit, page.has_more) == (None, False)
