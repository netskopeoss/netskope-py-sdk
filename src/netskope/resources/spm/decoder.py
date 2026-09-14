"""Typed, one-request response access for SPM's existing resource methods."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import TypeAdapter

from netskope.core.decoding import decode_body
from netskope.core.resource import AsyncResource, SyncResource
from netskope.models.spm import (
    SpmApplication,
    SpmInventoryRecord,
    SpmPolicyRule,
    SpmPostureScore,
    SpmRecentChanges,
)
from netskope.resources.spm.paths import (
    _INVENTORY_PATH,
    _POLICY_RULES_PATH,
    _POSTURE_SCORE_PATH,
    _RECENT_CHANGES_PATH,
    _app_body,
    _apps_body,
    _inventory_body,
    _policy_rule_params,
    _posture_score_body,
    _recent_changes_body,
)
from netskope.response import ApiResponse

_APPS = TypeAdapter(list[SpmApplication])
_INVENTORY = TypeAdapter(list[SpmInventoryRecord])
_SCORE = TypeAdapter(SpmPostureScore)
_RULES = TypeAdapter(list[SpmPolicyRule])
_CHANGES = TypeAdapter(SpmRecentChanges)


class SpmResponses(SyncResource):
    """Typed SPM application, inventory, posture and policy reads, with their buffered responses."""

    def list_apps(self, *, limit: int = 50, offset: int = 0) -> ApiResponse[list[SpmApplication]]:
        response = self._transport.request(
            "POST", _INVENTORY_PATH, json=_apps_body(limit, offset), retry_safe=True
        )
        return ApiResponse(response, lambda raw: decode_body(raw, _APPS, envelope="data"))

    def get_app(
        self, app_name: str, *, limit: int = 50, offset: int = 0
    ) -> ApiResponse[list[SpmApplication]]:
        response = self._transport.request(
            "POST", _INVENTORY_PATH, json=_app_body(app_name, limit, offset), retry_safe=True
        )
        return ApiResponse(response, lambda raw: decode_body(raw, _APPS, envelope="data"))

    def inventory(
        self,
        *,
        filter: str | None = None,
        fields: list[str] | None = None,
        group_by: str = "resource_name",
        limit: int = 50,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
        ngl_query: str | None = None,
        sort: list[dict[str, Any]] | None = None,
        timestamp: int | None = None,
        past_view: bool | None = None,
    ) -> ApiResponse[list[SpmInventoryRecord]]:
        body = _inventory_body(
            fields=fields,
            group_by=group_by,
            limit=limit,
            offset=offset,
            filters=filters,
            ngl_query=ngl_query if filter is None else filter,
            sort=sort,
            timestamp=timestamp,
            past_view=past_view,
        )
        response = self._transport.request("POST", _INVENTORY_PATH, json=body, retry_safe=True)
        return ApiResponse(response, lambda raw: decode_body(raw, _INVENTORY, envelope="data"))

    def posture_score(
        self,
        *,
        app_names: list[str] | None = None,
        appsuite_names: list[str] | None = None,
        instance_names: list[str] | None = None,
        posture_confidence_level: list[str] | None = None,
        timestamp: int | None = None,
    ) -> ApiResponse[SpmPostureScore]:
        body = _posture_score_body(
            app_names, appsuite_names, instance_names, posture_confidence_level, timestamp
        )
        response = self._transport.request("POST", _POSTURE_SCORE_PATH, json=body, retry_safe=True)
        return ApiResponse(response, lambda raw: decode_body(raw, _SCORE))

    def list_policy_rules(
        self,
        *,
        appsuite: str | None = None,
        filter: str | None = None,
        limit: int | None = None,
        view: str | None = None,
        sort_order: str | None = None,
        include_templates: bool | None = None,
        offset: int | None = None,
    ) -> ApiResponse[list[SpmPolicyRule]]:
        params = _policy_rule_params(
            appsuite, filter, limit, view, sort_order, include_templates, offset
        )
        response = self._transport.request("GET", _POLICY_RULES_PATH, params=params or None)
        return ApiResponse(response, lambda raw: decode_body(raw, _RULES, envelope="rules"))

    def recent_changes(
        self,
        *,
        start: datetime | int | None = None,
        end: datetime | int | None = None,
        app_name: str | None = None,
        instance_name: str | None = None,
    ) -> ApiResponse[SpmRecentChanges]:
        body = _recent_changes_body(start, end, app_name, instance_name)
        response = self._transport.request("POST", _RECENT_CHANGES_PATH, json=body, retry_safe=True)
        return ApiResponse(response, lambda raw: decode_body(raw, _CHANGES))


class AsyncSpmResponses(AsyncResource):
    """Typed SPM application, inventory, posture and policy reads, with their buffered responses."""

    async def list_apps(
        self, *, limit: int = 50, offset: int = 0
    ) -> ApiResponse[list[SpmApplication]]:
        response = await self._transport.request(
            "POST", _INVENTORY_PATH, json=_apps_body(limit, offset), retry_safe=True
        )
        return ApiResponse(response, lambda raw: decode_body(raw, _APPS, envelope="data"))

    async def get_app(
        self, app_name: str, *, limit: int = 50, offset: int = 0
    ) -> ApiResponse[list[SpmApplication]]:
        response = await self._transport.request(
            "POST", _INVENTORY_PATH, json=_app_body(app_name, limit, offset), retry_safe=True
        )
        return ApiResponse(response, lambda raw: decode_body(raw, _APPS, envelope="data"))

    async def inventory(
        self,
        *,
        filter: str | None = None,
        fields: list[str] | None = None,
        group_by: str = "resource_name",
        limit: int = 50,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
        ngl_query: str | None = None,
        sort: list[dict[str, Any]] | None = None,
        timestamp: int | None = None,
        past_view: bool | None = None,
    ) -> ApiResponse[list[SpmInventoryRecord]]:
        body = _inventory_body(
            fields=fields,
            group_by=group_by,
            limit=limit,
            offset=offset,
            filters=filters,
            ngl_query=ngl_query if filter is None else filter,
            sort=sort,
            timestamp=timestamp,
            past_view=past_view,
        )
        response = await self._transport.request(
            "POST", _INVENTORY_PATH, json=body, retry_safe=True
        )
        return ApiResponse(response, lambda raw: decode_body(raw, _INVENTORY, envelope="data"))

    async def posture_score(
        self,
        *,
        app_names: list[str] | None = None,
        appsuite_names: list[str] | None = None,
        instance_names: list[str] | None = None,
        posture_confidence_level: list[str] | None = None,
        timestamp: int | None = None,
    ) -> ApiResponse[SpmPostureScore]:
        body = _posture_score_body(
            app_names, appsuite_names, instance_names, posture_confidence_level, timestamp
        )
        response = await self._transport.request(
            "POST", _POSTURE_SCORE_PATH, json=body, retry_safe=True
        )
        return ApiResponse(response, lambda raw: decode_body(raw, _SCORE))

    async def list_policy_rules(
        self,
        *,
        appsuite: str | None = None,
        filter: str | None = None,
        limit: int | None = None,
        view: str | None = None,
        sort_order: str | None = None,
        include_templates: bool | None = None,
        offset: int | None = None,
    ) -> ApiResponse[list[SpmPolicyRule]]:
        params = _policy_rule_params(
            appsuite, filter, limit, view, sort_order, include_templates, offset
        )
        response = await self._transport.request("GET", _POLICY_RULES_PATH, params=params or None)
        return ApiResponse(response, lambda raw: decode_body(raw, _RULES, envelope="rules"))

    async def recent_changes(
        self,
        *,
        start: datetime | int | None = None,
        end: datetime | int | None = None,
        app_name: str | None = None,
        instance_name: str | None = None,
    ) -> ApiResponse[SpmRecentChanges]:
        body = _recent_changes_body(start, end, app_name, instance_name)
        response = await self._transport.request(
            "POST", _RECENT_CHANGES_PATH, json=body, retry_safe=True
        )
        return ApiResponse(response, lambda raw: decode_body(raw, _CHANGES))
