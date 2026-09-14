"""Tests for client.publishers with mocked HTTP."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.core.pagination import Page
from netskope.exceptions import (
    NetskopeError,
    ResponseValidationError,
    ValidationError,
)
from netskope.models.publishers import (
    Publisher,
    PublisherAlertsConfiguration,
    PublisherAlertsConfigurationStatus,
    PublisherCreate,
    PublisherRelease,
    PublisherUpdate,
)
from tests.unit.resources.conftest import drain, sent_json

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
    def test_list_page_reports_a_total_that_contradicts_the_rows(
        self, client: NetskopeClient
    ) -> None:
        body = {"publishers": [{"publisher_id": n} for n in (1, 2, 3)], "total": 1}
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=body))
        page = client.publishers.list_page()
        assert [publisher.publisher_id for publisher in page.items] == [1, 2, 3]
        assert page.total == 1
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
    async def test_list_page_reports_a_total_that_contradicts_the_rows(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        body = {"publishers": [{"publisher_id": n} for n in (1, 2, 3)], "total": 1}
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=body))
        page = await aclient.publishers.list_page()
        assert [publisher.publisher_id for publisher in page.items] == [1, 2, 3]
        assert page.total == 1
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
