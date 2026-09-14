"""The users sub-namespace of dem."""

from __future__ import annotations

import asyncio
import builtins
import functools
from datetime import datetime
from typing import Any

from netskope.core.ids import extract_item, extract_list
from netskope.core.resource import AsyncResource, SyncResource
from netskope.models.dem import (
    AdemApplication,
    AdemDevice,
    AdemUserInfo,
    AggregationType,
    NetworkMetricType,
)
from netskope.resources.dem._shared import (
    _filter_apps,
    _normalize_device_list,
    _npa_host_ips,
)
from netskope.resources.dem.decoder import (
    AsyncDemUserResponses,
    DemUserResponses,
)
from netskope.resources.dem.paths import (
    _ADEM_USERS_PATH,
    _adem_body,
)


class DemUsersResource(SyncResource):
    """ADEM per-user/per-device telemetry — ``/api/v2/adem/users`` (all POST, epoch **seconds**)."""

    @functools.cached_property
    def with_response(self) -> DemUserResponses:
        """Inspect one completed request together with its typed result."""

        return DemUserResponses(self._transport)

    def devices(
        self, user: str, *, start_time: datetime | int, end_time: datetime | int
    ) -> builtins.list[AdemDevice]:
        """List devices for a user with experience scores.

        The request body must include ``"userLocation": []`` for the API to
        return the full device list.
        """
        body = _adem_body(start_time, end_time, user=user, userLocation=[])
        resp = self._post(f"{_ADEM_USERS_PATH}/device/getlist", json=body, retry_safe=True)
        return [AdemDevice.model_validate(d) for d in _normalize_device_list(resp)]

    def device_details(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """Get detailed device information (hardware, software, location)."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._post(f"{_ADEM_USERS_PATH}/device/getdetails", json=body, retry_safe=True)

    def info(
        self, user: str, *, start_time: datetime | int, end_time: datetime | int
    ) -> AdemUserInfo:
        """Get the user info summary (experience score and location)."""
        body = _adem_body(start_time, end_time, user=user)
        resp = self._post(f"{_ADEM_USERS_PATH}/getinfo", json=body, retry_safe=True)
        return AdemUserInfo.model_validate(extract_item(resp))

    def applications(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> builtins.list[AdemApplication]:
        """List applications on a device with per-app experience scores.

        ``device_id`` is required: without it the API silently returns only a
        1-2 app subset instead of the full per-device list.
        """
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        resp = self._post(f"{_ADEM_USERS_PATH}/getapplications", json=body, retry_safe=True)
        return [AdemApplication.model_validate(a) for a in extract_list(resp, "applications")]

    def locations(self, *, start_time: datetime | int, end_time: datetime | int) -> dict[str, Any]:
        """Get all user locations."""
        body = _adem_body(start_time, end_time)
        return self._post(f"{_ADEM_USERS_PATH}/getlocations", json=body, retry_safe=True)

    def aggregated_scores(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        aggregation_type: str = AggregationType.AVG,
    ) -> dict[str, Any]:
        """Get aggregated experience scores for a device."""
        body = _adem_body(
            start_time,
            end_time,
            user=user,
            device_id=device_id,
            aggregationType=aggregation_type,
        )
        return self._post(
            f"{_ADEM_USERS_PATH}/device/getaggregatedscores", json=body, retry_safe=True
        )

    def exp_score(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """Get the experience-score time series for a device."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._post(f"{_ADEM_USERS_PATH}/metrics/getexpscore", json=body, retry_safe=True)

    def rca(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """Get the root-cause-analysis tree and per-component scores for a device."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._post(f"{_ADEM_USERS_PATH}/device/getrca", json=body, retry_safe=True)

    def network_metrics(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        metric_type: str = NetworkMetricType.ALL,
    ) -> dict[str, Any]:
        """Get the network-metrics time series (latency/packet loss/jitter) for a device."""
        body = _adem_body(
            start_time, end_time, user=user, device_id=device_id, metricType=metric_type
        )
        return self._post(f"{_ADEM_USERS_PATH}/metrics/getnetwork", json=body, retry_safe=True)

    def npa_hosts(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """Get NPA hosts (with scores/applications) for a user and device."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._post(f"{_ADEM_USERS_PATH}/npa/getnpahosts", json=body, retry_safe=True)

    def npa_network_paths(
        self,
        user: str,
        device_id: str,
        npa_host: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """Get the NPA network-path graph between a device and an NPA host."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id, npaHost=npa_host)
        return self._post(f"{_ADEM_USERS_PATH}/npa/getnetworkpaths", json=body, retry_safe=True)

    def traceroute_timestamps(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """List available traceroute timestamps for a device.

        PRIVILEGED: internal endpoint; scoped tokens may receive 403.
        """
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._post(
            f"{_ADEM_USERS_PATH}/device/gettraceroutetimestamps", json=body, retry_safe=True
        )

    def traceroute(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """Get detailed traceroute path data for a device.

        PRIVILEGED: internal endpoint; scoped tokens may receive 403.  Pass a
        single timestamp (from :meth:`traceroute_timestamps`) as both
        ``start_time`` and ``end_time``.
        """
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._post(f"{_ADEM_USERS_PATH}/device/gettraceroute", json=body, retry_safe=True)

    def diagnose(
        self,
        user: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        device_id: str | None = None,
        application: str | None = None,
        include_npa: bool = False,
    ) -> dict[str, Any]:
        """One-shot digital-experience diagnostic for a user.

        Composes several ADEM calls: user ``info``; the device list (or the
        single ``device_id`` when given); then per-device ``device_details``,
        ``applications``, ``aggregated_scores`` (avg) and ``rca``; and, when
        ``include_npa`` is set, ``npa_hosts`` plus per-host
        ``npa_network_paths``.

        Every sub-call is guarded: a failing endpoint stores ``None`` for that
        slice and appends ``{"endpoint": ..., "error": ...}`` to the returned
        ``"errors"`` list rather than raising.  When ``application`` is given,
        each device's application list is filtered to case-insensitive name
        matches.

        Returns a dict with ``"user_info"``, ``"devices"`` (each with
        ``device_id``, ``details``, ``applications``, ``scores``, ``rca`` and,
        when requested, ``npa``) and ``"errors"``.
        """
        errors: builtins.list[dict[str, Any]] = []
        user_info = self._safe(
            errors, "getinfo", lambda: self.info(user, start_time=start_time, end_time=end_time)
        )
        device_ids = self._resolve_device_ids(user, start_time, end_time, device_id, errors)
        devices = [
            self._diagnose_device(user, did, start_time, end_time, include_npa, application, errors)
            for did in device_ids
        ]
        return {"user_info": user_info, "devices": devices, "errors": errors}

    def _resolve_device_ids(
        self,
        user: str,
        start_time: datetime | int,
        end_time: datetime | int,
        device_id: str | None,
        errors: builtins.list[dict[str, Any]],
    ) -> builtins.list[str]:
        if device_id is not None:
            return [device_id]
        devices = self._safe(
            errors,
            "device/getlist",
            lambda: self.devices(user, start_time=start_time, end_time=end_time),
        )
        return [d.device_id for d in devices or [] if d.device_id]

    def _diagnose_device(
        self,
        user: str,
        did: str,
        start_time: datetime | int,
        end_time: datetime | int,
        include_npa: bool,
        application: str | None,
        errors: builtins.list[dict[str, Any]],
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {"device_id": did}
        entry["details"] = self._safe(
            errors,
            "device/getdetails",
            lambda: self.device_details(user, did, start_time=start_time, end_time=end_time),
        )
        apps = self._safe(
            errors,
            "getapplications",
            lambda: self.applications(user, did, start_time=start_time, end_time=end_time),
        )
        entry["applications"] = _filter_apps(apps, application)
        entry["scores"] = self._safe(
            errors,
            "device/getaggregatedscores",
            lambda: self.aggregated_scores(user, did, start_time=start_time, end_time=end_time),
        )
        entry["rca"] = self._safe(
            errors,
            "device/getrca",
            lambda: self.rca(user, did, start_time=start_time, end_time=end_time),
        )
        if include_npa:
            entry["npa"] = self._diagnose_npa(user, did, start_time, end_time, errors)
        return entry

    def _diagnose_npa(
        self,
        user: str,
        did: str,
        start_time: datetime | int,
        end_time: datetime | int,
        errors: builtins.list[dict[str, Any]],
    ) -> dict[str, Any]:
        hosts = self._safe(
            errors,
            "npa/getnpahosts",
            lambda: self.npa_hosts(user, did, start_time=start_time, end_time=end_time),
        )
        paths = []
        for host_ip in _npa_host_ips(hosts):
            path = self._safe(
                errors,
                f"npa/getnetworkpaths ({host_ip})",
                lambda h=host_ip: self.npa_network_paths(
                    user, did, h, start_time=start_time, end_time=end_time
                ),
            )
            if path is not None:
                paths.append({"npaHost": host_ip, "path": path})
        return {"hosts": hosts, "network_paths": paths}

    @staticmethod
    def _safe(errors: builtins.list[dict[str, Any]], endpoint: str, call: Any) -> Any:
        from netskope.exceptions import APIError

        try:
            return call()
        except APIError as exc:
            errors.append({"endpoint": endpoint, "error": str(exc)})
            return None


class AsyncDemUsersResource(AsyncResource):
    """Async ADEM per-user/per-device telemetry."""

    @functools.cached_property
    def with_response(self) -> AsyncDemUserResponses:
        """Inspect one completed request together with its typed result."""

        return AsyncDemUserResponses(self._transport)

    async def devices(
        self, user: str, *, start_time: datetime | int, end_time: datetime | int
    ) -> builtins.list[AdemDevice]:
        """See :meth:`DemUsersResource.devices`."""
        body = _adem_body(start_time, end_time, user=user, userLocation=[])
        resp = await self._post(f"{_ADEM_USERS_PATH}/device/getlist", json=body, retry_safe=True)
        return [AdemDevice.model_validate(d) for d in _normalize_device_list(resp)]

    async def device_details(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.device_details`."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._post(f"{_ADEM_USERS_PATH}/device/getdetails", json=body, retry_safe=True)

    async def info(
        self, user: str, *, start_time: datetime | int, end_time: datetime | int
    ) -> AdemUserInfo:
        """See :meth:`DemUsersResource.info`."""
        body = _adem_body(start_time, end_time, user=user)
        resp = await self._post(f"{_ADEM_USERS_PATH}/getinfo", json=body, retry_safe=True)
        return AdemUserInfo.model_validate(extract_item(resp))

    async def applications(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> builtins.list[AdemApplication]:
        """See :meth:`DemUsersResource.applications`."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        resp = await self._post(f"{_ADEM_USERS_PATH}/getapplications", json=body, retry_safe=True)
        return [AdemApplication.model_validate(a) for a in extract_list(resp, "applications")]

    async def locations(
        self, *, start_time: datetime | int, end_time: datetime | int
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.locations`."""
        body = _adem_body(start_time, end_time)
        return await self._post(f"{_ADEM_USERS_PATH}/getlocations", json=body, retry_safe=True)

    async def aggregated_scores(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        aggregation_type: str = AggregationType.AVG,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.aggregated_scores`."""
        body = _adem_body(
            start_time,
            end_time,
            user=user,
            device_id=device_id,
            aggregationType=aggregation_type,
        )
        return await self._post(
            f"{_ADEM_USERS_PATH}/device/getaggregatedscores", json=body, retry_safe=True
        )

    async def exp_score(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.exp_score`."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._post(
            f"{_ADEM_USERS_PATH}/metrics/getexpscore", json=body, retry_safe=True
        )

    async def rca(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.rca`."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._post(f"{_ADEM_USERS_PATH}/device/getrca", json=body, retry_safe=True)

    async def network_metrics(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        metric_type: str = NetworkMetricType.ALL,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.network_metrics`."""
        body = _adem_body(
            start_time, end_time, user=user, device_id=device_id, metricType=metric_type
        )
        return await self._post(
            f"{_ADEM_USERS_PATH}/metrics/getnetwork", json=body, retry_safe=True
        )

    async def npa_hosts(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.npa_hosts`."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._post(f"{_ADEM_USERS_PATH}/npa/getnpahosts", json=body, retry_safe=True)

    async def npa_network_paths(
        self,
        user: str,
        device_id: str,
        npa_host: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.npa_network_paths`."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id, npaHost=npa_host)
        return await self._post(
            f"{_ADEM_USERS_PATH}/npa/getnetworkpaths", json=body, retry_safe=True
        )

    async def traceroute_timestamps(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.traceroute_timestamps`.  PRIVILEGED."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._post(
            f"{_ADEM_USERS_PATH}/device/gettraceroutetimestamps", json=body, retry_safe=True
        )

    async def traceroute(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.traceroute`.  PRIVILEGED."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._post(
            f"{_ADEM_USERS_PATH}/device/gettraceroute", json=body, retry_safe=True
        )

    async def diagnose(
        self,
        user: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        device_id: str | None = None,
        application: str | None = None,
        include_npa: bool = False,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.diagnose`.  Per-device calls run concurrently."""
        errors: builtins.list[dict[str, Any]] = []
        user_info = await self._safe(
            errors, "getinfo", self.info(user, start_time=start_time, end_time=end_time)
        )
        if device_id is not None:
            device_ids = [device_id]
        else:
            devices = await self._safe(
                errors,
                "device/getlist",
                self.devices(user, start_time=start_time, end_time=end_time),
            )
            device_ids = [d.device_id for d in devices or [] if d.device_id]
        devices_out = await asyncio.gather(
            *(
                self._diagnose_device(
                    user, did, start_time, end_time, include_npa, application, errors
                )
                for did in device_ids
            )
        )
        return {"user_info": user_info, "devices": list(devices_out), "errors": errors}

    async def _diagnose_device(
        self,
        user: str,
        did: str,
        start_time: datetime | int,
        end_time: datetime | int,
        include_npa: bool,
        application: str | None,
        errors: builtins.list[dict[str, Any]],
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {"device_id": did}
        entry["details"] = await self._safe(
            errors,
            "device/getdetails",
            self.device_details(user, did, start_time=start_time, end_time=end_time),
        )
        apps = await self._safe(
            errors,
            "getapplications",
            self.applications(user, did, start_time=start_time, end_time=end_time),
        )
        entry["applications"] = _filter_apps(apps, application)
        entry["scores"] = await self._safe(
            errors,
            "device/getaggregatedscores",
            self.aggregated_scores(user, did, start_time=start_time, end_time=end_time),
        )
        entry["rca"] = await self._safe(
            errors,
            "device/getrca",
            self.rca(user, did, start_time=start_time, end_time=end_time),
        )
        if include_npa:
            entry["npa"] = await self._diagnose_npa(user, did, start_time, end_time, errors)
        return entry

    async def _diagnose_npa(
        self,
        user: str,
        did: str,
        start_time: datetime | int,
        end_time: datetime | int,
        errors: builtins.list[dict[str, Any]],
    ) -> dict[str, Any]:
        hosts = await self._safe(
            errors,
            "npa/getnpahosts",
            self.npa_hosts(user, did, start_time=start_time, end_time=end_time),
        )
        paths = []
        for host_ip in _npa_host_ips(hosts):
            path = await self._safe(
                errors,
                f"npa/getnetworkpaths ({host_ip})",
                self.npa_network_paths(
                    user, did, host_ip, start_time=start_time, end_time=end_time
                ),
            )
            if path is not None:
                paths.append({"npaHost": host_ip, "path": path})
        return {"hosts": hosts, "network_paths": paths}

    @staticmethod
    async def _safe(errors: builtins.list[dict[str, Any]], endpoint: str, coro: Any) -> Any:
        from netskope.exceptions import APIError

        try:
            return await coro
        except APIError as exc:
            errors.append({"endpoint": endpoint, "error": str(exc)})
            return None
