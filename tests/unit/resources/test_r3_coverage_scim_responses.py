"""R3S-C7: the typed SCIM deletes that no test executed.

``ScimGroupsResponses.delete`` and both ``AsyncScim*Responses.delete`` shipped
without running under ``tests/unit``.  Unlike the legacy ``scim.users.delete``,
these route the id through ``quote_id``, so the encoding is asserted here too.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError

_USERS_URL = "https://t.goskope.com/api/v2/scim/Users"
_GROUPS_URL = "https://t.goskope.com/api/v2/scim/Groups"


class TestScimResponseDeletes:
    @respx.mock
    def test_groups_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_GROUPS_URL}/grp-1").mock(return_value=httpx.Response(204))
        assert client.scim.groups.with_response.delete("grp-1") is None
        assert route.calls.last.request.method == "DELETE"

    @respx.mock
    def test_groups_delete_percent_encodes_the_id(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_GROUPS_URL}/eng%2Fweb").mock(return_value=httpx.Response(204))
        client.scim.groups.with_response.delete("eng/web")
        assert route.calls.last.request.url.raw_path.endswith(b"/eng%2Fweb")

    def test_groups_delete_rejects_an_id_with_whitespace(self, client: NetskopeClient) -> None:
        with respx.mock:
            route = respx.route(host="t.goskope.com")
            with pytest.raises(ValidationError, match="Invalid id for URL path"):
                client.scim.groups.with_response.delete("grp 1")
            assert not route.called

    @respx.mock
    async def test_async_users_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_USERS_URL}/8f2c4a1b").mock(return_value=httpx.Response(204))
        assert await aclient.scim.users.with_response.delete("8f2c4a1b") is None
        assert route.called

    @respx.mock
    async def test_async_users_delete_percent_encodes_the_id(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.delete(f"{_USERS_URL}/user%40example.com").mock(
            return_value=httpx.Response(204)
        )
        await aclient.scim.users.with_response.delete("user@example.com")
        assert route.calls.last.request.url.raw_path.endswith(b"/user%40example.com")

    @respx.mock
    async def test_async_groups_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_GROUPS_URL}/grp-1").mock(return_value=httpx.Response(204))
        assert await aclient.scim.groups.with_response.delete("grp-1") is None
        assert route.called
