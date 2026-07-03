"""Live integration tests for the Private Apps API.

Read-only smokes plus a tag write cycle against an existing private app.
Credentials come from environment variables only (see conftest.py).  Apps
themselves are never mutated; only ``sdk-inttest-``-prefixed tags are
created, renamed, and deleted.

Run with: pytest tests/integration/test_live_private_apps.py -m integration -v
"""

from __future__ import annotations

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.models.private_apps import PrivateApp

from .conftest import TEST_PREFIX, skip_if_unavailable, unique_name


@pytest.mark.integration
class TestPrivateAppsIntegration:
    """Live read-only smokes for the Private Apps API."""

    def test_list_apps(self, client: NetskopeClient) -> None:
        """Verify we can list private apps and get typed responses."""
        try:
            apps = client.private_apps.list(page_size=10).to_list(max_items=10)
        except APIError as exc:
            skip_if_unavailable(exc, "Private Apps API")
        assert isinstance(apps, list)
        assert len(apps) <= 10
        if apps:
            assert isinstance(apps[0], PrivateApp)

    def test_get_discovery_settings(self, client: NetskopeClient) -> None:
        """Verify the discovery-settings read endpoint responds."""
        try:
            body = client.private_apps.get_discovery_settings()
        except APIError as exc:
            skip_if_unavailable(exc, "Private App discovery settings")
        assert isinstance(body, dict)

    def test_list_tags(self, client: NetskopeClient) -> None:
        """Verify we can list private-app tags."""
        try:
            tags = client.private_apps.tags.list(page_size=10).to_list(max_items=10)
        except APIError as exc:
            skip_if_unavailable(exc, "Private App tags API")
        assert isinstance(tags, list)


@pytest.mark.integration
class TestPrivateAppTagsWriteCycle:
    """Create → read → update → delete cycle for a prefix-tagged tag.

    Requires an existing private app to attach the tag to; the app itself
    is never modified beyond the tag attachment, and the tag is deleted in
    a ``finally`` block.
    """

    def test_tag_write_cycle(self, client: NetskopeClient) -> None:
        try:
            app = client.private_apps.list(page_size=10).first()
        except APIError as exc:
            skip_if_unavailable(exc, "Private Apps API")
        if app is None or app.app_id is None:
            pytest.skip("no private app available")

        tag_name = unique_name("patag")
        renamed = unique_name("patag")
        tag_id: int | None = None
        try:
            try:
                created = client.private_apps.tags.create(app.app_id, [tag_name])
            except APIError as exc:
                skip_if_unavailable(exc, "Private App tags API")

            # Resolve the tag id from the create response or via readback.
            for tag in created:
                if tag.tag_name == tag_name and tag.tag_id is not None:
                    tag_id = tag.tag_id
            if tag_id is None:
                for tag in client.private_apps.tags.list(page_size=100).to_list(max_items=1000):
                    if tag.tag_name == tag_name and tag.tag_id is not None:
                        tag_id = tag.tag_id
                        break
            assert tag_id is not None, "created tag not found on readback"

            updated = client.private_apps.tags.update(tag_id, renamed)
            assert updated.tag_name in (renamed, None)

            # Confirm the rename is visible via list readback.
            names = {
                tag.tag_name
                for tag in client.private_apps.tags.list(page_size=100).to_list(max_items=1000)
            }
            assert renamed in names
        finally:
            if tag_id is not None:
                # Safety: only delete objects carrying the inttest prefix.
                assert tag_name.startswith(TEST_PREFIX) and renamed.startswith(TEST_PREFIX)
                try:
                    client.private_apps.tags.delete(tag_id)
                except APIError as exc:
                    if getattr(exc, "status_code", None) != 404:
                        raise
