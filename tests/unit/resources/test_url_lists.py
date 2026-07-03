"""Tests for client.url_lists with mocked HTTP."""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import NetskopeClient
from netskope.models.url_lists import UrlList
from tests.unit.resources.conftest import sent_json

_URL = "https://t.goskope.com/api/v2/policy/urllist"


class TestUrlListsResource:
    """Tests for client.url_lists."""

    @respx.mock
    def test_list(self, client: NetskopeClient) -> None:
        respx.get(_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "urllists": [
                            {"id": 1, "name": "Block", "urls": ["bad.com"]},
                        ]
                    },
                    "status": {"total": 1},
                },
            )
        )
        lists = list(client.url_lists.list())
        assert len(lists) == 1
        assert isinstance(lists[0], UrlList)
        assert lists[0].name == "Block"

    @respx.mock
    def test_create_sends_wrapped_body_and_handles_list_response(
        self, client: NetskopeClient
    ) -> None:
        """create() must wrap urls/type under ``data`` and accept the API's list response."""
        route = respx.post(_URL).mock(
            return_value=httpx.Response(
                201,
                json=[
                    {
                        "id": 42,
                        "name": "NewList",
                        "data": {"urls": ["new.com"], "type": "exact"},
                    }
                ],
            )
        )
        result = client.url_lists.create("NewList", ["new.com"], list_type="regex")

        assert sent_json(route) == {
            "name": "NewList",
            "data": {"urls": ["new.com"], "type": "regex"},
        }
        assert result.id == 42
        assert result.name == "NewList"
        assert result.urls == ["new.com"]
        assert result.type == "exact"

    @respx.mock
    def test_update_preserves_name_and_type_when_only_urls_given(
        self, client: NetskopeClient
    ) -> None:
        """update() must GET the list and merge user changes over current values."""
        respx.get(f"{_URL}/42").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 42,
                    "name": "ExistingList",
                    "data": {"urls": ["old.com"], "type": "regex"},
                },
            )
        )
        put_route = respx.put(f"{_URL}/42").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 42,
                    "name": "ExistingList",
                    "data": {"urls": ["new.com"], "type": "regex"},
                },
            )
        )
        result = client.url_lists.update(42, urls=["new.com"])

        assert sent_json(put_route) == {
            "name": "ExistingList",
            "data": {"urls": ["new.com"], "type": "regex"},
        }
        assert result.urls == ["new.com"]

    def test_update_raises_when_no_fields_provided(self, client: NetskopeClient) -> None:
        with pytest.raises(ValueError):
            client.url_lists.update(42)

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        respx.delete(f"{_URL}/42").mock(return_value=httpx.Response(200, json={}))
        client.url_lists.delete(42)  # Should not raise

    @respx.mock
    def test_deploy(self, client: NetskopeClient) -> None:
        respx.post("https://t.goskope.com/api/v2/policy/deploy").mock(
            return_value=httpx.Response(200, json={"status": "deployed"})
        )
        result = client.url_lists.deploy()
        assert result["status"] == "deployed"
