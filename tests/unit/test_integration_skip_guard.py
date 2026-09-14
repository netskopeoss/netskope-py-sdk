"""The live suite's unavailable-feature guard must not hide a wrong path.

``skip_if_unavailable`` decides whether a live run fails or quietly skips, so
its own behaviour is worth pinning here where it costs no credentials.  The
rule it enforces: an entitlement signal skips, a 404 fails unless the call site
says the route is documented as absent.
"""

from __future__ import annotations

import pytest

from netskope.exceptions import APIError
from tests.integration.conftest import skip_if_unavailable


def _api_error(status: int, message: str = "boom") -> APIError:
    return APIError(message, status_code=status, request_path="/api/v2/some/route")


@pytest.mark.parametrize("status", [402, 403, 501])
def test_entitlement_statuses_skip(status: int) -> None:
    """402, 403 and 501 say the tenant lacks the feature, which is not a failure."""
    with pytest.raises(pytest.skip.Exception):
        skip_if_unavailable(_api_error(status), "thing")


@pytest.mark.parametrize("message", ["Invalid quota", "not LICENSED for this"])
def test_licensing_messages_skip(message: str) -> None:
    """The gateway reports some entitlement gaps as a 401 carrying the reason."""
    with pytest.raises(pytest.skip.Exception):
        skip_if_unavailable(_api_error(401, message), "thing")


def test_a_404_fails_and_names_the_path() -> None:
    """This is the case the guard used to swallow.

    A path the SDK spells wrongly answers 404 on every tenant, so skipping left
    the live suite unable to tell a typo from a missing feature.
    """
    with pytest.raises(AssertionError) as caught:
        skip_if_unavailable(_api_error(404), "widgets")
    assert "/api/v2/some/route" in str(caught.value)
    assert "unrouted_ok=True" in str(caught.value)


def test_a_404_skips_only_when_the_call_site_says_the_route_is_absent() -> None:
    """``GET /api/v2/steering/devices`` is the documented case: no spec declares it."""
    with pytest.raises(pytest.skip.Exception):
        skip_if_unavailable(_api_error(404), "devices list", unrouted_ok=True)


def test_a_404_carrying_a_licensing_reason_still_skips() -> None:
    """A 404 that explains itself as an entitlement gap is not a suspect path."""
    with pytest.raises(pytest.skip.Exception):
        skip_if_unavailable(_api_error(404, "feature not licensed"), "thing")


def test_an_unrelated_error_is_re_raised() -> None:
    """Anything that is not an availability signal must still fail the test."""
    error = _api_error(500)
    with pytest.raises(APIError) as caught:
        skip_if_unavailable(error, "thing")
    assert caught.value is error
