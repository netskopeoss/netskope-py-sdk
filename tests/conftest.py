"""Shared fixtures for the Netskope SDK test suite."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import respx
from pydantic import SecretStr

from netskope._config import NetskopeConfig


@pytest.fixture
def config() -> NetskopeConfig:
    """A test configuration with dummy credentials."""
    return NetskopeConfig(
        tenant="test.goskope.com",
        api_token=SecretStr("test-token-abc123"),
        timeout=5.0,
        max_retries=1,
        backoff_factor=0.01,
    )


@pytest.fixture
def base_url(config: NetskopeConfig) -> str:
    return config.base_url


@pytest.fixture(autouse=True)
def no_unmocked_http(request: pytest.FixtureRequest) -> Iterator[None]:
    """Fail any test that lets an HTTP request reach the network.

    Tests marked ``integration`` talk to a live tenant and are exempt.

    This router carries no routes, so respx moves on to whichever router the
    test installs itself; a request that no router mocks fails as
    ``respx.models.AllMockedAssertionError`` instead of leaving the process.
    """
    if request.node.get_closest_marker("integration") is not None:
        yield
        return
    with respx.mock(assert_all_mocked=True, assert_all_called=False):
        yield
