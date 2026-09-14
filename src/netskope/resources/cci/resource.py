"""CCI resource — Cloud Confidence Index lookups and service tag management.

The Cloud Confidence Index (CCI) API exposes risk ratings, compliance
posture, and security attributes for cloud applications, plus management of
the tags used to categorize apps for policy targeting.

Tags are identified by their NAME string — they have no numeric IDs.  (The
``ids`` parameters below refer to *application* IDs, never tag IDs.)

Legacy methods retain their original dictionary results. The public
``with_response`` accessors expose typed records with future response fields
preserved, plus the completed response when original wire values are needed.

Example::

    # Look up CCI risk data for an app (exact name required)
    info = client.cci.lookup_app("Dropbox")

    # Manage tags
    all_tags = client.cci.tags.list()  # {"data": {"tags": [...], "tags_count": N}}
    client.cci.tags.create("Finance-Approved", apps=["Box", "Dropbox"])
    client.cci.tags.update("Finance-Approved", action="remove", apps=["Dropbox"])
    client.cci.tags.delete("Finance-Approved")  # 202 — async background deletion
"""

from __future__ import annotations

import builtins
import functools
from typing import Any, cast

from pydantic import ValidationError as ModelValidationError

from netskope.core.resource import AsyncResource, SyncResource
from netskope.exceptions import ValidationError
from netskope.models.cci import CciAppQuery
from netskope.resources.cci.decoder import (
    AsyncCciResponses,
    AsyncCciTagResponses,
    CciResponses,
    CciTagResponses,
)
from netskope.resources.cci.paths import (
    _APP_PATH,
    _APPS_SEPARATOR,
    _TAGS_ALL_PATH,
    _TAGS_PATH,
    _TAGS_RULES_PATH,
    _app_query_params,
    _build_tag_list_params,
    _tag_path,
)

_TAGS_ATTRIBUTES_PATH = "/api/v2/services/cci/tags/supportedattributes"

# The tags endpoints take ``apps``/``ids`` query parameters holding a
# semicolon-separated list (e.g. ``Box;Dropbox`` or ``4;7;11``).
# DELETE /tags takes a comma-separated ``tags`` query parameter.
_TAGS_SEPARATOR = ","


# ``GET /cci/app`` enumerates ccl, and types connector and discovered as
# presence flags with no "off" value (services/cci.yaml:2911-2942).
_CCL_VALUES = ("poor", "low", "medium", "high", "excellent")
_PRESENCE_VALUES = ("1", "true")


def _presence_flag(value: bool | str | None, name: str) -> str | None:
    """Render a CCI presence flag, or ``None`` to leave the parameter out.

    The gateway enumerates ``connector`` and ``discovered`` as ``1``/``true``.
    There is no "false" form and no inverse mode, so a falsy value omits the
    parameter rather than asking for the complement.
    """
    if value is None or value is False:
        return None
    if value is True:
        return "true"
    if value in _PRESENCE_VALUES:
        return str(value)
    raise ValidationError(
        f"{name} is a presence flag: pass True (or one of {', '.join(_PRESENCE_VALUES)}) "
        f"to select those applications, or omit it. There is no {name}=false mode."
    )


def _build_lookup_params(
    app_name: str | None,
    category: str | None,
    ccl: str | None,
    tag: str | None,
    connector: bool | str | None,
    discovered: bool | str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any]:
    """Build the ``GET /cci/app`` query through :class:`CciAppQuery`.

    The operation states that "All the query parameters are mutually exclusive
    except limit & offset" (services/cci.yaml:2889), so a second selector is
    rejected here instead of being sent.
    """
    selectors: dict[str, Any] = {}
    if app_name is not None:
        selectors["apps"] = app_name.split(_APPS_SEPARATOR) if isinstance(app_name, str) else []
    if category is not None:
        selectors["category"] = category
    if ccl is not None:
        if ccl not in _CCL_VALUES:
            raise ValidationError(f"ccl must be one of: {', '.join(_CCL_VALUES)}")
        selectors["ccl"] = ccl
    if tag is not None:
        selectors["tag"] = tag
    connector_flag = _presence_flag(connector, "connector")
    if connector_flag is not None:
        selectors["connector"] = connector_flag
    if _presence_flag(discovered, "discovered") is not None:
        # ``discovered`` enumerates 1/true; the model carries the flag itself.
        selectors["discovered"] = True
    if limit is not None:
        selectors["limit"] = limit
    if offset is not None:
        selectors["offset"] = offset
    try:
        query = CciAppQuery.model_validate(selectors)
    except ModelValidationError as exc:
        detail = "; ".join(error["msg"].removeprefix("Value error, ") for error in exc.errors())
        raise ValidationError(f"Invalid /cci/app query: {detail}") from None
    return _app_query_params(query)


def _build_tag_create_payload(
    name: str,
    apps: builtins.list[str] | None,
    ids: builtins.list[int | str] | None,
    rules: builtins.list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if apps and ids:
        raise ValidationError("apps and ids are mutually exclusive.")
    if not apps and not ids and not rules:
        raise ValidationError("Provide apps, ids, or rules when creating a tag.")
    payload: dict[str, Any] = {"tag": name}
    if apps:
        payload["apps"] = builtins.list(apps)
    if ids:
        payload["ids"] = builtins.list(ids)
    if rules:
        payload["rules"] = builtins.list(rules)
    return payload


def _build_tag_update_payload(
    action: str,
    apps: builtins.list[str] | None,
    ids: builtins.list[int | str] | None,
    add_apps: builtins.list[str] | None,
    delete_apps: builtins.list[str] | None,
    rules: builtins.list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if action not in ("append", "remove"):
        raise ValidationError(f"action must be 'append' or 'remove', got {action!r}")
    if apps and ids:
        raise ValidationError("apps and ids are mutually exclusive.")
    if (apps or ids) and (add_apps or delete_apps):
        raise ValidationError("apps/ids are mutually exclusive with add_apps/delete_apps.")
    if not apps and not ids and not add_apps and not delete_apps and not rules:
        raise ValidationError(
            "Provide apps, ids, add_apps, delete_apps, or rules when updating a tag."
        )
    payload: dict[str, Any] = {}
    if apps or ids:
        # ``action`` only applies to apps/ids updates, never add_apps/delete_apps.
        payload["action"] = action
    if apps:
        payload["apps"] = builtins.list(apps)
    if ids:
        payload["ids"] = builtins.list(ids)
    if add_apps:
        payload["add_apps"] = builtins.list(add_apps)
    if delete_apps:
        payload["delete_apps"] = builtins.list(delete_apps)
    if rules:
        payload["rules"] = builtins.list(rules)
    return payload


def _join_tags(tags: tuple[str, ...]) -> str:
    if not tags:
        raise ValidationError("Provide at least one tag name to delete.")
    return _TAGS_SEPARATOR.join(tags)


# Tag names may contain spaces, brackets, and parentheses (per the API's tag
# naming rules), so the shared quote_id helper (which forbids whitespace) is
# too strict here.  Reject only empty/dot-only names and control characters,
# then fully percent-encode for use as a single path segment.


class CciTagsResource(SyncResource):
    """Synchronous interface to CCI tags (``/api/v2/services/cci/tags``).

    CCI tags have no numeric IDs — the identifier is the tag name string.
    """

    @functools.cached_property
    def with_response(self) -> CciTagResponses:

        return CciTagResponses(self._transport)

    def list(
        self,
        *,
        apps: builtins.list[str] | None = None,
        ids: builtins.list[int | str] | None = None,
    ) -> dict[str, Any]:
        """List CCI tags.

        With no arguments, queries ``GET /cci/tags/all`` and returns
        ``{"data": {"tags": [<tag names>], "tags_count": N}, ...}``.

        With *apps* or *ids* (application names/IDs — mutually exclusive),
        queries ``GET /cci/tags`` and returns per-app tag data:
        ``{"data": {"<AppName>": {"app_type", "id", "sanctioned",
        "tags": [...]}}, ...}``.

        Args:
            apps: Application names to fetch tags for (semicolon-joined).
            ids: Application IDs to fetch tags for (semicolon-joined).

        Raises:
            netskope.exceptions.ValidationError: If both *apps* and *ids*
                are provided.
        """
        params = _build_tag_list_params(apps, ids)
        if params is None:
            return self._get(_TAGS_ALL_PATH)
        return self._get(_TAGS_PATH, **params)

    def create(
        self,
        name: str,
        *,
        apps: builtins.list[str] | None = None,
        ids: builtins.list[int | str] | None = None,
        rules: builtins.list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a CCI tag and associate it with apps, app IDs, or rules.

        Sends ``POST /cci/tags`` with body key ``"tag"``.  One of *apps* /
        *ids* / *rules* is required by the API; *apps* and *ids* are
        mutually exclusive.

        Args:
            name: Tag name (sent as ``tag``).
            apps: Application names to associate.
            ids: Application IDs to associate.
            rules: Attribute rules for rule-based tagging (each with
                ``attribute``, ``condition``, ``value``).

        Raises:
            netskope.exceptions.ValidationError: If none of *apps* / *ids* /
                *rules* is provided, or both *apps* and *ids* are.
        """
        return self._post(_TAGS_PATH, json=_build_tag_create_payload(name, apps, ids, rules))

    def update(
        self,
        tag: str,
        *,
        action: str = "append",
        apps: builtins.list[str] | None = None,
        ids: builtins.list[int | str] | None = None,
        add_apps: builtins.list[str] | None = None,
        delete_apps: builtins.list[str] | None = None,
        rules: builtins.list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Update an existing CCI tag's app associations or rules.

        Sends ``PATCH /cci/tags/{tag}`` (the tag name is URL-quoted).
        *apps*/*ids* apply *action* (``"append"`` or ``"remove"``);
        *add_apps*/*delete_apps* add/remove without an action and are
        mutually exclusive with *apps*/*ids*.  *rules* overwrite any
        existing attribute rules.

        Args:
            tag: Existing tag name.
            action: ``"append"`` (default) or ``"remove"`` — only used with
                *apps*/*ids*.
            apps: Application names to append/remove.
            ids: Application IDs to append/remove.
            add_apps: Application names to add to the tag.
            delete_apps: Application names to delete from the tag.
            rules: Attribute rules (overwrite existing rules).

        Raises:
            netskope.exceptions.ValidationError: If no update fields are
                provided, or a mutually exclusive combination is used.
        """
        payload = _build_tag_update_payload(action, apps, ids, add_apps, delete_apps, rules)
        return self._patch(_tag_path(tag), json=payload)

    def delete(self, *tags: str) -> dict[str, Any]:
        """Delete one or more CCI tags by name.

        Sends ``DELETE /cci/tags?tags=a,b`` (comma-joined).  The API returns
        HTTP 202 — deletion happens asynchronously in the background, so the
        tag may remain visible briefly after this call returns.

        Args:
            *tags: One or more tag names (at least one required).

        Raises:
            netskope.exceptions.ValidationError: If no tag names are given.
        """
        joined = _join_tags(tags)
        resp = self._transport.request("DELETE", _TAGS_PATH, params={"tags": joined})
        try:
            return cast(dict[str, Any], resp.json())
        except (ValueError, UnicodeDecodeError):
            return {}

    def list_rules(
        self,
        *,
        tag: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Get attribute-rule data for tags (``GET /cci/tags/rules``).

        Args:
            tag: Restrict to a single tag name.
            limit: Max records to return (API default 100).
            offset: Records to skip.
        """
        params: dict[str, Any] = {}
        if tag is not None:
            params["tag"] = tag
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self._get(_TAGS_RULES_PATH, **params)

    def supported_attributes(self) -> dict[str, Any]:
        """Get the CCI attributes usable in rule-based tags.

        Sends ``GET /cci/tags/supportedattributes``.
        """
        return self._get(_TAGS_ATTRIBUTES_PATH)


class CciResource(SyncResource):
    """Synchronous interface to the Cloud Confidence Index (CCI) API."""

    @functools.cached_property
    def with_response(self) -> CciResponses:

        return CciResponses(self._transport)

    def lookup_app(
        self,
        app_name: str | None = None,
        *,
        category: str | None = None,
        ccl: str | None = None,
        tag: str | None = None,
        connector: bool | str | None = None,
        discovered: bool | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Look up CCI risk data by application name or by one other selector.

        ``GET /cci/app`` states that "All the query parameters are mutually
        exclusive except limit & offset" (services/cci.yaml:2889), so exactly
        one of *app_name*, *category*, *ccl*, *tag*, *connector* and
        *discovered* may be given; *limit* and *offset* may accompany it.
        Application names are matched exactly (e.g. ``"Dropbox"``, ``"Box"``)
        and several may be passed as one ``;``-separated string; there is no
        partial or wildcard search.

        Args:
            app_name: Exact application name, or several joined by ``;``.
            category: Filter by application category (e.g. ``"Cloud Storage"``).
            ccl: Filter by Cloud Confidence Level — ``"poor"``, ``"low"``,
                ``"medium"``, ``"high"`` or ``"excellent"``.
            tag: Filter by tag name.
            connector: Presence flag: ``True`` keeps only applications with a
                dedicated connector.  Omit it (or pass ``False``) for no
                filtering — the parameter has no "false" form.
            discovered: Presence flag: ``True`` keeps only discovered (shadow
                IT) applications.  Omit it (or pass ``False``) for no
                filtering; there is no sanctioned-only mode.
            limit: Maximum number of results to return.
            offset: Number of results to skip for pagination.

        Raises:
            netskope.exceptions.ValidationError: If no selector or more than
                one selector is given, *ccl* is outside the enumeration, or a
                presence flag carries an unsupported value.
        """
        params = _build_lookup_params(
            app_name, category, ccl, tag, connector, discovered, limit, offset
        )
        return self._get(_APP_PATH, **params)

    @functools.cached_property
    def tags(self) -> CciTagsResource:
        """Access the CCI tags API."""
        return CciTagsResource(self._transport)


class AsyncCciTagsResource(AsyncResource):
    """Asynchronous interface to CCI tags.

    CCI tags have no numeric IDs — the identifier is the tag name string.
    """

    @functools.cached_property
    def with_response(self) -> AsyncCciTagResponses:

        return AsyncCciTagResponses(self._transport)

    async def list(
        self,
        *,
        apps: builtins.list[str] | None = None,
        ids: builtins.list[int | str] | None = None,
    ) -> dict[str, Any]:
        """List CCI tags.  See :meth:`CciTagsResource.list`."""
        params = _build_tag_list_params(apps, ids)
        if params is None:
            return await self._get(_TAGS_ALL_PATH)
        return await self._get(_TAGS_PATH, **params)

    async def create(
        self,
        name: str,
        *,
        apps: builtins.list[str] | None = None,
        ids: builtins.list[int | str] | None = None,
        rules: builtins.list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a CCI tag.  See :meth:`CciTagsResource.create`."""
        return await self._post(_TAGS_PATH, json=_build_tag_create_payload(name, apps, ids, rules))

    async def update(
        self,
        tag: str,
        *,
        action: str = "append",
        apps: builtins.list[str] | None = None,
        ids: builtins.list[int | str] | None = None,
        add_apps: builtins.list[str] | None = None,
        delete_apps: builtins.list[str] | None = None,
        rules: builtins.list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Update an existing CCI tag.  See :meth:`CciTagsResource.update`."""
        payload = _build_tag_update_payload(action, apps, ids, add_apps, delete_apps, rules)
        return await self._patch(_tag_path(tag), json=payload)

    async def delete(self, *tags: str) -> dict[str, Any]:
        """Delete one or more CCI tags by name (HTTP 202 — async deletion).

        See :meth:`CciTagsResource.delete`.
        """
        joined = _join_tags(tags)
        resp = await self._transport.request("DELETE", _TAGS_PATH, params={"tags": joined})
        try:
            return cast(dict[str, Any], resp.json())
        except (ValueError, UnicodeDecodeError):
            return {}

    async def list_rules(
        self,
        *,
        tag: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Get attribute-rule data for tags.  See :meth:`CciTagsResource.list_rules`."""
        params: dict[str, Any] = {}
        if tag is not None:
            params["tag"] = tag
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return await self._get(_TAGS_RULES_PATH, **params)

    async def supported_attributes(self) -> dict[str, Any]:
        """Get the CCI attributes usable in rule-based tags."""
        return await self._get(_TAGS_ATTRIBUTES_PATH)


class AsyncCciResource(AsyncResource):
    """Asynchronous interface to the Cloud Confidence Index (CCI) API."""

    @functools.cached_property
    def with_response(self) -> AsyncCciResponses:

        return AsyncCciResponses(self._transport)

    async def lookup_app(
        self,
        app_name: str | None = None,
        *,
        category: str | None = None,
        ccl: str | None = None,
        tag: str | None = None,
        connector: bool | str | None = None,
        discovered: bool | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Look up CCI risk data by application name or by one other selector.

        Exactly one selector, optionally with paging.  See
        :meth:`CciResource.lookup_app`.
        """
        params = _build_lookup_params(
            app_name, category, ccl, tag, connector, discovered, limit, offset
        )
        return await self._get(_APP_PATH, **params)

    @functools.cached_property
    def tags(self) -> AsyncCciTagsResource:
        """Access the CCI tags API."""
        return AsyncCciTagsResource(self._transport)
