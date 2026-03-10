"""Tests for the pagination system."""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import SecretStr

from netskope._config import NetskopeConfig
from netskope._pagination import Page, SyncPaginatedResponse
from netskope._transport import SyncTransport
from netskope.models.alerts import Alert


@pytest.fixture
def transport() -> SyncTransport:
    config = NetskopeConfig(
        tenant="test.goskope.com",
        api_token=SecretStr("test-token"),
        timeout=5.0,
        max_retries=0,
        backoff_factor=0.01,
    )
    return SyncTransport(config)


def _extract(body: dict) -> list[dict]:
    return body.get("result", [])


class TestSyncPaginatedResponse:
    """Tests for the synchronous pagination iterator."""

    @respx.mock
    def test_iterates_all_items(self, transport: SyncTransport) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test")
        route.side_effect = [
            httpx.Response(200, json={
                "result": [{"_id": "1"}, {"_id": "2"}],
                "status": {"total": 3},
            }),
            httpx.Response(200, json={
                "result": [{"_id": "3"}],
                "status": {"total": 3},
            }),
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
            httpx.Response(200, json={
                "result": [{"_id": "1"}, {"_id": "2"}],
                "status": {"total": 4},
            }),
            httpx.Response(200, json={
                "result": [{"_id": "3"}, {"_id": "4"}],
                "status": {"total": 4},
            }),
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
            httpx.Response(200, json={
                "result": [{"_id": str(i)} for i in range(100)],
                "status": {"total": 500},
            }),
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
            return_value=httpx.Response(200, json={
                "result": [{"_id": "first"}],
                "status": {"total": 1},
            })
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
