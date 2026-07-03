"""Notifications resource — manage user notification templates and delivery settings.

Example::

    for template in client.notifications.list_templates():
        print(f"{template.id}: {template.name}")

    template = client.notifications.create_template(
        "Custom Block Page",
        title="Access Denied",
        message="This site is blocked by policy NS_POLICY_NAME.",
        ack_button_text="OK",
    )
"""

from __future__ import annotations

import builtins
from typing import Any

from netskope.exceptions import ValidationError
from netskope.models.notifications import LogoSize, NotificationTemplate, TemplateActionType
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list, validate_id

_TEMPLATES_PATH = "/api/v2/notifications/user/templates"
_DELIVERY_SETTINGS_PATH = "/api/v2/notifications/user/deliverysettings"

_VALID_ACTION_TYPES = tuple(t.value for t in TemplateActionType)
_VALID_LOGO_SIZES = tuple(s.value for s in LogoSize)


def _build_list_params(limit: int | None, offset: int | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return params


def _build_template_payload(
    *,
    name: str | None,
    title: str | None,
    message: str | None,
    action_type: TemplateActionType | str | None,
    subtitle: str | None,
    ack_button_text: str | None,
    proceed_button_text: str | None,
    stop_button_text: str | None,
    footer_message: str | None,
    logo_image_name: str | None,
    logo_size: LogoSize | str | None,
    redirect_url: str | None,
    stripe_color: str | None,
) -> dict[str, Any]:
    """Assemble a template create/update body, validating enumerated fields.

    Only fields that are not ``None`` are included, keyed by the API's
    camelCase field names.
    """
    if action_type is not None and str(action_type) not in _VALID_ACTION_TYPES:
        raise ValidationError(
            f"Invalid action_type {action_type!r}. Must be one of: {', '.join(_VALID_ACTION_TYPES)}"
        )
    if logo_size is not None and str(logo_size) not in _VALID_LOGO_SIZES:
        raise ValidationError(
            f"Invalid logo_size {logo_size!r}. Must be one of: {', '.join(_VALID_LOGO_SIZES)}"
        )
    fields: tuple[tuple[str, Any], ...] = (
        ("name", name),
        ("title", title),
        ("message", message),
        ("templateActionType", None if action_type is None else str(action_type)),
        ("subtitle", subtitle),
        ("ackButtonText", ack_button_text),
        ("proceedButtonText", proceed_button_text),
        ("stopButtonText", stop_button_text),
        ("footerMessage", footer_message),
        ("logoImageName", logo_image_name),
        ("logoSize", None if logo_size is None else str(logo_size)),
        ("redirectUrl", redirect_url),
        ("stripeColor", stripe_color),
    )
    return {key: value for key, value in fields if value is not None}


def _template_path(template_id: str | int) -> str:
    return f"{_TEMPLATES_PATH}/{validate_id(template_id, 'template_id')}"


class NotificationsResource(SyncResource):
    """Synchronous interface to the user notifications API."""

    def list_templates(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> builtins.list[NotificationTemplate]:
        """List user notification templates.

        Args:
            limit: Maximum number of templates to return.
            offset: Number of records to skip (pagination).

        Returns:
            A list of :class:`~netskope.models.notifications.NotificationTemplate`.
        """
        body = self._get(_TEMPLATES_PATH, **_build_list_params(limit, offset))
        return [NotificationTemplate.model_validate(item) for item in extract_list(body)]

    def get_template(self, template_id: str | int) -> NotificationTemplate:
        """Get a single notification template by ID.

        Args:
            template_id: The template identifier.
        """
        body = self._get(_template_path(template_id))
        return NotificationTemplate.model_validate(extract_item(body))

    def create_template(
        self,
        name: str,
        *,
        title: str,
        message: str,
        action_type: TemplateActionType | str | None = None,
        subtitle: str | None = None,
        ack_button_text: str | None = None,
        proceed_button_text: str | None = None,
        stop_button_text: str | None = None,
        footer_message: str | None = None,
        logo_image_name: str | None = None,
        logo_size: LogoSize | str | None = None,
        redirect_url: str | None = None,
        stripe_color: str | None = None,
    ) -> NotificationTemplate:
        """Create a user notification template.

        ``name``, ``title``, and ``message`` are required by the API.  With
        the default ``block`` action type the API requires
        ``ack_button_text``; the ``useralert`` action type requires
        ``stop_button_text`` and ``proceed_button_text`` instead.

        Args:
            name: Display name (max 256 characters).
            title: Notification title (max 60 characters).
            message: Notification body text (accepts ``NS_*`` variables).
            action_type: ``"block"`` (default server-side) or ``"useralert"``.
            subtitle: Subtitle text (max 80 characters).
            ack_button_text: Acknowledge-button label (block templates).
            proceed_button_text: Proceed-button label (useralert templates).
            stop_button_text: Stop-button label (useralert templates).
            footer_message: Footer text (max 160 characters).
            logo_image_name: Name of a custom logo image.
            logo_size: ``"small"``, ``"medium"``, or ``"large"``.
            redirect_url: URL to redirect end users to.
            stripe_color: Hexadecimal color code (e.g. ``"#A659B1"``).

        Raises:
            netskope.exceptions.ValidationError: If *action_type* or
                *logo_size* is not a supported value.
        """
        payload = _build_template_payload(
            name=name,
            title=title,
            message=message,
            action_type=action_type,
            subtitle=subtitle,
            ack_button_text=ack_button_text,
            proceed_button_text=proceed_button_text,
            stop_button_text=stop_button_text,
            footer_message=footer_message,
            logo_image_name=logo_image_name,
            logo_size=logo_size,
            redirect_url=redirect_url,
            stripe_color=stripe_color,
        )
        body = self._post(_TEMPLATES_PATH, json=payload)
        return NotificationTemplate.model_validate(extract_item(body))

    def update_template(
        self,
        template_id: str | int,
        *,
        name: str | None = None,
        title: str | None = None,
        message: str | None = None,
        action_type: TemplateActionType | str | None = None,
        subtitle: str | None = None,
        ack_button_text: str | None = None,
        proceed_button_text: str | None = None,
        stop_button_text: str | None = None,
        footer_message: str | None = None,
        logo_image_name: str | None = None,
        logo_size: LogoSize | str | None = None,
        redirect_url: str | None = None,
        stripe_color: str | None = None,
    ) -> NotificationTemplate:
        """Update a notification template (PATCH).

        Only the provided fields are sent.  Note the API's update schema
        marks ``name``, ``title``, and ``message`` as required, so partial
        updates may be rejected server-side — pass all three to be safe.

        Args:
            template_id: The template identifier.
            name: New display name.
            title: New title.
            message: New body text.
            action_type: ``"block"`` or ``"useralert"``.
            subtitle: New subtitle.
            ack_button_text: Acknowledge-button label (block templates).
            proceed_button_text: Proceed-button label (useralert templates).
            stop_button_text: Stop-button label (useralert templates).
            footer_message: New footer text.
            logo_image_name: Name of a custom logo image.
            logo_size: ``"small"``, ``"medium"``, or ``"large"``.
            redirect_url: New redirect URL.
            stripe_color: New hexadecimal color code.

        Raises:
            netskope.exceptions.ValidationError: If no fields are provided,
                or *action_type* / *logo_size* is not a supported value.
        """
        payload = _build_template_payload(
            name=name,
            title=title,
            message=message,
            action_type=action_type,
            subtitle=subtitle,
            ack_button_text=ack_button_text,
            proceed_button_text=proceed_button_text,
            stop_button_text=stop_button_text,
            footer_message=footer_message,
            logo_image_name=logo_image_name,
            logo_size=logo_size,
            redirect_url=redirect_url,
            stripe_color=stripe_color,
        )
        if not payload:
            raise ValidationError("At least one field must be provided to update a template.")
        body = self._patch(_template_path(template_id), json=payload)
        return NotificationTemplate.model_validate(extract_item(body))

    def delete_template(self, template_id: str | int) -> None:
        """Delete a notification template.  Irreversible.

        Args:
            template_id: The template identifier.
        """
        self._delete(_template_path(template_id))

    def get_delivery_settings(self) -> dict[str, Any]:
        """Get tenant-wide user notification delivery settings (read-only).

        Returns:
            A dict with ``cloudAppsDeliveryMethod``, ``webTrafficDeliveryMethod``
            (each ``"client"`` or ``"browser"``), and ``notificationTimeout``
            (seconds, 60-600).
        """
        return self._get(_DELIVERY_SETTINGS_PATH)


class AsyncNotificationsResource(AsyncResource):
    """Asynchronous interface to the user notifications API."""

    async def list_templates(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> builtins.list[NotificationTemplate]:
        """List user notification templates.

        See :meth:`NotificationsResource.list_templates`.
        """
        body = await self._get(_TEMPLATES_PATH, **_build_list_params(limit, offset))
        return [NotificationTemplate.model_validate(item) for item in extract_list(body)]

    async def get_template(self, template_id: str | int) -> NotificationTemplate:
        """Get a single notification template by ID."""
        body = await self._get(_template_path(template_id))
        return NotificationTemplate.model_validate(extract_item(body))

    async def create_template(
        self,
        name: str,
        *,
        title: str,
        message: str,
        action_type: TemplateActionType | str | None = None,
        subtitle: str | None = None,
        ack_button_text: str | None = None,
        proceed_button_text: str | None = None,
        stop_button_text: str | None = None,
        footer_message: str | None = None,
        logo_image_name: str | None = None,
        logo_size: LogoSize | str | None = None,
        redirect_url: str | None = None,
        stripe_color: str | None = None,
    ) -> NotificationTemplate:
        """Create a user notification template.

        See :meth:`NotificationsResource.create_template`.
        """
        payload = _build_template_payload(
            name=name,
            title=title,
            message=message,
            action_type=action_type,
            subtitle=subtitle,
            ack_button_text=ack_button_text,
            proceed_button_text=proceed_button_text,
            stop_button_text=stop_button_text,
            footer_message=footer_message,
            logo_image_name=logo_image_name,
            logo_size=logo_size,
            redirect_url=redirect_url,
            stripe_color=stripe_color,
        )
        body = await self._post(_TEMPLATES_PATH, json=payload)
        return NotificationTemplate.model_validate(extract_item(body))

    async def update_template(
        self,
        template_id: str | int,
        *,
        name: str | None = None,
        title: str | None = None,
        message: str | None = None,
        action_type: TemplateActionType | str | None = None,
        subtitle: str | None = None,
        ack_button_text: str | None = None,
        proceed_button_text: str | None = None,
        stop_button_text: str | None = None,
        footer_message: str | None = None,
        logo_image_name: str | None = None,
        logo_size: LogoSize | str | None = None,
        redirect_url: str | None = None,
        stripe_color: str | None = None,
    ) -> NotificationTemplate:
        """Update a notification template (PATCH).

        See :meth:`NotificationsResource.update_template`.
        """
        payload = _build_template_payload(
            name=name,
            title=title,
            message=message,
            action_type=action_type,
            subtitle=subtitle,
            ack_button_text=ack_button_text,
            proceed_button_text=proceed_button_text,
            stop_button_text=stop_button_text,
            footer_message=footer_message,
            logo_image_name=logo_image_name,
            logo_size=logo_size,
            redirect_url=redirect_url,
            stripe_color=stripe_color,
        )
        if not payload:
            raise ValidationError("At least one field must be provided to update a template.")
        body = await self._patch(_template_path(template_id), json=payload)
        return NotificationTemplate.model_validate(extract_item(body))

    async def delete_template(self, template_id: str | int) -> None:
        """Delete a notification template.  Irreversible."""
        await self._delete(_template_path(template_id))

    async def get_delivery_settings(self) -> dict[str, Any]:
        """Get tenant-wide user notification delivery settings (read-only).

        See :meth:`NotificationsResource.get_delivery_settings`.
        """
        return await self._get(_DELIVERY_SETTINGS_PATH)
