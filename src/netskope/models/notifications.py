"""Models for the Netskope user notifications API."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from netskope.models.administration import AdminRequest
from netskope.models.common import NetskopeModel


class NotificationTemplateWrite(AdminRequest):
    """Complete template content required by both POST and PATCH."""

    name: str = Field(min_length=1, max_length=256)
    title: str = Field(max_length=60)
    message: str = Field(max_length=256000)
    action_type: Literal["block", "useralert"] = Field("block", alias="templateActionType")
    ack_button_text: str | None = Field(None, alias="ackButtonText", max_length=14)
    proceed_button_text: str | None = Field(None, alias="proceedButtonText", max_length=14)
    stop_button_text: str | None = Field(None, alias="stopButtonText", max_length=14)
    subtitle: str | None = Field(None, max_length=80)
    footer_message: str | None = Field(None, alias="footerMessage", max_length=160)
    logo_image_name: str | None = Field(None, alias="logoImageName")
    logo_size: Literal["small", "medium", "large"] | None = Field(None, alias="logoSize")
    redirect_url: str | None = Field(None, alias="redirectUrl")
    # user-notifications-templates.yaml:62-64 declares stripeColor as a bare
    # string ("A valid hexadecimal color code"), with no pattern.
    stripe_color: str | None = Field(None, alias="stripeColor")

    @model_validator(mode="after")
    def _action_buttons(self) -> Self:
        if self.action_type == "block":
            if (
                self.ack_button_text is None
                or self.proceed_button_text is not None
                or self.stop_button_text is not None
            ):
                raise ValueError(
                    "Block templates require ack_button_text and forbid proceed/stop buttons."
                )
        elif (
            self.ack_button_text is not None
            or self.proceed_button_text is None
            or self.stop_button_text is None
        ):
            raise ValueError(
                "User-alert templates require proceed/stop buttons "
                "and forbid an acknowledge button."
            )
        return self


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


class NotificationDeliverySettings(NetskopeModel):
    """The configured delivery channels and notification timeout."""

    cloud_apps_delivery_method: str = Field(alias="cloudAppsDeliveryMethod")
    web_traffic_delivery_method: str = Field(alias="webTrafficDeliveryMethod")
    notification_timeout: int = Field(alias="notificationTimeout")
