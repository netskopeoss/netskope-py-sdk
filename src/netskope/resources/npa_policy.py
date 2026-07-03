"""NPA policy resource — manage Private Access policy rules and groups.

Example::

    for rule in client.npa.policy.rules.list():
        print(f"{rule.rule_id} — {rule.rule_name} enabled={rule.enabled}")

    group = client.npa.policy.groups.create("Engineering Rules")
    rule = client.npa.policy.rules.create(
        rule_name="Allow SSH",
        group_id=group.group_id,
        enabled=False,
        rule_data={
            "policy_type": "private-app",
            "match_criteria_action": {"action_name": "allow"},
            "privateApps": ["ssh-server"],
        },
    )
"""

from __future__ import annotations

import builtins
import functools
from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.exceptions import ValidationError
from netskope.models.npa_policy import NpaPolicyGroup, NpaPolicyRule
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list, validate_id

_RULES_PATH = "/api/v2/policy/npa/rules"
_GROUPS_PATH = "/api/v2/policy/npa/policygroups"


def _extract_rules(body: dict[str, Any]) -> list[dict[str, Any]]:
    return extract_list(body, "rules")


def _extract_groups(body: dict[str, Any]) -> list[dict[str, Any]]:
    return extract_list(body, "policygroups")


def _rule_path(rule_id: int) -> str:
    return f"{_RULES_PATH}/{validate_id(rule_id, 'rule_id')}"


def _group_path(group_id: int) -> str:
    return f"{_GROUPS_PATH}/{validate_id(group_id, 'group_id')}"


def _build_rules_list_params(
    filter_expr: str | None,
    fields: builtins.list[str] | None,
    sort_by: str | None,
    sort_order: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if filter_expr:
        params["filter"] = filter_expr
    if fields:
        params["fields"] = ",".join(fields)
    if sort_by:
        params["sortby"] = sort_by
    if sort_order:
        params["sortorder"] = sort_order
    return params


_RULE_DATA_EXAMPLE = (
    'rule_data={"policy_type": "private-app", '
    '"match_criteria_action": {"action_name": "allow"}, "privateApps": ["app1"]}'
)


def _build_rule_create_payload(
    rule_name: str | None,
    group_id: int | str | None,
    enabled: bool,
    rule_data: dict[str, Any] | None,
    extra_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    if rule_name is None and rule_data is None and not extra_fields:
        raise ValidationError(
            "Provide rule_name (with optional group_id) or a full body via rule_data/extra_fields."
        )
    effective_rule_data = rule_data
    if not effective_rule_data and extra_fields:
        maybe = extra_fields.get("rule_data")
        if isinstance(maybe, dict):
            effective_rule_data = maybe
    if not effective_rule_data:
        raise ValidationError(
            "rule_data is required by the NPA policy API and must contain privateApps, "
            f"privateAppTags, or privateAppTagIds. Minimal example: {_RULE_DATA_EXAMPLE}"
        )
    payload: dict[str, Any] = {}
    if rule_name is not None:
        payload["rule_name"] = rule_name
    if group_id is not None:
        payload["group_id"] = group_id
    payload["enabled"] = "1" if enabled else "0"
    if rule_data is not None:
        payload["rule_data"] = rule_data
    if extra_fields:
        payload.update(extra_fields)
    return payload


def _build_rule_update_payload(
    rule_name: str | None,
    enabled: bool | None,
    extra_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if rule_name is not None:
        payload["rule_name"] = rule_name
    if enabled is not None:
        payload["enabled"] = "1" if enabled else "0"
    if extra_fields:
        payload.update(extra_fields)
    if not payload:
        raise ValidationError("No update fields provided. Set rule_name, enabled, or extra_fields.")
    return payload


def _build_group_update_payload(group_name: str | None) -> dict[str, Any]:
    if group_name is None:
        raise ValidationError("No update fields provided. Set group_name.")
    return {"group_name": group_name}


_GROUP_ORDER_VALUES = ("before", "after")

# Values the API has been observed to use for ``can_be_edited_deleted``
# (the spec says integer, live responses return the string "True").
_EDITABLE_TRUTHY = ("True", "true", "1", 1, True)


def _validate_group_order(order: str) -> None:
    if order not in _GROUP_ORDER_VALUES:
        raise ValidationError(f"order must be one of {_GROUP_ORDER_VALUES!r}, got {order!r}")


def _pick_anchor_group_id(groups: list[dict[str, Any]]) -> str | None:
    """Choose an anchor group for ``group_order`` from an existing group list.

    Prefers the last group that is user-editable (``can_be_edited_deleted``
    truthy); falls back to the last group; returns ``None`` when the tenant
    has no groups at all (in which case ``group_order`` is omitted).
    """
    anchor: dict[str, Any] | None = None
    for group in groups:
        if group.get("can_be_edited_deleted") in _EDITABLE_TRUTHY:
            anchor = group
    if anchor is None and groups:
        anchor = groups[-1]
    if anchor is None:
        return None
    group_id = anchor.get("group_id")
    return None if group_id is None else str(group_id)


def _build_group_create_payload(
    group_name: str,
    order: str,
    anchor_group_id: int | str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"group_name": group_name}
    if anchor_group_id is not None:
        payload["group_order"] = {"group_id": str(anchor_group_id), "order": order}
    return payload


class NpaPolicyRulesResource(SyncResource):
    """Synchronous interface to ``/api/v2/policy/npa/rules``."""

    def list(
        self,
        *,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[NpaPolicyRule]:
        """List NPA policy rules.

        Args:
            filter_expr: Filter expression to narrow results.
            fields: Specific fields to return (comma-joined into ``fields``).
            sort_by: Field name to sort results by.
            sort_order: ``"asc"`` or ``"desc"``.
            page_size: Results per page.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_RULES_PATH,
            params=_build_rules_list_params(filter_expr, fields, sort_by, sort_order),
            model=NpaPolicyRule,
            page_size=page_size,
            extract=_extract_rules,
        )

    def get(self, rule_id: int, *, fields: builtins.list[str] | None = None) -> NpaPolicyRule:
        """Get an NPA policy rule by numeric ID.

        Args:
            rule_id: The rule identifier.
            fields: Specific fields to return.
        """
        params: dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)
        body = self._get(_rule_path(rule_id), **params)
        return NpaPolicyRule.model_validate(extract_item(body))

    def create(
        self,
        *,
        rule_name: str | None = None,
        group_id: int | str | None = None,
        enabled: bool = True,
        rule_data: dict[str, Any] | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> NpaPolicyRule:
        """Create an NPA policy rule.

        The API expects ``enabled`` as the string ``"1"`` or ``"0"``; the
        boolean is converted automatically.

        ``rule_data`` is REQUIRED by the API and must contain one of
        ``privateApps``, ``privateAppTags``, or ``privateAppTagIds``.
        Minimal working example::

            client.npa.policy.rules.create(
                rule_name="Allow SSH",
                group_id="7",
                enabled=False,
                rule_data={
                    "policy_type": "private-app",
                    "match_criteria_action": {"action_name": "allow"},
                    "privateApps": ["ssh-server"],
                },
            )

        Other ``rule_data`` fields include ``users``, ``userType``,
        ``access_method`` (``Client``/``Clientless``/``Enterprise Browser``),
        ``net_location_obj``, ``classification``, and ``json_version``.

        Args:
            rule_name: Display name for the new rule.
            group_id: Policy group ID to assign this rule to.
            enabled: Whether the rule is enabled (default ``True``).
            rule_data: Full ``rule_data`` block (match criteria, actions...).
                Required by the API — see above.
            extra_fields: Additional top-level body fields, merged last.

        Raises:
            netskope.exceptions.ValidationError: If *rule_data* is missing or
                empty (and *extra_fields* does not supply one), or no body
                fields are provided at all.
        """
        payload = _build_rule_create_payload(rule_name, group_id, enabled, rule_data, extra_fields)
        body = self._post(_RULES_PATH, json=payload)
        return NpaPolicyRule.model_validate(extract_item(body))

    def update(
        self,
        rule_id: int,
        *,
        rule_name: str | None = None,
        enabled: bool | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> NpaPolicyRule:
        """Partial-update an NPA policy rule (PATCH). Only set fields are sent.

        Args:
            rule_id: The rule identifier.
            rule_name: New display name.
            enabled: Enable/disable the rule (converted to ``"1"``/``"0"``).
            extra_fields: Additional top-level body fields, merged last.

        Raises:
            netskope.exceptions.ValidationError: If no fields are provided.
        """
        payload = _build_rule_update_payload(rule_name, enabled, extra_fields)
        body = self._patch(_rule_path(rule_id), json=payload)
        return NpaPolicyRule.model_validate(extract_item(body))

    def delete(self, rule_id: int) -> None:
        """Delete an NPA policy rule.  Irreversible."""
        self._delete(_rule_path(rule_id))


class NpaPolicyGroupsResource(SyncResource):
    """Synchronous interface to ``/api/v2/policy/npa/policygroups``."""

    def list(
        self,
        *,
        fields: builtins.list[str] | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[NpaPolicyGroup]:
        """List NPA policy groups.

        Args:
            fields: Specific fields to return.
            page_size: Results per page.
        """
        params: dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_GROUPS_PATH,
            params=params,
            model=NpaPolicyGroup,
            page_size=page_size,
            extract=_extract_groups,
        )

    def get(self, group_id: int) -> NpaPolicyGroup:
        """Get an NPA policy group by numeric ID."""
        body = self._get(_group_path(group_id))
        return NpaPolicyGroup.model_validate(extract_item(body))

    def create(
        self,
        group_name: str,
        *,
        order: str = "after",
        anchor_group_id: int | str | None = None,
    ) -> NpaPolicyGroup:
        """Create an NPA policy group.

        The API requires a ``group_order`` object anchoring the new group's
        position relative to an existing group (the server error message
        calls it "grouporder", but the body key is ``group_order``).  When
        *anchor_group_id* is not given, the group list is fetched and the
        last user-editable group is used as the anchor automatically.

        Args:
            group_name: Display name for the new group.  Must be unique.
            order: Position relative to the anchor group — ``"before"`` or
                ``"after"`` (default ``"after"``).
            anchor_group_id: Existing group ID to anchor against.  Sent as a
                string, as the API expects.  When ``None``, an anchor is
                auto-selected from the current group list.

        Raises:
            netskope.exceptions.ValidationError: If *order* is not
                ``"before"``/``"after"``.
        """
        _validate_group_order(order)
        if anchor_group_id is None:
            list_body = self._get(_GROUPS_PATH)
            anchor_group_id = _pick_anchor_group_id(_extract_groups(list_body))
        payload = _build_group_create_payload(group_name, order, anchor_group_id)
        body = self._post(_GROUPS_PATH, json=payload)
        return NpaPolicyGroup.model_validate(extract_item(body))

    def update(self, group_id: int, *, group_name: str) -> NpaPolicyGroup:
        """Rename an NPA policy group (PATCH).

        Only ``group_name`` is sent; the API does not require ``group_order``
        on PATCH.

        Args:
            group_id: The group identifier.
            group_name: New display name.
        """
        payload = _build_group_update_payload(group_name)
        body = self._patch(_group_path(group_id), json=payload)
        return NpaPolicyGroup.model_validate(extract_item(body))

    def delete(self, group_id: int) -> None:
        """Delete an NPA policy group.  Irreversible."""
        self._delete(_group_path(group_id))


class NpaPolicyResource(SyncResource):
    """NPA policy namespace: ``client.npa.policy.rules`` / ``client.npa.policy.groups``."""

    @functools.cached_property
    def rules(self) -> NpaPolicyRulesResource:
        """Access the NPA policy rules API."""
        return NpaPolicyRulesResource(self._transport)

    @functools.cached_property
    def groups(self) -> NpaPolicyGroupsResource:
        """Access the NPA policy groups API."""
        return NpaPolicyGroupsResource(self._transport)


# --- Async counterparts ---


class AsyncNpaPolicyRulesResource(AsyncResource):
    """Async NPA policy rules."""

    def list(
        self,
        *,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[NpaPolicyRule]:
        """List NPA policy rules.  See :meth:`NpaPolicyRulesResource.list`."""
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_RULES_PATH,
            params=_build_rules_list_params(filter_expr, fields, sort_by, sort_order),
            model=NpaPolicyRule,
            page_size=page_size,
            extract=_extract_rules,
        )

    async def get(self, rule_id: int, *, fields: builtins.list[str] | None = None) -> NpaPolicyRule:
        """Get an NPA policy rule by numeric ID."""
        params: dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)
        body = await self._get(_rule_path(rule_id), **params)
        return NpaPolicyRule.model_validate(extract_item(body))

    async def create(
        self,
        *,
        rule_name: str | None = None,
        group_id: int | str | None = None,
        enabled: bool = True,
        rule_data: dict[str, Any] | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> NpaPolicyRule:
        """Create an NPA policy rule.  See :meth:`NpaPolicyRulesResource.create`."""
        payload = _build_rule_create_payload(rule_name, group_id, enabled, rule_data, extra_fields)
        body = await self._post(_RULES_PATH, json=payload)
        return NpaPolicyRule.model_validate(extract_item(body))

    async def update(
        self,
        rule_id: int,
        *,
        rule_name: str | None = None,
        enabled: bool | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> NpaPolicyRule:
        """Partial-update an NPA policy rule.  See :meth:`NpaPolicyRulesResource.update`."""
        payload = _build_rule_update_payload(rule_name, enabled, extra_fields)
        body = await self._patch(_rule_path(rule_id), json=payload)
        return NpaPolicyRule.model_validate(extract_item(body))

    async def delete(self, rule_id: int) -> None:
        """Delete an NPA policy rule.  Irreversible."""
        await self._delete(_rule_path(rule_id))


class AsyncNpaPolicyGroupsResource(AsyncResource):
    """Async NPA policy groups."""

    def list(
        self,
        *,
        fields: builtins.list[str] | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[NpaPolicyGroup]:
        """List NPA policy groups."""
        params: dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_GROUPS_PATH,
            params=params,
            model=NpaPolicyGroup,
            page_size=page_size,
            extract=_extract_groups,
        )

    async def get(self, group_id: int) -> NpaPolicyGroup:
        """Get an NPA policy group by numeric ID."""
        body = await self._get(_group_path(group_id))
        return NpaPolicyGroup.model_validate(extract_item(body))

    async def create(
        self,
        group_name: str,
        *,
        order: str = "after",
        anchor_group_id: int | str | None = None,
    ) -> NpaPolicyGroup:
        """Create an NPA policy group.  See :meth:`NpaPolicyGroupsResource.create`."""
        _validate_group_order(order)
        if anchor_group_id is None:
            list_body = await self._get(_GROUPS_PATH)
            anchor_group_id = _pick_anchor_group_id(_extract_groups(list_body))
        payload = _build_group_create_payload(group_name, order, anchor_group_id)
        body = await self._post(_GROUPS_PATH, json=payload)
        return NpaPolicyGroup.model_validate(extract_item(body))

    async def update(self, group_id: int, *, group_name: str) -> NpaPolicyGroup:
        """Rename an NPA policy group (PATCH)."""
        payload = _build_group_update_payload(group_name)
        body = await self._patch(_group_path(group_id), json=payload)
        return NpaPolicyGroup.model_validate(extract_item(body))

    async def delete(self, group_id: int) -> None:
        """Delete an NPA policy group.  Irreversible."""
        await self._delete(_group_path(group_id))


class AsyncNpaPolicyResource(AsyncResource):
    """Async NPA policy namespace."""

    @functools.cached_property
    def rules(self) -> AsyncNpaPolicyRulesResource:
        """Access the NPA policy rules API."""
        return AsyncNpaPolicyRulesResource(self._transport)

    @functools.cached_property
    def groups(self) -> AsyncNpaPolicyGroupsResource:
        """Access the NPA policy groups API."""
        return AsyncNpaPolicyGroupsResource(self._transport)
