"""Live integration tests for the SPM (SaaS Security Posture Management) API.

These tests require valid credentials and hit the real API.
Run with: pytest tests/integration/ -m integration -v

Credentials come from environment variables only (see conftest.py).

All checks are READ-ONLY smokes.  SPM is a licensed add-on, so tenants
without it will return 402/403/404/501 or a licensing error — those are
skips, not failures (see :func:`skip_if_unavailable`).

``client.spm`` is not wired into the client, so these tests instantiate the
:class:`~netskope.resources.spm.SpmResource` directly against the client's
transport.
"""

from __future__ import annotations

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.resources.spm import SpmResource

from .conftest import skip_if_unavailable


@pytest.mark.integration
class TestSpmIntegration:
    """Live read-only smokes for the SPM API."""

    def test_list_apps(self, client: NetskopeClient) -> None:
        """List monitored SaaS apps; skip when SPM is unlicensed."""
        spm = SpmResource(client._transport)
        try:
            data = spm.list_apps()
        except APIError as e:
            skip_if_unavailable(e, "SPM apps list")
        else:
            assert isinstance(data, dict)

    def test_posture_score(self, client: NetskopeClient) -> None:
        """Fetch the aggregate posture score; skip when SPM is unlicensed."""
        spm = SpmResource(client._transport)
        try:
            data = spm.posture_score()
        except APIError as e:
            skip_if_unavailable(e, "SPM posture score")
        else:
            assert isinstance(data, dict)

    def test_list_policy_rules(self, client: NetskopeClient) -> None:
        """List posture policy rules; skip when SPM is unlicensed."""
        spm = SpmResource(client._transport)
        try:
            data = spm.list_policy_rules()
        except APIError as e:
            skip_if_unavailable(e, "SPM policy rules")
        else:
            assert isinstance(data, dict)

    def test_get_app_round_trip(self, client: NetskopeClient) -> None:
        """If list_apps returns apps, get_app on the first one round-trips."""
        spm = SpmResource(client._transport)
        try:
            listing = spm.list_apps()
        except APIError as e:
            skip_if_unavailable(e, "SPM apps list")
            return

        name = _first_app_name(listing)
        if name is None:
            pytest.skip("No SPM apps returned to exercise get_app")

        try:
            detail = spm.get_app(name)
        except APIError as e:
            skip_if_unavailable(e, "SPM app detail")
        else:
            assert isinstance(detail, dict)


def _first_app_name(body: dict[str, object]) -> str | None:
    """Best-effort extraction of the first app name from a list_apps body.

    The envelope shape is not pinned, so probe the common containers
    (``data``/``result``/``apps`` or a bare list) and look for a
    ``name``/``app_name`` field on the first entry.
    """
    items: object = body
    if isinstance(body, dict):
        for key in ("data", "result", "apps"):
            value = body.get(key)
            if isinstance(value, list):
                items = value
                break
    if not isinstance(items, list) or not items:
        return None
    first = items[0]
    if not isinstance(first, dict):
        return None
    for key in ("name", "app_name", "appName"):
        value = first.get(key)
        if isinstance(value, str) and value:
            return value
    return None
