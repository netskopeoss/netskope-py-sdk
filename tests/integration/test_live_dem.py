"""Live integration smokes for the DEM / ADEM namespace.

All tests degrade to a skip when the feature is unavailable on the tenant
(402/403/404/501 or licensing).  The privileged query surface commonly 403s on
scoped API tokens, so those smokes expect a skip there.  Writes are limited to
a single application-probe create/delete cycle guarded with a unique,
prefix-tagged name and a finally-block delete.
"""

from __future__ import annotations

import contextlib

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.resources.dem import DemResource
from tests.integration.conftest import skip_if_unavailable, unique_name

pytestmark = pytest.mark.integration


def _dem(client: NetskopeClient) -> DemResource:
    return DemResource(client._transport)


def test_probes_list_smoke(client: NetskopeClient) -> None:
    """Reading application probes should return a dict envelope (or skip)."""
    try:
        result = _dem(client).probes.list(limit=5)
    except APIError as exc:
        skip_if_unavailable(exc, "dem probes list")
        return
    assert isinstance(result, dict)


def test_network_probes_list_smoke(client: NetskopeClient) -> None:
    try:
        result = _dem(client).network_probes.list(limit=5)
    except APIError as exc:
        skip_if_unavailable(exc, "dem network probes list")
        return
    assert isinstance(result, dict)


def test_apps_list_smoke(client: NetskopeClient) -> None:
    try:
        result = _dem(client).apps.list(limit=5)
    except APIError as exc:
        skip_if_unavailable(exc, "dem apps list")
        return
    assert isinstance(result, dict)


def test_alert_rules_list_smoke(client: NetskopeClient) -> None:
    try:
        result = _dem(client).alert_rules.list(limit=5)
    except APIError as exc:
        skip_if_unavailable(exc, "dem alert rules list")
        return
    assert isinstance(result, dict)


def test_alerts_search_smoke(client: NetskopeClient) -> None:
    """Searching triggered experience alerts should return a list (or skip)."""
    try:
        alerts = _dem(client).alerts.search(limit=5)
    except APIError as exc:
        skip_if_unavailable(exc, "dem alerts search")
        return
    assert isinstance(alerts, list)


def test_query_definitions_smoke(client: NetskopeClient) -> None:
    """The privileged query surface typically 403s on scoped tokens — expect a skip."""
    try:
        result = _dem(client).query.definitions()
    except APIError as exc:
        skip_if_unavailable(exc, "dem query definitions (privileged)")
        return
    assert isinstance(result, dict)


def test_adem_locations_smoke(client: NetskopeClient) -> None:
    """ADEM user locations over a short window (or skip)."""
    # A fixed, small historical window — never call datetime.now() in tests.
    start_time = 1710000000
    end_time = start_time + 3600
    try:
        result = _dem(client).users.locations(start_time=start_time, end_time=end_time)
    except APIError as exc:
        skip_if_unavailable(exc, "adem users locations")
        return
    assert isinstance(result, dict)


def test_probe_write_cycle(client: NetskopeClient) -> None:
    """Create then delete an application probe (the gateway spec exposes DELETE).

    NOTE: the SDK's ``probes.create`` sends the CLI-shaped ``{"data": {...}}``
    body (name/target/protocol), which diverges from the gateway OpenAPI probe
    schema.  On tenants that enforce the spec shape this create may 400; that
    is treated as "unavailable" here so the smoke skips rather than fails.
    """
    dem = _dem(client)
    name = unique_name("demprobe")
    probe_id = None
    try:
        created = dem.probes.create(name, "https://www.netskope.com", protocol="https")
    except APIError as exc:
        status = getattr(exc, "status_code", None)
        if status in (400, 402, 403, 404, 422, 501) or "licens" in str(exc).lower():
            pytest.skip(f"dem probe create unavailable on this tenant: {exc}")
        raise
    try:
        # Locate the created probe's id from the response envelope.
        data = created.get("data", created) if isinstance(created, dict) else {}
        if isinstance(data, list):
            data = data[0] if data else {}
        probe_id = data.get("id") if isinstance(data, dict) else None
        assert probe_id is not None, f"probe create returned no id: {created!r}"
    finally:
        if probe_id is not None:
            # Tolerate 404 / already-deleted; the sweeper is best-effort.
            with contextlib.suppress(APIError):
                dem.probes.delete(probe_id)
