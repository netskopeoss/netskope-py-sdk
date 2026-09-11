"""Typed notification template and delivery-setting responses."""

from __future__ import annotations

from netskope.models.notifications import (
    NotificationDeliverySettings,
    NotificationTemplate,
    NotificationTemplateWrite,
)
from netskope.resources._admin_response import item, request_payload
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import validate_id
from netskope.resources._response_list import parse_response_list
from netskope.response import ApiResponse


class NotificationsResponses(SyncResource):
    def create_template(
        self, request: NotificationTemplateWrite
    ) -> ApiResponse[NotificationTemplate]:
        response = self._transport.request(
            "POST",
            "/api/v2/notifications/user/templates",
            json=request_payload(request, NotificationTemplateWrite),
        )
        return ApiResponse(response, lambda raw: item(raw, NotificationTemplate))

    def update_template(
        self, template_id: str | int, request: NotificationTemplateWrite
    ) -> ApiResponse[NotificationTemplate]:
        path = f"/api/v2/notifications/user/templates/{validate_id(template_id, 'template_id')}"
        response = self._transport.request(
            "PATCH", path, json=request_payload(request, NotificationTemplateWrite)
        )
        return ApiResponse(response, lambda raw: item(raw, NotificationTemplate))

    def list_templates(self) -> ApiResponse[list[NotificationTemplate]]:
        response = self._transport.request("GET", "/api/v2/notifications/user/templates")
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), NotificationTemplate)
        )

    def get_template(self, template_id: str | int) -> ApiResponse[NotificationTemplate]:
        path = f"/api/v2/notifications/user/templates/{validate_id(template_id, 'template_id')}"
        response = self._transport.request("GET", path)
        return ApiResponse(response, lambda raw: item(raw, NotificationTemplate))

    def delivery_settings(self) -> ApiResponse[NotificationDeliverySettings]:
        response = self._transport.request("GET", "/api/v2/notifications/user/deliverysettings")
        return ApiResponse(response, lambda raw: item(raw, NotificationDeliverySettings))


class AsyncNotificationsResponses(AsyncResource):
    async def create_template(
        self, request: NotificationTemplateWrite
    ) -> ApiResponse[NotificationTemplate]:
        response = await self._transport.request(
            "POST",
            "/api/v2/notifications/user/templates",
            json=request_payload(request, NotificationTemplateWrite),
        )
        return ApiResponse(response, lambda raw: item(raw, NotificationTemplate))

    async def update_template(
        self, template_id: str | int, request: NotificationTemplateWrite
    ) -> ApiResponse[NotificationTemplate]:
        path = f"/api/v2/notifications/user/templates/{validate_id(template_id, 'template_id')}"
        response = await self._transport.request(
            "PATCH", path, json=request_payload(request, NotificationTemplateWrite)
        )
        return ApiResponse(response, lambda raw: item(raw, NotificationTemplate))

    async def list_templates(self) -> ApiResponse[list[NotificationTemplate]]:
        response = await self._transport.request("GET", "/api/v2/notifications/user/templates")
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), NotificationTemplate)
        )

    async def get_template(self, template_id: str | int) -> ApiResponse[NotificationTemplate]:
        path = f"/api/v2/notifications/user/templates/{validate_id(template_id, 'template_id')}"
        response = await self._transport.request("GET", path)
        return ApiResponse(response, lambda raw: item(raw, NotificationTemplate))

    async def delivery_settings(self) -> ApiResponse[NotificationDeliverySettings]:
        response = await self._transport.request(
            "GET", "/api/v2/notifications/user/deliverysettings"
        )
        return ApiResponse(response, lambda raw: item(raw, NotificationDeliverySettings))
