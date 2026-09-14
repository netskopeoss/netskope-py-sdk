"""The alert rules sub-namespace of dem."""

from __future__ import annotations

import functools
from typing import Any, cast

from netskope.core.ids import quote_id
from netskope.core.resource import AsyncResource, SyncResource
from netskope.resources.dem.decoder import (
    AsyncDemAlertRuleResponses,
    DemAlertRuleResponses,
)
from netskope.resources.dem.paths import (
    _ALERT_RULES_PATH,
    _alert_rule_create_body,
    _alert_rule_params,
    _slice_rules,
    validate_window,
)


class DemAlertRulesResource(SyncResource):
    """DEM experience-alert rules — ``/api/v2/dem/alert/rules``."""

    @functools.cached_property
    def with_response(self) -> DemAlertRuleResponses:
        """Inspect one completed request together with its typed result."""

        return DemAlertRuleResponses(self._transport)

    def list(
        self,
        *,
        category: str | None = None,
        type: str | None = None,
        enabled: bool | None = None,
        severity: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List configured DEM alert rules.

        ``GET /api/v2/dem/alert/rules`` declares only the four filters below
        and returns every match, so *limit* and *offset* slice the decoded
        ``rules`` collection on the client rather than travelling as query
        parameters.

        Args:
            category: ``"Network"``, ``"Platform"``, ``"Private Apps"``,
                ``"User Experience"`` or ``"Site"``.
            type: An ``AlertType`` value, e.g. ``"Experience Score"``.
            enabled: Restrict to enabled or disabled rules.
            severity: ``"info"``, ``"low"``, ``"medium"``, ``"high"`` or
                ``"critical"``.
            limit: Rules to keep, applied by the SDK after decoding.
            offset: Rules to skip, applied by the SDK after decoding.
        """
        validate_window(limit, offset)
        params = _alert_rule_params(category, type, enabled, severity)
        body = self._get(_ALERT_RULES_PATH, **params)
        return cast(dict[str, Any], _slice_rules(body, limit, offset))

    def create(
        self,
        name: str,
        metric: str,
        threshold: float,
        *,
        severity: str = "medium",
        probe_id: str | None = None,
        category: str | None = None,
        type: str | None = None,
        enabled: bool = True,
        email_receiver: str | None = None,
        criteria_type: str | None = None,
        window: int | None = None,
        filter: dict[str, Any] | None = None,
        duration: int | None = None,
        criteria: dict[str, Any] | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a DEM alert rule.

        ``POST /api/v2/dem/alert/rules`` takes the rule object itself.  The
        measurement and its threshold live inside ``criteria``:
        ``{"condition": {"measure": <metric>, "thresholds": {"threshold":
        <threshold>}}}``.

        Args:
            name: Rule name.
            metric: An ``AlertRuleMeasure`` value (e.g. ``"userDemScore"``,
                ``"popLatency_p95"``), sent as ``criteria.condition.measure``.
            threshold: Sent as ``criteria.condition.thresholds.threshold``.
            severity: ``"info"``, ``"low"``, ``"medium"``, ``"high"`` or
                ``"critical"``.
            probe_id: Retired — the schema has no probe_id.  Supplying it
                raises; scope a rule with ``criteria.condition.filter``.
            category: An ``AlertCategory`` value.
            type: An ``AlertType`` value.
            enabled: Whether the rule is active.
            email_receiver: Address to notify.
            criteria_type: ``criteriaType``; the API supports ``"event"``.
            window: Aggregation window in seconds, inside ``criteria.condition``.
            filter: ``criteria.condition.filter`` scope expression.
            duration: Seconds the threshold must stay violated.
            criteria: A complete ``criteria`` object, replacing the one built
                from *metric*/*threshold*/*window*/*filter*/*duration*.
            additional_fields: Extra top-level body fields, merged last.

        Raises:
            netskope.exceptions.ValidationError: If *probe_id* is supplied.
        """
        body = _alert_rule_create_body(
            name,
            metric,
            threshold,
            severity,
            probe_id,
            category=category,
            alert_type=type,
            enabled=enabled,
            email_receiver=email_receiver,
            criteria_type=criteria_type,
            window=window,
            filter=filter,
            duration=duration,
            criteria=criteria,
            additional_fields=additional_fields,
        )
        return self._post(_ALERT_RULES_PATH, json=body)

    def get(self, rule_id: str) -> dict[str, Any]:
        """Get a single alert rule by ID."""
        return self._get(f"{_ALERT_RULES_PATH}/{quote_id(rule_id)}")

    def update(self, rule_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an alert rule (PUT).  *data* is sent as the raw body."""
        return self._put(f"{_ALERT_RULES_PATH}/{quote_id(rule_id)}", json=data)

    def delete(self, rule_id: str) -> None:
        """Delete an alert rule.  Irreversible."""
        self._delete(f"{_ALERT_RULES_PATH}/{quote_id(rule_id)}")


class AsyncDemAlertRulesResource(AsyncResource):
    """Async DEM experience-alert rules."""

    @functools.cached_property
    def with_response(self) -> AsyncDemAlertRuleResponses:
        """Inspect one completed request together with its typed result."""

        return AsyncDemAlertRuleResponses(self._transport)

    async def list(
        self,
        *,
        category: str | None = None,
        type: str | None = None,
        enabled: bool | None = None,
        severity: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemAlertRulesResource.list`."""
        validate_window(limit, offset)
        params = _alert_rule_params(category, type, enabled, severity)
        body = await self._get(_ALERT_RULES_PATH, **params)
        return cast(dict[str, Any], _slice_rules(body, limit, offset))

    async def create(
        self,
        name: str,
        metric: str,
        threshold: float,
        *,
        severity: str = "medium",
        probe_id: str | None = None,
        category: str | None = None,
        type: str | None = None,
        enabled: bool = True,
        email_receiver: str | None = None,
        criteria_type: str | None = None,
        window: int | None = None,
        filter: dict[str, Any] | None = None,
        duration: int | None = None,
        criteria: dict[str, Any] | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemAlertRulesResource.create`."""
        body = _alert_rule_create_body(
            name,
            metric,
            threshold,
            severity,
            probe_id,
            category=category,
            alert_type=type,
            enabled=enabled,
            email_receiver=email_receiver,
            criteria_type=criteria_type,
            window=window,
            filter=filter,
            duration=duration,
            criteria=criteria,
            additional_fields=additional_fields,
        )
        return await self._post(_ALERT_RULES_PATH, json=body)

    async def get(self, rule_id: str) -> dict[str, Any]:
        """See :meth:`DemAlertRulesResource.get`."""
        return await self._get(f"{_ALERT_RULES_PATH}/{quote_id(rule_id)}")

    async def update(self, rule_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """See :meth:`DemAlertRulesResource.update`."""
        return await self._put(f"{_ALERT_RULES_PATH}/{quote_id(rule_id)}", json=data)

    async def delete(self, rule_id: str) -> None:
        """See :meth:`DemAlertRulesResource.delete`."""
        await self._delete(f"{_ALERT_RULES_PATH}/{quote_id(rule_id)}")
