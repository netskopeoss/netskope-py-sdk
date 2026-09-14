"""Tests for the RBI (Remote Browser Isolation) resource with mocked HTTP.

Pins the wire contract for each RBI endpoint from the gateway OpenAPI spec
(``ms-rbi-api.yaml``): URL, HTTP verb, query-parameter serialization (the
``status``/``fields`` template filters use comma-joined lists), request bodies,
and that the raw response envelope is returned unchanged as a ``dict``.

``client.rbi`` is not wired on the client, so tests instantiate the resource
classes directly against the transport.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.rbi import RbiTemplateSettings, RbiToggle
from netskope.resources.rbi.resource import AsyncRbiResource, RbiResource
from tests.unit.resources.conftest import EXAMPLE_BASE, contract_router, sent_json

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
    def test_restore_cdr_uses_put(self, client: NetskopeClient) -> None:
        """``RestoreCdr`` is ``PUT /cdr/default``; the path has no ``post`` (rbi/cdr.yaml:164)."""
        route = respx.put(f"{_CDR_URL}/default").mock(return_value=httpx.Response(200, json=_OK))
        assert _rbi(client).restore_cdr() == _OK
        assert route.calls.last.request.method == "PUT"

    @respx.mock
    async def test_restore_cdr_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(f"{_CDR_URL}/default").mock(return_value=httpx.Response(200, json=_OK))
        assert await _arbi(aclient).restore_cdr() == _OK
        assert route.calls.last.request.method == "PUT"

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
    def test_test_cdr_config_is_a_get_with_query(self, client: NetskopeClient) -> None:
        """``TestCdrConfig`` is ``GET /cdr/testconfig`` with query params (cdr.yaml:380-480)."""
        route = respx.get(f"{_CDR_URL}/testconfig").mock(return_value=httpx.Response(200, json=_OK))

        result = _rbi(client).test_cdr_config(
            vendor="votiro",
            endpoint_url="https://api.example.test/v4",
            workflow_rule_name="cdr",
        )

        assert result == _OK
        request = route.calls.last.request
        assert request.method == "GET"
        assert request.content == b""
        assert dict(request.url.params) == {
            "vendor": "votiro",
            "endpoint_url": "https://api.example.test/v4",
            "workflow_rule_name": "cdr",
        }

    @respx.mock
    def test_legacy_mapping_becomes_the_query(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_CDR_URL}/testconfig").mock(return_value=httpx.Response(200, json=_OK))

        _rbi(client).test_cdr_config({"id": "0b2f1a3e-0000-4000-8000-000000000001"})

        assert dict(route.calls.last.request.url.params) == {
            "id": "0b2f1a3e-0000-4000-8000-000000000001"
        }

    @respx.mock
    @pytest.mark.parametrize(
        ("payload", "message"),
        [
            ({"api_key": "k"}, "needs either config_id"),
            ({"nope": 1}, "does not accept"),
        ],
    )
    def test_rejected_arguments_never_reach_the_wire(
        self, client: NetskopeClient, payload: dict[str, object], message: str
    ) -> None:
        route = respx.route(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match=message):
            _rbi(client).test_cdr_config(payload)
        assert route.call_count == 0

    @respx.mock
    def test_no_selector_is_rejected(self, client: NetskopeClient) -> None:
        route = respx.route(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="needs either config_id"):
            _rbi(client).test_cdr_config()
        assert route.call_count == 0

    @respx.mock
    async def test_test_cdr_config_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(f"{_CDR_URL}/testconfig").mock(return_value=httpx.Response(200, json=_OK))
        await _arbi(aclient).test_cdr_config({"vendor": "votiro"})
        assert route.calls.last.request.method == "GET"
        assert dict(route.calls.last.request.url.params) == {"vendor": "votiro"}


class TestInlineCdrApiKey:
    """Inline mode carries the key in ``X-CDR-Api-Key`` (rbi/cdr.yaml:472-480)."""

    @respx.mock
    def test_api_key_travels_as_a_header_not_a_query_value(self, client: NetskopeClient) -> None:
        route = respx.get(url__regex=r".*/api/v2/rbi/cdr/testconfig.*").mock(
            return_value=httpx.Response(200, json={"test_result": {"success": True}})
        )
        _rbi(client).test_cdr_config(
            {"vendor": "votiro", "api_key": "sk-abc", "endpoint_url": "https://v.example.com"}
        )
        request = route.calls.last.request
        assert request.headers["X-CDR-Api-Key"] == "sk-abc"
        assert "api_key" not in str(request.url)
        assert request.url.params["vendor"] == "votiro"


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.


@respx.mock
def test_rbi_list_templates_accepts_a_single_status(example_client: NetskopeClient) -> None:
    """rbi/templates.yaml:220-229 declares `status` as an array, style=form.

    A bare `str` is iterable, so forwarding it unchanged produced
    `status=a,p,p,l,i,e,d`.
    """
    route = respx.get(f"{EXAMPLE_BASE}/api/v2/rbi/templates").mock(
        return_value=httpx.Response(200, json={"data": [], "total_count": 0})
    )
    example_client.rbi.list_templates(status="applied")
    assert dict(route.calls[-1].request.url.params)["status"] == "applied"

    example_client.rbi.list_templates(status=["applied", "pending-create"])
    assert dict(route.calls[-1].request.url.params)["status"] == "applied,pending-create"


@respx.mock
def test_rbi_deploy_bounds_its_template_ids(example_client: NetskopeClient) -> None:
    """rbi/templates.yaml:2061 and :2085 set minItems 1; :456-460 forbids all+ids."""
    route = respx.post(f"{EXAMPLE_BASE}/api/v2/rbi/templates/deploy").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    example_client.rbi.deploy_templates("abc")
    assert route.calls[-1].request.read() == b'{"template_ids":["abc"]}'

    with pytest.raises(ValidationError, match="at least one template"):
        example_client.rbi.deploy_templates([])
    with pytest.raises(ValidationError, match="exactly one"):
        example_client.rbi.deploy_templates(["a"], deploy_all=True)


class TestRbiWatermarkIsOptional:
    def test_watermark_without_enabled_decodes(self) -> None:
        """``watermark.enabled`` is in no ``required`` list and the contract
        notes migrated tenants may not carry it (rbi/templates.yaml:1654-1661);
        ``TemplateData`` also leaves ``watermark`` itself out of its required
        set (:1662-1678)."""
        settings = RbiTemplateSettings.model_validate({"name": "t", "watermark": {}})
        assert settings.watermark is not None and settings.watermark.enabled is None

    def test_the_other_toggles_still_require_enabled(self) -> None:
        """Every other ``$Enabled`` toggle requires ``enabled``."""
        with pytest.raises(Exception, match="enabled"):
            RbiToggle.model_validate({})


class TestRbiTemplateQueryEnums:
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"sort_by": "nope"}, "sort_by must be one of"),
            ({"sort_order": "sideways"}, "sort_order must be one of"),
            ({"status": ["bogus"]}, "Invalid status value"),
            ({"fields": ["not_a_field"]}, "Invalid fields value"),
            ({"status": []}, "at least one template status"),
        ],
    )
    def test_unenumerated_values_are_rejected(
        self, contract_client: NetskopeClient, kwargs: dict[str, Any], message: str
    ) -> None:
        """``sortby`` (rbi/templates.yaml:181-194), ``sortorder`` (:195-206),
        ``status`` (:207-229, ``minItems: 1``) and ``fields`` (:230-257) are all
        enumerated."""
        with contract_router() as mock:
            route = mock.get("/api/v2/rbi/templates").mock(
                return_value=httpx.Response(200, json={})
            )
            with pytest.raises(ValidationError, match=message):
                contract_client.rbi.list_templates(**kwargs)
            assert route.call_count == 0

    def test_declared_values_are_comma_joined(self, contract_client: NetskopeClient) -> None:
        """``status`` and ``fields`` are ``style: form, explode: false``
        (rbi/templates.yaml:218-219, :237-238)."""
        with contract_router() as mock:
            route = mock.get("/api/v2/rbi/templates").mock(
                return_value=httpx.Response(200, json={"templates": []})
            )
            contract_client.rbi.list_templates(
                sort_by="template_name",
                sort_order="desc",
                status=["applied", "pending-update"],
                fields=["name", "watermark"],
            )
        assert dict(route.calls.last.request.url.params) == {
            "sortby": "template_name",
            "sortorder": "desc",
            "status": "applied,pending-update",
            "fields": "name,watermark",
        }

    async def test_async_rejects_the_same_values(
        self, contract_aclient: AsyncNetskopeClient
    ) -> None:
        with contract_router() as mock:
            route = mock.get("/api/v2/rbi/templates").mock(
                return_value=httpx.Response(200, json={})
            )
            with pytest.raises(ValidationError, match="sort_by must be one of"):
                await contract_aclient.rbi.list_templates(sort_by="nope")
            assert route.call_count == 0
