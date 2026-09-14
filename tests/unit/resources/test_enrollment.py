"""Tests for the enrollment resource with mocked HTTP.

``client.enrollment`` is not wired into the client yet, so tests
instantiate ``EnrollmentResource`` / ``AsyncEnrollmentResource`` directly
against the client's transport.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ServerError, ValidationError
from netskope.models.enrollment import EnrollmentTokenSet
from netskope.resources.enrollment.resource import AsyncEnrollmentResource, EnrollmentResource
from tests.unit.resources.conftest import CONTRACT_BASE, sent_json

_URL = "https://t.goskope.com/api/v2/enrollment/tokenset"

_TOKEN_SET = {
    "tsid": 4,
    "created_date": "2024-10-15T06:09:52.449Z",
    "auth_token": "vault:v1:abc123",
    "encrypt_token": "",
    "valid_till": None,
    "enforce_status": 0,
}


@pytest.fixture
def enrollment(client: NetskopeClient) -> EnrollmentResource:
    return EnrollmentResource(client._transport)


@pytest.fixture
def aenrollment(aclient: AsyncNetskopeClient) -> AsyncEnrollmentResource:
    return AsyncEnrollmentResource(aclient._transport)


class TestEnrollmentResource:
    """Sync tests for the enrollment token set API."""

    @respx.mock
    def test_list_token_sets(self, enrollment: EnrollmentResource) -> None:
        """GET /tokenset returns a bare array; items become typed models."""
        route = respx.get(_URL).mock(
            return_value=httpx.Response(200, json=[_TOKEN_SET, {**_TOKEN_SET, "tsid": 5}])
        )
        token_sets = enrollment.list_token_sets()

        assert route.calls.last.request.url.params == httpx.QueryParams()
        assert len(token_sets) == 2
        assert all(isinstance(ts, EnrollmentTokenSet) for ts in token_sets)
        assert token_sets[0].id == 4
        assert token_sets[0].auth_token == "vault:v1:abc123"
        assert token_sets[0].valid_till is None
        assert token_sets[0].enforce_status == 0
        assert token_sets[0].created_date is not None
        assert token_sets[0].created_date.year == 2024

    @respx.mock
    def test_list_token_sets_ignores_pagination_arguments(
        self, enrollment: EnrollmentResource
    ) -> None:
        """TokensetController_getTokenSets declares no parameters (:48-79)."""
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=[]))
        with pytest.warns(DeprecationWarning, match="limit, offset"):
            token_sets = enrollment.list_token_sets(limit=5, offset=10)

        assert route.calls.last.request.url.params == httpx.QueryParams()
        assert token_sets == []

    @respx.mock
    def test_create_token_set_sends_no_body(self, enrollment: EnrollmentResource) -> None:
        """TokensetController_createTokenSet declares no requestBody (:12-47)."""
        route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_TOKEN_SET))
        created = enrollment.create_token_set()

        assert route.calls.last.request.content == b""
        assert isinstance(created, EnrollmentTokenSet)
        assert created.id == 4

    @respx.mock
    def test_create_token_set_warns_about_undeclared_fields(
        self, enrollment: EnrollmentResource
    ) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_TOKEN_SET))
        with pytest.warns(DeprecationWarning, match="max_devices, name"):
            enrollment.create_token_set("Contractors", max_devices=100)

        assert route.calls.last.request.content == b""

    @respx.mock
    def test_update_token_set(self, enrollment: EnrollmentResource) -> None:
        """PATCH /tokenset/{id} sends the UpdateTokenSetDto keys."""
        route = respx.patch(f"{_URL}/4").mock(
            return_value=httpx.Response(200, json={**_TOKEN_SET, "enforce_status": 1})
        )
        updated = enrollment.update_token_set(4, token_type=0, valid_until=30, enforce_status=1)

        assert sent_json(route) == {"type": 0, "valid_until": 30, "enforce_status": 1}
        assert updated.enforce_status == 1

    @respx.mock
    def test_update_token_set_partial_body(self, enrollment: EnrollmentResource) -> None:
        """Only provided fields are sent; enforce_status=0 is a valid value."""
        route = respx.patch(f"{_URL}/4").mock(return_value=httpx.Response(200, json=_TOKEN_SET))
        enrollment.update_token_set(4, enforce_status=0)

        assert sent_json(route) == {"enforce_status": 0}

    def test_update_token_set_requires_a_field(self, enrollment: EnrollmentResource) -> None:
        with pytest.raises(ValidationError):
            enrollment.update_token_set(4)

    def test_update_token_set_rejects_bad_values(self, enrollment: EnrollmentResource) -> None:
        with pytest.raises(ValidationError):
            enrollment.update_token_set(4, token_type=2)
        with pytest.raises(ValidationError):
            enrollment.update_token_set(4, enforce_status=3)

    @respx.mock
    def test_delete_token_set(self, enrollment: EnrollmentResource) -> None:
        route = respx.delete(f"{_URL}/7").mock(return_value=httpx.Response(204))
        assert enrollment.delete_token_set(7) is None
        assert route.called

    @respx.mock
    def test_delete_token_type_returns_remaining_set(self, enrollment: EnrollmentResource) -> None:
        respx.delete(f"{_URL}/4/1").mock(return_value=httpx.Response(200, json=_TOKEN_SET))
        remaining = enrollment.delete_token_type(4, 1)
        assert isinstance(remaining, EnrollmentTokenSet)
        assert remaining.id == 4

    @respx.mock
    def test_delete_token_type_returns_none_on_204(self, enrollment: EnrollmentResource) -> None:
        route = respx.delete(f"{_URL}/4/0").mock(return_value=httpx.Response(204))
        assert enrollment.delete_token_type(4, 0) is None
        # Without this the test cannot tell a decoded 204 from a request never made.
        assert route.called

    def test_delete_token_type_rejects_bad_type(self, enrollment: EnrollmentResource) -> None:
        with pytest.raises(ValidationError):
            enrollment.delete_token_type(4, 2)


class TestAsyncEnrollmentResource:
    """Async tests mirroring the sync surface."""

    @respx.mock
    async def test_list_token_sets(self, aenrollment: AsyncEnrollmentResource) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=[_TOKEN_SET]))
        with pytest.warns(DeprecationWarning, match="limit, offset"):
            token_sets = await aenrollment.list_token_sets(limit=5, offset=10)

        assert route.calls.last.request.url.params == httpx.QueryParams()
        assert len(token_sets) == 1
        assert isinstance(token_sets[0], EnrollmentTokenSet)
        assert token_sets[0].id == 4

    @respx.mock
    async def test_create_token_set(self, aenrollment: AsyncEnrollmentResource) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_TOKEN_SET))
        created = await aenrollment.create_token_set()

        assert route.calls.last.request.content == b""
        assert created.id == 4

    @respx.mock
    async def test_update_token_set(self, aenrollment: AsyncEnrollmentResource) -> None:
        route = respx.patch(f"{_URL}/4").mock(return_value=httpx.Response(200, json=_TOKEN_SET))
        updated = await aenrollment.update_token_set(4, valid_until=90)

        assert sent_json(route) == {"valid_until": 90}
        assert isinstance(updated, EnrollmentTokenSet)

    async def test_update_token_set_requires_a_field(
        self, aenrollment: AsyncEnrollmentResource
    ) -> None:
        with pytest.raises(ValidationError):
            await aenrollment.update_token_set(4)

    @respx.mock
    async def test_delete_token_set(self, aenrollment: AsyncEnrollmentResource) -> None:
        route = respx.delete(f"{_URL}/7").mock(return_value=httpx.Response(204))
        assert await aenrollment.delete_token_set(7) is None
        assert route.called

    @respx.mock
    async def test_delete_token_type(self, aenrollment: AsyncEnrollmentResource) -> None:
        respx.delete(f"{_URL}/4/1").mock(return_value=httpx.Response(200, json=_TOKEN_SET))
        remaining = await aenrollment.delete_token_type(4, 1)
        assert remaining is not None
        assert remaining.id == 4


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.

_TOKENSET_URL = f"{CONTRACT_BASE}/api/v2/enrollment/tokenset"
_contract_mock = respx.mock(assert_all_mocked=True, assert_all_called=False)


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda c: c.enrollment.list_token_sets(), id="legacy"),
        pytest.param(
            lambda c: c.enrollment.with_response.list_token_sets().parse(), id="with_response"
        ),
    ],
)
@_contract_mock
def test_the_tokenset_read_is_not_replayed(retrying_client: NetskopeClient, call: object) -> None:
    route = _contract_mock.get(_TOKENSET_URL).respond(500, json={"message": "boom"})
    with pytest.raises(ServerError):
        call(retrying_client)
    assert route.call_count == 1


@pytest.mark.parametrize("typed", [False, True], ids=["legacy", "with_response"])
@_contract_mock
async def test_the_async_tokenset_read_is_not_replayed(
    retrying_aclient: AsyncNetskopeClient, typed: bool
) -> None:
    route = _contract_mock.get(_TOKENSET_URL).respond(500, json={"message": "boom"})
    with pytest.raises(ServerError):
        if typed:
            (await retrying_aclient.enrollment.with_response.list_token_sets()).parse()
        else:
            await retrying_aclient.enrollment.list_token_sets()
    assert route.call_count == 1


@_contract_mock
def test_the_tokenset_read_still_decodes_its_bare_array(contract_client: NetskopeClient) -> None:
    """TokenSetResponse (enrollment-service-configuration.yaml:744-773)."""
    _contract_mock.get(_TOKENSET_URL).respond(200, json=[{"tsid": 1, "enforce_status": 0}])
    token_sets = contract_client.enrollment.list_token_sets()
    assert [token_set.id for token_set in token_sets] == [1]


_DOCUMENTED_TOKEN_SET = {
    "tsid": 4,
    "created_date": "2024-10-15T06:09:52.449Z",
    "auth_token": "vault:v1:Dta+itEEzx6aMalndfi2ZC1wH4+mjSYriEYScvBvYJnTGJYvuz5GyvmGeYVdyZ+t",
    "encrypt_token": "",
    "valid_till": None,
    "enforce_status": 0,
}


class TestEnrollmentTokenSets:
    """SPEC-I8 / SPEC-I9: the token-set operations declare no body and no parameters."""

    @respx.mock
    def test_create_sends_no_body(self, client: NetskopeClient) -> None:
        """TokensetController_createTokenSet has no requestBody (:12-49)."""
        route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_DOCUMENTED_TOKEN_SET))
        created = client.enrollment.create_token_set()
        request = route.calls.last.request
        assert request.content == b""
        assert "content-type" not in request.headers
        assert created.id == 4
        assert created.enforce_status == 0

    @respx.mock
    def test_list_sends_no_query(self, client: NetskopeClient) -> None:
        """TokensetController_getTokenSets has no parameters; its 200 is a bare array (:50-83)."""
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=[_DOCUMENTED_TOKEN_SET]))
        token_sets = client.enrollment.list_token_sets()
        assert route.calls.last.request.url.params == httpx.QueryParams()
        assert [ts.id for ts in token_sets] == [4]

    @respx.mock
    async def test_async_create_sends_no_body(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_DOCUMENTED_TOKEN_SET))
        await aclient.enrollment.create_token_set()
        assert route.calls.last.request.content == b""
