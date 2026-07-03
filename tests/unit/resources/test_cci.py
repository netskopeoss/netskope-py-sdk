"""Tests for the CCI resource with mocked HTTP.

Pins the live-verified wire shapes for the CCI tags API: tags are identified
by NAME (no numeric ids), lists use semicolon-joined ``apps``/``ids`` query
params, create posts a ``tag`` body key, update PATCHes ``/tags/{tag}``, and
delete sends a comma-joined ``tags`` query param (HTTP 202, async deletion).
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.resources.cci import AsyncCciResource, CciResource
from tests.unit.resources.conftest import sent_json

_APP_URL = "https://t.goskope.com/api/v2/services/cci/app"
_TAGS_URL = "https://t.goskope.com/api/v2/services/cci/tags"
_TAGS_ALL_URL = "https://t.goskope.com/api/v2/services/cci/tags/all"
_TAGS_RULES_URL = "https://t.goskope.com/api/v2/services/cci/tags/rules"
_TAGS_ATTRS_URL = "https://t.goskope.com/api/v2/services/cci/tags/supportedattributes"

# Live-verified response shapes.
_TAGS_ALL_BODY = {
    "data": {"tags": ["Finance", "High-Risk"], "tags_count": 2},
    "status": "Success",
    "status_code": 200,
}
_TAGS_BY_APP_BODY = {
    "data": {
        "Dropbox": {"app_type": "cloud", "id": 4, "sanctioned": "no", "tags": ["Finance"]},
    },
    "status": "Success",
    "status_code": 200,
}
_TAG_POST_BODY = {
    "tag": "Finance",
    "apps": ["Box", "Dropbox"],
    "message": "Tag created successfully to the list of apps/ids",
    "status": "Success",
}
_TAG_DELETE_BODY = {"message": "Request accepted", "status": "Success", "status_code": 202}


def _cci(client: NetskopeClient) -> CciResource:
    return CciResource(client._transport)


def _acci(aclient: AsyncNetskopeClient) -> AsyncCciResource:
    return AsyncCciResource(aclient._transport)


class TestCciLookupApp:
    """Tests for CciResource.lookup_app."""

    @respx.mock
    def test_lookup_app_sends_apps_param(self, client: NetskopeClient) -> None:
        route = respx.get(_APP_URL).mock(
            return_value=httpx.Response(200, json={"data": [{"app_name": "Dropbox"}]})
        )
        result = _cci(client).lookup_app("Dropbox")

        assert result == {"data": [{"app_name": "Dropbox"}]}
        request = route.calls.last.request
        assert request.method == "GET"
        assert dict(request.url.params) == {"apps": "Dropbox"}

    @respx.mock
    def test_lookup_app_sends_optional_filters(self, client: NetskopeClient) -> None:
        route = respx.get(_APP_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        _cci(client).lookup_app(
            "Box",
            category="Cloud Storage",
            ccl="excellent",
            tag="Finance",
            connector="api",
            discovered=True,
            limit=5,
            offset=10,
        )

        params = dict(route.calls.last.request.url.params)
        assert params == {
            "apps": "Box",
            "category": "Cloud Storage",
            "ccl": "excellent",
            "tag": "Finance",
            "connector": "api",
            "discovered": "true",
            "limit": "5",
            "offset": "10",
        }

    @respx.mock
    def test_lookup_app_omits_unset_filters(self, client: NetskopeClient) -> None:
        route = respx.get(_APP_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        _cci(client).lookup_app("Slack", limit=1)

        params = dict(route.calls.last.request.url.params)
        assert params == {"apps": "Slack", "limit": "1"}


class TestCciTags:
    """Tests for CciResource.tags."""

    @respx.mock
    def test_list_without_args_uses_tags_all(self, client: NetskopeClient) -> None:
        route = respx.get(_TAGS_ALL_URL).mock(return_value=httpx.Response(200, json=_TAGS_ALL_BODY))
        result = _cci(client).tags.list()

        assert result == _TAGS_ALL_BODY
        assert result["data"]["tags"] == ["Finance", "High-Risk"]
        request = route.calls.last.request
        assert request.method == "GET"
        assert dict(request.url.params) == {}

    @respx.mock
    def test_list_with_apps_joins_with_semicolons(self, client: NetskopeClient) -> None:
        route = respx.get(_TAGS_URL).mock(return_value=httpx.Response(200, json=_TAGS_BY_APP_BODY))
        result = _cci(client).tags.list(apps=["Box", "Dropbox", "Slack"])

        assert dict(route.calls.last.request.url.params) == {"apps": "Box;Dropbox;Slack"}
        assert result["data"]["Dropbox"]["tags"] == ["Finance"]

    @respx.mock
    def test_list_with_ids_joins_with_semicolons(self, client: NetskopeClient) -> None:
        route = respx.get(_TAGS_URL).mock(return_value=httpx.Response(200, json=_TAGS_BY_APP_BODY))
        _cci(client).tags.list(ids=[4, 7, 11])

        assert dict(route.calls.last.request.url.params) == {"ids": "4;7;11"}

    @respx.mock
    def test_list_apps_and_ids_mutually_exclusive_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _cci(client).tags.list(apps=["Box"], ids=[4])
        assert len(respx.calls) == 0

    @respx.mock
    def test_list_with_empty_apps_uses_tags_all(self, client: NetskopeClient) -> None:
        route = respx.get(_TAGS_ALL_URL).mock(return_value=httpx.Response(200, json=_TAGS_ALL_BODY))
        _cci(client).tags.list(apps=[])

        assert route.called

    @respx.mock
    def test_create_with_apps(self, client: NetskopeClient) -> None:
        route = respx.post(_TAGS_URL).mock(return_value=httpx.Response(200, json=_TAG_POST_BODY))
        result = _cci(client).tags.create("Finance", apps=["Box", "Dropbox"])

        assert result == _TAG_POST_BODY
        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {"tag": "Finance", "apps": ["Box", "Dropbox"]}

    @respx.mock
    def test_create_with_ids(self, client: NetskopeClient) -> None:
        route = respx.post(_TAGS_URL).mock(return_value=httpx.Response(200, json=_TAG_POST_BODY))
        _cci(client).tags.create("Finance", ids=[4, 7])

        assert sent_json(route) == {"tag": "Finance", "ids": [4, 7]}

    @respx.mock
    def test_create_with_rules(self, client: NetskopeClient) -> None:
        route = respx.post(_TAGS_URL).mock(return_value=httpx.Response(202, json={}))
        rules = [{"attribute": "Data classification", "condition": "is", "value": ["Yes"]}]
        _cci(client).tags.create("attr-tag", rules=rules)

        assert sent_json(route) == {"tag": "attr-tag", "rules": rules}

    @respx.mock
    def test_create_requires_apps_ids_or_rules_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _cci(client).tags.create("Finance")
        with pytest.raises(ValidationError):
            _cci(client).tags.create("Finance", apps=["Box"], ids=[4])
        assert len(respx.calls) == 0

    @respx.mock
    def test_update_appends_apps(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_TAGS_URL}/Finance").mock(
            return_value=httpx.Response(200, json={"status": "Success"})
        )
        _cci(client).tags.update("Finance", apps=["Slack"])

        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"action": "append", "apps": ["Slack"]}

    @respx.mock
    def test_update_removes_apps(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_TAGS_URL}/Finance").mock(
            return_value=httpx.Response(200, json={"status": "Success"})
        )
        _cci(client).tags.update("Finance", action="remove", apps=["Dropbox"])

        assert sent_json(route) == {"action": "remove", "apps": ["Dropbox"]}

    @respx.mock
    def test_update_quotes_tag_in_path(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_TAGS_URL}/my%20tag").mock(
            return_value=httpx.Response(200, json={"status": "Success"})
        )
        _cci(client).tags.update("my tag", apps=["Box"])

        assert route.called

    @respx.mock
    def test_update_add_and_delete_apps_without_action(self, client: NetskopeClient) -> None:
        """add_apps/delete_apps must not carry the action key (per the API spec)."""
        route = respx.patch(f"{_TAGS_URL}/Finance").mock(
            return_value=httpx.Response(200, json={"status": "Success"})
        )
        _cci(client).tags.update("Finance", add_apps=["Campfire"], delete_apps=["Box"])

        assert sent_json(route) == {"add_apps": ["Campfire"], "delete_apps": ["Box"]}

    @respx.mock
    def test_update_with_rules(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_TAGS_URL}/attr-tag").mock(return_value=httpx.Response(202, json={}))
        rules = [{"attribute": "Data classification", "condition": "is", "value": ["Yes"]}]
        _cci(client).tags.update("attr-tag", rules=rules)

        assert sent_json(route) == {"rules": rules}

    @respx.mock
    def test_update_validation_no_http(self, client: NetskopeClient) -> None:
        cci = _cci(client)
        with pytest.raises(ValidationError):
            cci.tags.update("Finance")  # nothing to update
        with pytest.raises(ValidationError):
            cci.tags.update("Finance", apps=["Box"], ids=[4])  # mutually exclusive
        with pytest.raises(ValidationError):
            cci.tags.update("Finance", apps=["Box"], add_apps=["Slack"])  # exclusive groups
        with pytest.raises(ValidationError):
            cci.tags.update("Finance", action="replace", apps=["Box"])  # bad action
        assert len(respx.calls) == 0

    @respx.mock
    def test_delete_sends_comma_joined_tags_param(self, client: NetskopeClient) -> None:
        route = respx.delete(_TAGS_URL).mock(
            return_value=httpx.Response(202, json=_TAG_DELETE_BODY)
        )
        result = _cci(client).tags.delete("Finance", "High-Risk")

        assert result == _TAG_DELETE_BODY
        request = route.calls.last.request
        assert request.method == "DELETE"
        assert dict(request.url.params) == {"tags": "Finance,High-Risk"}

    @respx.mock
    def test_delete_requires_at_least_one_tag_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _cci(client).tags.delete()
        assert len(respx.calls) == 0

    @respx.mock
    def test_list_rules(self, client: NetskopeClient) -> None:
        route = respx.get(_TAGS_RULES_URL).mock(
            return_value=httpx.Response(200, json={"data": [], "status": "Success"})
        )
        result = _cci(client).tags.list_rules(tag="attr-tag", limit=10, offset=5)

        assert result["status"] == "Success"
        params = dict(route.calls.last.request.url.params)
        assert params == {"tag": "attr-tag", "limit": "10", "offset": "5"}

    @respx.mock
    def test_supported_attributes(self, client: NetskopeClient) -> None:
        route = respx.get(_TAGS_ATTRS_URL).mock(
            return_value=httpx.Response(200, json={"data": {}, "status": "Success"})
        )
        result = _cci(client).tags.supported_attributes()

        assert result["status"] == "Success"
        assert route.called

    def test_tags_is_cached(self, client: NetskopeClient) -> None:
        cci = _cci(client)
        assert cci.tags is cci.tags


class TestAsyncCciLookupApp:
    """Tests for AsyncCciResource.lookup_app."""

    @respx.mock
    async def test_lookup_app_sends_apps_param(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_APP_URL).mock(
            return_value=httpx.Response(200, json={"data": [{"app_name": "Dropbox"}]})
        )
        result = await _acci(aclient).lookup_app("Dropbox")

        assert result == {"data": [{"app_name": "Dropbox"}]}
        assert dict(route.calls.last.request.url.params) == {"apps": "Dropbox"}

    @respx.mock
    async def test_lookup_app_sends_optional_filters(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_APP_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        await _acci(aclient).lookup_app("Box", ccl="low", discovered=False, offset=3)

        params = dict(route.calls.last.request.url.params)
        assert params == {"apps": "Box", "ccl": "low", "discovered": "false", "offset": "3"}


class TestAsyncCciTags:
    """Tests for AsyncCciResource.tags."""

    @respx.mock
    async def test_list_without_args_uses_tags_all(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_TAGS_ALL_URL).mock(return_value=httpx.Response(200, json=_TAGS_ALL_BODY))
        result = await _acci(aclient).tags.list()

        assert result["data"]["tags_count"] == 2
        assert route.called

    @respx.mock
    async def test_list_with_apps_joins_with_semicolons(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_TAGS_URL).mock(return_value=httpx.Response(200, json=_TAGS_BY_APP_BODY))
        await _acci(aclient).tags.list(apps=["Box", "Dropbox"])

        assert dict(route.calls.last.request.url.params) == {"apps": "Box;Dropbox"}

    @respx.mock
    async def test_list_with_ids(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_TAGS_URL).mock(return_value=httpx.Response(200, json=_TAGS_BY_APP_BODY))
        await _acci(aclient).tags.list(ids=["4", "7"])

        assert dict(route.calls.last.request.url.params) == {"ids": "4;7"}

    @respx.mock
    async def test_list_apps_and_ids_mutually_exclusive(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await _acci(aclient).tags.list(apps=["Box"], ids=[4])
        assert len(respx.calls) == 0

    @respx.mock
    async def test_create_with_apps(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_TAGS_URL).mock(return_value=httpx.Response(200, json=_TAG_POST_BODY))
        await _acci(aclient).tags.create("High-Risk", apps=["TikTok"])

        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {"tag": "High-Risk", "apps": ["TikTok"]}

    @respx.mock
    async def test_create_requires_apps_ids_or_rules(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await _acci(aclient).tags.create("High-Risk")
        assert len(respx.calls) == 0

    @respx.mock
    async def test_update_patches_tag_by_name(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(f"{_TAGS_URL}/High-Risk").mock(
            return_value=httpx.Response(200, json={"status": "Success"})
        )
        await _acci(aclient).tags.update("High-Risk", action="remove", apps=["Zoom"])

        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"action": "remove", "apps": ["Zoom"]}

    @respx.mock
    async def test_update_nothing_to_update(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await _acci(aclient).tags.update("High-Risk")
        assert len(respx.calls) == 0

    @respx.mock
    async def test_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(_TAGS_URL).mock(
            return_value=httpx.Response(202, json=_TAG_DELETE_BODY)
        )
        result = await _acci(aclient).tags.delete("High-Risk")

        assert result == _TAG_DELETE_BODY
        assert dict(route.calls.last.request.url.params) == {"tags": "High-Risk"}

    @respx.mock
    async def test_delete_requires_tags(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await _acci(aclient).tags.delete()
        assert len(respx.calls) == 0

    @respx.mock
    async def test_list_rules_and_supported_attributes(self, aclient: AsyncNetskopeClient) -> None:
        rules_route = respx.get(_TAGS_RULES_URL).mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        attrs_route = respx.get(_TAGS_ATTRS_URL).mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        tags = _acci(aclient).tags
        assert (await tags.list_rules())["data"] == []
        assert (await tags.supported_attributes())["data"] == {}
        assert rules_route.called
        assert attrs_route.called

    async def test_tags_is_cached(self, aclient: AsyncNetskopeClient) -> None:
        cci = _acci(aclient)
        assert cci.tags is cci.tags
