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
import functools
from typing import Any

from pydantic import ValidationError as ModelValidationError

from netskope.core.ids import extract_item, extract_list, validate_id
from netskope.core.resource import AsyncResource, SyncResource
from netskope.exceptions import ValidationError
from netskope.models.notifications import (
    LogoSize,
    NotificationTemplate,
    NotificationTemplateWrite,
    TemplateActionType,
)
from netskope.resources.notifications.decoder import (
    AsyncNotificationsResponses,
    NotificationsResponses,
)
from netskope.resources.shared.admin import page_params

_TEMPLATES_PATH = "/api/v2/notifications/user/templates"
_DELIVERY_SETTINGS_PATH = "/api/v2/notifications/user/deliverysettings"

_VALID_ACTION_TYPES = tuple(t.value for t in TemplateActionType)
_VALID_LOGO_SIZES = tuple(s.value for s in LogoSize)


def _slice_templates(
    templates: builtins.list[NotificationTemplate], limit: int | None, offset: int | None
) -> builtins.list[NotificationTemplate]:
    """Apply an SDK-side slice to an unpaginated template collection.

    ``GET /user/templates`` (user-notifications-templates.yaml:206-239)
    declares no parameters and returns every template, so *limit*/*offset* are
    honoured here rather than sent as query values the operation would ignore.
    """
    if limit is None and offset is None:
        return templates
    start = offset or 0
    return templates[start : None if limit is None else start + limit]


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
    """Validate the complete template body, omitting optional unset fields.

    ``POST /user/templates`` and ``PATCH /user/templates/{id}`` share the
    ``NotificationsCreateRequest`` body (user-notifications-templates.yaml:10-91,
    :243-247, :376-381), so the same model expresses every ``maxLength``, both
    enumerations and the block-versus-useralert button rule for both.
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
    supplied = {key: value for key, value in fields if value is not None}
    try:
        validated = NotificationTemplateWrite.model_validate(supplied)
    except ModelValidationError as exc:
        detail = "; ".join(
            f"{'.'.join(map(str, error['loc'])) or 'template'}: "
            f"{error['msg'].removeprefix('Value error, ')}"
            for error in exc.errors()
        )
        missing = any(error["type"] == "missing" for error in exc.errors())
        advice = (
            " The API takes the complete template on create and on update, so a partial"
            " update is a read-modify-write: read the template, change the field, and"
            " resend the whole body."
            if missing
            else ""
        )
        raise ValidationError(f"Invalid notification template: {detail}.{advice}") from None
    return validated.model_dump(mode="json", by_alias=True, exclude_unset=True)


def _template_path(template_id: str | int) -> str:
    return f"{_TEMPLATES_PATH}/{validate_id(template_id, 'template_id')}"


class NotificationsResource(SyncResource):
    """Synchronous interface to the user notifications API."""

    @functools.cached_property
    def with_response(self) -> NotificationsResponses:
        return NotificationsResponses(self._transport)

    def list_templates(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> builtins.list[NotificationTemplate]:
        """List user notification templates.

        ``GET /api/v2/notifications/user/templates`` is unpaginated and takes
        no query parameters, so *limit* and *offset* slice the decoded list in
        the SDK.

        Args:
            limit: Templates to keep, applied after decoding.
            offset: Templates to skip, applied after decoding.

        Returns:
            A list of :class:`~netskope.models.notifications.NotificationTemplate`.
        """
        # Called for its validation alone: the window is applied to records the
        # client already holds, and `templates[-2:]` is the last two templates,
        # not "page -2", so a bad value has to be refused before it is used.
        page_params(limit, offset)
        body = self._get(_TEMPLATES_PATH)
        templates = [NotificationTemplate.model_validate(item) for item in extract_list(body)]
        return _slice_templates(templates, limit, offset)

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
                *logo_size* is not a supported value, a field exceeds its
                declared ``maxLength``, or the buttons do not match the action
                type (``block`` requires *ack_button_text* and forbids the
                other two; ``useralert`` is the mirror image).
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

        The API takes the complete template on update, not a patch of changed
        fields: ``name``, ``title`` and ``message`` are required, and
        ``action_type`` decides which button fields are required and which are
        forbidden. A partial update is therefore a read-modify-write — read the
        template with :meth:`get_template`, change the field, and pass the whole
        body back, ``action_type`` included.

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
            netskope.exceptions.ValidationError: If a required field is missing,
                *action_type* / *logo_size* is not a supported value, a field
                exceeds its declared ``maxLength``, or a button conflicts with
                the selected *action_type*.
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

    @functools.cached_property
    def with_response(self) -> AsyncNotificationsResponses:
        return AsyncNotificationsResponses(self._transport)

    async def list_templates(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> builtins.list[NotificationTemplate]:
        """List user notification templates.

        See :meth:`NotificationsResource.list_templates`.
        """
        page_params(limit, offset)
        body = await self._get(_TEMPLATES_PATH)
        templates = [NotificationTemplate.model_validate(item) for item in extract_list(body)]
        return _slice_templates(templates, limit, offset)

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
