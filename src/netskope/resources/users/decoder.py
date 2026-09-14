"""Typed, bounded response access for User Management queries."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic import ValidationError as ModelValidationError

from netskope.core.pagination import Page, build_page, coerce_total
from netskope.core.resource import AsyncResource, SyncResource
from netskope.core.response_list import extract_response_list
from netskope.exceptions import ValidationError
from netskope.models.users import UmGroup, UmUser, UserQuery
from netskope.response import ApiResponse

T = TypeVar("T", bound=BaseModel)

# ``userName`` is a property of EnterpriseAccount, not EnterpriseUser
# (usermanager.yaml:1034-1042), so a username filter must be account-scoped —
# as the spec's own getusers example is (:358).
USERNAME_FILTER_FIELD = "accounts.userName"


def _body(query: UserQuery) -> dict[str, Any]:
    try:
        query = UserQuery.model_validate(query.model_dump())
    except ModelValidationError:
        raise ValidationError(
            "Invalid user query: limit must be 0..1000, offset nonnegative, and filter an object."
        ) from None
    payload: dict[str, Any] = {"paging": {"limit": query.limit, "offset": query.offset}}
    if query.filter is not None:
        payload["filter"] = query.filter
    return {"query": payload}


def _page(body: Any, model: type[T], query: UserQuery, key: str) -> Page[T]:
    """Decode one User Management page using the operation's own record key."""
    items = [model.model_validate(row) for row in extract_response_list(body, key)]
    metadata = dict(body) if isinstance(body, dict) else {}
    for records_key in ("data", "result", key):
        metadata.pop(records_key, None)
    raw_counts = metadata.get("counts")
    # The counts block carries this page's own paging echo when present.
    counts: dict[str, Any] = raw_counts if isinstance(raw_counts, dict) else metadata
    return build_page(
        items,
        offset=query.offset,
        limit=query.limit,
        total=coerce_total(counts.get("totalResults", counts.get("total"))),
        metadata=metadata,
        echoed_offset=coerce_total(counts.get("offset")),
    )


class UserGroupsResponses(SyncResource):
    def list_page(self, query: UserQuery | None = None) -> ApiResponse[Page[UmGroup]]:
        query = query or UserQuery()
        response = self._transport.request(
            "POST", "/api/v2/users/getgroups", json=_body(query), retry_safe=True
        )
        return ApiResponse(response, lambda raw: _page(raw.json(), UmGroup, query, "groups"))

    def get_page(self, name: str) -> ApiResponse[Page[UmGroup]]:
        return self.list_page(UserQuery(filter={"displayName": {"eq": name}}, limit=1))

    def members_page(
        self, name: str, *, limit: int = 100, offset: int = 0
    ) -> ApiResponse[Page[UmUser]]:
        query = UserQuery(
            filter={"accounts.parentGroups": {"in": [name]}}, limit=limit, offset=offset
        )
        response = self._transport.request(
            "POST", "/api/v2/users/getusers", json=_body(query), retry_safe=True
        )
        return ApiResponse(response, lambda raw: _page(raw.json(), UmUser, query, "users"))


class UsersResponses(SyncResource):
    def list_page(self, query: UserQuery | None = None) -> ApiResponse[Page[UmUser]]:
        query = query or UserQuery()
        response = self._transport.request(
            "POST", "/api/v2/users/getusers", json=_body(query), retry_safe=True
        )
        return ApiResponse(response, lambda raw: _page(raw.json(), UmUser, query, "users"))

    def get_page(self, identifier: str, *, by: str | None = None) -> ApiResponse[Page[UmUser]]:
        if by not in (None, "email", "username"):
            raise ValidationError("by must be 'email' or 'username'.")
        field = (
            "emails"
            if by == "email" or (by is None and "@" in identifier)
            else USERNAME_FILTER_FIELD
        )
        return self.list_page(UserQuery(filter={"and": [{field: {"eq": identifier}}]}, limit=1))


class AsyncUserGroupsResponses(AsyncResource):
    async def list_page(self, query: UserQuery | None = None) -> ApiResponse[Page[UmGroup]]:
        query = query or UserQuery()
        response = await self._transport.request(
            "POST", "/api/v2/users/getgroups", json=_body(query), retry_safe=True
        )
        return ApiResponse(response, lambda raw: _page(raw.json(), UmGroup, query, "groups"))

    async def get_page(self, name: str) -> ApiResponse[Page[UmGroup]]:
        return await self.list_page(UserQuery(filter={"displayName": {"eq": name}}, limit=1))

    async def members_page(
        self, name: str, *, limit: int = 100, offset: int = 0
    ) -> ApiResponse[Page[UmUser]]:
        query = UserQuery(
            filter={"accounts.parentGroups": {"in": [name]}}, limit=limit, offset=offset
        )
        response = await self._transport.request(
            "POST", "/api/v2/users/getusers", json=_body(query), retry_safe=True
        )
        return ApiResponse(response, lambda raw: _page(raw.json(), UmUser, query, "users"))


class AsyncUsersResponses(AsyncResource):
    async def list_page(self, query: UserQuery | None = None) -> ApiResponse[Page[UmUser]]:
        query = query or UserQuery()
        response = await self._transport.request(
            "POST", "/api/v2/users/getusers", json=_body(query), retry_safe=True
        )
        return ApiResponse(response, lambda raw: _page(raw.json(), UmUser, query, "users"))

    async def get_page(
        self, identifier: str, *, by: str | None = None
    ) -> ApiResponse[Page[UmUser]]:
        if by not in (None, "email", "username"):
            raise ValidationError("by must be 'email' or 'username'.")
        field = (
            "emails"
            if by == "email" or (by is None and "@" in identifier)
            else USERNAME_FILTER_FIELD
        )
        return await self.list_page(
            UserQuery(filter={"and": [{field: {"eq": identifier}}]}, limit=1)
        )
