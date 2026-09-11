"""Every resource and response accessor documents the subject it speaks for."""

from __future__ import annotations

import functools
import importlib
import inspect
import pkgutil

import pytest

import netskope
from netskope.resources._dspm_response import AsyncDspmResponses, DspmResponses
from netskope.resources._rbi_response import AsyncRbiResponses, RbiResponses
from netskope.resources._spm_response import AsyncSpmResponses, SpmResponses
from netskope.resources.aicc import (
    AiccAgentResource,
    AiccAnalytics,
    AiccApplicationResource,
    AiccDataProtection,
    AiccExtensionResource,
    AiccIdentityResource,
    AiccMcpServerResource,
    AiccModelResource,
    AiccResource,
    AsyncAiccAgentResource,
    AsyncAiccAnalytics,
    AsyncAiccApplicationResource,
    AsyncAiccDataProtection,
    AsyncAiccExtensionResource,
    AsyncAiccIdentityResource,
    AsyncAiccMcpServerResource,
    AsyncAiccModelResource,
    AsyncAiccResource,
)
from netskope.resources.private_apps import (
    AsyncPrivateAppsResource,
    AsyncPrivateAppTagsResource,
    PrivateAppsResource,
    PrivateAppTagsResource,
)
from netskope.resources.steering import AsyncSteeringResource, SteeringResource
from netskope.resources.url_lists import AsyncUrlListsResource, UrlListsResource

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
# (``netskope.resources._scim_response`` and friends) are implementation detail
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
        "netskope.models.publishers.PublisherAlertsConfigurationPatch.require_changes",
        # src/netskope/models/steering.py
        "netskope.models.steering.IPSecTunnelPatch.integer_bandwidth",
        "netskope.models.steering.IPSecTunnelPatch.require_changes",
        # src/netskope/resources/npa.py — the typed NPA response accessors.
        "netskope.resources.npa.AsyncNpaResponses.search_private_apps",
        "netskope.resources.npa.AsyncNpaResponses.search_publishers",
        "netskope.resources.npa.AsyncNpaResponses.validate_name",
        "netskope.resources.npa.NpaResponses.search_private_apps",
        "netskope.resources.npa.NpaResponses.search_publishers",
        "netskope.resources.npa.NpaResponses.validate_name",
        # ``with_response`` accessors, one per resource class.
        "netskope.resources.atp.AsyncAtpResource.with_response",
        "netskope.resources.atp.AtpResource.with_response",
        "netskope.resources.cci.AsyncCciResource.with_response",
        "netskope.resources.cci.AsyncCciTagsResource.with_response",
        "netskope.resources.cci.CciResource.with_response",
        "netskope.resources.cci.CciTagsResource.with_response",
        "netskope.resources.devices.AsyncDevicesResource.with_response",
        "netskope.resources.devices.DevicesResource.with_response",
        "netskope.resources.dns.AsyncDnsInheritanceGroupsResource.with_response",
        "netskope.resources.dns.AsyncDnsResource.with_response",
        "netskope.resources.dns.DnsInheritanceGroupsResource.with_response",
        "netskope.resources.dns.DnsResource.with_response",
        "netskope.resources.dspm.AsyncDspmResource.with_response",
        "netskope.resources.dspm.DspmResource.with_response",
        "netskope.resources.enrollment.AsyncEnrollmentResource.with_response",
        "netskope.resources.enrollment.EnrollmentResource.with_response",
        "netskope.resources.incidents.AsyncIncidentsResource.with_response",
        "netskope.resources.incidents.IncidentsResource.with_response",
        "netskope.resources.ips.AsyncIpsResource.with_response",
        "netskope.resources.ips.IpsResource.with_response",
        "netskope.resources.notifications.AsyncNotificationsResource.with_response",
        "netskope.resources.notifications.NotificationsResource.with_response",
        "netskope.resources.npa.AsyncNpaResource.with_response",
        "netskope.resources.npa.NpaResource.with_response",
        "netskope.resources.npa_policy.AsyncNpaPolicyGroupsResource.with_response",
        "netskope.resources.npa_policy.AsyncNpaPolicyRulesResource.with_response",
        "netskope.resources.npa_policy.NpaPolicyGroupsResource.with_response",
        "netskope.resources.npa_policy.NpaPolicyRulesResource.with_response",
        "netskope.resources.nsiq.AsyncNsiqResource.with_response",
        "netskope.resources.nsiq.NsiqResource.with_response",
        "netskope.resources.rbi.AsyncRbiResource.with_response",
        "netskope.resources.rbi.RbiResource.with_response",
        "netskope.resources.spm.AsyncSpmResource.with_response",
        "netskope.resources.spm.SpmResource.with_response",
        "netskope.resources.tokens.AsyncTokensResource.with_response",
        "netskope.resources.tokens.TokensResource.with_response",
        "netskope.resources.users.AsyncUserGroupsResource.with_response",
        "netskope.resources.users.AsyncUsersResource.with_response",
        "netskope.resources.users.UserGroupsResource.with_response",
        "netskope.resources.users.UsersResource.with_response",
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


def _public_modules():
    """Import and yield every module whose dotted path has no private component."""
    names = ["netskope"] + [
        module.name for module in pkgutil.walk_packages(netskope.__path__, "netskope.")
    ]
    for name in names:
        if any(part.startswith("_") for part in name.split(".")[1:]):
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
