"""Every resource and response accessor documents the subject it speaks for."""

from __future__ import annotations

import functools
import importlib
import inspect
import pkgutil

import pytest

import netskope
from netskope.resources.aicc.agents import (
    AiccAgentResource,
    AsyncAiccAgentResource,
)
from netskope.resources.aicc.ai_models import (
    AiccModelResource,
    AsyncAiccModelResource,
)
from netskope.resources.aicc.analytics import (
    AiccAnalytics,
    AsyncAiccAnalytics,
)
from netskope.resources.aicc.applications import (
    AiccApplicationResource,
    AsyncAiccApplicationResource,
)
from netskope.resources.aicc.data_protection import (
    AiccDataProtection,
    AsyncAiccDataProtection,
)
from netskope.resources.aicc.extensions import (
    AiccExtensionResource,
    AsyncAiccExtensionResource,
)
from netskope.resources.aicc.identities import (
    AiccIdentityResource,
    AsyncAiccIdentityResource,
)
from netskope.resources.aicc.mcp_servers import (
    AiccMcpServerResource,
    AsyncAiccMcpServerResource,
)
from netskope.resources.aicc.namespace import (
    AiccResource,
    AsyncAiccResource,
)
from netskope.resources.dspm.decoder import AsyncDspmResponses, DspmResponses
from netskope.resources.private_apps.resource import (
    AsyncPrivateAppsResource,
    AsyncPrivateAppTagsResource,
    PrivateAppsResource,
    PrivateAppTagsResource,
)
from netskope.resources.rbi.decoder import AsyncRbiResponses, RbiResponses
from netskope.resources.spm.decoder import AsyncSpmResponses, SpmResponses
from netskope.resources.steering.resource import AsyncSteeringResource, SteeringResource
from netskope.resources.url_lists.resource import AsyncUrlListsResource, UrlListsResource

# Each class and a word its documentation must contain, so a docstring cannot
# drift into describing something else.
RESOURCES = [
    (PrivateAppsResource, "private"),
    (AsyncPrivateAppsResource, "private"),
    (PrivateAppTagsResource, "tags"),
    (AsyncPrivateAppTagsResource, "tags"),
    (UrlListsResource, "urllist"),
    (AsyncUrlListsResource, "urllist"),
    (SteeringResource, "steering"),
    (AsyncSteeringResource, "steering"),
    (AiccResource, "aicc"),
    (AsyncAiccResource, "aicc"),
    (AiccApplicationResource, "application"),
    (AsyncAiccApplicationResource, "application"),
    (AiccMcpServerResource, "mcp server"),
    (AsyncAiccMcpServerResource, "mcp server"),
    (AiccIdentityResource, "identity"),
    (AsyncAiccIdentityResource, "identity"),
    (AiccModelResource, "model"),
    (AsyncAiccModelResource, "model"),
    (AiccAgentResource, "agent"),
    (AsyncAiccAgentResource, "agent"),
    (AiccExtensionResource, "extension"),
    (AsyncAiccExtensionResource, "extension"),
    (AiccAnalytics, "analytics"),
    (AsyncAiccAnalytics, "analytics"),
    (AiccDataProtection, "data-protection"),
    (AsyncAiccDataProtection, "data-protection"),
    (RbiResponses, "rbi"),
    (AsyncRbiResponses, "rbi"),
    (SpmResponses, "spm"),
    (AsyncSpmResponses, "spm"),
    (DspmResponses, "dspm"),
    (AsyncDspmResponses, "dspm"),
]


@pytest.mark.parametrize(
    "resource,keyword", RESOURCES, ids=lambda value: getattr(value, "__name__", value)
)
def test_class_documentation_names_its_subject(resource, keyword):
    documentation = inspect.getdoc(resource)
    assert documentation, f"{resource.__name__} has no documentation."
    assert keyword in documentation.lower()


@pytest.mark.parametrize(
    "resource",
    [resource for resource, _ in RESOURCES if hasattr(resource, "with_response")],
    ids=lambda cls: cls.__name__,
)
def test_the_response_accessor_documents_itself(resource):
    documentation = resource.with_response.__doc__
    assert documentation and documentation.strip()


# --- Package-wide docstring coverage (R3S-A8) ---------------------------------
#
# The parametrized checks above cover a hand-picked import list.  The walk below
# covers every public member reachable through a public module, so a new
# accessor cannot ship undocumented.  "Public" means: a module whose dotted path
# has no underscore-prefixed component, and a class, function, method or
# property whose own name does not start with an underscore.  Private modules
# (``netskope.resources.scim.decoder`` and friends) are implementation detail
# and are deliberately out of scope.

# Members that still lack a docstring, grouped by the file that owns them.
# Every entry is a known gap the docstring pass could not close; delete the
# entry (not the assertion) once the owning file is fixed.  ``test_...stale``
# below fails if an entry here has since gained a docstring.
UNDOCUMENTED_ALLOWLIST = frozenset(
    {
        # src/netskope/models/cci.py — validators on request models.
        "netskope.models.cci.CciAppQuery.discovery_flag",
        "netskope.models.cci.CciAppQuery.one_selector",
        "netskope.models.cci.CciAppQuery.query_list_values",
        "netskope.models.cci.CciTagCreate.require_membership",
        "netskope.models.cci.CciTagCreate.tag_name",
        "netskope.models.cci.CciTagPatch.one_membership",
        # src/netskope/models/common.py — pre-existing on origin/main.
        "netskope.models.common.PaginatedResponse.count",
        "netskope.models.common.PaginatedResponse.total",
        # src/netskope/models/incidents.py
        "netskope.models.incidents.IncidentUpdateRequest.validate_target",
        # src/netskope/models/npa_policy.py
        "netskope.models.npa_policy.NpaPolicyGroupPatch.require_changes",
        "netskope.models.npa_policy.NpaPolicyRuleCreate.require_application_selection",
        "netskope.models.npa_policy.NpaPolicyRulePatch.require_changes",
        "netskope.models.npa_policy.NpaPolicyRulePatch.serialize_enabled",
        "netskope.models.npa_policy.NpaPolicyRulePatch.serialize_group_id",
        "netskope.models.npa_policy.NpaUserConfidence.valid_threshold",
        # src/netskope/models/publishers.py
        # src/netskope/models/steering.py
        "netskope.models.steering.IPSecTunnelPatch.integer_bandwidth",
        "netskope.models.steering.IPSecTunnelPatch.require_changes",
        # src/netskope/resources/npa.py — the typed NPA response accessors.
        "netskope.resources.npa.resource.AsyncNpaResponses.search_private_apps",
        "netskope.resources.npa.resource.AsyncNpaResponses.search_publishers",
        "netskope.resources.npa.resource.AsyncNpaResponses.validate_name",
        "netskope.resources.npa.resource.NpaResponses.search_private_apps",
        "netskope.resources.npa.resource.NpaResponses.search_publishers",
        "netskope.resources.npa.resource.NpaResponses.validate_name",
        # ``with_response`` accessors, one per resource class.
        "netskope.resources.atp.resource.AsyncAtpResource.with_response",
        "netskope.resources.atp.resource.AtpResource.with_response",
        "netskope.resources.cci.resource.AsyncCciResource.with_response",
        "netskope.resources.cci.resource.AsyncCciTagsResource.with_response",
        "netskope.resources.cci.resource.CciResource.with_response",
        "netskope.resources.cci.resource.CciTagsResource.with_response",
        "netskope.resources.devices.resource.AsyncDevicesResource.with_response",
        "netskope.resources.devices.resource.DevicesResource.with_response",
        "netskope.resources.dns.resource.AsyncDnsInheritanceGroupsResource.with_response",
        "netskope.resources.dns.resource.AsyncDnsResource.with_response",
        "netskope.resources.dns.resource.DnsInheritanceGroupsResource.with_response",
        "netskope.resources.dns.resource.DnsResource.with_response",
        "netskope.resources.dspm.resource.AsyncDspmResource.with_response",
        "netskope.resources.dspm.resource.DspmResource.with_response",
        "netskope.resources.enrollment.resource.AsyncEnrollmentResource.with_response",
        "netskope.resources.enrollment.resource.EnrollmentResource.with_response",
        "netskope.resources.incidents.resource.AsyncIncidentsResource.with_response",
        "netskope.resources.incidents.resource.IncidentsResource.with_response",
        "netskope.resources.ips.resource.AsyncIpsResource.with_response",
        "netskope.resources.ips.resource.IpsResource.with_response",
        "netskope.resources.notifications.resource.AsyncNotificationsResource.with_response",
        "netskope.resources.notifications.resource.NotificationsResource.with_response",
        "netskope.resources.npa.resource.AsyncNpaResource.with_response",
        "netskope.resources.npa.resource.NpaResource.with_response",
        "netskope.resources.npa_policy.resource.AsyncNpaPolicyGroupsResource.with_response",
        "netskope.resources.npa_policy.resource.AsyncNpaPolicyRulesResource.with_response",
        "netskope.resources.npa_policy.resource.NpaPolicyGroupsResource.with_response",
        "netskope.resources.npa_policy.resource.NpaPolicyRulesResource.with_response",
        "netskope.resources.nsiq.resource.AsyncNsiqResource.with_response",
        "netskope.resources.nsiq.resource.NsiqResource.with_response",
        "netskope.resources.rbi.resource.AsyncRbiResource.with_response",
        "netskope.resources.rbi.resource.RbiResource.with_response",
        "netskope.resources.spm.resource.AsyncSpmResource.with_response",
        "netskope.resources.spm.resource.SpmResource.with_response",
        "netskope.resources.tokens.resource.AsyncTokensResource.with_response",
        "netskope.resources.tokens.resource.TokensResource.with_response",
        "netskope.resources.users.resource.AsyncUserGroupsResource.with_response",
        "netskope.resources.users.resource.AsyncUsersResource.with_response",
        "netskope.resources.users.resource.UserGroupsResource.with_response",
        "netskope.resources.users.resource.UsersResource.with_response",
    }
)


def _underlying(member):
    """Return the function behind a property, cached_property or class/staticmethod."""
    if isinstance(member, functools.cached_property):
        return member.func
    if isinstance(member, property):
        return member.fget
    if isinstance(member, (classmethod, staticmethod)):
        return member.__func__
    return member


# Implementation modules inside an otherwise public package. Before the layered
# layout these were `_atp_response.py`, `_pagination.py` and friends, and the
# leading underscore kept them out of this walk. They are no less internal for
# living at `resources/atp/decoder.py` now, so name them instead.
_INTERNAL_LEAVES = frozenset({"decoder", "paths", "tags_decoder"})
_INTERNAL_PACKAGES = ("netskope.core", "netskope.resources.shared")


def _is_public(name: str) -> bool:
    parts = name.split(".")
    if any(part.startswith("_") for part in parts[1:]):
        return False
    if parts[-1] in _INTERNAL_LEAVES:
        return False
    return not name.startswith(_INTERNAL_PACKAGES)


def _public_modules():
    """Import and yield every module that forms part of the SDK's public surface."""
    names = ["netskope"] + [
        module.name for module in pkgutil.walk_packages(netskope.__path__, "netskope.")
    ]
    for name in names:
        if not _is_public(name):
            continue
        yield name, importlib.import_module(name)


def undocumented_public_members():
    """Return the qualified names of public members with no docstring."""
    missing = []
    for name, module in _public_modules():
        if not inspect.getdoc(module):
            missing.append(name)
        for attribute, value in vars(module).items():
            if attribute.startswith("_"):
                continue
            if inspect.isfunction(value) and value.__module__ == name:
                if not inspect.getdoc(value):
                    missing.append(f"{name}.{attribute}")
                continue
            if not inspect.isclass(value) or value.__module__ != name:
                continue
            if not inspect.getdoc(value):
                missing.append(f"{name}.{attribute}")
            for member_name, raw in vars(value).items():
                if member_name.startswith("_"):
                    continue
                function = _underlying(raw)
                if inspect.isfunction(function) and not inspect.getdoc(function):
                    missing.append(f"{name}.{attribute}.{member_name}")
    return sorted(missing)


def test_every_public_member_is_documented():
    gaps = [name for name in undocumented_public_members() if name not in UNDOCUMENTED_ALLOWLIST]
    assert not gaps, "Public members without a docstring:\n  " + "\n  ".join(gaps)


def test_the_allowlist_has_no_stale_entries():
    documented = UNDOCUMENTED_ALLOWLIST - set(undocumented_public_members())
    assert not documented, "Now documented — drop from UNDOCUMENTED_ALLOWLIST:\n  " + "\n  ".join(
        sorted(documented)
    )
