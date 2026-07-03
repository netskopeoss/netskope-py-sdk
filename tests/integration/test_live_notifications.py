"""Live integration tests for the user notifications API.

Follows the safety checklist in ``tests/integration/conftest.py``: test
objects use the ``sdk-inttest-`` prefix, every create has a guaranteed
delete, and unavailable APIs skip rather than fail.  Delivery settings are
read-only here — they are a tenant-wide setting and never mutated.

``client.notifications`` is not wired into the clients yet, so the resource
is instantiated directly against the client transport.
"""

from __future__ import annotations

import contextlib

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.models.notifications import NotificationTemplate
from netskope.resources.notifications import NotificationsResource

from .conftest import skip_if_unavailable, unique_name


@pytest.fixture
def notifications(client: NetskopeClient) -> NotificationsResource:
    return NotificationsResource(client._transport)


@pytest.mark.integration
class TestNotificationTemplatesIntegration:
    """Live tests for user notification templates."""

    def test_list_templates(self, notifications: NotificationsResource) -> None:
        """Read smoke: listing templates succeeds and yields typed models."""
        try:
            templates = notifications.list_templates(limit=10)
        except APIError as e:
            skip_if_unavailable(e, "Notification templates")
        else:
            assert isinstance(templates, list)
            if templates:
                assert isinstance(templates[0], NotificationTemplate)

    def test_template_write_cycle(self, notifications: NotificationsResource) -> None:
        """Create → get → update name → delete a notification template."""
        name = unique_name("notif")
        try:
            created = notifications.create_template(
                name,
                title="sdk-inttest title",
                message="sdk-inttest body",
                action_type="block",
                ack_button_text="OK",
            )
        except APIError as e:
            skip_if_unavailable(e, "Notification templates")
            return
        assert created.id is not None
        try:
            fetched = notifications.get_template(created.id)
            assert fetched.id == created.id
            assert fetched.name == name

            # The update schema marks name/title/message required, so send
            # all three even when only renaming.
            new_name = unique_name("notif")
            updated = notifications.update_template(
                created.id,
                name=new_name,
                title="sdk-inttest title",
                message="sdk-inttest body",
            )
            assert updated.name == new_name
        finally:
            with contextlib.suppress(APIError):
                notifications.delete_template(created.id)


@pytest.mark.integration
class TestDeliverySettingsIntegration:
    """Live read-only tests for notification delivery settings."""

    def test_get_delivery_settings(self, notifications: NotificationsResource) -> None:
        """Read smoke: delivery settings are retrievable (never mutated)."""
        try:
            settings = notifications.get_delivery_settings()
        except APIError as e:
            skip_if_unavailable(e, "Notification delivery settings")
        else:
            assert isinstance(settings, dict)
