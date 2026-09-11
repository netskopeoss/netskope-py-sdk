"""Backoff timing and Retry-After handling in the retry policy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
from pydantic import SecretStr

from netskope._config import NetskopeConfig
from netskope._retry import _get_retry_after, _sleep_duration


@pytest.fixture
def retry_config() -> NetskopeConfig:
    return NetskopeConfig(
        tenant="test.goskope.com",
        api_token=SecretStr("test-token"),
        timeout=5.0,
        max_retries=2,
        backoff_factor=0.5,
    )


def _response(headers: dict[str, str]) -> httpx.Response:
    return httpx.Response(429, headers=headers)


class TestRetryAfterHeader:
    def test_delay_seconds_are_used_directly(self) -> None:
        assert _get_retry_after(_response({"retry-after": "12"})) == 12.0

    def test_missing_header_is_unknown(self) -> None:
        assert _get_retry_after(_response({})) is None

    def test_http_date_is_converted_to_seconds(self) -> None:
        deadline = datetime.now(UTC) + timedelta(seconds=90)
        header = format_datetime(deadline, usegmt=True)
        parsed = _get_retry_after(_response({"retry-after": header}))
        assert parsed is not None
        assert 85.0 <= parsed <= 90.0

    def test_http_date_in_the_past_does_not_go_negative(self) -> None:
        past = datetime.now(UTC) - timedelta(seconds=90)
        assert _get_retry_after(_response({"retry-after": format_datetime(past, usegmt=True)})) == 0


class TestSleepDuration:
    def test_zero_retry_after_falls_through_to_jittered_backoff(
        self, retry_config: NetskopeConfig
    ) -> None:
        sleep = _sleep_duration(0, retry_config, 0.0)
        assert 0.5 <= sleep <= 0.55

    def test_absent_retry_after_uses_jittered_backoff(self, retry_config: NetskopeConfig) -> None:
        sleep = _sleep_duration(1, retry_config, None)
        assert 1.0 <= sleep <= 1.1

    def test_positive_retry_after_wins(self, retry_config: NetskopeConfig) -> None:
        assert _sleep_duration(3, retry_config, 7.5) == 7.5

    def test_retry_after_keeps_the_five_minute_cap(self, retry_config: NetskopeConfig) -> None:
        assert _sleep_duration(0, retry_config, 9000.0) == 300.0
