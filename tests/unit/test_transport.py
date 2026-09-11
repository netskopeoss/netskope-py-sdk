"""Tests for the HTTP transport and retry logic."""

from __future__ import annotations

import ssl
from dataclasses import replace
from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr

from netskope._config import NetskopeConfig
from netskope._retry import async_send_with_retries, send_with_retries
from netskope._transport import AsyncTransport, SyncTransport, _resolve_verify
from netskope.exceptions import (
    APIError,
    AuthenticationError,
    ConnectionError,
    NotFoundError,
    ServerError,
    TimeoutError,
    ValidationError,
)
from netskope.resources._base import AsyncResource, SyncResource


@pytest.fixture
def transport_config() -> NetskopeConfig:
    return NetskopeConfig(
        tenant="test.goskope.com",
        api_token=SecretStr("test-token"),
        timeout=5.0,
        max_retries=2,
        backoff_factor=0.01,
    )


class TestSyncTransport:
    """Tests for SyncTransport request handling."""

    @respx.mock
    def test_successful_get(self, transport_config: NetskopeConfig) -> None:
        respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(200, json={"data": "ok"})
        )
        transport = SyncTransport(transport_config)
        resp = transport.request("GET", "/api/v2/test")
        assert resp.status_code == 200
        assert resp.json()["data"] == "ok"
        transport.close()

    @respx.mock
    def test_auth_header_sent(self, transport_config: NetskopeConfig) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(200, json={})
        )
        transport = SyncTransport(transport_config)
        transport.request("GET", "/api/v2/test")
        assert route.calls[0].request.headers["netskope-api-token"] == "test-token"
        transport.close()

    @respx.mock
    def test_user_agent_header(self, transport_config: NetskopeConfig) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(200, json={})
        )
        transport = SyncTransport(transport_config)
        transport.request("GET", "/api/v2/test")
        ua = route.calls[0].request.headers["user-agent"]
        assert "netskope-python-sdk" in ua
        transport.close()

    @respx.mock
    def test_401_raises_authentication_error(self, transport_config: NetskopeConfig) -> None:
        respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(401, json={"message": "Unauthorized"})
        )
        transport = SyncTransport(transport_config)
        with pytest.raises(AuthenticationError):
            transport.request("GET", "/api/v2/test")
        transport.close()

    @respx.mock
    def test_404_raises_not_found(self, transport_config: NetskopeConfig) -> None:
        respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(404, json={"message": "Not found"})
        )
        transport = SyncTransport(transport_config)
        with pytest.raises(NotFoundError):
            transport.request("GET", "/api/v2/test")
        transport.close()

    @respx.mock
    def test_retry_on_500(self, transport_config: NetskopeConfig) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test")
        route.side_effect = [
            httpx.Response(500, json={"message": "Internal error"}),
            httpx.Response(500, json={"message": "Internal error"}),
            httpx.Response(200, json={"data": "ok"}),
        ]
        transport = SyncTransport(transport_config)
        resp = transport.request("GET", "/api/v2/test")
        assert resp.status_code == 200
        assert route.call_count == 3
        transport.close()

    @respx.mock
    def test_retry_exhausted_raises(self, transport_config: NetskopeConfig) -> None:
        respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(500, json={"message": "Error"})
        )
        transport = SyncTransport(transport_config)
        with pytest.raises(ServerError):
            transport.request("GET", "/api/v2/test")
        transport.close()

    @respx.mock
    def test_retry_on_429(self, transport_config: NetskopeConfig) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test")
        route.side_effect = [
            httpx.Response(429, json={"message": "Rate limit"}, headers={"retry-after": "0"}),
            httpx.Response(200, json={"data": "ok"}),
        ]
        transport = SyncTransport(transport_config)
        resp = transport.request("GET", "/api/v2/test")
        assert resp.status_code == 200
        transport.close()

    @respx.mock
    def test_post_with_json(self, transport_config: NetskopeConfig) -> None:
        respx.post("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(200, json={"created": True})
        )
        transport = SyncTransport(transport_config)
        resp = transport.request("POST", "/api/v2/test", json={"name": "test"})
        assert resp.json()["created"] is True
        transport.close()

    @respx.mock
    def test_params_forwarded(self, transport_config: NetskopeConfig) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(200, json={})
        )
        transport = SyncTransport(transport_config)
        transport.request("GET", "/api/v2/test", params={"limit": 10, "offset": 0})
        assert "limit=10" in str(route.calls[0].request.url)
        transport.close()

    @pytest.mark.parametrize("use_cookie", [False, True])
    def test_borrowed_defaults_cannot_change_request(
        self, transport_config: NetskopeConfig, use_cookie: bool
    ) -> None:
        if use_cookie:
            transport_config = replace(
                transport_config, api_token=None, ci_session=SecretStr("sdk-cookie")
            )
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={})

        with httpx.Client(
            base_url="https://other.example/",
            headers={"Netskope-Api-Token": "other-token", "X-Other-Secret": "secret"},
            cookies={"ci_session": "other-cookie"},
            params={"other_secret": "secret"},
            auth=("other-user", "other-password"),
            timeout=91,
            transport=httpx.MockTransport(respond),
        ) as http_client:
            transport = SyncTransport(transport_config, http_client=http_client)
            transport.request("GET", "/api/v2/test", params={"limit": 2})
            transport.close()
            assert not http_client.is_closed
            assert http_client.headers["netskope-api-token"] == "other-token"
            assert http_client.cookies["ci_session"] == "other-cookie"

        request = requests[0]
        assert request.url == "https://test.goskope.com/api/v2/test?limit=2"
        assert "authorization" not in request.headers
        assert "x-other-secret" not in request.headers
        assert request.extensions["timeout"] == httpx.Timeout(5).as_dict()
        if use_cookie:
            assert "netskope-api-token" not in request.headers
            assert request.headers["cookie"] == "ci_session=sdk-cookie"
        else:
            assert request.headers["netskope-api-token"] == "test-token"
            assert "cookie" not in request.headers

    @pytest.mark.parametrize(
        "path",
        [
            "https://other.example/api/v2/test",
            "//other.example/api/v2/test",
            "http://test.goskope.com/api/v2/test",
            "https://user:password@test.goskope.com/api/v2/test",
        ],
    )
    def test_rejects_unsafe_destination(self, transport_config: NetskopeConfig, path: str) -> None:
        def unexpected_request(request: httpx.Request) -> httpx.Response:
            pytest.fail("An unsafe request reached the network")

        with httpx.Client(transport=httpx.MockTransport(unexpected_request)) as http_client:
            transport = SyncTransport(transport_config, http_client=http_client)
            with pytest.raises(ValidationError):
                transport.request("GET", path)
            transport.close()

    def test_borrowed_redirect_default_is_disabled(self, transport_config: NetskopeConfig) -> None:
        requests: list[httpx.Request] = []

        def redirect(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(302, headers={"location": "https://other.example/"})

        with httpx.Client(
            follow_redirects=True, transport=httpx.MockTransport(redirect)
        ) as http_client:
            transport = SyncTransport(transport_config, http_client=http_client)
            with pytest.raises(APIError):
                transport.request("GET", "/api/v2/test")
            transport.close()
        assert len(requests) == 1

    @respx.mock
    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    @pytest.mark.parametrize("status", [429, 500])
    def test_mutations_do_not_retry(
        self, transport_config: NetskopeConfig, method: str, status: int
    ) -> None:
        route = respx.route(method=method, url="https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(status, json={"message": "failed"})
        )
        transport = SyncTransport(transport_config)
        with pytest.raises(APIError):
            transport.request(method, "/api/v2/test", json={"name": "new"})
        assert route.call_count == 1
        transport.close()

    @respx.mock
    @pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
    def test_timeout_retry_depends_on_operation(
        self, transport_config: NetskopeConfig, method: str
    ) -> None:
        route = respx.route(method=method, url="https://test.goskope.com/api/v2/test").mock(
            side_effect=httpx.ReadTimeout("Response timed out")
        )
        transport = SyncTransport(transport_config)
        with pytest.raises(TimeoutError) as exc_info:
            transport.request(method, "/api/v2/test")
        assert isinstance(exc_info.value.__cause__, httpx.ReadTimeout)
        assert route.call_count == (3 if method == "GET" else 1)
        transport.close()

    @respx.mock
    def test_safe_post_consumed_by_resource_helper(self, transport_config: NetskopeConfig) -> None:
        route = respx.post("https://test.goskope.com/api/v2/query").mock(
            side_effect=[httpx.Response(503), httpx.Response(200, json={"data": []})]
        )
        transport = SyncTransport(transport_config)
        result = SyncResource(transport)._post(
            "/api/v2/query", json={"filter": "active"}, retry_safe=True, limit=3
        )
        assert result == {"data": []}
        assert route.call_count == 2
        assert all(dict(call.request.url.params) == {"limit": "3"} for call in route.calls)
        assert route.calls[0].request.content == route.calls[1].request.content
        transport.close()

    @respx.mock
    def test_explicitly_disable_safe_method_retry(self, transport_config: NetskopeConfig) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(503)
        )
        transport = SyncTransport(transport_config)
        with pytest.raises(ServerError):
            transport.request("GET", "/api/v2/test", retry_safe=False)
        assert route.call_count == 1
        transport.close()

    @pytest.mark.parametrize("status", [200, 503])
    def test_multipart_body_sent_once_without_forced_buffering(
        self, transport_config: NetskopeConfig, status: int
    ) -> None:
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            assert b"file contents" in request.content
            return httpx.Response(status)

        with httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
            transport = SyncTransport(transport_config, http_client=http_client)
            if status == 200:
                assert (
                    transport.request(
                        "POST",
                        "/api/v2/upload",
                        files={"file": ("test.txt", b"file contents")},
                        retry_safe=True,
                    ).status_code
                    == 200
                )
            else:
                with pytest.raises(ServerError):
                    transport.request(
                        "POST",
                        "/api/v2/upload",
                        files={"file": ("test.txt", b"file contents")},
                        retry_safe=True,
                    )
            transport.close()
        assert len(requests) == 1

    @respx.mock
    def test_empty_retry_status_set_disables_status_retries(
        self, transport_config: NetskopeConfig
    ) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(503)
        )
        transport = SyncTransport(replace(transport_config, retry_on_status=frozenset()))
        with pytest.raises(ServerError):
            transport.request("GET", "/api/v2/test")
        assert route.call_count == 1
        transport.close()

    @respx.mock
    def test_network_error_retry_follows_the_operation_declaration(
        self, transport_config: NetskopeConfig
    ) -> None:
        route = respx.post("https://test.goskope.com/api/v2/query").mock(
            side_effect=[
                httpx.ConnectError("Connection reset"),
                httpx.Response(200, json={"data": []}),
            ]
        )
        transport = SyncTransport(transport_config)
        response = transport.request(
            "POST", "/api/v2/query", json={"filter": "active"}, retry_safe=True
        )
        assert response.json() == {"data": []}
        assert route.call_count == 2
        assert route.calls[0].request.content == route.calls[1].request.content
        transport.close()

    @respx.mock
    def test_default_post_does_not_retry_a_network_error(
        self, transport_config: NetskopeConfig
    ) -> None:
        route = respx.post("https://test.goskope.com/api/v2/query").mock(
            side_effect=httpx.ConnectError("Connection reset")
        )
        transport = SyncTransport(transport_config)
        with pytest.raises(ConnectionError):
            transport.request("POST", "/api/v2/query", json={"filter": "active"})
        assert route.call_count == 1
        transport.close()

    def test_retries_preserve_request_extensions(self, transport_config: NetskopeConfig) -> None:
        requests: list[httpx.Request] = []
        responses: list[httpx.Response] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            response = httpx.Response(503 if len(requests) == 1 else 200)
            responses.append(response)
            return response

        extensions = {"timeout": httpx.Timeout(7).as_dict(), "custom": "trace-context"}
        request = httpx.Request(
            "GET", "https://test.goskope.com/api/v2/test", extensions=extensions
        )
        with httpx.Client(transport=httpx.MockTransport(respond), timeout=91) as http_client:
            assert send_with_retries(http_client, request, transport_config).status_code == 200
        assert len(requests) == 2
        assert all(request.extensions == extensions for request in requests)
        assert responses[0].is_closed


class TestAsyncTransport:
    async def test_borrowed_defaults_and_cookie_auth(
        self, transport_config: NetskopeConfig
    ) -> None:
        config = replace(transport_config, api_token=None, ci_session=SecretStr("sdk-cookie"))
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={})

        async with httpx.AsyncClient(
            base_url="https://other.example/",
            headers={"Netskope-Api-Token": "other-token"},
            cookies={"ci_session": "other-cookie"},
            params={"other_secret": "secret"},
            auth=("other-user", "other-password"),
            timeout=91,
            transport=httpx.MockTransport(respond),
        ) as http_client:
            transport = AsyncTransport(config, http_client=http_client)
            await transport.request("GET", "/api/v2/test", params={"limit": 2})
            await transport.close()
            assert not http_client.is_closed
            assert http_client.cookies["ci_session"] == "other-cookie"

        request = requests[0]
        assert request.url == "https://test.goskope.com/api/v2/test?limit=2"
        assert request.headers["cookie"] == "ci_session=sdk-cookie"
        assert "netskope-api-token" not in request.headers
        assert "authorization" not in request.headers
        assert request.extensions["timeout"] == httpx.Timeout(5).as_dict()

    @respx.mock
    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    async def test_mutations_do_not_retry(
        self, transport_config: NetskopeConfig, method: str
    ) -> None:
        route = respx.route(method=method, url="https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(503)
        )
        transport = AsyncTransport(transport_config)
        with pytest.raises(ServerError):
            await transport.request(method, "/api/v2/test", json={"name": "new"})
        assert route.call_count == 1
        await transport.close()

    @respx.mock
    async def test_safe_post_consumed_by_resource_helper(
        self, transport_config: NetskopeConfig
    ) -> None:
        route = respx.post("https://test.goskope.com/api/v2/query").mock(
            side_effect=[httpx.Response(503), httpx.Response(200, json={"data": []})]
        )
        transport = AsyncTransport(transport_config)
        result = await AsyncResource(transport)._post(
            "/api/v2/query", json={"filter": "active"}, retry_safe=True, limit=3
        )
        assert result == {"data": []}
        assert route.call_count == 2
        assert all(dict(call.request.url.params) == {"limit": "3"} for call in route.calls)
        await transport.close()

    @respx.mock
    async def test_mutation_timeout_not_retried(self, transport_config: NetskopeConfig) -> None:
        route = respx.post("https://test.goskope.com/api/v2/test").mock(
            side_effect=httpx.WriteTimeout("Write timed out")
        )
        transport = AsyncTransport(transport_config)
        with pytest.raises(TimeoutError):
            await transport.request("POST", "/api/v2/test", json={"name": "new"})
        assert route.call_count == 1
        await transport.close()

    @respx.mock
    async def test_connection_failure_is_translated(self, transport_config: NetskopeConfig) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )
        transport = AsyncTransport(transport_config)
        with pytest.raises(ConnectionError):
            await transport.request("GET", "/api/v2/test")
        assert route.call_count == 3
        await transport.close()

    @respx.mock
    async def test_empty_retry_status_set_disables_status_retries(
        self, transport_config: NetskopeConfig
    ) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(503)
        )
        transport = AsyncTransport(replace(transport_config, retry_on_status=frozenset()))
        with pytest.raises(ServerError):
            await transport.request("GET", "/api/v2/test")
        assert route.call_count == 1
        await transport.close()

    @respx.mock
    async def test_network_error_retry_follows_the_operation_declaration(
        self, transport_config: NetskopeConfig
    ) -> None:
        route = respx.post("https://test.goskope.com/api/v2/query").mock(
            side_effect=[
                httpx.ConnectError("Connection reset"),
                httpx.Response(200, json={"data": []}),
            ]
        )
        transport = AsyncTransport(transport_config)
        response = await transport.request(
            "POST", "/api/v2/query", json={"filter": "active"}, retry_safe=True
        )
        assert response.json() == {"data": []}
        assert route.call_count == 2
        assert route.calls[0].request.content == route.calls[1].request.content
        await transport.close()

    @respx.mock
    async def test_default_post_does_not_retry_a_network_error(
        self, transport_config: NetskopeConfig
    ) -> None:
        route = respx.post("https://test.goskope.com/api/v2/query").mock(
            side_effect=httpx.ConnectError("Connection reset")
        )
        transport = AsyncTransport(transport_config)
        with pytest.raises(ConnectionError):
            await transport.request("POST", "/api/v2/query", json={"filter": "active"})
        assert route.call_count == 1
        await transport.close()

    async def test_streaming_body_not_retried(self, transport_config: NetskopeConfig) -> None:
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            assert b"file contents" in request.content
            return httpx.Response(503)

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
            transport = AsyncTransport(transport_config, http_client=http_client)
            with pytest.raises(ServerError):
                await transport.request(
                    "POST",
                    "/api/v2/upload",
                    files={"file": ("test.txt", b"file contents")},
                    retry_safe=True,
                )
            await transport.close()
        assert len(requests) == 1

    @pytest.mark.parametrize(
        "path",
        [
            "https://other.example/api/v2/test",
            "//other.example/api/v2/test",
            "http://test.goskope.com/api/v2/test",
            "https://user:password@test.goskope.com/api/v2/test",
        ],
    )
    async def test_rejects_unsafe_destination(
        self, transport_config: NetskopeConfig, path: str
    ) -> None:
        def unexpected_request(request: httpx.Request) -> httpx.Response:
            pytest.fail("An unsafe request reached the network")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(unexpected_request)
        ) as http_client:
            transport = AsyncTransport(transport_config, http_client=http_client)
            with pytest.raises(ValidationError):
                await transport.request("GET", path)
            await transport.close()

    async def test_borrowed_redirect_default_is_disabled(
        self, transport_config: NetskopeConfig
    ) -> None:
        requests: list[httpx.Request] = []

        def redirect(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(302, headers={"location": "https://other.example/"})

        async with httpx.AsyncClient(
            follow_redirects=True, transport=httpx.MockTransport(redirect)
        ) as http_client:
            transport = AsyncTransport(transport_config, http_client=http_client)
            with pytest.raises(APIError):
                await transport.request("GET", "/api/v2/test")
            await transport.close()
        assert len(requests) == 1

    async def test_retries_preserve_request_extensions(
        self, transport_config: NetskopeConfig
    ) -> None:
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(503 if len(requests) == 1 else 200)

        extensions = {"timeout": httpx.Timeout(7).as_dict(), "custom": "trace-context"}
        request = httpx.Request(
            "GET", "https://test.goskope.com/api/v2/test", extensions=extensions
        )
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond), timeout=91
        ) as http_client:
            response = await async_send_with_retries(http_client, request, transport_config)
            assert response.status_code == 200
        assert len(requests) == 2
        assert all(request.extensions == extensions for request in requests)


def _config_with_verify(verify: bool | str) -> NetskopeConfig:
    return NetskopeConfig(
        tenant="test.goskope.com",
        api_token=SecretStr("test-token"),
        verify=verify,
    )


def _ca_bundle_path() -> str:
    import certifi

    return certifi.where()


class TestVerify:
    """Tests for SSL verification wiring into httpx clients."""

    def test_resolve_verify_true_passthrough(self) -> None:
        assert _resolve_verify(_config_with_verify(True)) is True

    def test_resolve_verify_false_passthrough(self) -> None:
        assert _resolve_verify(_config_with_verify(False)) is False

    def test_resolve_verify_path_builds_ssl_context(self) -> None:
        resolved = _resolve_verify(_config_with_verify(_ca_bundle_path()))
        assert isinstance(resolved, ssl.SSLContext)

    def _capture_client_kwargs(self, monkeypatch: pytest.MonkeyPatch, attr: str) -> dict[str, Any]:
        captured: dict[str, Any] = {}
        real_cls = getattr(httpx, attr)

        def fake_client(**kwargs: Any) -> Any:
            captured.update(kwargs)
            return real_cls(**kwargs)

        monkeypatch.setattr(f"netskope._transport.httpx.{attr}", fake_client)
        return captured

    def test_sync_client_receives_verify_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = self._capture_client_kwargs(monkeypatch, "Client")
        transport = SyncTransport(_config_with_verify(False))
        assert captured["verify"] is False
        transport.close()

    def test_sync_client_receives_verify_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = self._capture_client_kwargs(monkeypatch, "Client")
        transport = SyncTransport(_config_with_verify(True))
        assert captured["verify"] is True
        transport.close()

    def test_sync_client_receives_ssl_context_for_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = self._capture_client_kwargs(monkeypatch, "Client")
        transport = SyncTransport(_config_with_verify(_ca_bundle_path()))
        assert isinstance(captured["verify"], ssl.SSLContext)
        transport.close()

    async def test_async_client_receives_verify_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = self._capture_client_kwargs(monkeypatch, "AsyncClient")
        transport = AsyncTransport(_config_with_verify(False))
        assert captured["verify"] is False
        await transport.close()

    async def test_async_client_receives_ssl_context_for_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = self._capture_client_kwargs(monkeypatch, "AsyncClient")
        transport = AsyncTransport(_config_with_verify(_ca_bundle_path()))
        assert isinstance(captured["verify"], ssl.SSLContext)
        await transport.close()
