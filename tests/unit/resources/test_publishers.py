"""Tests for client.publishers with mocked HTTP."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from pydantic import ValidationError as PydanticValidationError

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.core.pagination import Page
from netskope.exceptions import (
    NetskopeError,
    NotFoundError,
    ResponseValidationError,
    ValidationError,
)
from netskope.models.publishers import (
    Publisher,
    PublisherAlertsConfiguration,
    PublisherAlertsConfigurationPatch,
    PublisherAlertsConfigurationStatus,
    PublisherApp,
    PublisherCreate,
    PublisherRelease,
    PublisherStatus,
    PublisherUpdate,
)
from tests.unit.resources.conftest import CONTRACT_BASE, EXAMPLE_BASE, drain, sent_json

_URL = "https://t.goskope.com/api/v2/infrastructure/publishers"
_RELEASES_URL = f"{_URL}/releases"
_BULK_URL = f"{_URL}/bulk"
_ALERTS_CONFIG_URL = f"{_URL}/alertsconfiguration"

_LIST_BODY = {
    "data": {
        "publishers": [
            {"publisher_id": 1, "publisher_name": "Pub1", "status": "connected"},
        ]
    },
    "status": {"total": 1},
}

_RELEASES_BODY = {
    "data": {
        "releases": [
            {
                "version": "1.2.3",
                "docker_tag": "release-1.2.3",
                "release_type": "GA",
                "is_recommended": True,
            },
            {
                "version": "1.3.0",
                "docker_tag": "release-1.3.0",
                "release_type": "Beta",
                "is_recommended": False,
            },
        ]
    }
}

_APPS_BODY = {
    "data": {
        "apps": [
            {"app_name": "wiki", "app_id": 7, "host": "wiki.internal", "protocol": "tcp"},
        ]
    }
}

_ALERTS_CONFIG_BODY = {
    "data": {
        "adminUsers": ["admin@example.com"],
        "eventTypes": ["UPGRADE_FAILED", "CONNECTION_FAILED"],
    }
}


class TestPublishersResource:
    """Tests for client.publishers (sync)."""

    @respx.mock
    def test_list(self, client: NetskopeClient) -> None:
        respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        pubs = list(client.publishers.list())
        assert len(pubs) == 1
        assert isinstance(pubs[0], Publisher)
        assert pubs[0].publisher_name == "Pub1"

    @respx.mock
    def test_list_sends_only_the_declared_fields_parameter(self, client: NetskopeClient) -> None:
        """``getNPAPublishers`` declares only ``fields`` (npa_publishers.yaml:1024-1032)."""
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        list(client.publishers.list(fields=["publisher_id", "publisher_name"]))
        assert route.call_count == 1
        assert dict(route.calls.last.request.url.params) == {
            "fields": "publisher_id,publisher_name"
        }

    @respx.mock
    def test_list_rejects_the_undeclared_filter_parameter(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="filter_expr is not supported"):
            list(client.publishers.list(filter_expr="status eq 'connected'"))
        assert len(respx.calls) == 0

    @respx.mock
    def test_list_fetches_the_collection_once(self, client: NetskopeClient) -> None:
        """With no ``offset``/``limit`` declared there is no second page to ask for."""
        body = {"publishers": [{"publisher_id": n} for n in (1, 2, 3)], "total": 3}
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=body))
        assert [pub.publisher_id for pub in client.publishers.list(page_size=1)] == [1, 2, 3]
        assert route.call_count == 1
        assert not route.calls.last.request.url.params

    @respx.mock
    def test_list_page_preserves_omitted_pagination(self, client: NetskopeClient) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        page = client.publishers.list_page()

        assert route.call_count == 1
        assert not route.calls.last.request.url.params
        assert isinstance(page, Page)
        assert isinstance(page.items[0], Publisher)
        assert page.offset == 0
        assert page.limit is None
        assert page.total == 1
        assert page.has_more is False
        assert page.metadata == {"status": {"total": 1}}

    @respx.mock
    def test_list_page_preserves_projection_and_metadata(self, client: NetskopeClient) -> None:
        record = {"publisher_id": 7, "status": None, "future": {"name": "blue"}}
        metadata = {
            "data": {"query_id": "q1"},
            "status": {"total": "1", "count": 1},
            "warnings": ["partial inventory"],
        }
        body = {**metadata, "data": {"publishers": [record], "query_id": "q1"}}
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=body))

        page = client.publishers.list_page(
            fields=["publisher_id", "status", "future"],
            offset=0,
            limit=1,
        )

        assert route.call_count == 1
        # Only ``fields`` is declared, so offset/limit never reach the wire.
        assert dict(route.calls.last.request.url.params) == {"fields": "publisher_id,status,future"}
        assert page.offset == 0
        assert page.limit == 1
        assert page.total == 1
        assert page.has_more is False
        assert page.metadata == metadata
        assert page.items[0].model_dump(mode="json", by_alias=True, exclude_unset=True) == record

    @pytest.mark.parametrize(
        ("metadata", "total"),
        [
            ({"status": {"total": 0}}, 0),
            ({"total": "3"}, 3),
            ({"totalResults": 3}, 3),
            ({"status": {"total": "invalid"}, "total": 3}, 3),
            ({"status": {"count": 10_000}}, None),
            ({"count": 10_000}, None),
            ({"status": {"total": True}}, None),
            ({"status": {"total": -1}}, None),
            ({"status": {"total": 1.5}}, None),
            ({"status": {"total": "1.5"}}, None),
            ({}, None),
        ],
    )
    @respx.mock
    def test_list_page_uses_only_valid_totals(
        self, client: NetskopeClient, metadata: dict, total: int | None
    ) -> None:
        records = [{"publisher_id": n} for n in range(total or 0)]
        body = {"data": {"publishers": records}, **metadata}
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=body))

        page = client.publishers.list_page(limit=100)

        assert route.call_count == 1
        assert page.total == total
        assert page.has_more is False
        assert page.metadata == metadata

    @pytest.mark.parametrize(
        "body",
        [
            [{"publisher_id": 7}],
            {"result": [{"publisher_id": 7}]},
            {"data": [{"publisher_id": 7}]},
            {"publishers": [{"publisher_id": 7}]},
            {"Resources": [{"publisher_id": 7}]},
        ],
    )
    @respx.mock
    def test_list_page_accepts_existing_envelope_variants(
        self, client: NetskopeClient, body: object
    ) -> None:
        respx.get(_URL).mock(return_value=httpx.Response(200, json=body))
        page = client.publishers.list_page()
        assert page.items[0].publisher_id == 7
        assert page.metadata == {}
        assert page.has_more is False

    @pytest.mark.parametrize(
        "body",
        [
            None,
            {},
            {"data": {}},
            {"data": {"publishers": {"publisher_id": 7}}},
            {"data": {"publishers": [None]}},
            {"publishers": [{"publisher_id": 7}, "bad record"]},
        ],
    )
    @respx.mock
    def test_list_page_rejects_malformed_envelopes(
        self, client: NetskopeClient, body: object
    ) -> None:
        respx.get(_URL).mock(return_value=httpx.Response(200, content=json.dumps(body)))
        with pytest.raises(ResponseValidationError):
            client.publishers.list_page()

    @pytest.mark.parametrize("params", [{"offset": -1}, {"limit": 0}, {"offset": True}])
    @respx.mock
    def test_list_page_invalid_pagination_sends_no_http(
        self, client: NetskopeClient, params: dict
    ) -> None:
        with pytest.raises(ValidationError):
            client.publishers.list_page(**params)
        assert len(respx.calls) == 0

    @respx.mock
    def test_lazy_list_uses_same_page_metadata(self, client: NetskopeClient) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        result = client.publishers.list(page_size=1)
        assert route.call_count == 0

        page = next(result.pages())

        assert route.call_count == 1
        assert page.metadata == {"status": {"total": 1}}
        assert page.has_more is False
        assert page.items[0].publisher_name == "Pub1"

    @respx.mock
    def test_lazy_list_rejects_malformed_envelope(self, client: NetskopeClient) -> None:
        respx.get(_URL).mock(return_value=httpx.Response(200, json={"data": {}}))
        with pytest.raises(NetskopeError, match="Invalid publishers response"):
            list(client.publishers.list())

    @respx.mock
    def test_get(self, client: NetskopeClient) -> None:
        respx.get(f"{_URL}/42").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"publisher_id": 42, "publisher_name": "Pub42"}},
            )
        )
        pub = client.publishers.get(42)
        assert pub.publisher_id == 42
        assert pub.publisher_name == "Pub42"

    @respx.mock
    def test_create_sends_name_not_publisher_name(self, client: NetskopeClient) -> None:
        """create() must send {"name": ...} — the API rejects publisher_name on write."""
        route = respx.post(_URL).mock(
            return_value=httpx.Response(
                200,
                json={"data": {"publisher_id": 99, "publisher_name": "NewPub"}},
            )
        )
        pub = client.publishers.create(name="NewPub")
        assert pub.publisher_id == 99
        # publisher_post_request spells the flag ``lbrokerconnect``
        # (npa_publishers.yaml:323-326).
        assert sent_json(route) == {"name": "NewPub", "lbrokerconnect": False}

    @respx.mock
    def test_create_with_lbroker_connect(self, client: NetskopeClient) -> None:
        route = respx.post(_URL).mock(
            return_value=httpx.Response(200, json={"data": {"publisher_id": 100}})
        )
        client.publishers.create(name="DC-Primary", lbroker_connect=True)
        assert sent_json(route) == {"name": "DC-Primary", "lbrokerconnect": True}

    @respx.mock
    def test_create_validates_final_overrides_and_preserves_extensions(
        self, client: NetskopeClient
    ) -> None:
        route = respx.post(_URL).mock(
            return_value=httpx.Response(200, json={"data": {"publisher_id": 100}})
        )
        client.publishers.create(
            name="Original",
            extra_fields={"name": "", "lbroker_connect": True, "future": {"enabled": False}},
        )
        assert sent_json(route) == {
            "name": "",
            "lbrokerconnect": True,
            "future": {"enabled": False},
        }

    @pytest.mark.parametrize(
        "extra_fields", [{"name": 123}, {"lbroker_connect": "true"}, {"lbroker_connect": 1}]
    )
    @respx.mock
    def test_create_invalid_override_sends_no_http(
        self, client: NetskopeClient, extra_fields: dict
    ) -> None:
        with pytest.raises(ValidationError):
            client.publishers.create(name="Original", extra_fields=extra_fields)
        assert len(respx.calls) == 0

    @respx.mock
    def test_update_uses_patch_and_name_key(self, client: NetskopeClient) -> None:
        """update() must PATCH (not PUT) and send {"name": ...}."""
        route = respx.patch(f"{_URL}/42").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"publisher_id": 42, "publisher_name": "Renamed"}},
            )
        )
        pub = client.publishers.update(42, name="Renamed")
        assert pub.publisher_name == "Renamed"
        assert sent_json(route) == {"name": "Renamed"}

    @respx.mock
    def test_update_merges_extras_with_the_required_name(self, client: NetskopeClient) -> None:
        """``publisher_patch_request`` declares ``required: [name]`` (:338-341)."""
        route = respx.patch(f"{_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": {"publisher_id": 42}})
        )
        client.publishers.update(42, name="Renamed", extra_fields={"future": False})
        assert sent_json(route) == {"name": "Renamed", "future": False}

        client.publishers.update(42, extra_fields={"name": "From extras"})
        assert sent_json(route) == {"name": "From extras"}

    @respx.mock
    def test_update_without_a_name_sends_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="requires name"):
            client.publishers.update(42, extra_fields={"future": False})
        with pytest.raises(ValidationError, match="requires name"):
            client.publishers.update(42, name="Original", extra_fields={"name": None})
        assert len(respx.calls) == 0

    @respx.mock
    def test_update_invalid_override_sends_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            client.publishers.update(42, name="Original", extra_fields={"name": 123})
        assert len(respx.calls) == 0

    @respx.mock
    def test_list_page_drops_a_total_that_contradicts_the_rows(
        self, client: NetskopeClient
    ) -> None:
        body = {"publishers": [{"publisher_id": n} for n in (1, 2, 3)], "total": 1}
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=body))
        page = client.publishers.list_page()
        assert [publisher.publisher_id for publisher in page.items] == [1, 2, 3]
        assert page.total is None
        assert route.call_count == 1

    @respx.mock
    def test_list_returns_rows_a_reported_total_would_have_refused(
        self, client: NetskopeClient
    ) -> None:
        """A contradicting total must not reach the unpaginated branch of ``pages()``.

        That branch raises :class:`PaginationError` when the stated total
        exceeds the records the response carries, so a total reported verbatim
        makes ``list()`` yield nothing while ``list_page()`` still returns the
        same rows.  Dropping it in ``local_page`` is what keeps the two
        surfaces agreeing on a response the gateway sent successfully.
        """
        body = {"publishers": [{"publisher_id": n} for n in (1, 2, 3)], "total": 9}
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=body))
        assert [pub.publisher_id for pub in client.publishers.list()] == [1, 2, 3]
        assert route.call_count == 1

    @respx.mock
    def test_list_and_list_page_report_the_same_envelope_failure(
        self, client: NetskopeClient
    ) -> None:
        respx.get(_URL).mock(return_value=httpx.Response(200, json={"data": {}}))
        message = "Invalid publishers response: expected a publisher collection."
        with pytest.raises(ResponseValidationError) as from_page:
            client.publishers.list_page()
        with pytest.raises(ResponseValidationError) as from_list:
            list(client.publishers.list())
        assert str(from_page.value) == str(from_list.value) == message
        assert from_page.value.request_path == "/api/v2/infrastructure/publishers"

    @respx.mock
    def test_update_without_fields_sends_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="requires name"):
            client.publishers.update(42)
        assert len(respx.calls) == 0

    @pytest.mark.parametrize("publisher_ids", ["12", 12, (1, 2), [True], [1, None], []])
    @respx.mock
    def test_bulk_upgrade_rejects_non_integer_ids(
        self, client: NetskopeClient, publisher_ids: object
    ) -> None:
        with pytest.raises(ValidationError, match="publisher_ids"):
            client.publishers.bulk_upgrade(publisher_ids)  # type: ignore[arg-type]
        assert len(respx.calls) == 0

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_URL}/42").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        client.publishers.delete(42)
        assert route.called

    @respx.mock
    def test_list_apps(self, client: NetskopeClient) -> None:
        respx.get(f"{_URL}/42/apps").mock(return_value=httpx.Response(200, json=_APPS_BODY))
        apps = client.publishers.list_apps(42)
        assert apps == _APPS_BODY["data"]["apps"]

    @respx.mock
    def test_create_registration_token(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_URL}/42/registration_token").mock(
            return_value=httpx.Response(200, json={"data": {"token": "abc123"}})
        )
        token = client.publishers.create_registration_token(42)
        assert token == "abc123"
        assert route.called

    @respx.mock
    def test_create_registration_token_top_level_fallback(self, client: NetskopeClient) -> None:
        respx.post(f"{_URL}/42/registration_token").mock(
            return_value=httpx.Response(200, json={"token": 987654})
        )
        assert client.publishers.create_registration_token(42) == "987654"

    @respx.mock
    def test_create_registration_token_missing_raises(self, client: NetskopeClient) -> None:
        respx.post(f"{_URL}/42/registration_token").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        with pytest.raises(ResponseValidationError):
            client.publishers.create_registration_token(42)

    @respx.mock
    def test_list_releases(self, client: NetskopeClient) -> None:
        route = respx.get(_RELEASES_URL).mock(return_value=httpx.Response(200, json=_RELEASES_BODY))
        releases = client.publishers.list_releases()
        assert route.called
        assert len(releases) == 2
        assert isinstance(releases[0], PublisherRelease)
        assert releases[0].version == "1.2.3"
        assert releases[0].docker_tag == "release-1.2.3"
        assert releases[0].release_type == "GA"

    @respx.mock
    def test_bulk_upgrade_body_shape(self, client: NetskopeClient) -> None:
        route = respx.put(_BULK_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        result = client.publishers.bulk_upgrade([1, 2, 3])
        assert result == {"status": "success"}
        # publishers_bulk_request ids are strings (npa_publishers.yaml:294-299).
        assert sent_json(route) == {
            "publishers": {
                "apply": {"upgrade_request": True},
                "id": ["1", "2", "3"],
            }
        }

    @respx.mock
    def test_bulk_upgrade_accepts_ids_already_given_as_strings(
        self, client: NetskopeClient
    ) -> None:
        """The bulk schema's items are {type: string} (npa_publishers.yaml:297-299)."""
        route = respx.put(_BULK_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        client.publishers.bulk_upgrade([1, "2"])
        assert sent_json(route)["publishers"]["id"] == ["1", "2"]

    @respx.mock
    def test_get_alerts_configuration(self, client: NetskopeClient) -> None:
        respx.get(_ALERTS_CONFIG_URL).mock(
            return_value=httpx.Response(200, json=_ALERTS_CONFIG_BODY)
        )
        config = client.publishers.get_alerts_configuration()
        assert isinstance(config, PublisherAlertsConfiguration)
        assert config.admin_users == ["admin@example.com"]
        assert config.event_types == ["UPGRADE_FAILED", "CONNECTION_FAILED"]

    @respx.mock
    def test_update_alerts_configuration_sends_camelcase(self, client: NetskopeClient) -> None:
        route = respx.put(_ALERTS_CONFIG_URL).mock(
            return_value=httpx.Response(200, json=_ALERTS_CONFIG_BODY)
        )
        status = client.publishers.update_alerts_configuration(
            admin_users=["admin@example.com"],
            event_types=["UPGRADE_FAILED", "CONNECTION_FAILED"],
            selected_users=["a@example.com", "b@example.com"],
        )
        # ``publishers_alert_put_response`` declares only ``status`` (:630-638).
        assert isinstance(status, PublisherAlertsConfigurationStatus)
        assert sent_json(route) == {
            "adminUsers": ["admin@example.com"],
            "eventTypes": ["UPGRADE_FAILED", "CONNECTION_FAILED"],
            "selectedUsers": "a@example.com,b@example.com",
        }

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            {"admin_users": ["a@example.com"]},
            {"admin_users": ["a@example.com"], "event_types": ["UPGRADE_FAILED"]},
            {"event_types": ["UPGRADE_FAILED"], "selected_users": "a@example.com"},
        ],
    )
    @respx.mock
    def test_update_alerts_configuration_requires_all_three_keys(
        self, client: NetskopeClient, kwargs: dict
    ) -> None:
        """All three are ``required`` on the PUT (npa_publishers.yaml:591-594)."""
        with pytest.raises(ValidationError, match="requires"):
            client.publishers.update_alerts_configuration(**kwargs)
        assert len(respx.calls) == 0

    @respx.mock
    def test_update_alerts_configuration_invalid_event_type_no_http(
        self, client: NetskopeClient
    ) -> None:
        with pytest.raises(ValidationError, match="UPGRADE_EXPLODED"):
            client.publishers.update_alerts_configuration(event_types=["UPGRADE_EXPLODED"])
        assert len(respx.calls) == 0


class TestAsyncPublishersResource:
    """Tests for aclient.publishers (async)."""

    @respx.mock
    async def test_list(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        pubs = await drain(aclient.publishers.list())
        assert len(pubs) == 1
        assert isinstance(pubs[0], Publisher)
        assert pubs[0].publisher_name == "Pub1"

    @respx.mock
    async def test_list_sends_only_the_declared_fields_parameter(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        await drain(aclient.publishers.list(fields=["publisher_id", "publisher_name"]))
        assert route.call_count == 1
        assert dict(route.calls.last.request.url.params) == {
            "fields": "publisher_id,publisher_name"
        }

    @respx.mock
    async def test_list_rejects_the_undeclared_filter_parameter(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError, match="filter_expr is not supported"):
            await drain(aclient.publishers.list(filter_expr="status eq 'connected'"))
        assert len(respx.calls) == 0

    @respx.mock
    async def test_list_fetches_the_collection_once(self, aclient: AsyncNetskopeClient) -> None:
        body = {"publishers": [{"publisher_id": n} for n in (1, 2, 3)], "total": 3}
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=body))
        pubs = await drain(aclient.publishers.list(page_size=1))
        assert [pub.publisher_id for pub in pubs] == [1, 2, 3]
        assert route.call_count == 1
        assert not route.calls.last.request.url.params

    @respx.mock
    async def test_list_page_preserves_omitted_pagination(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        page = await aclient.publishers.list_page()
        assert route.call_count == 1
        assert not route.calls.last.request.url.params
        assert page.offset == 0
        assert page.limit is None
        assert page.total == 1
        assert page.has_more is False
        assert page.metadata == {"status": {"total": 1}}
        assert isinstance(page.items[0], Publisher)

    @respx.mock
    async def test_list_page_preserves_parameters(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        page = await aclient.publishers.list_page(
            fields=["publisher_id", "status"],
            offset=0,
            limit=1,
        )
        assert route.call_count == 1
        assert dict(route.calls.last.request.url.params) == {"fields": "publisher_id,status"}
        assert page.limit == 1
        assert page.items[0].publisher_id == 1

    @respx.mock
    async def test_list_page_rejects_the_undeclared_filter_parameter(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError, match="filter_expr is not supported"):
            await aclient.publishers.list_page(filter_expr="status eq 'connected'")
        assert len(respx.calls) == 0

    @respx.mock
    async def test_lazy_list_uses_same_page_metadata(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        result = aclient.publishers.list(page_size=1)
        assert route.call_count == 0
        page = await anext(result.pages())
        assert page.metadata == {"status": {"total": 1}}
        assert page.has_more is False

    @respx.mock
    async def test_list_page_rejects_malformed_envelope(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_URL).mock(return_value=httpx.Response(200, json={"data": {}}))
        with pytest.raises(ResponseValidationError):
            await aclient.publishers.list_page()

    @respx.mock
    async def test_list_page_invalid_pagination_sends_no_http(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError):
            await aclient.publishers.list_page(limit=0)
        assert len(respx.calls) == 0

    @respx.mock
    async def test_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_URL}/42").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"publisher_id": 42, "publisher_name": "Pub42"}},
            )
        )
        pub = await aclient.publishers.get(42)
        assert pub.publisher_id == 42

    @respx.mock
    async def test_create_sends_name_not_publisher_name(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_URL).mock(
            return_value=httpx.Response(200, json={"data": {"publisher_id": 99}})
        )
        pub = await aclient.publishers.create(name="NewPub", lbroker_connect=True)
        assert pub.publisher_id == 99
        assert sent_json(route) == {"name": "NewPub", "lbrokerconnect": True}

    @respx.mock
    async def test_create_invalid_override_sends_no_http(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError):
            await aclient.publishers.create(name="Original", extra_fields={"lbroker_connect": 1})
        assert len(respx.calls) == 0

    @respx.mock
    async def test_update_uses_patch_and_name_key(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(f"{_URL}/42").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"publisher_id": 42, "publisher_name": "Renamed"}},
            )
        )
        pub = await aclient.publishers.update(42, name="Renamed")
        assert pub.publisher_name == "Renamed"
        assert sent_json(route) == {"name": "Renamed"}

    @respx.mock
    async def test_update_invalid_override_sends_no_http(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError):
            await aclient.publishers.update(42, extra_fields={"name": False})
        assert len(respx.calls) == 0

    @respx.mock
    async def test_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_URL}/42").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        await aclient.publishers.delete(42)
        assert route.called

    @respx.mock
    async def test_list_apps(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_URL}/42/apps").mock(return_value=httpx.Response(200, json=_APPS_BODY))
        apps = await aclient.publishers.list_apps(42)
        assert apps == _APPS_BODY["data"]["apps"]

    @respx.mock
    async def test_create_registration_token(self, aclient: AsyncNetskopeClient) -> None:
        respx.post(f"{_URL}/42/registration_token").mock(
            return_value=httpx.Response(200, json={"data": {"token": "abc123"}})
        )
        assert await aclient.publishers.create_registration_token(42) == "abc123"

    @respx.mock
    async def test_create_registration_token_missing_raises(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        respx.post(f"{_URL}/42/registration_token").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        with pytest.raises(ResponseValidationError):
            await aclient.publishers.create_registration_token(42)

    @respx.mock
    async def test_list_releases(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_RELEASES_URL).mock(return_value=httpx.Response(200, json=_RELEASES_BODY))
        releases = await aclient.publishers.list_releases()
        assert len(releases) == 2
        assert isinstance(releases[0], PublisherRelease)
        assert releases[0].version == "1.2.3"

    @respx.mock
    async def test_bulk_upgrade_body_shape(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(_BULK_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        result = await aclient.publishers.bulk_upgrade([7])
        assert result == {"status": "success"}
        assert sent_json(route) == {
            "publishers": {
                "apply": {"upgrade_request": True},
                "id": ["7"],
            }
        }

    @respx.mock
    async def test_update_without_fields_sends_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError, match="requires name"):
            await aclient.publishers.update(42)
        assert len(respx.calls) == 0

    @pytest.mark.parametrize("publisher_ids", ["12", [True], []])
    @respx.mock
    async def test_bulk_upgrade_rejects_non_integer_ids(
        self, aclient: AsyncNetskopeClient, publisher_ids: object
    ) -> None:
        with pytest.raises(ValidationError, match="publisher_ids"):
            await aclient.publishers.bulk_upgrade(publisher_ids)  # type: ignore[arg-type]
        assert len(respx.calls) == 0

    @respx.mock
    async def test_list_page_drops_a_total_that_contradicts_the_rows(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        body = {"publishers": [{"publisher_id": n} for n in (1, 2, 3)], "total": 1}
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=body))
        page = await aclient.publishers.list_page()
        assert [publisher.publisher_id for publisher in page.items] == [1, 2, 3]
        assert page.total is None
        assert route.call_count == 1

    @respx.mock
    async def test_list_returns_rows_a_reported_total_would_have_refused(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        """Async twin of the sync guard; see that test for the reasoning."""
        body = {"publishers": [{"publisher_id": n} for n in (1, 2, 3)], "total": 9}
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=body))
        pubs = await drain(aclient.publishers.list())
        assert [pub.publisher_id for pub in pubs] == [1, 2, 3]
        assert route.call_count == 1

    @respx.mock
    async def test_get_alerts_configuration(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_ALERTS_CONFIG_URL).mock(
            return_value=httpx.Response(200, json=_ALERTS_CONFIG_BODY)
        )
        config = await aclient.publishers.get_alerts_configuration()
        assert config.admin_users == ["admin@example.com"]
        assert config.event_types == ["UPGRADE_FAILED", "CONNECTION_FAILED"]

    @respx.mock
    async def test_update_alerts_configuration_sends_camelcase(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.put(_ALERTS_CONFIG_URL).mock(
            return_value=httpx.Response(200, json=_ALERTS_CONFIG_BODY)
        )
        status = await aclient.publishers.update_alerts_configuration(
            admin_users=["admin@example.com"],
            event_types=["UPGRADE_FAILED"],
            selected_users="a@example.com",
        )
        assert isinstance(status, PublisherAlertsConfigurationStatus)
        assert sent_json(route) == {
            "adminUsers": ["admin@example.com"],
            "eventTypes": ["UPGRADE_FAILED"],
            "selectedUsers": "a@example.com",
        }

    @respx.mock
    async def test_update_alerts_configuration_requires_all_three_keys(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError, match="requires"):
            await aclient.publishers.update_alerts_configuration(
                admin_users=["a@example.com"], event_types=["UPGRADE_FAILED"]
            )
        assert len(respx.calls) == 0

    @respx.mock
    async def test_update_alerts_configuration_invalid_event_type_no_http(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError, match="UPGRADE_EXPLODED"):
            await aclient.publishers.update_alerts_configuration(event_types=["UPGRADE_EXPLODED"])
        assert len(respx.calls) == 0


class TestPublisherRequests:
    @pytest.mark.parametrize("model", [PublisherCreate, PublisherUpdate])
    def test_requests_reject_unknown_fields(self, model: type) -> None:
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            model.model_validate({"name": "Publisher", "misspelled_setting": True})

    def test_update_requires_a_name(self) -> None:
        """``publisher_patch_request.required`` is ``[name]`` (npa_publishers.yaml:338-341)."""
        from pydantic import ValidationError as PydanticValidationError

        assert PublisherUpdate(name="Pub").model_dump(exclude_unset=True) == {"name": "Pub"}
        for invalid in ({}, {"name": None}):
            with pytest.raises(PydanticValidationError):
                PublisherUpdate.model_validate(invalid)


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.

_PUBLISHERS_URL = f"{CONTRACT_BASE}/api/v2/infrastructure/publishers"


@respx.mock
def test_publisher_patch_requires_the_declared_name(contract_client: NetskopeClient) -> None:
    """``publisher_patch_request`` declares ``required: [name]``.

    Spec: infrastructure/npa_publishers.yaml:338-341, for
    ``PATCH /publishers/{publisher_id}``.  A body that changed only
    ``lbrokerconnect`` was reported as a success the gateway had rejected.
    """
    with pytest.raises(ValidationError, match="requires name"):
        contract_client.publishers.update(6, extra_fields={"lbroker_connect": True})
    assert len(respx.calls) == 0

    route = respx.patch(f"{_PUBLISHERS_URL}/6").mock(
        return_value=httpx.Response(200, json={"data": {"id": 6, "name": "pub"}})
    )
    contract_client.publishers.update(6, name="pub", extra_fields={"lbroker_connect": True})
    assert sent_json(route) == {"name": "pub", "lbrokerconnect": True}


@respx.mock
async def test_async_publisher_patch_requires_the_declared_name(
    contract_aclient: AsyncNetskopeClient,
) -> None:
    """The async mirror enforces the same ``required: [name]`` (:338-341)."""
    with pytest.raises(ValidationError, match="requires name"):
        await contract_aclient.publishers.update(6, extra_fields={"lbroker_connect": True})
    assert len(respx.calls) == 0


@respx.mock
def test_alerts_put_sends_all_three_required_keys(contract_client: NetskopeClient) -> None:
    """``publishers_alert_put_request.required`` is all three keys.

    Spec: infrastructure/npa_publishers.yaml:591-594 for the required set,
    :624-625 for the 1..5 ``eventTypes`` bound and :627-629 for
    ``selectedUsers`` as one comma-joined string.  A no-argument call used to
    send ``{}`` to a three-required-property schema and report success.
    """
    with pytest.raises(ValidationError, match="requires admin_users, event_types, selected_users"):
        contract_client.publishers.update_alerts_configuration()
    assert len(respx.calls) == 0

    route = respx.put(f"{_PUBLISHERS_URL}/alertsconfiguration").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    contract_client.publishers.update_alerts_configuration(
        admin_users=["admin1@abc.com"],
        event_types=["UPGRADE_FAILED"],
        selected_users=["abc@xyz.com", "def@xyz.com"],
    )
    assert sent_json(route) == {
        "adminUsers": ["admin1@abc.com"],
        "eventTypes": ["UPGRADE_FAILED"],
        "selectedUsers": "abc@xyz.com,def@xyz.com",
    }


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_alerts_put_returns_a_status_acknowledgment(
    contract_client: NetskopeClient, contract_aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    """``publishers_alert_put_response`` declares only ``status``.

    Spec: infrastructure/npa_publishers.yaml:630-638, enum
    ``success`` / ``not found`` / ``failure``, referenced from the PUT at
    :1180-1187.  Parsing it into the configuration model produced a hollow
    object indistinguishable from a configuration that really is empty.
    """
    route = respx.put(f"{_PUBLISHERS_URL}/alertsconfiguration").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    client = contract_aclient if asynchronous else contract_client
    result = client.publishers.update_alerts_configuration(
        admin_users=["admin1@abc.com"],
        event_types=["UPGRADE_FAILED"],
        selected_users="abc@xyz.com",
    )
    if asynchronous:
        result = await result

    assert isinstance(result, PublisherAlertsConfigurationStatus)
    assert result.status == "success"
    assert not hasattr(result, "admin_users")
    assert route.call_count == 1


@respx.mock
def test_publisher_list_sends_no_undeclared_parameters(contract_client: NetskopeClient) -> None:
    """Only ``fields`` reaches the wire, and the collection is fetched once."""
    body = {
        "data": {"publishers": [{"publisher_id": n} for n in (1, 2, 3, 4, 5)]},
        "total": 5,
        "status": "success",
    }
    route = respx.get(_PUBLISHERS_URL).mock(return_value=httpx.Response(200, json=body))

    # A page size smaller than the collection must not make the parser refuse
    # the body or ask for a second page that would re-deliver the same records.
    assert [pub.publisher_id for pub in contract_client.publishers.list(page_size=2)] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert route.call_count == 1
    assert not route.calls.last.request.url.params

    page = contract_client.publishers.list_page(fields=["publisher_id"], offset=1, limit=2)
    assert [pub.publisher_id for pub in page.items] == [2, 3]
    assert (page.offset, page.limit, page.total, page.has_more) == (1, 2, 5, True)
    assert page.metadata == {"total": 5, "status": "success"}
    assert dict(route.calls.last.request.url.params) == {"fields": "publisher_id"}
    assert route.call_count == 2


@respx.mock
async def test_async_publisher_list_makes_exactly_one_request(
    contract_aclient: AsyncNetskopeClient,
) -> None:
    """The async iterator makes no extra HTTP call for a collection it already holds."""
    body = {"publishers": [{"publisher_id": n} for n in (1, 2, 3)], "total": 3}
    route = respx.get(_PUBLISHERS_URL).mock(return_value=httpx.Response(200, json=body))
    records = await drain(contract_aclient.publishers.list(page_size=1))
    assert [pub.publisher_id for pub in records] == [1, 2, 3]
    assert route.call_count == 1
    assert not route.calls.last.request.url.params


@respx.mock
def test_status_not_found_on_http_200_raises_not_found(example_client: NetskopeClient) -> None:
    """`not found` is a declared 200-level status value.

    npa_publishers.yaml:871-876 (status_enum, used by the publishers
    list/get/create/update operations), npa_apps_private.yaml:25-26,
    npa_private_tag.yaml:412, npa_generic.yaml:152-156.
    """
    respx.get(f"{EXAMPLE_BASE}/api/v2/infrastructure/publishers/7").mock(
        return_value=httpx.Response(200, json={"status": "not found"})
    )
    with pytest.raises(NotFoundError) as excinfo:
        example_client.publishers.get(7)
    assert "not found" in str(excinfo.value).lower()


_EXAMPLE_PUBLISHERS_URL = f"{EXAMPLE_BASE}/api/v2/infrastructure/publishers"


@respx.mock
def test_publisher_create_sends_the_lbrokerconnect_key(example_client: NetskopeClient) -> None:
    """publisher_post_request names the flag ``lbrokerconnect``.

    Spec: npa_publishers.yaml:323-326 (post), :354 (patch), :368 (put).  The
    SDK sent ``lbroker_connect``, which the gateway drops, so the flag never
    took effect on any create.
    """
    route = respx.post(_EXAMPLE_PUBLISHERS_URL).mock(
        return_value=httpx.Response(200, json={"data": {"id": 6, "name": "npa_publisher_1"}})
    )
    example_client.publishers.create("npa_publisher_1", lbroker_connect=True)

    body = sent_json(route)
    assert body == {"name": "npa_publisher_1", "lbrokerconnect": True}
    assert "lbroker_connect" not in body


@respx.mock
def test_publisher_update_renames_an_extra_lbroker_connect_field(
    example_client: NetskopeClient,
) -> None:
    """publisher_patch_request carries the same ``lbrokerconnect`` key (npa_publishers.yaml:354)."""
    route = respx.patch(f"{_EXAMPLE_PUBLISHERS_URL}/6").mock(
        return_value=httpx.Response(200, json={"data": {"id": 6, "name": "pub01.local"}})
    )
    example_client.publishers.update(6, name="pub01.local", extra_fields={"lbroker_connect": False})

    assert sent_json(route) == {"name": "pub01.local", "lbrokerconnect": False}


@respx.mock
def test_publisher_bulk_upgrade_sends_string_ids(example_client: NetskopeClient) -> None:
    """publishers_bulk_request.publishers.id.items is {type: string}.

    Spec: npa_publishers.yaml:294-299, with the endpoint's own examples at
    :1230-1244 sending ``["12"]``.
    """
    route = respx.put(f"{_EXAMPLE_PUBLISHERS_URL}/bulk").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    example_client.publishers.bulk_upgrade([12, 15])

    assert sent_json(route) == {
        "publishers": {"apply": {"upgrade_request": True}, "id": ["12", "15"]}
    }


@respx.mock
def test_publisher_alerts_put_carries_selected_users(example_client: NetskopeClient) -> None:
    """publishers_alert_put_request requires all three keys.

    Spec: npa_publishers.yaml:589-594 for the required set and :627-629 for
    ``selectedUsers``, a comma-joined string.  The SDK could not send it at all.
    """
    route = respx.put(f"{_EXAMPLE_PUBLISHERS_URL}/alertsconfiguration").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    example_client.publishers.update_alerts_configuration(
        admin_users=["admin1@abc.com", "admin2@abc.com"],
        event_types=["CONNECTION_FAILED", "UPGRADE_STARTED"],
        selected_users=["abc@xyz.com", "def@xyz.com"],
    )

    assert sent_json(route) == {
        "adminUsers": ["admin1@abc.com", "admin2@abc.com"],
        "eventTypes": ["CONNECTION_FAILED", "UPGRADE_STARTED"],
        "selectedUsers": "abc@xyz.com,def@xyz.com",
    }


@respx.mock
@pytest.mark.parametrize("event_types", [[], ["UPGRADE_FAILED"] * 6])
def test_publisher_alerts_put_bounds_event_types(
    example_client: NetskopeClient, event_types: list[str]
) -> None:
    """eventTypes carries minItems: 1 / maxItems: 5 (npa_publishers.yaml:624-625)."""
    with pytest.raises(ValidationError, match="between 1 and 5"):
        example_client.publishers.update_alerts_configuration(event_types=event_types)
    assert len(respx.calls) == 0


def test_publisher_alerts_request_model_bounds_event_types() -> None:
    """The typed path enforces the same 1..5 bound (npa_publishers.yaml:624-625)."""

    def build(event_types: list[str]) -> PublisherAlertsConfigurationPatch:
        return PublisherAlertsConfigurationPatch(
            admin_users=["admin1@abc.com"],
            event_types=event_types,
            selected_users="abc@xyz.com",
        )

    build(["UPGRADE_FAILED"])
    with pytest.raises(PydanticValidationError, match="at most 5"):
        build(["UPGRADE_FAILED"] * 6)
    with pytest.raises(PydanticValidationError, match="at least 1"):
        build([])


def test_publisher_alerts_request_model_requires_every_declared_key() -> None:
    """``publishers_alert_put_request.required`` is all three (npa_publishers.yaml:591-594)."""
    for partial in (
        {},
        {"adminUsers": ["admin1@abc.com"]},
        {"adminUsers": ["admin1@abc.com"], "eventTypes": ["UPGRADE_FAILED"]},
        {"eventTypes": ["UPGRADE_FAILED"], "selectedUsers": "abc@xyz.com"},
    ):
        with pytest.raises(PydanticValidationError, match=r"[Ff]ield required"):
            PublisherAlertsConfigurationPatch.model_validate(partial)


def test_publisher_alerts_response_reads_selected_users() -> None:
    """publishers_alert_get_response.data declares selectedUsers (npa_publishers.yaml:580-582)."""
    config = PublisherAlertsConfiguration.model_validate(
        {
            "adminUsers": ["admin1@abc.com"],
            "eventTypes": ["CONNECTION_FAILED"],
            "selectedUsers": "abc@xyz.com,def@xyz.com",
        }
    )
    assert config.selected_users == "abc@xyz.com,def@xyz.com"


@respx.mock
def test_publisher_single_object_envelope_populates_id_and_name(
    example_client: NetskopeClient,
) -> None:
    """publisher_response.data names the record id/name, not publisher_id/publisher_name.

    Spec: npa_publishers.yaml:477-481 (``id``) and :493-496 (``name``), with
    the same spelling in publisher_bulk_item (:198, :214).  Every get/create/
    update used to parse to ``publisher_id=None``, so the module's own example
    (``create_registration_token(new_pub.publisher_id)``) passed ``None``.
    """
    respx.get(f"{_EXAMPLE_PUBLISHERS_URL}/6").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "id": 6,
                    "name": "pub01.local",
                    "common_name": "e2eabac9e9f715ff",
                    "lbrokerconnect": False,
                    "registered": True,
                    "status": "connected",
                    "upgrade_request": True,
                },
            },
        )
    )
    publisher = example_client.publishers.get(6)

    assert (publisher.publisher_id, publisher.publisher_name) == (6, "pub01.local")
    # upgrade_request (:537-539) and lbrokerconnect (:490-492), not the
    # publisher_upgrade_request / lbroker_proxy / sticky_ip_enabled the SDK
    # declared and the spec has nowhere.
    assert publisher.upgrade_request is True
    assert publisher.lbrokerconnect is False
    for absent in ("publisher_upgrade_request", "lbroker_proxy", "sticky_ip_enabled"):
        assert absent not in Publisher.model_fields


def test_publisher_list_item_keeps_its_own_spelling() -> None:
    """publishers_get_response keys the list item publisher_id/publisher_name.

    Spec: npa_publishers.yaml:812-818.  Both spellings must reach the same
    attributes.
    """
    publisher = Publisher.model_validate(
        {"publisher_id": 6, "publisher_name": "pub01.local", "status": "connected"}
    )
    assert (publisher.publisher_id, publisher.publisher_name) == (6, "pub01.local")


def test_publisher_status_enum_matches_the_spec_value() -> None:
    """The enum is exactly [connected, not registered] (npa_publishers.yaml:827-832)."""
    assert PublisherStatus.NOT_REGISTERED.value == "not registered"
    assert {member.value for member in PublisherStatus} == {"connected", "not registered"}


def test_publisher_app_reads_the_publisher_apps_response() -> None:
    """publishers_private_apps_response.data[] names id/name/private_app_protocol.

    Spec: npa_publishers.yaml:33 (``id``), :40 (``name``), :44
    (``private_app_protocol``), :30 (``host``).  Against those keys every
    record used to parse to all-``None``.
    """
    app = PublisherApp.model_validate(
        {
            "id": 3,
            "name": "[Web-Management]",
            "host": "192.168.1.1",
            "private_app_protocol": "https",
            "protocols": [{"port": "443", "transport": "tcp"}],
        }
    )
    assert (app.app_id, app.app_name, app.host) == (3, "[Web-Management]", "192.168.1.1")
    assert app.protocol == "https"


def test_publisher_release_declares_only_the_spec_fields() -> None:
    """release_item declares docker_tag, name and version (npa_publishers.yaml:950-961)."""
    assert set(PublisherRelease.model_fields) == {"version", "docker_tag", "release_type"}
    release = PublisherRelease.model_validate(
        {"docker_tag": "8690", "name": "Latest", "version": "117.0.0.8690"}
    )
    assert release.release_type == "Latest"
