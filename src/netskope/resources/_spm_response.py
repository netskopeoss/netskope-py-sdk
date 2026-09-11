"""Typed, one-request response access for SPM's existing resource methods."""

from __future__ import annotations

from pydantic import TypeAdapter

from netskope.models.spm import (
    SpmApplication,
    SpmInventoryRecord,
    SpmPolicyRule,
    SpmPostureScore,
    SpmRecentChanges,
)
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._typed_response import decode_body
from netskope.resources.spm import (
    _APPS_PATH,
    _INVENTORY_PATH,
    _POLICY_RULES_PATH,
    _POSTURE_SCORE_PATH,
    _RECENT_CHANGES_PATH,
    _app_path,
    _inventory_body,
)
from netskope.response import ApiResponse

_APPS = TypeAdapter(list[SpmApplication])
_APP = TypeAdapter(SpmApplication)
_INVENTORY = TypeAdapter(list[SpmInventoryRecord])
_SCORE = TypeAdapter(SpmPostureScore)
_RULES = TypeAdapter(list[SpmPolicyRule])
_CHANGES = TypeAdapter(SpmRecentChanges)


class SpmResponses(SyncResource):
    """Typed SPM application, inventory, posture and policy reads, with their buffered responses."""

    def list_apps(self) -> ApiResponse[list[SpmApplication]]:
        response = self._transport.request("GET", _APPS_PATH)
        return ApiResponse(response, lambda raw: decode_body(raw, _APPS, envelope="data"))

    def get_app(self, app_name: str) -> ApiResponse[SpmApplication]:
        response = self._transport.request("GET", _app_path(app_name))
        return ApiResponse(response, lambda raw: decode_body(raw, _APP, envelope="data"))

    def inventory(self, *, filter: str | None = None) -> ApiResponse[list[SpmInventoryRecord]]:
        response = self._transport.request(
            "POST", _INVENTORY_PATH, json=_inventory_body(filter), retry_safe=True
        )
        return ApiResponse(response, lambda raw: decode_body(raw, _INVENTORY, envelope="data"))

    def posture_score(self) -> ApiResponse[SpmPostureScore]:
        response = self._transport.request("GET", _POSTURE_SCORE_PATH)
        return ApiResponse(response, lambda raw: decode_body(raw, _SCORE, envelope="data"))

    def list_policy_rules(self) -> ApiResponse[list[SpmPolicyRule]]:
        response = self._transport.request("GET", _POLICY_RULES_PATH)
        return ApiResponse(response, lambda raw: decode_body(raw, _RULES, envelope="data"))

    def recent_changes(self) -> ApiResponse[SpmRecentChanges]:
        response = self._transport.request("GET", _RECENT_CHANGES_PATH)
        return ApiResponse(response, lambda raw: decode_body(raw, _CHANGES, envelope="data"))


class AsyncSpmResponses(AsyncResource):
    """Typed SPM application, inventory, posture and policy reads, with their buffered responses."""

    async def list_apps(self) -> ApiResponse[list[SpmApplication]]:
        response = await self._transport.request("GET", _APPS_PATH)
        return ApiResponse(response, lambda raw: decode_body(raw, _APPS, envelope="data"))

    async def get_app(self, app_name: str) -> ApiResponse[SpmApplication]:
        response = await self._transport.request("GET", _app_path(app_name))
        return ApiResponse(response, lambda raw: decode_body(raw, _APP, envelope="data"))

    async def inventory(
        self, *, filter: str | None = None
    ) -> ApiResponse[list[SpmInventoryRecord]]:
        response = await self._transport.request(
            "POST", _INVENTORY_PATH, json=_inventory_body(filter), retry_safe=True
        )
        return ApiResponse(response, lambda raw: decode_body(raw, _INVENTORY, envelope="data"))

    async def posture_score(self) -> ApiResponse[SpmPostureScore]:
        response = await self._transport.request("GET", _POSTURE_SCORE_PATH)
        return ApiResponse(response, lambda raw: decode_body(raw, _SCORE, envelope="data"))

    async def list_policy_rules(self) -> ApiResponse[list[SpmPolicyRule]]:
        response = await self._transport.request("GET", _POLICY_RULES_PATH)
        return ApiResponse(response, lambda raw: decode_body(raw, _RULES, envelope="data"))

    async def recent_changes(self) -> ApiResponse[SpmRecentChanges]:
        response = await self._transport.request("GET", _RECENT_CHANGES_PATH)
        return ApiResponse(response, lambda raw: decode_body(raw, _CHANGES, envelope="data"))
