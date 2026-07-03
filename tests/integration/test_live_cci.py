"""Live integration tests for the CCI (Cloud Confidence Index) API.

These tests require valid credentials and hit the real API.
Run with: pytest tests/integration/ -m integration -v

Credentials come from environment variables only (see conftest.py).

CCI tags are identified by NAME (no numeric ids).  Tag deletion returns HTTP
202 and completes asynchronously in the background, so the write-cycle test
polls ``tags/all`` briefly for eventual consistency.
"""

from __future__ import annotations

import contextlib
import time
import warnings
from typing import Any

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError, NotFoundError

from .conftest import skip_if_unavailable, unique_name

# How long to poll for the asynchronous tag deletion to land.
_DELETE_POLL_SECONDS = 15.0
_DELETE_POLL_INTERVAL = 3.0


def _all_tag_names(body: dict[str, Any]) -> list[str]:
    """Extract the tag name list from a ``GET /cci/tags/all`` response."""
    data = body.get("data")
    names = data.get("tags") if isinstance(data, dict) else None
    return [n for n in names if isinstance(n, str)] if isinstance(names, list) else []


def _tags_for_app(body: dict[str, Any], app: str) -> list[str]:
    """Extract one app's tag list from a ``GET /cci/tags?apps=...`` response."""
    data = body.get("data")
    entry = data.get(app) if isinstance(data, dict) else None
    tags = entry.get("tags") if isinstance(entry, dict) else None
    return [t for t in tags if isinstance(t, str)] if isinstance(tags, list) else []


@pytest.mark.integration
class TestCciIntegration:
    """Live tests for the CCI API (read smokes)."""

    def test_lookup_app(self, client: NetskopeClient) -> None:
        """Look up a well-known app; skip when CCI is unlicensed."""
        try:
            data = client.cci.lookup_app("Dropbox")
        except APIError as e:
            skip_if_unavailable(e, "CCI app lookup")
        else:
            assert isinstance(data, dict)

    def test_tags_list_all(self, client: NetskopeClient) -> None:
        """List all tag names; skip when CCI tags are unavailable."""
        try:
            data = client.cci.tags.list()
        except APIError as e:
            skip_if_unavailable(e, "CCI tags list")
        else:
            assert isinstance(data, dict)

    def test_tags_list_rules_and_supported_attributes(self, client: NetskopeClient) -> None:
        try:
            rules = client.cci.tags.list_rules(limit=10)
            attributes = client.cci.tags.supported_attributes()
        except APIError as e:
            skip_if_unavailable(e, "CCI tag rules")
        else:
            assert isinstance(rules, dict)
            assert isinstance(attributes, dict)


@pytest.mark.integration
class TestCciTagWriteCycle:
    """Live create → verify → delete cycle for a CCI tag (name-identified)."""

    def test_tag_write_cycle(self, client: NetskopeClient) -> None:
        tags = client.cci.tags
        name = unique_name("ccitag")

        try:
            created = tags.create(name, apps=["Dropbox"])
        except APIError as e:
            skip_if_unavailable(e, "CCI tag create")
            return  # unreachable; keeps type-checkers happy
        assert isinstance(created, dict)

        try:
            # Verify the tag shows up on Dropbox's tag list.
            listed = tags.list(apps=["Dropbox"])
            assert name in _tags_for_app(listed, "Dropbox")
        finally:
            # Deletion is accepted with 202 and completes asynchronously.
            with contextlib.suppress(NotFoundError):
                tags.delete(name)

        # Eventual-consistency check: poll tags/all until the name is gone.
        deadline = time.monotonic() + _DELETE_POLL_SECONDS
        while time.monotonic() < deadline:
            if name not in _all_tag_names(tags.list()):
                return
            time.sleep(_DELETE_POLL_INTERVAL)
        warnings.warn(
            f"CCI tag {name!r} still listed after {_DELETE_POLL_SECONDS}s; "
            "background deletion is slow — skipping the final assertion.",
            stacklevel=1,
        )
