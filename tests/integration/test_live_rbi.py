"""Live integration tests for the RBI (Remote Browser Isolation) API.

These tests require valid credentials and hit the real API.
Run with: pytest tests/integration/ -m integration -v

Credentials come from environment variables only (see conftest.py).

RBI is a licensed feature, so every smoke is wrapped with
:func:`skip_if_unavailable` — tenants without RBI return 403/404 and are
skipped rather than failed.  These are strictly read-only smokes; no template,
Cloud Storage, or CDR mutations are performed.
"""

from __future__ import annotations

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError

from .conftest import skip_if_unavailable


@pytest.mark.integration
class TestRbiIntegration:
    """Live read-only smokes for the RBI API."""

    def test_list_applications(self, client: NetskopeClient) -> None:
        try:
            data = client.rbi.list_applications()
        except APIError as e:
            skip_if_unavailable(e, "RBI applications")
        else:
            assert isinstance(data, dict)

    def test_list_supported_browsers(self, client: NetskopeClient) -> None:
        try:
            data = client.rbi.list_supported_browsers()
        except APIError as e:
            skip_if_unavailable(e, "RBI supported browsers")
        else:
            # The endpoint returns a JSON array of browser objects.
            assert isinstance(data, (list, dict))

    def test_list_default_categories(self, client: NetskopeClient) -> None:
        try:
            data = client.rbi.list_default_categories()
        except APIError as e:
            skip_if_unavailable(e, "RBI default categories")
        else:
            assert isinstance(data, (list, dict))

    def test_list_templates(self, client: NetskopeClient) -> None:
        try:
            data = client.rbi.list_templates(limit=5)
        except APIError as e:
            skip_if_unavailable(e, "RBI templates")
        else:
            assert isinstance(data, dict)
