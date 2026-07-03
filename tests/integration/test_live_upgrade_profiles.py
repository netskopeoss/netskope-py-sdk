"""Live integration tests for the publisher upgrade profiles API.

Exercises a full write cycle (create → get → update → delete) on a uniquely
named, DISABLED profile per the safety checklist in
``tests/integration/conftest.py``.  Bulk publisher assignment is never called
against live tenants.  Credentials come from environment variables only.

Run with: pytest tests/integration/test_live_upgrade_profiles.py -m integration -v
"""

from __future__ import annotations

import contextlib

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.models.infrastructure import PublisherUpgradeProfile

from .conftest import skip_if_unavailable, unique_name


def _pick_docker_tag(client: NetskopeClient) -> str:
    """Pick a valid docker tag from the publisher releases endpoint."""
    try:
        releases = client.publishers.list_releases()
    except APIError as exc:
        skip_if_unavailable(exc, "Publisher releases API")
        raise
    for release in releases:
        if release.release_type == "Latest" and release.docker_tag:
            return release.docker_tag
    for release in releases:
        if release.docker_tag:
            return release.docker_tag
    pytest.skip("No publisher releases available to source a docker_tag from")


@pytest.mark.integration
class TestUpgradeProfilesIntegration:
    """Live tests for the publisher upgrade profiles API."""

    def test_list_upgrade_profiles(self, client: NetskopeClient) -> None:
        """List upgrade profiles and get typed responses."""
        try:
            profiles = client.npa.upgrade_profiles.list()
        except APIError as exc:
            skip_if_unavailable(exc, "Upgrade profiles API")
            return
        assert isinstance(profiles, list)
        if profiles:
            assert isinstance(profiles[0], PublisherUpgradeProfile)

    def test_write_cycle(self, client: NetskopeClient) -> None:
        """Create a disabled profile, read it back, rename it, delete it."""
        docker_tag = _pick_docker_tag(client)
        # The API caps profile names at 20 chars; TEST_PREFIX (12) + 8 hex = 20.
        name = unique_name("upgprof").replace("upgprof-", "")

        try:
            created = client.npa.upgrade_profiles.create(
                name,
                docker_tag=docker_tag,
                frequency="0 3 * * *",
                timezone="US/Pacific",
                release_type="Latest",
                enabled=False,
            )
        except APIError as exc:
            skip_if_unavailable(exc, "Upgrade profiles API")
            return

        profile_id = created.external_id if created.external_id is not None else created.id
        assert profile_id is not None
        try:
            assert created.name == name
            assert created.enabled is False

            fetched = client.npa.upgrade_profiles.get(profile_id)
            assert fetched.name == name
            assert fetched.enabled is False
            assert fetched.release_type == "Latest"

            new_name = unique_name("upgprof").replace("upgprof-", "")
            updated = client.npa.upgrade_profiles.update(profile_id, name=new_name)
            assert updated.name == new_name
            assert updated.enabled is False
        finally:
            # Already gone or delete unavailable — never fail teardown.
            with contextlib.suppress(APIError):
                client.npa.upgrade_profiles.delete(profile_id)
