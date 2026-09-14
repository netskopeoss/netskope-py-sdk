"""Tests for the notifications resource with mocked HTTP.

``client.notifications`` is not wired into the clients yet, so the resources
are instantiated directly against the client transports.

Per the API gateway spec: list responses use a ``{"totalCount": n, "result":
[...]}`` envelope, create requires ``name``/``title``/``message``, update is
PATCH, and ``templateActionType`` is limited to ``block``/``useralert``.
"""

from __future__ import annotations

import json
from typing import ClassVar

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.notifications import (
    NotificationTemplate,
    NotificationTemplateWrite,
    TemplateActionType,
)
from netskope.resources.notifications.resource import (
    AsyncNotificationsResource,
    NotificationsResource,
)
from tests.unit.resources.conftest import contract_router, sent_json

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
    def test_limit_and_offset_slice_locally(self, client: NetskopeClient) -> None:
        """``GET /user/templates`` declares no parameters at all
        (user-notifications-templates.yaml:206-239), so paging happens in the SDK."""
        rows = [{**_TEMPLATE, "id": str(index)} for index in range(5)]
        route = respx.get(_TEMPLATES_URL).mock(
            return_value=httpx.Response(200, json={"totalCount": 5, "result": rows})
        )
        templates = NotificationsResource(client._transport).list_templates(limit=2, offset=1)

        assert [template.id for template in templates] == ["1", "2"]
        assert not route.calls.last.request.url.params

    @respx.mock
    def test_offset_zero_keeps_the_whole_collection(self, client: NetskopeClient) -> None:
        rows = [{**_TEMPLATE, "id": str(index)} for index in range(3)]
        route = respx.get(_TEMPLATES_URL).mock(
            return_value=httpx.Response(200, json={"totalCount": 3, "result": rows})
        )
        templates = NotificationsResource(client._transport).list_templates(offset=0)
        assert [template.id for template in templates] == ["0", "1", "2"]
        assert not route.calls.last.request.url.params

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
    def test_update_template_patch_verb_complete_payload(self, client: NetskopeClient) -> None:
        """PATCH uses NotificationsCreateRequest (user-notifications-templates.yaml:376)."""
        route = respx.patch(f"{_TEMPLATES_URL}/42").mock(
            return_value=httpx.Response(200, json={**_TEMPLATE, "name": "Renamed"})
        )
        template = NotificationsResource(client._transport).update_template(
            42,
            name="Renamed",
            title="Access Denied",
            message="This site is blocked.",
            ack_button_text="OK",
        )

        assert sent_json(route) == {
            "name": "Renamed",
            "title": "Access Denied",
            "message": "This site is blocked.",
            "ackButtonText": "OK",
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
        assert not route.calls.last.request.url.params

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
            42,
            name="Block",
            title="Denied",
            message="Blocked",
            ack_button_text="OK",
            subtitle="New",
        )
        assert sent_json(route) == {
            "name": "Block",
            "title": "Denied",
            "message": "Blocked",
            "ackButtonText": "OK",
            "subtitle": "New",
        }
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


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.


class TestNotificationTemplateRules:
    _TEMPLATE: ClassVar[dict[str, str]] = {"id": "42", "name": "Custom Block Page"}

    def test_create_applies_lengths_and_button_rules(self, contract_client: NetskopeClient) -> None:
        """``NotificationsCreateRequest`` caps ``title`` at 60 and each button
        label at 14 characters, and its property descriptions make
        ``ackButtonText`` required for ``block`` and disallowed for
        ``useralert`` (user-notifications-templates.yaml:10-91)."""
        with contract_router() as mock:
            route = mock.post("/api/v2/notifications/user/templates").mock(
                return_value=httpx.Response(201, json=self._TEMPLATE)
            )
            with pytest.raises(ValidationError, match="title"):
                contract_client.notifications.create_template(
                    "n", title="T" * 80, message="m", ack_button_text="OK"
                )
            with pytest.raises(ValidationError, match="ackButtonText"):
                contract_client.notifications.create_template(
                    "n", title="T", message="m", ack_button_text="A" * 30
                )
            with pytest.raises(ValidationError, match="forbid proceed/stop"):
                contract_client.notifications.create_template(
                    "n",
                    title="T",
                    message="m",
                    action_type="block",
                    ack_button_text="OK",
                    proceed_button_text="Go",
                )
            assert route.call_count == 0

    def test_a_valid_create_still_sends_camel_case_fields(
        self, contract_client: NetskopeClient
    ) -> None:
        with contract_router() as mock:
            route = mock.post("/api/v2/notifications/user/templates").mock(
                return_value=httpx.Response(201, json=self._TEMPLATE)
            )
            contract_client.notifications.create_template(
                "Custom Block Page",
                title="Access Denied",
                message="This site is blocked.",
                action_type="block",
                ack_button_text="OK",
            )
        assert json.loads(route.calls.last.request.content) == {
            "name": "Custom Block Page",
            "title": "Access Denied",
            "message": "This site is blocked.",
            "templateActionType": "block",
            "ackButtonText": "OK",
        }

    def test_patch_requires_the_complete_body_and_applies_the_lengths(
        self, contract_client: NetskopeClient
    ) -> None:
        """``PATCH /user/templates/{id}`` points at the same body schema
        (user-notifications-templates.yaml:376-381), so required fields and ``maxLength`` rules
        apply to PATCH as well as POST."""
        with contract_router() as mock:
            route = mock.patch("/api/v2/notifications/user/templates/42").mock(
                return_value=httpx.Response(200, json={**self._TEMPLATE, "subtitle": "New"})
            )
            with pytest.raises(ValidationError, match="subtitle"):
                contract_client.notifications.update_template(42, subtitle="S" * 100)
            with pytest.raises(ValidationError, match="name"):
                contract_client.notifications.update_template(42, subtitle="New")
            template = contract_client.notifications.update_template(
                42,
                name="Block",
                title="Denied",
                message="Blocked",
                ack_button_text="OK",
                subtitle="New",
            )
        assert template.subtitle == "New"
        assert json.loads(route.calls.last.request.content) == {
            "name": "Block",
            "title": "Denied",
            "message": "Blocked",
            "ackButtonText": "OK",
            "subtitle": "New",
        }

    async def test_async_writes_apply_the_same_rules(
        self, contract_aclient: AsyncNetskopeClient
    ) -> None:
        with contract_router() as mock:
            route = mock.route(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
            with pytest.raises(ValidationError, match="title"):
                await contract_aclient.notifications.create_template(
                    "n", title="T" * 80, message="m", ack_button_text="OK"
                )
            with pytest.raises(ValidationError, match="stopButtonText"):
                await contract_aclient.notifications.update_template(42, stop_button_text="S" * 30)
            assert route.call_count == 0

    def test_the_typed_write_model_is_unchanged(self) -> None:
        """The typed surface already required the trio and the button rules."""
        with pytest.raises(Exception, match="title"):
            NotificationTemplateWrite(name="n", title="T" * 80, message="m", ackButtonText="OK")


class TestTemplateUpdateIsAWholeDocument:
    """The PATCH body is the complete template, and the errors have to say so.

    ``NotificationTemplateWrite`` is documented as "Complete template content
    required by both POST and PATCH", so a partial update is a read-modify-write
    the caller performs. These pin that contract and pin the two error messages
    a caller actually hits, because the previous wording sent them the wrong way:
    ``action_type`` defaults to ``block``, so omitting it on a useralert update
    produced a block-button complaint that never named the real cause.
    """

    @respx.mock
    def test_a_partial_update_is_refused_before_any_request(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError) as caught:
            NotificationsResource(client._transport).update_template("7", subtitle="new")
        assert "name" in str(caught.value)
        assert "complete" in str(caught.value).lower()
        assert len(respx.calls) == 0

    @respx.mock
    def test_useralert_buttons_without_an_action_type_name_the_action_type(
        self, client: NetskopeClient
    ) -> None:
        with pytest.raises(ValidationError) as caught:
            NotificationsResource(client._transport).update_template(
                "7",
                name="n",
                title="t",
                message="m",
                proceed_button_text="Go",
                stop_button_text="Stop",
            )
        assert "action_type" in str(caught.value)
        assert len(respx.calls) == 0

    @respx.mock
    def test_a_complete_useralert_body_reaches_the_wire(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_TEMPLATES_URL}/7").mock(
            return_value=httpx.Response(200, json={"id": 7, "name": "n"})
        )
        NotificationsResource(client._transport).update_template(
            "7",
            name="n",
            title="t",
            message="m",
            action_type="useralert",
            proceed_button_text="Go",
            stop_button_text="Stop",
        )
        assert json.loads(route.calls.last.request.content)["templateActionType"] == "useralert"

    @respx.mock
    async def test_async_partial_update_is_refused_before_any_request(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError):
            await AsyncNotificationsResource(aclient._transport).update_template("7", subtitle="s")
        assert len(respx.calls) == 0


class TestTemplateWindowIsValidated:
    """A local window is refused, not applied from the wrong end.

    ``GET /user/templates`` is unpaginated, so ``limit``/``offset`` slice the
    decoded list. ``templates[-2:]`` is the last two templates, not "page -2",
    so an out-of-range value has to be refused rather than applied.
    """

    @respx.mock
    @pytest.mark.parametrize(
        "window", [{"offset": -2}, {"limit": -2}], ids=["negative-offset", "negative-limit"]
    )
    def test_a_negative_window_is_refused_before_the_request(
        self, client: NetskopeClient, window: dict[str, int]
    ) -> None:
        with pytest.raises(ValidationError):
            NotificationsResource(client._transport).list_templates(**window)
        assert len(respx.calls) == 0

    @respx.mock
    async def test_async_negative_window_is_refused_before_the_request(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError):
            await AsyncNotificationsResource(aclient._transport).list_templates(offset=-2)
        assert len(respx.calls) == 0
