"""Typed same-request accessors for DEM and ADEM operations."""

from __future__ import annotations

import builtins
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter
from pydantic import ValidationError as ModelValidationError

from netskope.exceptions import ValidationError
from netskope.models.dem import (
    AdemAggregatedScores,
    AdemApplication,
    AdemDevice,
    AdemDeviceDetails,
    AdemLocation,
    AdemMetricPoint,
    AdemNetworkGraph,
    AdemQueryRequest,
    AdemRootCause,
    AdemUserInfo,
    DemAlert,
    DemAlertRule,
    DemAlertRuleCreate,
    DemApp,
    DemDefinitions,
    DemEntity,
    DemProbe,
    DemProbeCreate,
    DemQueryRequest,
    DemQueryResult,
    NpaHost,
)
from netskope.resources import dem as api
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import quote_id
from netskope.resources._response_list import extract_response_list
from netskope.response import ApiResponse

T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)
_GRAPH_QUERY: TypeAdapter[DemQueryResult | AdemNetworkGraph] = TypeAdapter(
    DemQueryResult | AdemNetworkGraph
)


def _collection(model: type[M], *keys: str) -> Callable[[Any], builtins.list[M]]:
    return lambda body: [model.model_validate(row) for row in extract_response_list(body, *keys)]


def _item(model: type[M]) -> Callable[[Any], M]:
    def parse(body: Any) -> M:
        if not isinstance(body, dict):
            raise ValueError("Expected a DEM object response.")
        if "id" not in body and "_id" not in body:
            for key in ("data", "result"):
                if key in body:
                    if not isinstance(body[key], dict):
                        raise ValueError("Expected a DEM object response.")
                    body = body[key]
                    break
        return model.model_validate(body)

    return parse


def _validated(model: type[M], body: dict[str, Any]) -> dict[str, Any]:
    try:
        request = model.model_validate(body)
    except ModelValidationError as exc:
        fields = ", ".join(".".join(map(str, error["loc"])) for error in exc.errors())
        raise ValidationError(f"Invalid DEM request fields: {fields or 'time window'}.") from None
    return request.model_dump(by_alias=True, exclude_unset=True)


def _paging(limit: int | None, offset: int | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for name, value in (("limit", limit), ("offset", offset)):
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValidationError(f"{name} must be a non-negative integer.")
            params[name] = value
    return params


def _time_bounds(begin: datetime | int, end: datetime | int, *, millis: bool) -> None:
    for value in (begin, end):
        if isinstance(value, bool) or not isinstance(value, (datetime, int)):
            raise ValidationError(
                "Time bounds must be datetimes or integers in the endpoint's native units."
            )
        if isinstance(value, datetime) and (value.tzinfo is None or value.utcoffset() is None):
            raise ValidationError("Datetime bounds must include a timezone.")
    convert = api._epoch_millis if millis else api._epoch_seconds
    if convert(end) < convert(begin):
        raise ValidationError("end_time must not precede start_time.")


def _adem_body(
    start_time: datetime | int,
    end_time: datetime | int,
    *,
    user: str | None = None,
    device_id: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    _time_bounds(start_time, end_time, millis=False)
    return api._adem_body(start_time, end_time, user=user, device_id=device_id, **extra)


def _dataset_body(
    data_source: str,
    select: builtins.list[Any],
    begin: datetime | int,
    end: datetime | int,
    where: Any | None,
    group_by: builtins.list[str] | None,
    order_by: Any | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any]:
    sources = {
        "rum_bypassed",
        "rum_steered",
        "traceroute_bypassed",
        "traceroute_pop",
        "traceroute_all",
        "http_steered",
        "http_bypassed",
        "http_all",
    }
    if data_source not in sources:
        raise ValidationError(
            "The dataset endpoint supports only RUM, HTTP, and traceroute sources."
        )
    _paging(limit, offset)
    _time_bounds(begin, end, millis=True)
    start_ms, end_ms = api._epoch_millis(begin), api._epoch_millis(end)
    if end_ms - start_ms > 48 * 3600 * 1000:
        raise ValidationError("The dataset time range must not exceed 48 hours.")
    body = api._getdata_body(
        data_source, select, begin, end, where, group_by, order_by, limit, offset
    )
    if limit is not None:
        body["limit"] = min(limit, 9999)
    return _validated(DemQueryRequest, body)


class _DemResponses(SyncResource):
    def _response(
        self,
        method: str,
        path: str,
        parser: Callable[[Any], T],
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        retry_safe: bool | None = None,
    ) -> ApiResponse[T]:
        """Send one request; only an explicit ``retry_safe=True`` lets a POST replay."""
        response = self._transport.request(
            method, path, params=params, json=json, retry_safe=retry_safe
        )
        return ApiResponse(response, lambda raw: parser(raw.json()))


class _AsyncDemResponses(AsyncResource):
    async def _response(
        self,
        method: str,
        path: str,
        parser: Callable[[Any], T],
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        retry_safe: bool | None = None,
    ) -> ApiResponse[T]:
        """Send one request; only an explicit ``retry_safe=True`` lets a POST replay."""
        response = await self._transport.request(
            method, path, params=params, json=json, retry_safe=retry_safe
        )
        return ApiResponse(response, lambda raw: parser(raw.json()))


class DemProbeResponses(_DemResponses):
    def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[builtins.list[DemProbe]]:
        return self._response(
            "GET",
            api._APPPROBES_PATH,
            _collection(DemProbe, "probes"),
            params=_paging(limit, offset),
        )

    def create(
        self,
        name: str,
        target: str,
        *,
        protocol: str = "https",
        interval: int | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> ApiResponse[DemProbe]:
        body = api._probe_create_body(name, target, protocol, interval, additional_fields)
        body["data"] = _validated(DemProbeCreate, body["data"])
        return self._response(
            "POST", api._APPPROBES_PATH, _item(DemProbe), json=body, retry_safe=False
        )


class DemNetworkProbeResponses(_DemResponses):
    def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[builtins.list[DemProbe]]:
        return self._response(
            "GET",
            api._NETWORKPROBES_PATH,
            _collection(DemProbe, "probes"),
            params=_paging(limit, offset),
        )


class DemAlertRuleResponses(_DemResponses):
    def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[builtins.list[DemAlertRule]]:
        return self._response(
            "GET",
            api._ALERT_RULES_PATH,
            _collection(DemAlertRule, "rules"),
            params=_paging(limit, offset),
        )

    def create(
        self,
        name: str,
        metric: str,
        threshold: float,
        *,
        severity: str = "medium",
        probe_id: str | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> ApiResponse[DemAlertRule]:
        body = api._alert_rule_create_body(
            name, metric, threshold, severity, probe_id, additional_fields
        )
        body["data"] = _validated(DemAlertRuleCreate, body["data"])
        return self._response(
            "POST", api._ALERT_RULES_PATH, _item(DemAlertRule), json=body, retry_safe=False
        )


class DemQueryResponses(_DemResponses):
    def get_data(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[DemQueryResult]:
        _paging(limit, offset)
        _time_bounds(begin, end, millis=True)
        body = api._getdata_body(
            data_source, select, begin, end, where, group_by, order_by, limit, offset
        )
        return self._response(
            "POST",
            api._QUERY_GETDATA_PATH,
            DemQueryResult.model_validate,
            json=_validated(DemQueryRequest, body),
            retry_safe=True,
        )

    def get_dataset(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[DemQueryResult]:
        body = _dataset_body(
            data_source, select, begin, end, where, group_by, order_by, limit, offset
        )
        return self._response(
            "POST",
            api._QUERY_GETDATASET_PATH,
            DemQueryResult.model_validate,
            json=body,
            retry_safe=True,
        )

    def get_entities(
        self,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        user: str | None = None,
        application: str | None = None,
        applications: builtins.list[str] | None = None,
        device_os: builtins.list[str] | None = None,
        monitoring: str | None = None,
        exp_score: builtins.list[str] | None = None,
        pop: builtins.list[str] | None = None,
        source_ip: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_order: str | None = None,
    ) -> ApiResponse[builtins.list[DemEntity]]:
        _time_bounds(start_time, end_time, millis=False)
        if sort_order is not None and sort_order not in ("asc", "desc"):
            raise ValidationError("sort_order must be asc or desc.")
        body = api._getentities_body(
            start_time,
            end_time,
            user,
            application,
            applications,
            device_os,
            monitoring,
            exp_score,
            pop,
            source_ip,
        )
        _paging(limit, offset)
        params = api._getentities_params(limit, offset, sort_order)
        return self._response(
            "POST",
            api._QUERY_GETENTITIES_PATH,
            _collection(DemEntity, "users"),
            params=params,
            json=body,
            retry_safe=True,
        )

    def get_states(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[DemQueryResult]:
        body = api._getstates_body(data_source, select, where, group_by, order_by, limit, offset)
        return self._response(
            "POST",
            api._QUERY_GETSTATES_PATH,
            DemQueryResult.model_validate,
            json=_validated(DemQueryRequest, body),
            retry_safe=True,
        )

    def get_traceroute(
        self,
        data_source: str,
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        order_by: Any | None = None,
    ) -> ApiResponse[DemQueryResult | AdemNetworkGraph]:
        _time_bounds(begin, end, millis=True)
        body = api._gettraceroute_body(data_source, begin, end, where, order_by)
        return self._response(
            "POST",
            api._QUERY_GETTRACEROUTE_PATH,
            _GRAPH_QUERY.validate_python,
            json=body,
            retry_safe=True,
        )

    def definitions(self, *, source: str | None = None) -> ApiResponse[DemDefinitions]:
        params = {"source": source} if source is not None else None
        return self._response(
            "GET", api._QUERY_DEFINITIONS_PATH, DemDefinitions.model_validate, params=params
        )


class DemAlertResponses(_DemResponses):
    def search(
        self,
        *,
        alert_category: builtins.list[str] | None = None,
        alert_type: builtins.list[str] | None = None,
        severity: builtins.list[str] | None = None,
        open_time: int | None = None,
        sort_field: str | None = None,
        sort_desc: bool = True,
        limit: int = 10,
        offset: int | None = None,
    ) -> ApiResponse[builtins.list[DemAlert]]:
        _paging(limit, offset)
        body = api._getalerts_body(
            alert_category, alert_type, severity, open_time, sort_field, sort_desc, limit, offset
        )
        return self._response(
            "POST",
            api._GETALERTS_PATH,
            _collection(DemAlert, "alerts"),
            json=body,
            retry_safe=True,
        )

    def get(self, alert_id: str) -> ApiResponse[DemAlert]:
        return self._response("GET", f"{api._ALERTS_PATH}/{quote_id(alert_id)}", _item(DemAlert))

    def entities(
        self,
        alert_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> ApiResponse[builtins.list[DemEntity]]:
        params = _paging(limit, offset)
        if sort_by is not None:
            params["sortby"] = sort_by
        if sort_order is not None:
            params["sortorder"] = sort_order
        return self._response(
            "GET",
            f"{api._ALERTS_PATH}/{quote_id(alert_id)}/entities",
            _collection(DemEntity, "entities"),
            params=params,
        )


class DemAppResponses(_DemResponses):
    def list(
        self,
        *,
        app_type: str | None = None,
        name: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[builtins.list[DemApp]]:
        params = _paging(limit, offset)
        if name is not None:
            params["name"] = name
        if app_type is not None:
            params["type"] = app_type
        return self._response("GET", api._APPS_PATH, _collection(DemApp, "apps"), params=params)


class DemUserResponses(_DemResponses):
    def devices(
        self,
        user: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[builtins.list[AdemDevice]]:
        body = _adem_body(start_time, end_time, user=user, userLocation=[])
        return self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/device/getlist",
            _collection(AdemDevice, "devices"),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    def device_details(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[AdemDeviceDetails]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/device/getdetails",
            _item(AdemDeviceDetails),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    def info(
        self,
        user: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[AdemUserInfo]:
        body = _adem_body(start_time, end_time, user=user)
        return self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/getinfo",
            _item(AdemUserInfo),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    def applications(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[builtins.list[AdemApplication]]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/getapplications",
            _collection(AdemApplication, "applications"),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    def locations(
        self,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[builtins.list[AdemLocation]]:
        body = _adem_body(start_time, end_time)
        return self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/getlocations",
            _collection(AdemLocation, "userLocations"),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    def aggregated_scores(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        aggregation_type: str = "avg",
    ) -> ApiResponse[AdemAggregatedScores]:
        body = _adem_body(
            start_time, end_time, user=user, device_id=device_id, aggregationType=aggregation_type
        )
        return self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/device/getaggregatedscores",
            AdemAggregatedScores.model_validate,
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    def exp_score(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[builtins.list[AdemMetricPoint]]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/metrics/getexpscore",
            _collection(AdemMetricPoint, "metrics"),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    def rca(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[AdemRootCause]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/device/getrca",
            AdemRootCause.model_validate,
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    def network_metrics(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        metric_type: str = "all",
    ) -> ApiResponse[builtins.list[AdemMetricPoint]]:
        body = _adem_body(
            start_time, end_time, user=user, device_id=device_id, metricType=metric_type
        )
        return self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/metrics/getnetwork",
            _collection(AdemMetricPoint, "metrics"),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    def npa_hosts(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[builtins.list[NpaHost]]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/npa/getnpahosts",
            _collection(NpaHost, "npaHosts"),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    def npa_network_paths(
        self,
        user: str,
        device_id: str,
        npa_host: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[AdemNetworkGraph]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id, npaHost=npa_host)
        return self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/npa/getnetworkpaths",
            AdemNetworkGraph.model_validate,
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    def traceroute_timestamps(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[builtins.list[AdemMetricPoint]]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/device/gettraceroutetimestamps",
            _collection(AdemMetricPoint, "timestamps"),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    def traceroute(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[AdemNetworkGraph]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/device/gettraceroute",
            AdemNetworkGraph.model_validate,
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )


class AsyncDemProbeResponses(_AsyncDemResponses):
    async def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[builtins.list[DemProbe]]:
        return await self._response(
            "GET",
            api._APPPROBES_PATH,
            _collection(DemProbe, "probes"),
            params=_paging(limit, offset),
        )

    async def create(
        self,
        name: str,
        target: str,
        *,
        protocol: str = "https",
        interval: int | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> ApiResponse[DemProbe]:
        body = api._probe_create_body(name, target, protocol, interval, additional_fields)
        body["data"] = _validated(DemProbeCreate, body["data"])
        return await self._response(
            "POST", api._APPPROBES_PATH, _item(DemProbe), json=body, retry_safe=False
        )


class AsyncDemNetworkProbeResponses(_AsyncDemResponses):
    async def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[builtins.list[DemProbe]]:
        return await self._response(
            "GET",
            api._NETWORKPROBES_PATH,
            _collection(DemProbe, "probes"),
            params=_paging(limit, offset),
        )


class AsyncDemAlertRuleResponses(_AsyncDemResponses):
    async def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[builtins.list[DemAlertRule]]:
        return await self._response(
            "GET",
            api._ALERT_RULES_PATH,
            _collection(DemAlertRule, "rules"),
            params=_paging(limit, offset),
        )

    async def create(
        self,
        name: str,
        metric: str,
        threshold: float,
        *,
        severity: str = "medium",
        probe_id: str | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> ApiResponse[DemAlertRule]:
        body = api._alert_rule_create_body(
            name, metric, threshold, severity, probe_id, additional_fields
        )
        body["data"] = _validated(DemAlertRuleCreate, body["data"])
        return await self._response(
            "POST", api._ALERT_RULES_PATH, _item(DemAlertRule), json=body, retry_safe=False
        )


class AsyncDemQueryResponses(_AsyncDemResponses):
    async def get_data(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[DemQueryResult]:
        _paging(limit, offset)
        _time_bounds(begin, end, millis=True)
        body = api._getdata_body(
            data_source, select, begin, end, where, group_by, order_by, limit, offset
        )
        return await self._response(
            "POST",
            api._QUERY_GETDATA_PATH,
            DemQueryResult.model_validate,
            json=_validated(DemQueryRequest, body),
            retry_safe=True,
        )

    async def get_dataset(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[DemQueryResult]:
        body = _dataset_body(
            data_source, select, begin, end, where, group_by, order_by, limit, offset
        )
        return await self._response(
            "POST",
            api._QUERY_GETDATASET_PATH,
            DemQueryResult.model_validate,
            json=body,
            retry_safe=True,
        )

    async def get_entities(
        self,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        user: str | None = None,
        application: str | None = None,
        applications: builtins.list[str] | None = None,
        device_os: builtins.list[str] | None = None,
        monitoring: str | None = None,
        exp_score: builtins.list[str] | None = None,
        pop: builtins.list[str] | None = None,
        source_ip: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_order: str | None = None,
    ) -> ApiResponse[builtins.list[DemEntity]]:
        _time_bounds(start_time, end_time, millis=False)
        if sort_order is not None and sort_order not in ("asc", "desc"):
            raise ValidationError("sort_order must be asc or desc.")
        body = api._getentities_body(
            start_time,
            end_time,
            user,
            application,
            applications,
            device_os,
            monitoring,
            exp_score,
            pop,
            source_ip,
        )
        _paging(limit, offset)
        params = api._getentities_params(limit, offset, sort_order)
        return await self._response(
            "POST",
            api._QUERY_GETENTITIES_PATH,
            _collection(DemEntity, "users"),
            params=params,
            json=body,
            retry_safe=True,
        )

    async def get_states(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[DemQueryResult]:
        body = api._getstates_body(data_source, select, where, group_by, order_by, limit, offset)
        return await self._response(
            "POST",
            api._QUERY_GETSTATES_PATH,
            DemQueryResult.model_validate,
            json=_validated(DemQueryRequest, body),
            retry_safe=True,
        )

    async def get_traceroute(
        self,
        data_source: str,
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        order_by: Any | None = None,
    ) -> ApiResponse[DemQueryResult | AdemNetworkGraph]:
        _time_bounds(begin, end, millis=True)
        body = api._gettraceroute_body(data_source, begin, end, where, order_by)
        return await self._response(
            "POST",
            api._QUERY_GETTRACEROUTE_PATH,
            _GRAPH_QUERY.validate_python,
            json=body,
            retry_safe=True,
        )

    async def definitions(self, *, source: str | None = None) -> ApiResponse[DemDefinitions]:
        params = {"source": source} if source is not None else None
        return await self._response(
            "GET", api._QUERY_DEFINITIONS_PATH, DemDefinitions.model_validate, params=params
        )


class AsyncDemAlertResponses(_AsyncDemResponses):
    async def search(
        self,
        *,
        alert_category: builtins.list[str] | None = None,
        alert_type: builtins.list[str] | None = None,
        severity: builtins.list[str] | None = None,
        open_time: int | None = None,
        sort_field: str | None = None,
        sort_desc: bool = True,
        limit: int = 10,
        offset: int | None = None,
    ) -> ApiResponse[builtins.list[DemAlert]]:
        _paging(limit, offset)
        body = api._getalerts_body(
            alert_category, alert_type, severity, open_time, sort_field, sort_desc, limit, offset
        )
        return await self._response(
            "POST",
            api._GETALERTS_PATH,
            _collection(DemAlert, "alerts"),
            json=body,
            retry_safe=True,
        )

    async def get(self, alert_id: str) -> ApiResponse[DemAlert]:
        return await self._response(
            "GET", f"{api._ALERTS_PATH}/{quote_id(alert_id)}", _item(DemAlert)
        )

    async def entities(
        self,
        alert_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> ApiResponse[builtins.list[DemEntity]]:
        params = _paging(limit, offset)
        if sort_by is not None:
            params["sortby"] = sort_by
        if sort_order is not None:
            params["sortorder"] = sort_order
        return await self._response(
            "GET",
            f"{api._ALERTS_PATH}/{quote_id(alert_id)}/entities",
            _collection(DemEntity, "entities"),
            params=params,
        )


class AsyncDemAppResponses(_AsyncDemResponses):
    async def list(
        self,
        *,
        app_type: str | None = None,
        name: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[builtins.list[DemApp]]:
        params = _paging(limit, offset)
        if name is not None:
            params["name"] = name
        if app_type is not None:
            params["type"] = app_type
        return await self._response(
            "GET", api._APPS_PATH, _collection(DemApp, "apps"), params=params
        )


class AsyncDemUserResponses(_AsyncDemResponses):
    async def devices(
        self,
        user: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[builtins.list[AdemDevice]]:
        body = _adem_body(start_time, end_time, user=user, userLocation=[])
        return await self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/device/getlist",
            _collection(AdemDevice, "devices"),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    async def device_details(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[AdemDeviceDetails]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/device/getdetails",
            _item(AdemDeviceDetails),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    async def info(
        self,
        user: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[AdemUserInfo]:
        body = _adem_body(start_time, end_time, user=user)
        return await self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/getinfo",
            _item(AdemUserInfo),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    async def applications(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[builtins.list[AdemApplication]]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/getapplications",
            _collection(AdemApplication, "applications"),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    async def locations(
        self,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[builtins.list[AdemLocation]]:
        body = _adem_body(start_time, end_time)
        return await self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/getlocations",
            _collection(AdemLocation, "userLocations"),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    async def aggregated_scores(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        aggregation_type: str = "avg",
    ) -> ApiResponse[AdemAggregatedScores]:
        body = _adem_body(
            start_time, end_time, user=user, device_id=device_id, aggregationType=aggregation_type
        )
        return await self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/device/getaggregatedscores",
            AdemAggregatedScores.model_validate,
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    async def exp_score(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[builtins.list[AdemMetricPoint]]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/metrics/getexpscore",
            _collection(AdemMetricPoint, "metrics"),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    async def rca(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[AdemRootCause]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/device/getrca",
            AdemRootCause.model_validate,
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    async def network_metrics(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        metric_type: str = "all",
    ) -> ApiResponse[builtins.list[AdemMetricPoint]]:
        body = _adem_body(
            start_time, end_time, user=user, device_id=device_id, metricType=metric_type
        )
        return await self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/metrics/getnetwork",
            _collection(AdemMetricPoint, "metrics"),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    async def npa_hosts(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[builtins.list[NpaHost]]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/npa/getnpahosts",
            _collection(NpaHost, "npaHosts"),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    async def npa_network_paths(
        self,
        user: str,
        device_id: str,
        npa_host: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[AdemNetworkGraph]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id, npaHost=npa_host)
        return await self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/npa/getnetworkpaths",
            AdemNetworkGraph.model_validate,
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    async def traceroute_timestamps(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[builtins.list[AdemMetricPoint]]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/device/gettraceroutetimestamps",
            _collection(AdemMetricPoint, "timestamps"),
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )

    async def traceroute(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> ApiResponse[AdemNetworkGraph]:
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._response(
            "POST",
            f"{api._ADEM_USERS_PATH}/device/gettraceroute",
            AdemNetworkGraph.model_validate,
            json=_validated(AdemQueryRequest, body),
            retry_safe=True,
        )
