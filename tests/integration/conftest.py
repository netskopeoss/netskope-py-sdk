"""Shared plumbing for live integration tests.

Safety checklist — every integration test MUST follow these rules:

1. Credentials come from environment variables only; never written to files.
2. Every created object is named ``sdk-inttest-<kind>-<uuid8>`` (use
   :func:`unique_name`).
3. Never mutate or delete objects lacking the ``sdk-inttest-`` prefix.
4. Every create has a finally-guaranteed delete that tolerates 404.
5. The leftover sweeper never raises — it must not fail the session.
6. 402/403/404/501 or licensing errors cause a skip, not a failure (use
   :func:`skip_if_unavailable`).
7. No deploy/activation endpoints, and no tenant-wide settings mutations.
8. Tests run sequentially with small page sizes.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterator
from typing import Any
from uuid import uuid4

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError

logger = logging.getLogger("netskope.inttest")

TEST_PREFIX = "sdk-inttest-"


def unique_name(kind: str) -> str:
    """Return a unique, prefix-tagged name for a test-created object."""
    return f"sdk-inttest-{kind}-{uuid4().hex[:8]}"


def skip_if_unavailable(exc: Exception, what: str) -> None:
    """Skip the current test when *exc* means the feature is unavailable.

    402/403/404/501 responses and licensing errors indicate the tenant does
    not support the API under test — that is a skip, not a failure.  Any
    other exception is re-raised.
    """
    status = getattr(exc, "status_code", None) if isinstance(exc, APIError) else None
    message = str(exc).lower()
    # "invalid quota" is a 401 the gateway returns when a service is not
    # licensed/entitled for the tenant — a skip, not an auth failure.
    unavailable_message = "licens" in message or "quota" in message
    if status in (402, 403, 404, 501) or unavailable_message:
        pytest.skip(f"{what} unavailable on this tenant: {exc}")
    raise exc


def _tenant_matrix() -> list[tuple[str, str]]:
    """Collect (tenant, token) pairs from the environment."""
    pairs: list[tuple[str, str]] = []
    for tenant_var, token_var in (
        ("NETSKOPE_TENANT", "NETSKOPE_API_TOKEN"),
        ("NETSKOPE_TENANT_2", "NETSKOPE_API_TOKEN_2"),
    ):
        tenant = os.environ.get(tenant_var, "")
        token = os.environ.get(token_var, "")
        if tenant and token:
            pairs.append((tenant, token))
    return pairs


_MATRIX = _tenant_matrix()


@pytest.fixture(
    scope="session",
    params=_MATRIX or [None],
    ids=[tenant for tenant, _ in _MATRIX] or ["no-credentials"],
)
def client(request: pytest.FixtureRequest) -> Iterator[NetskopeClient]:
    """A real client per configured tenant; skips when no credentials are set."""
    if request.param is None:
        pytest.skip("NETSKOPE_TENANT and NETSKOPE_API_TOKEN env vars required")
    tenant, token = request.param
    c = NetskopeClient(
        tenant=tenant,
        api_token=token,
        timeout=60.0,
        max_retries=5,
        backoff_factor=1.0,
    )
    yield c
    c.close()


@pytest.fixture(scope="session", autouse=True)
def _sweep_leftovers(client: NetskopeClient) -> None:
    """Best-effort deletion of leftover ``sdk-inttest-*`` objects at session start.

    Runs once per tenant in the matrix.  Each sweep step is individually
    guarded and probes the client with ``hasattr`` so steps no-op until the
    corresponding namespace exists in the SDK.  The sweeper must never fail
    the session.
    """

    def _sweep_url_lists() -> None:
        if not hasattr(client, "url_lists"):
            return
        for url_list in client.url_lists.list(page_size=50).to_list(max_items=500):
            if (url_list.name or "").startswith(TEST_PREFIX) and url_list.id is not None:
                client.url_lists.delete(url_list.id)
                logger.info("Swept leftover url_list %s (%s)", url_list.id, url_list.name)

    def _sweep_scim_users() -> None:
        scim = getattr(client, "scim", None)
        if scim is None or not hasattr(scim, "users"):
            return
        users = scim.users.list(filter_expr=f'userName sw "{TEST_PREFIX}"', page_size=50).to_list(
            max_items=500
        )
        for user in users:
            if (user.user_name or "").startswith(TEST_PREFIX) and user.id:
                scim.users.delete(user.id)
                logger.info("Swept leftover SCIM user %s (%s)", user.id, user.user_name)

    def _sweep_scim_groups() -> None:
        scim = getattr(client, "scim", None)
        if scim is None or not hasattr(scim, "groups"):
            return
        for group in scim.groups.list(page_size=50).to_list(max_items=500):
            if (group.display_name or "").startswith(TEST_PREFIX) and group.id:
                scim.groups.delete(group.id)
                logger.info("Swept leftover SCIM group %s (%s)", group.id, group.display_name)

    def _sweep_npa_rules() -> None:
        npa = getattr(client, "npa", None)
        if npa is None:
            return
        for rule in npa.policy.rules.list(page_size=50).to_list(max_items=500):
            name = rule.rule_name or ""
            if name.startswith(TEST_PREFIX) and rule.rule_id is not None:
                npa.policy.rules.delete(int(rule.rule_id))
                logger.info("Swept leftover NPA rule %s (%s)", rule.rule_id, name)

    def _sweep_npa_groups() -> None:
        npa = getattr(client, "npa", None)
        if npa is None:
            return
        for group in npa.policy.groups.list(page_size=50).to_list(max_items=500):
            name = group.group_name or ""
            if name.startswith(TEST_PREFIX) and group.group_id is not None:
                npa.policy.groups.delete(int(group.group_id))
                logger.info("Swept leftover NPA policy group %s (%s)", group.group_id, name)

    def _sweep_private_app_tags() -> None:
        private_apps = getattr(client, "private_apps", None)
        if private_apps is None or not hasattr(private_apps, "tags"):
            return
        for tag in private_apps.tags.list(page_size=50).to_list(max_items=500):
            if (tag.tag_name or "").startswith(TEST_PREFIX) and tag.tag_id is not None:
                private_apps.tags.delete(tag.tag_id)
                logger.info("Swept leftover private-app tag %s (%s)", tag.tag_id, tag.tag_name)

    def _sweep_dns_profiles() -> None:
        dns = getattr(client, "dns", None)
        if dns is None:
            return
        for profile in dns.list(page_size=50).to_list(max_items=500):
            if (profile.name or "").startswith(TEST_PREFIX) and profile.id is not None:
                dns.delete(profile.id)
                logger.info("Swept leftover DNS profile %s (%s)", profile.id, profile.name)

    def _sweep_dns_inheritance_groups() -> None:
        dns = getattr(client, "dns", None)
        if dns is None:
            return
        for group in dns.inheritance_groups.list(page_size=50).to_list(max_items=500):
            if (group.name or "").startswith(TEST_PREFIX) and group.id is not None:
                dns.inheritance_groups.delete(group.id)
                logger.info("Swept leftover DNS inheritance group %s (%s)", group.id, group.name)

    def _sweep_device_tags() -> None:
        devices = getattr(client, "devices", None)
        if devices is None:
            return
        for tag in devices.tags.list(limit=100):
            if (tag.name or "").startswith(TEST_PREFIX) and tag.id is not None:
                devices.tags.delete(int(tag.id))
                logger.info("Swept leftover device tag %s (%s)", tag.id, tag.name)

    def _sweep_enrollment() -> None:
        enrollment = getattr(client, "enrollment", None)
        if enrollment is None:
            return
        for token_set in enrollment.list_token_sets():
            name = getattr(token_set, "name", None) or ""
            if name.startswith(TEST_PREFIX) and token_set.id is not None:
                enrollment.delete_token_set(int(token_set.id))
                logger.info("Swept leftover enrollment token set %s (%s)", token_set.id, name)

    def _sweep_upgrade_profiles() -> None:
        npa = getattr(client, "npa", None)
        if npa is None or not hasattr(npa, "upgrade_profiles"):
            return
        for profile in npa.upgrade_profiles.list():
            name = getattr(profile, "name", None) or ""
            profile_id = getattr(profile, "external_id", None) or getattr(profile, "id", None)
            if name.startswith(TEST_PREFIX) and profile_id is not None:
                npa.upgrade_profiles.delete(int(profile_id))
                logger.info("Swept leftover upgrade profile %s (%s)", profile_id, name)

    def _sweep_rbac_roles() -> None:
        rbac = getattr(client, "rbac", None)
        if rbac is None:
            return
        for role in rbac.roles.list():
            if (role.name or "").startswith(TEST_PREFIX) and role.id is not None:
                rbac.roles.delete(int(role.id))
                logger.info("Swept leftover RBAC role %s (%s)", role.id, role.name)

    def _sweep_tokens() -> None:
        tokens = getattr(client, "tokens", None)
        if tokens is None:
            return
        for token in tokens.list():
            if (token.name or "").startswith(TEST_PREFIX) and token.id is not None:
                tokens.delete(token.id)
                logger.info("Swept leftover API token %s (%s)", token.id, token.name)

    def _sweep_notification_templates() -> None:
        notifications = getattr(client, "notifications", None)
        if notifications is None:
            return
        for tmpl in notifications.list_templates(limit=100):
            if (tmpl.name or "").startswith(TEST_PREFIX) and tmpl.id is not None:
                notifications.delete_template(tmpl.id)
                logger.info("Swept leftover notification template %s (%s)", tmpl.id, tmpl.name)

    def _sweep_cci_tags() -> None:
        cci = getattr(client, "cci", None)
        if cci is None:
            return
        # GET /cci/tags/all returns {"data": {"tags": [<name strings>], ...}}.
        body = cci.tags.list()
        data = body.get("data") if isinstance(body, dict) else None
        names = data.get("tags") if isinstance(data, dict) else None
        for name in names if isinstance(names, list) else []:
            if isinstance(name, str) and name.startswith(TEST_PREFIX):
                cci.tags.delete(name)  # 202 — async background deletion
                logger.info("Swept leftover CCI tag %s", name)

    steps: list[tuple[str, Callable[[], Any]]] = [
        ("url_lists", _sweep_url_lists),
        ("scim users", _sweep_scim_users),
        ("scim groups", _sweep_scim_groups),
        ("npa policy rules", _sweep_npa_rules),
        ("npa policy groups", _sweep_npa_groups),
        ("private-app tags", _sweep_private_app_tags),
        ("dns profiles", _sweep_dns_profiles),
        ("dns inheritance groups", _sweep_dns_inheritance_groups),
        ("cci tags", _sweep_cci_tags),
        ("device tags", _sweep_device_tags),
        ("enrollment tokens", _sweep_enrollment),
        ("upgrade profiles", _sweep_upgrade_profiles),
        ("rbac roles", _sweep_rbac_roles),
        ("api tokens", _sweep_tokens),
        ("notification templates", _sweep_notification_templates),
        # Placeholders — add sweep steps as the namespaces land in the SDK:
        # ("dem probes", _sweep_dem_probes),
    ]
    for description, step in steps:
        try:
            step()
        except Exception as exc:
            logger.warning("Sweep step %r skipped: %s", description, exc)
