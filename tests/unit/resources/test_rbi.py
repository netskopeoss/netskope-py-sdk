"""Tests for the RBI (Remote Browser Isolation) resource with mocked HTTP.

Pins the wire contract for each RBI endpoint from the gateway OpenAPI spec
(``ms-rbi-api.yaml``): URL, HTTP verb, query-parameter serialization (the
``status``/``fields`` template filters use comma-joined lists), request bodies,
and that the raw response envelope is returned unchanged as a ``dict``.

``client.rbi`` is not wired on the client, so tests instantiate the resource
classes directly against the transport.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.resources.rbi import AsyncRbiResource, RbiResource
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com/api/v2/rbi"
_APPLICATIONS_URL = f"{_BASE}/applications"
_BROWSERS_URL = f"{_BASE}/browsers/supported"
_CATEGORIES_URL = f"{_BASE}/categories/default"
_TEMPLATES_URL = f"{_BASE}/templates"
_TEMPLATES_DEFAULT_URL = f"{_TEMPLATES_URL}/default"
_TEMPLATES_DIFFS_URL = f"{_TEMPLATES_URL}/diffs"
_TEMPLATES_DEPLOY_URL = f"{_TEMPLATES_URL}/deploy"
_TEMPLATES_REVERT_URL = f"{_TEMPLATES_URL}/revert"
_CLOUDSTORAGE_URL = f"{_BASE}/cloudstorage"
_CDR_URL = f"{_BASE}/cdr"

_TEMPLATE_ID = "e2cbba33-5ffc-4b0a-a4ae-3d58ce82d186"

_OK = {"status": "success", "message": ""}


def _rbi(client: NetskopeClient) -> RbiResource:
    return RbiResource(client._transport)


def _arbi(aclient: AsyncNetskopeClient) -> AsyncRbiResource:
    return AsyncRbiResource(aclient._transport)


class TestReferenceData:
    """Applications, supported browsers, and default categories (read-only)."""

    @respx.mock
    def test_list_applications(self, client: NetskopeClient) -> None:
        body = {"status": "success", "applications": {"google": {"appName": "Google"}}}
        route = respx.get(_APPLICATIONS_URL).mock(return_value=httpx.Response(200, json=body))

        result = _rbi(client).list_applications()

        assert result == body
        assert route.calls.last.request.method == "GET"
        # The gateway spec defines no query params for this endpoint.
        assert dict(route.calls.last.request.url.params) == {}

    @respx.mock
    async def test_list_applications_async(self, aclient: AsyncNetskopeClient) -> None:
        body = {"status": "success", "applications": {}}
        respx.get(_APPLICATIONS_URL).mock(return_value=httpx.Response(200, json=body))
        assert await _arbi(aclient).list_applications() == body

    @respx.mock
    def test_list_supported_browsers(self, client: NetskopeClient) -> None:
        body = [{"browserName": "Chrome"}, {"browserName": "Firefox"}]
        route = respx.get(_BROWSERS_URL).mock(return_value=httpx.Response(200, json=body))

        result = _rbi(client).list_supported_browsers()

        assert result == body
        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_list_supported_browsers_async(self, aclient: AsyncNetskopeClient) -> None:
        body = [{"browserName": "Edge"}]
        respx.get(_BROWSERS_URL).mock(return_value=httpx.Response(200, json=body))
        assert await _arbi(aclient).list_supported_browsers() == body

    @respx.mock
    def test_list_default_categories(self, client: NetskopeClient) -> None:
        body = [{"appCategory": "Uncategorized", "category": ["5001"], "activities": []}]
        route = respx.get(_CATEGORIES_URL).mock(return_value=httpx.Response(200, json=body))

        result = _rbi(client).list_default_categories()

        assert result == body
        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_list_default_categories_async(self, aclient: AsyncNetskopeClient) -> None:
        body = [{"appCategory": "Parked Domains", "category": ["549"]}]
        respx.get(_CATEGORIES_URL).mock(return_value=httpx.Response(200, json=body))
        assert await _arbi(aclient).list_default_categories() == body


class TestTemplatesRead:
    """Template read endpoints."""

    @respx.mock
    def test_list_templates_no_params(self, client: NetskopeClient) -> None:
        body = {"status": "success", "items": [], "total_count": 0}
        route = respx.get(_TEMPLATES_URL).mock(return_value=httpx.Response(200, json=body))

        result = _rbi(client).list_templates()

        assert result == body
        assert route.calls.last.request.method == "GET"
        assert dict(route.calls.last.request.url.params) == {}

    @respx.mock
    def test_list_templates_all_params(self, client: NetskopeClient) -> None:
        route = respx.get(_TEMPLATES_URL).mock(return_value=httpx.Response(200, json=_OK))

        _rbi(client).list_templates(
            name="Accounting",
            limit=10,
            offset=20,
            sort_by="template_name",
            sort_order="desc",
            status=["applied", "pending-update"],
            fields=["name", "popup_message"],
        )

        params = dict(route.calls.last.request.url.params)
        assert params == {
            "name": "Accounting",
            "limit": "10",
            "offset": "20",
            "sortby": "template_name",
            "sortorder": "desc",
            "status": "applied,pending-update",
            "fields": "name,popup_message",
        }

    @respx.mock
    async def test_list_templates_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_TEMPLATES_URL).mock(return_value=httpx.Response(200, json=_OK))
        await _arbi(aclient).list_templates(limit=5, status=["pending-create"])
        params = dict(route.calls.last.request.url.params)
        assert params == {"limit": "5", "status": "pending-create"}

    @respx.mock
    def test_get_template(self, client: NetskopeClient) -> None:
        body = {"status": "success", "template_metadata": {"template_id": _TEMPLATE_ID}}
        route = respx.get(f"{_TEMPLATES_URL}/{_TEMPLATE_ID}").mock(
            return_value=httpx.Response(200, json=body)
        )

        result = _rbi(client).get_template(_TEMPLATE_ID)

        assert result == body
        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_get_template_async(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_TEMPLATES_URL}/{_TEMPLATE_ID}").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        assert await _arbi(aclient).get_template(_TEMPLATE_ID) == _OK

    def test_get_template_rejects_bad_id(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _rbi(client).get_template("bad id!")

    @respx.mock
    def test_get_default_template(self, client: NetskopeClient) -> None:
        route = respx.get(_TEMPLATES_DEFAULT_URL).mock(return_value=httpx.Response(200, json=_OK))
        assert _rbi(client).get_default_template() == _OK
        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_get_default_template_async(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_TEMPLATES_DEFAULT_URL).mock(return_value=httpx.Response(200, json=_OK))
        assert await _arbi(aclient).get_default_template() == _OK

    @respx.mock
    def test_list_template_diffs(self, client: NetskopeClient) -> None:
        route = respx.get(_TEMPLATES_DIFFS_URL).mock(return_value=httpx.Response(200, json=_OK))
        assert _rbi(client).list_template_diffs() == _OK
        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_list_template_diffs_async(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_TEMPLATES_DIFFS_URL).mock(return_value=httpx.Response(200, json=_OK))
        assert await _arbi(aclient).list_template_diffs() == _OK

    @respx.mock
    def test_get_template_diffs(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_TEMPLATES_URL}/{_TEMPLATE_ID}/diffs").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        assert _rbi(client).get_template_diffs(_TEMPLATE_ID) == _OK
        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_get_template_diffs_async(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_TEMPLATES_URL}/{_TEMPLATE_ID}/diffs").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        assert await _arbi(aclient).get_template_diffs(_TEMPLATE_ID) == _OK


class TestTemplatesWrite:
    """Template create/update/delete/restore/deploy/revert endpoints."""

    @respx.mock
    def test_create_template(self, client: NetskopeClient) -> None:
        route = respx.post(_TEMPLATES_URL).mock(return_value=httpx.Response(201, json=_OK))
        payload = {"name": "My Template", "printing": {"enabled": True}}

        result = _rbi(client).create_template(payload)

        assert result == _OK
        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == payload

    @respx.mock
    async def test_create_template_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_TEMPLATES_URL).mock(return_value=httpx.Response(201, json=_OK))
        await _arbi(aclient).create_template({"name": "T"})
        assert sent_json(route) == {"name": "T"}

    @respx.mock
    def test_update_template(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_TEMPLATES_URL}/{_TEMPLATE_ID}").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        payload = {"name": "New name", "printing": {"enabled": True}}

        result = _rbi(client).update_template(_TEMPLATE_ID, payload)

        assert result == _OK
        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == payload

    @respx.mock
    async def test_update_template_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(f"{_TEMPLATES_URL}/{_TEMPLATE_ID}").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        await _arbi(aclient).update_template(_TEMPLATE_ID, {"name": "N"})
        assert sent_json(route) == {"name": "N"}

    @respx.mock
    def test_delete_template(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_TEMPLATES_URL}/{_TEMPLATE_ID}").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        assert _rbi(client).delete_template(_TEMPLATE_ID) == _OK
        assert route.calls.last.request.method == "DELETE"

    @respx.mock
    async def test_delete_template_async(self, aclient: AsyncNetskopeClient) -> None:
        respx.delete(f"{_TEMPLATES_URL}/{_TEMPLATE_ID}").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        assert await _arbi(aclient).delete_template(_TEMPLATE_ID) == _OK

    @respx.mock
    def test_restore_template(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_TEMPLATES_URL}/{_TEMPLATE_ID}/default").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        assert _rbi(client).restore_template(_TEMPLATE_ID) == _OK
        assert route.calls.last.request.method == "POST"

    @respx.mock
    async def test_restore_template_async(self, aclient: AsyncNetskopeClient) -> None:
        respx.post(f"{_TEMPLATES_URL}/{_TEMPLATE_ID}/default").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        assert await _arbi(aclient).restore_template(_TEMPLATE_ID) == _OK

    @respx.mock
    def test_deploy_templates_by_ids(self, client: NetskopeClient) -> None:
        route = respx.post(_TEMPLATES_DEPLOY_URL).mock(return_value=httpx.Response(200, json=_OK))

        _rbi(client).deploy_templates([_TEMPLATE_ID], note="deploy note")

        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {"template_ids": [_TEMPLATE_ID], "note": "deploy note"}
        assert dict(route.calls.last.request.url.params) == {}

    @respx.mock
    def test_deploy_templates_all(self, client: NetskopeClient) -> None:
        route = respx.post(_TEMPLATES_DEPLOY_URL).mock(return_value=httpx.Response(200, json=_OK))

        _rbi(client).deploy_templates(deploy_all=True)

        assert dict(route.calls.last.request.url.params) == {"all": "true"}

    @respx.mock
    async def test_deploy_templates_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_TEMPLATES_DEPLOY_URL).mock(return_value=httpx.Response(200, json=_OK))
        await _arbi(aclient).deploy_templates([_TEMPLATE_ID])
        assert sent_json(route) == {"template_ids": [_TEMPLATE_ID]}

    @respx.mock
    def test_revert_templates(self, client: NetskopeClient) -> None:
        route = respx.post(_TEMPLATES_REVERT_URL).mock(return_value=httpx.Response(200, json=_OK))

        _rbi(client).revert_templates([_TEMPLATE_ID])

        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {"template_ids": [_TEMPLATE_ID]}

    @respx.mock
    async def test_revert_templates_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_TEMPLATES_REVERT_URL).mock(return_value=httpx.Response(200, json=_OK))
        await _arbi(aclient).revert_templates([_TEMPLATE_ID])
        assert sent_json(route) == {"template_ids": [_TEMPLATE_ID]}


class TestCloudStorage:
    """Cloud Storage configuration endpoints."""

    @respx.mock
    def test_get_cloud_storage(self, client: NetskopeClient) -> None:
        route = respx.get(_CLOUDSTORAGE_URL).mock(return_value=httpx.Response(200, json=_OK))
        assert _rbi(client).get_cloud_storage() == _OK
        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_get_cloud_storage_async(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_CLOUDSTORAGE_URL).mock(return_value=httpx.Response(200, json=_OK))
        assert await _arbi(aclient).get_cloud_storage() == _OK

    @respx.mock
    def test_update_cloud_storage(self, client: NetskopeClient) -> None:
        route = respx.patch(_CLOUDSTORAGE_URL).mock(return_value=httpx.Response(200, json=_OK))
        payload = {"enabled": True, "extended_storage_domains": ["example.com"]}

        _rbi(client).update_cloud_storage(payload)

        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == payload

    @respx.mock
    async def test_update_cloud_storage_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(_CLOUDSTORAGE_URL).mock(return_value=httpx.Response(200, json=_OK))
        await _arbi(aclient).update_cloud_storage({"enabled": False})
        assert sent_json(route) == {"enabled": False}

    @respx.mock
    def test_restore_cloud_storage(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_CLOUDSTORAGE_URL}/default").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        assert _rbi(client).restore_cloud_storage() == _OK
        assert route.calls.last.request.method == "POST"

    @respx.mock
    async def test_restore_cloud_storage_async(self, aclient: AsyncNetskopeClient) -> None:
        respx.post(f"{_CLOUDSTORAGE_URL}/default").mock(return_value=httpx.Response(200, json=_OK))
        assert await _arbi(aclient).restore_cloud_storage() == _OK

    @respx.mock
    def test_invalidate_cloud_storage(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_CLOUDSTORAGE_URL}/invalidate").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        assert _rbi(client).invalidate_cloud_storage() == _OK
        assert route.calls.last.request.method == "POST"

    @respx.mock
    async def test_invalidate_cloud_storage_async(self, aclient: AsyncNetskopeClient) -> None:
        respx.post(f"{_CLOUDSTORAGE_URL}/invalidate").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        assert await _arbi(aclient).invalidate_cloud_storage() == _OK


class TestCdr:
    """Content Disarm & Reconstruction (CDR) configuration endpoints."""

    @respx.mock
    def test_get_cdr(self, client: NetskopeClient) -> None:
        route = respx.get(_CDR_URL).mock(return_value=httpx.Response(200, json=_OK))
        assert _rbi(client).get_cdr() == _OK
        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_get_cdr_async(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_CDR_URL).mock(return_value=httpx.Response(200, json=_OK))
        assert await _arbi(aclient).get_cdr() == _OK

    @respx.mock
    def test_update_cdr(self, client: NetskopeClient) -> None:
        route = respx.patch(_CDR_URL).mock(return_value=httpx.Response(200, json=_OK))
        payload = {"vendor": "votiro", "api_key": "sk-abc"}

        _rbi(client).update_cdr(payload)

        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == payload

    @respx.mock
    async def test_update_cdr_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(_CDR_URL).mock(return_value=httpx.Response(200, json=_OK))
        await _arbi(aclient).update_cdr({"vendor": "opswat"})
        assert sent_json(route) == {"vendor": "opswat"}

    @respx.mock
    def test_restore_cdr(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_CDR_URL}/default").mock(return_value=httpx.Response(200, json=_OK))
        assert _rbi(client).restore_cdr() == _OK
        assert route.calls.last.request.method == "POST"

    @respx.mock
    async def test_restore_cdr_async(self, aclient: AsyncNetskopeClient) -> None:
        respx.post(f"{_CDR_URL}/default").mock(return_value=httpx.Response(200, json=_OK))
        assert await _arbi(aclient).restore_cdr() == _OK

    @respx.mock
    def test_list_cdr_vendors(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_CDR_URL}/vendors").mock(return_value=httpx.Response(200, json=_OK))
        assert _rbi(client).list_cdr_vendors() == _OK
        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_list_cdr_vendors_async(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_CDR_URL}/vendors").mock(return_value=httpx.Response(200, json=_OK))
        assert await _arbi(aclient).list_cdr_vendors() == _OK

    @respx.mock
    def test_test_cdr_config(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_CDR_URL}/testconfig").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        payload = {
            "vendor": "votiro",
            "endpoint_url": "https://x",
            "api_key": "k",
            "workflow_rule_name": "r",
        }

        _rbi(client).test_cdr_config(payload)

        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == payload

    @respx.mock
    async def test_test_cdr_config_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_CDR_URL}/testconfig").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        await _arbi(aclient).test_cdr_config({"vendor": "votiro"})
        assert sent_json(route) == {"vendor": "votiro"}
