"""Models for the Netskope user notifications API."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from netskope.models.common import NetskopeModel


class TemplateActionType(StrEnum):
    """Action type of a user notification template.

    ``block`` templates require ``ack_button_text``; ``useralert`` templates
    require ``stop_button_text`` and ``proceed_button_text``.  The API default
    is ``block``.
    """

    BLOCK = "block"
    USERALERT = "useralert"


class LogoSize(StrEnum):
    """Logo size options for a user notification template."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class NotificationTemplate(NetskopeModel):
    """A user notification template.

    Templates define the block/user-alert page shown to end users when a
    policy action triggers.  ``message``, ``subtitle``, and ``redirect_url``
    accept Netskope substitution variables such as ``NS_APP``, ``NS_URL``,
    and ``NS_USER``.

    Note:
        The API returns ``id`` as a string.  Field aliases map the API's
        camelCase names to snake_case (e.g. ``templateActionType`` →
        ``template_action_type``).

    Example::

        for template in notifications.list_templates():
            print(f"{template.id}: {template.name} ({template.template_action_type})")
    """

    id: str | int | None = None
    name: str | None = None
    title: str | None = None
    message: str | None = None
    subtitle: str | None = None
    template_action_type: str | None = Field(default=None, alias="templateActionType")
    ack_button_text: str | None = Field(default=None, alias="ackButtonText")
    proceed_button_text: str | None = Field(default=None, alias="proceedButtonText")
    stop_button_text: str | None = Field(default=None, alias="stopButtonText")
    footer_message: str | None = Field(default=None, alias="footerMessage")
    logo_image_name: str | None = Field(default=None, alias="logoImageName")
    logo_size: str | None = Field(default=None, alias="logoSize")
    redirect_url: str | None = Field(default=None, alias="redirectUrl")
    stripe_color: str | None = Field(default=None, alias="stripeColor")
