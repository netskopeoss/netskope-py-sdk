"""Tests for the notifications resource with mocked HTTP.

``client.notifications`` is not wired into the clients yet, so the resources
are instantiated directly against the client transports.

Per the API gateway spec: list responses use a ``{"totalCount": n, "result":
[...]}`` envelope, create requires ``name``/``title``/``message``, update is
PATCH, and ``templateActionType`` is limited to ``block``/``useralert``.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.notifications import NotificationTemplate, TemplateActionType
from netskope.resources.notifications import AsyncNotificationsResource, NotificationsResource
from tests.unit.resources.conftest import sent_json

_TEMPLATES_URL = "https://t.goskope.com/api/v2/notifications/user/templates"
_SETTINGS_URL = "https://t.goskope.com/api/v2/notifications/user/deliverysettings"

# Per the gateway spec, template ids are strings and field names are camelCase.
_TEMPLATE = {
    "id": "42",
    "name": "Custom Block Page",
    "title": "Access Denied",
    "message": "This site is blocked.",
    "templateActionType": "block",
    "ackButtonText": "OK",
    "logoSize": "medium",
    "stripeColor": "#A659B1",
}

_SETTINGS = {
    "cloudAppsDeliveryMethod": "client",
    "webTrafficDeliveryMethod": "browser",
    "notificationTimeout": 120,
}


class TestNotificationsResource:
    """Sync tests for the notifications resource."""

    @respx.mock
    def test_list_templates_result_envelope_no_params(self, client: NetskopeClient) -> None:
        """list_templates() GETs the base path; spec envelope is {totalCount, result}."""
        route = respx.get(_TEMPLATES_URL).mock(
            return_value=httpx.Response(200, json={"totalCount": 1, "result": [_TEMPLATE]})
        )
        templates = NotificationsResource(client._transport).list_templates()

        assert len(templates) == 1
        assert isinstance(templates[0], NotificationTemplate)
        assert templates[0].id == "42"
        assert templates[0].name == "Custom Block Page"
        assert templates[0].template_action_type == "block"
        assert templates[0].ack_button_text == "OK"
        # No pagination params are sent when limit/offset are left as None.
        assert not route.calls.last.request.url.params

    @respx.mock
    def test_list_templates_sends_limit_and_offset(self, client: NetskopeClient) -> None:
        route = respx.get(_TEMPLATES_URL).mock(
            return_value=httpx.Response(200, json={"totalCount": 0, "result": []})
        )
        templates = NotificationsResource(client._transport).list_templates(limit=5, offset=10)

        assert templates == []
        params = route.calls.last.request.url.params
        assert params["limit"] == "5"
        assert params["offset"] == "10"

    @respx.mock
    def test_list_templates_offset_zero_is_sent(self, client: NetskopeClient) -> None:
        """offset=0 is a valid value and must not be dropped."""
        route = respx.get(_TEMPLATES_URL).mock(
            return_value=httpx.Response(200, json={"totalCount": 0, "result": []})
        )
        NotificationsResource(client._transport).list_templates(offset=0)
        assert route.calls.last.request.url.params["offset"] == "0"

    @respx.mock
    def test_get_template_top_level_body(self, client: NetskopeClient) -> None:
        """get_template() returns the template parsed from a top-level body."""
        respx.get(f"{_TEMPLATES_URL}/42").mock(return_value=httpx.Response(200, json=_TEMPLATE))
        template = NotificationsResource(client._transport).get_template(42)

        assert template.id == "42"
        assert template.title == "Access Denied"
        assert template.logo_size == "medium"
        assert template.stripe_color == "#A659B1"

    @respx.mock
    def test_get_template_invalid_id_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            NotificationsResource(client._transport).get_template("../etc/passwd")

    @respx.mock
    def test_create_template_payload_and_response(self, client: NetskopeClient) -> None:
        """Create POSTs camelCase fields; unset optional fields are omitted."""
        route = respx.post(_TEMPLATES_URL).mock(return_value=httpx.Response(201, json=_TEMPLATE))
        template = NotificationsResource(client._transport).create_template(
            "Custom Block Page",
            title="Access Denied",
            message="This site is blocked.",
            action_type=TemplateActionType.BLOCK,
            ack_button_text="OK",
        )

        assert sent_json(route) == {
            "name": "Custom Block Page",
            "title": "Access Denied",
            "message": "This site is blocked.",
            "templateActionType": "block",
            "ackButtonText": "OK",
        }
        assert isinstance(template, NotificationTemplate)
        assert template.id == "42"

    @respx.mock
    def test_create_template_useralert_all_optional_fields(self, client: NetskopeClient) -> None:
        route = respx.post(_TEMPLATES_URL).mock(return_value=httpx.Response(201, json=_TEMPLATE))
        NotificationsResource(client._transport).create_template(
            "Alert Page",
            title="Warning",
            message="Sensitive data.",
            action_type="useralert",
            subtitle="Think twice",
            proceed_button_text="Proceed",
            stop_button_text="Stop",
            footer_message="Contact IT",
            logo_image_name="corp-logo",
            logo_size="large",
            redirect_url="https://example.invalid/blocked",
            stripe_color="#A659B1",
        )

        assert sent_json(route) == {
            "name": "Alert Page",
            "title": "Warning",
            "message": "Sensitive data.",
            "templateActionType": "useralert",
            "subtitle": "Think twice",
            "proceedButtonText": "Proceed",
            "stopButtonText": "Stop",
            "footerMessage": "Contact IT",
            "logoImageName": "corp-logo",
            "logoSize": "large",
            "redirectUrl": "https://example.invalid/blocked",
            "stripeColor": "#A659B1",
        }

    @respx.mock
    def test_create_template_invalid_action_type_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            NotificationsResource(client._transport).create_template(
                "X", title="T", message="M", action_type="warn"
            )

    @respx.mock
    def test_create_template_invalid_logo_size_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            NotificationsResource(client._transport).create_template(
                "X", title="T", message="M", logo_size="huge"
            )

    @respx.mock
    def test_update_template_patch_verb_partial_payload(self, client: NetskopeClient) -> None:
        """Update uses PATCH (per gateway spec; the CLI's PUT is a known quirk)."""
        route = respx.patch(f"{_TEMPLATES_URL}/42").mock(
            return_value=httpx.Response(200, json={**_TEMPLATE, "name": "Renamed"})
        )
        template = NotificationsResource(client._transport).update_template(
            42, name="Renamed", title="Access Denied", message="This site is blocked."
        )

        assert sent_json(route) == {
            "name": "Renamed",
            "title": "Access Denied",
            "message": "This site is blocked.",
        }
        assert template.name == "Renamed"

    @respx.mock
    def test_update_template_no_fields_raises_without_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            NotificationsResource(client._transport).update_template(42)

    @respx.mock
    def test_update_template_invalid_action_type_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            NotificationsResource(client._transport).update_template(42, action_type="redirect")

    @respx.mock
    def test_update_template_invalid_id_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            NotificationsResource(client._transport).update_template("a/b", name="X")

    @respx.mock
    def test_delete_template_returns_none(self, client: NetskopeClient) -> None:
        """Delete returns None even though the API echoes {id, name}."""
        route = respx.delete(f"{_TEMPLATES_URL}/42").mock(
            return_value=httpx.Response(200, json={"id": "42", "name": "Custom Block Page"})
        )
        result = NotificationsResource(client._transport).delete_template(42)
        assert result is None
        assert route.called

    @respx.mock
    def test_delete_template_invalid_id_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            NotificationsResource(client._transport).delete_template("a b")

    @respx.mock
    def test_get_delivery_settings(self, client: NetskopeClient) -> None:
        route = respx.get(_SETTINGS_URL).mock(return_value=httpx.Response(200, json=_SETTINGS))
        settings = NotificationsResource(client._transport).get_delivery_settings()

        assert settings == _SETTINGS
        assert route.calls.last.request.method == "GET"


class TestAsyncNotificationsResource:
    """Async tests mirroring the sync coverage."""

    @respx.mock
    async def test_list_templates_result_envelope(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_TEMPLATES_URL).mock(
            return_value=httpx.Response(200, json={"totalCount": 1, "result": [_TEMPLATE]})
        )
        templates = await AsyncNotificationsResource(aclient._transport).list_templates(limit=25)

        assert len(templates) == 1
        assert isinstance(templates[0], NotificationTemplate)
        assert templates[0].id == "42"
        assert route.calls.last.request.url.params["limit"] == "25"

    @respx.mock
    async def test_get_template(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_TEMPLATES_URL}/42").mock(return_value=httpx.Response(200, json=_TEMPLATE))
        template = await AsyncNotificationsResource(aclient._transport).get_template("42")
        assert template.id == "42"
        assert template.template_action_type == "block"

    @respx.mock
    async def test_get_template_invalid_id_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await AsyncNotificationsResource(aclient._transport).get_template("../x")

    @respx.mock
    async def test_create_template_payload(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_TEMPLATES_URL).mock(return_value=httpx.Response(201, json=_TEMPLATE))
        template = await AsyncNotificationsResource(aclient._transport).create_template(
            "Custom Block Page",
            title="Access Denied",
            message="This site is blocked.",
            ack_button_text="OK",
        )

        assert sent_json(route) == {
            "name": "Custom Block Page",
            "title": "Access Denied",
            "message": "This site is blocked.",
            "ackButtonText": "OK",
        }
        assert template.id == "42"

    @respx.mock
    async def test_create_template_invalid_action_type_no_http(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError):
            await AsyncNotificationsResource(aclient._transport).create_template(
                "X", title="T", message="M", action_type="quarantine"
            )

    @respx.mock
    async def test_update_template_patch_verb(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(f"{_TEMPLATES_URL}/42").mock(
            return_value=httpx.Response(200, json={**_TEMPLATE, "subtitle": "New"})
        )
        template = await AsyncNotificationsResource(aclient._transport).update_template(
            42, subtitle="New"
        )
        assert sent_json(route) == {"subtitle": "New"}
        assert template.subtitle == "New"

    @respx.mock
    async def test_update_template_no_fields_raises_without_http(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError):
            await AsyncNotificationsResource(aclient._transport).update_template(42)

    @respx.mock
    async def test_delete_template(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_TEMPLATES_URL}/42").mock(
            return_value=httpx.Response(200, json={"id": "42", "name": "X"})
        )
        result = await AsyncNotificationsResource(aclient._transport).delete_template(42)
        assert result is None
        assert route.called

    @respx.mock
    async def test_get_delivery_settings(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_SETTINGS_URL).mock(return_value=httpx.Response(200, json=_SETTINGS))
        settings = await AsyncNotificationsResource(aclient._transport).get_delivery_settings()
        assert settings == _SETTINGS
