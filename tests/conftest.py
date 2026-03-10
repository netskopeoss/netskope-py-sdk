"""Shared fixtures for the Netskope SDK test suite."""

from __future__ import annotations

import pytest

from netskope._config import NetskopeConfig


@pytest.fixture
def config() -> NetskopeConfig:
    """A test configuration with dummy credentials."""
    return NetskopeConfig(
        tenant="test.goskope.com",
        api_token="test-token-abc123",
        timeout=5.0,
        max_retries=1,
        backoff_factor=0.01,
    )


@pytest.fixture
def base_url(config: NetskopeConfig) -> str:
    return config.base_url
