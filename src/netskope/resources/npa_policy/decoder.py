"""Typed bounded NPA policy reads and single-request mutations."""

from __future__ import annotations

from typing import Any

from netskope.core.pagination import Page
from netskope.core.resource import AsyncResource, SyncResource
from netskope.models._npa_requests import request_payload
from netskope.models.npa_policy import (
    NpaPolicyGroup,
    NpaPolicyGroupCreate,
    NpaPolicyGroupPatch,
    NpaPolicyRule,
    NpaPolicyRuleCreate,
    NpaPolicyRulePatch,
)
from netskope.resources.npa_policy.paths import (
    _GROUPS_PATH,
    _RULES_PATH,
    _build_rules_list_params,
    _group_path,
    _rule_path,
)
from netskope.resources.shared.npa import page_params, parse_item, parse_page
from netskope.response import ApiResponse


def _rule_params(
    filter_expr: str | None,
    fields: list[str] | None,
    sort_by: str | None,
    sort_order: str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any]:
    return {
        **_build_rules_list_params(filter_expr, fields, sort_by, sort_order),
        **page_params(limit, offset),
    }


class NpaPolicyRuleResponses(SyncResource):
    """Completed NPA policy rule responses."""

    def list_page(
        self,
        *,
        filter_expr: str | None = None,
        fields: list[str] | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[NpaPolicyRule]]:
        params = _rule_params(filter_expr, fields, sort_by, sort_order, limit, offset)
        response = self._transport.request("GET", _RULES_PATH, params=params or None)
        return ApiResponse(
            response, lambda raw: parse_page(raw.json(), NpaPolicyRule, limit, offset, "rules")
        )

    def get(self, rule_id: int, *, fields: list[str] | None = None) -> ApiResponse[NpaPolicyRule]:
        params = {"fields": ",".join(fields)} if fields else None
        response = self._transport.request("GET", _rule_path(rule_id), params=params)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), NpaPolicyRule))

    def create_request(self, request: NpaPolicyRuleCreate) -> ApiResponse[NpaPolicyRule]:
        payload = request_payload(request, NpaPolicyRuleCreate)
        response = self._transport.request("POST", _RULES_PATH, json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), NpaPolicyRule))

    def update_request(
        self, rule_id: int, request: NpaPolicyRulePatch
    ) -> ApiResponse[NpaPolicyRule]:
        payload = request_payload(request, NpaPolicyRulePatch)
        response = self._transport.request("PATCH", _rule_path(rule_id), json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), NpaPolicyRule))


class NpaPolicyGroupResponses(SyncResource):
    """Completed NPA policy group responses, with no implicit anchor lookup."""

    def list_page(
        self,
        *,
        filter_expr: str | None = None,
        fields: list[str] | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[NpaPolicyGroup]]:
        params = _rule_params(filter_expr, fields, sort_by, sort_order, limit, offset)
        response = self._transport.request("GET", _GROUPS_PATH, params=params or None)
        return ApiResponse(
            response,
            lambda raw: parse_page(raw.json(), NpaPolicyGroup, limit, offset, "policygroups"),
        )

    def get(self, group_id: int) -> ApiResponse[NpaPolicyGroup]:
        response = self._transport.request("GET", _group_path(group_id))
        return ApiResponse(response, lambda raw: parse_item(raw.json(), NpaPolicyGroup))

    def create_request(self, request: NpaPolicyGroupCreate) -> ApiResponse[NpaPolicyGroup]:
        payload = request_payload(request, NpaPolicyGroupCreate)
        response = self._transport.request("POST", _GROUPS_PATH, json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), NpaPolicyGroup))

    def update_request(
        self, group_id: int, request: NpaPolicyGroupPatch
    ) -> ApiResponse[NpaPolicyGroup]:
        payload = request_payload(request, NpaPolicyGroupPatch)
        response = self._transport.request("PATCH", _group_path(group_id), json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), NpaPolicyGroup))


class AsyncNpaPolicyRuleResponses(AsyncResource):
    """Completed NPA policy rule responses."""

    async def list_page(
        self,
        *,
        filter_expr: str | None = None,
        fields: list[str] | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[NpaPolicyRule]]:
        params = _rule_params(filter_expr, fields, sort_by, sort_order, limit, offset)
        response = await self._transport.request("GET", _RULES_PATH, params=params or None)
        return ApiResponse(
            response, lambda raw: parse_page(raw.json(), NpaPolicyRule, limit, offset, "rules")
        )

    async def get(
        self, rule_id: int, *, fields: list[str] | None = None
    ) -> ApiResponse[NpaPolicyRule]:
        params = {"fields": ",".join(fields)} if fields else None
        response = await self._transport.request("GET", _rule_path(rule_id), params=params)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), NpaPolicyRule))

    async def create_request(self, request: NpaPolicyRuleCreate) -> ApiResponse[NpaPolicyRule]:
        payload = request_payload(request, NpaPolicyRuleCreate)
        response = await self._transport.request("POST", _RULES_PATH, json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), NpaPolicyRule))

    async def update_request(
        self, rule_id: int, request: NpaPolicyRulePatch
    ) -> ApiResponse[NpaPolicyRule]:
        payload = request_payload(request, NpaPolicyRulePatch)
        response = await self._transport.request("PATCH", _rule_path(rule_id), json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), NpaPolicyRule))


class AsyncNpaPolicyGroupResponses(AsyncResource):
    """Completed NPA policy group responses, with no implicit anchor lookup."""

    async def list_page(
        self,
        *,
        filter_expr: str | None = None,
        fields: list[str] | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[NpaPolicyGroup]]:
        params = _rule_params(filter_expr, fields, sort_by, sort_order, limit, offset)
        response = await self._transport.request("GET", _GROUPS_PATH, params=params or None)
        return ApiResponse(
            response,
            lambda raw: parse_page(raw.json(), NpaPolicyGroup, limit, offset, "policygroups"),
        )

    async def get(self, group_id: int) -> ApiResponse[NpaPolicyGroup]:
        response = await self._transport.request("GET", _group_path(group_id))
        return ApiResponse(response, lambda raw: parse_item(raw.json(), NpaPolicyGroup))

    async def create_request(self, request: NpaPolicyGroupCreate) -> ApiResponse[NpaPolicyGroup]:
        payload = request_payload(request, NpaPolicyGroupCreate)
        response = await self._transport.request("POST", _GROUPS_PATH, json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), NpaPolicyGroup))

    async def update_request(
        self, group_id: int, request: NpaPolicyGroupPatch
    ) -> ApiResponse[NpaPolicyGroup]:
        payload = request_payload(request, NpaPolicyGroupPatch)
        response = await self._transport.request("PATCH", _group_path(group_id), json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), NpaPolicyGroup))
