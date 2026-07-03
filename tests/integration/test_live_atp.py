"""Live integration tests for the ATP (Advanced Threat Protection) API.

These tests require valid credentials and hit the real API.
Run with: pytest tests/integration/ -m integration -v

Credentials come from environment variables only (see conftest.py).

``client.atp`` is not wired onto the client, so these tests drive the resource
directly via ``AtpResource(client._transport)``.  Every test is READ-ONLY: we
only look up reports for obviously-nonexistent IDs and expect a not-found /
error response (or a skip on unlicensed tenants).  No files or URLs are ever
submitted for scanning in CI — that would consume tenant quota.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError, NotFoundError
from netskope.resources.atp import AtpResource

from .conftest import skip_if_unavailable

# Obviously-nonexistent identifiers; no real scan is ever submitted.
_FAKE_JOB_ID = f"sdk-inttest-{uuid4().hex}"
_FAKE_SUBMISSION_ID = str(uuid4())


@pytest.mark.integration
class TestAtpIntegration:
    """Live read-only smokes for the ATP API."""

    def test_get_report_nonexistent(self, client: NetskopeClient) -> None:
        """A bogus sandbox jobid should not resolve to a real report."""
        atp = AtpResource(client._transport)
        try:
            body = atp.get_report(_FAKE_JOB_ID)
        except NotFoundError:
            pass  # expected: no such job
        except APIError as e:
            skip_if_unavailable(e, "ATP sandbox report")
        else:
            # Some tenants answer 200 with an error/pending envelope rather
            # than 404 — just assert we got a JSON object back.
            assert isinstance(body, dict)

    def test_get_submission_report_nonexistent(self, client: NetskopeClient) -> None:
        """A bogus TPaaS submission_id should not resolve to a real report."""
        atp = AtpResource(client._transport)
        try:
            body = atp.get_submission_report(_FAKE_SUBMISSION_ID)
        except NotFoundError:
            pass
        except APIError as e:
            skip_if_unavailable(e, "ATP TPaaS submission report")
        else:
            assert isinstance(body, dict)

    def test_get_scan_result_nonexistent(self, client: NetskopeClient) -> None:
        """A bogus TPaaS submission_id should not resolve to a real result."""
        atp = AtpResource(client._transport)
        try:
            body = atp.get_scan_result(_FAKE_SUBMISSION_ID)
        except NotFoundError:
            pass
        except APIError as e:
            skip_if_unavailable(e, "ATP TPaaS scan result")
        else:
            assert isinstance(body, dict)

    def test_get_url_report_nonexistent(self, client: NetskopeClient) -> None:
        """A bogus URL-scan submission_id should not resolve to a real report."""
        atp = AtpResource(client._transport)
        try:
            body = atp.get_url_report(_FAKE_SUBMISSION_ID)
        except NotFoundError:
            pass
        except APIError as e:
            skip_if_unavailable(e, "ATP URL-scan report")
        else:
            assert isinstance(body, dict)

    def test_list_url_artifacts_nonexistent(self, client: NetskopeClient) -> None:
        """A bogus URL-scan submission_id should not resolve to real artifacts."""
        atp = AtpResource(client._transport)
        try:
            body = atp.list_url_artifacts(_FAKE_SUBMISSION_ID)
        except NotFoundError:
            pass
        except APIError as e:
            skip_if_unavailable(e, "ATP URL-scan artifacts")
        else:
            assert isinstance(body, dict)
