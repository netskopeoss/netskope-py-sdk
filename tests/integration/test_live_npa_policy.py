"""Live integration tests for the NPA policy namespace.

Follows the safety checklist in tests/integration/conftest.py: every created
object carries the ``sdk-inttest-`` prefix, every create is paired with a
finally-guaranteed delete that tolerates 404, and unavailable-feature errors
skip rather than fail.
"""

from __future__ import annotations

import contextlib

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError, NotFoundError
from netskope.models.npa_policy import NpaPolicyGroup, NpaPolicyRule
from tests.integration.conftest import TEST_PREFIX, skip_if_unavailable, unique_name


def _delete_group_quietly(client: NetskopeClient, group_id: int) -> None:
    # Teardown-only: the happy path already asserted deletion; deleting an
    # already-deleted group yields odd errors ("not deletable"), so log and
    # move on — the session sweeper is the backstop for real leaks.
    with contextlib.suppress(APIError):
        client.npa.policy.groups.delete(group_id)


def _delete_rule_quietly(client: NetskopeClient, rule_id: int) -> None:
    with contextlib.suppress(APIError):
        client.npa.policy.rules.delete(rule_id)


@pytest.mark.integration
class TestNpaPolicyGroupsIntegration:
    """Live tests for NPA policy groups."""

    def test_list_groups(self, client: NetskopeClient) -> None:
        try:
            groups = client.npa.policy.groups.list(page_size=10).to_list(max_items=10)
        except APIError as e:
            skip_if_unavailable(e, "NPA policy groups")
        assert isinstance(groups, list)
        if groups:
            assert isinstance(groups[0], NpaPolicyGroup)

    def test_group_write_cycle(self, client: NetskopeClient) -> None:
        """Create, read back, rename, and delete a policy group."""
        name = unique_name("npagroup")
        assert name.startswith(TEST_PREFIX)
        try:
            group = client.npa.policy.groups.create(name)
        except APIError as e:
            skip_if_unavailable(e, "NPA policy group creation")
        assert group.group_id is not None
        group_id = int(group.group_id)
        try:
            fetched = client.npa.policy.groups.get(group_id)
            assert fetched.group_name == name

            renamed = client.npa.policy.groups.update(group_id, group_name=f"{name}-renamed")
            assert renamed.group_name in (f"{name}-renamed", None)

            client.npa.policy.groups.delete(group_id)
            with pytest.raises(NotFoundError):
                client.npa.policy.groups.get(group_id)
        finally:
            _delete_group_quietly(client, group_id)


@pytest.mark.integration
class TestNpaPolicyRulesIntegration:
    """Live tests for NPA policy rules."""

    def test_list_rules(self, client: NetskopeClient) -> None:
        try:
            rules = client.npa.policy.rules.list(page_size=10).to_list(max_items=10)
        except APIError as e:
            skip_if_unavailable(e, "NPA policy rules")
        assert isinstance(rules, list)
        if rules:
            assert isinstance(rules[0], NpaPolicyRule)

    def test_rule_write_cycle(self, client: NetskopeClient) -> None:
        """Create a disabled rule in a scratch group, read/update/delete both."""
        group_name = unique_name("npagroup")
        try:
            group = client.npa.policy.groups.create(group_name)
        except APIError as e:
            skip_if_unavailable(e, "NPA policy group creation")
        assert group.group_id is not None
        group_id = int(group.group_id)

        rule_id: int | None = None
        try:
            # The API requires rule_data referencing at least one private app;
            # borrow an existing app from the tenant or skip.
            try:
                apps = client.private_apps.list(page_size=10).to_list(max_items=10)
            except APIError as e:
                skip_if_unavailable(e, "Private apps listing (needed for rule_data)")
            app_name = next((a.app_name for a in apps if a.app_name), None)
            if app_name is None:
                pytest.skip("no private app for rule test")

            rule_name = unique_name("nparule")
            rule_data = {
                "policy_type": "private-app",
                "match_criteria_action": {"action_name": "allow"},
                "privateApps": [app_name],
                "access_method": ["Client"],
            }
            try:
                # Always create the rule DISABLED so it can never take effect.
                rule = client.npa.policy.rules.create(
                    rule_name=rule_name,
                    group_id=str(group_id),
                    enabled=False,
                    rule_data=rule_data,
                )
            except APIError as e:
                skip_if_unavailable(e, "NPA policy rule creation")
            assert rule.rule_id is not None
            rule_id = int(rule.rule_id)

            fetched = client.npa.policy.rules.get(rule_id)
            assert fetched.rule_name == rule_name
            assert fetched.enabled in ("0", None)

            updated = client.npa.policy.rules.update(rule_id, rule_name=f"{rule_name}-renamed")
            assert updated.rule_name in (f"{rule_name}-renamed", None)

            client.npa.policy.rules.delete(rule_id)
            with pytest.raises(NotFoundError):
                client.npa.policy.rules.get(rule_id)
            rule_id = None
        finally:
            if rule_id is not None:
                _delete_rule_quietly(client, rule_id)
            _delete_group_quietly(client, group_id)


@pytest.mark.integration
class TestNpaUtilitiesIntegration:
    """Live tests for NPA name validation and search."""

    def test_validate_name(self, client: NetskopeClient) -> None:
        try:
            body = client.npa.validate_name("policy", unique_name("npacheck"))
        except APIError as e:
            skip_if_unavailable(e, "NPA name validation")
        assert isinstance(body, dict)

    def test_search_publishers(self, client: NetskopeClient) -> None:
        try:
            body = client.npa.search("publishers", f"name sw {TEST_PREFIX}")
        except APIError as e:
            skip_if_unavailable(e, "NPA search")
        assert isinstance(body, dict)
