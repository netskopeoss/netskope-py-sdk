"""Tests for client.url_lists with mocked HTTP."""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.url_lists import UrlList
from tests.unit.resources.conftest import CONTRACT_BASE, EXAMPLE_BASE, drain, sent_json, sent_params

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
        with pytest.raises(ValidationError):
            client.url_lists.update(42)

    @respx.mock
    def test_delete_issues_one_request_to_the_list_path(self, client: NetskopeClient) -> None:
        """``delete`` returns nothing, so the route is the only evidence it ran.

        ``tests/conftest.py:44`` sets ``assert_all_called=False``, so a route
        left unasserted would let a no-op implementation pass this test.
        """
        route = respx.delete(f"{_URL}/42").mock(return_value=httpx.Response(200, json={}))

        assert client.url_lists.delete(42) is None
        assert route.call_count == 1

    @respx.mock
    def test_deploy_posts_to_the_urllist_deploy_path(self, client: NetskopeClient) -> None:
        """The only deploy operation is POST /urllist/deploy (policy/urllist.yaml:201-227).

        The SDK posted to a bare ``/api/v2/policy/deploy``, which appears in no
        path in the spec and answered 404.
        """
        stale = respx.post("https://t.goskope.com/api/v2/policy/deploy").mock(
            return_value=httpx.Response(404, json={"status": "not found"})
        )
        route = respx.post(f"{_URL}/deploy").mock(
            return_value=httpx.Response(200, json={"status": "deployed"})
        )
        result = client.url_lists.deploy()
        assert route.call_count == 1
        assert stale.call_count == 0
        assert result["status"] == "deployed"


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.

_URLLIST_URL = f"{CONTRACT_BASE}/api/v2/policy/urllist"


@respx.mock
async def test_async_url_list_list_makes_exactly_one_request(
    contract_aclient: AsyncNetskopeClient,
) -> None:
    """The async iterator holds the whole collection after one request."""
    records = [{"id": n, "name": f"l{n}"} for n in (1, 2, 3)]
    route = respx.get(_URLLIST_URL).mock(return_value=httpx.Response(200, json=records))
    items = await drain(contract_aclient.url_lists.list(page_size=1))
    assert [item.id for item in items] == [1, 2, 3]
    assert route.call_count == 1
    assert not route.calls.last.request.url.params


_EXAMPLE_URLLIST_URL = f"{EXAMPLE_BASE}/api/v2/policy/urllist"


@respx.mock
def test_url_list_listing_sends_the_two_declared_filters(example_client: NetskopeClient) -> None:
    """GET /urllist accepts pending (0|1) and field, singular.

    Spec: policy/urllist.yaml:133-142 and :143-156.
    """
    route = respx.get(_EXAMPLE_URLLIST_URL).mock(return_value=httpx.Response(200, json=[]))
    list(example_client.url_lists.list(pending=1, field="name"))

    params = sent_params(route)
    assert params["pending"] == "1"
    assert params["field"] == "name"

    with pytest.raises(ValidationError, match="pending must be"):
        list(example_client.url_lists.list(pending=2))
    with pytest.raises(ValidationError, match="field must be"):
        list(example_client.url_lists.list(field="urls"))


def test_url_list_pending_is_an_integer() -> None:
    """Urllist.pending is {type: integer} (policy/urllist.yaml:119-120).

    A boolean field coerced 0/1 and raised on anything else.
    """
    assert UrlList.model_validate({"id": 1, "pending": 2}).pending == 2
    assert UrlList.model_validate({"id": 1, "pending": 1}).pending == 1
    for absent in ("count", "json_version"):
        assert absent not in UrlList.model_fields
