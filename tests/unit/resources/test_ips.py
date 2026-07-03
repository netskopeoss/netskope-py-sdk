"""Tests for the IPS resource with mocked HTTP.

Pins the wire shapes from the ms-ips gateway OpenAPI spec:

- GET/PATCH ``/ips/status`` — per-traffic-type booleans (web/nonweb/npa).
- GET/PATCH ``/ips/allowlist`` — ``src_ids``/``domain``/``dst_ids`` arrays
  (NOT the ``{"data": {"ip": ...}}`` POST shape the CLI used).
- GET ``/ips/signaturereferencelist`` — ``limit``/``offset``/``reference``
  query params; ``data`` is a list of reference strings.
- POST ``/ips/getsignaturelist`` — paging plus a nested ``filter`` object.
- GET/PUT ``/ips/alertonlymode`` — ``{"enabled": bool}``.
- GET/PUT ``/ips/signatureoverrides`` and POST
  ``/ips/deletesignatureoverrides`` — ``sig_id`` arrays.
- GET/PATCH ``/ips/notificationtemplate`` — ``web.template_file_name``.
- GET/PATCH ``/ips/threathuntingconfig`` — nested ``{"enabled": bool}``.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.resources.ips import AsyncIpsResource, IpsResource
from tests.unit.resources.conftest import sent_json

_STATUS_URL = "https://t.goskope.com/api/v2/ips/status"
_ALLOWLIST_URL = "https://t.goskope.com/api/v2/ips/allowlist"
_SIG_REF_URL = "https://t.goskope.com/api/v2/ips/signaturereferencelist"
_SIG_SEARCH_URL = "https://t.goskope.com/api/v2/ips/getsignaturelist"
_ALERT_ONLY_URL = "https://t.goskope.com/api/v2/ips/alertonlymode"
_OVERRIDES_URL = "https://t.goskope.com/api/v2/ips/signatureoverrides"
_DELETE_OVERRIDES_URL = "https://t.goskope.com/api/v2/ips/deletesignatureoverrides"
_TEMPLATE_URL = "https://t.goskope.com/api/v2/ips/notificationtemplate"
_THREAT_HUNTING_URL = "https://t.goskope.com/api/v2/ips/threathuntingconfig"

# Response bodies matching the gateway spec examples.
_STATUS_BODY = {"status": "Success", "data": {"web": True, "nonweb": True, "npa": False}}
_ALLOWLIST_BODY = {
    "status": "Success",
    "data": {
        "src_ids": ["69c0661d-3e5d-49d6-88ee-3c1390955004"],
        "domain": ["example.com"],
        "dst_ids": ["c9c0661d-3e5d-49d6-88ee-3c1390955004"],
    },
}
_SIG_REF_BODY = {"status": "Success", "data": ["bid:15208", "bid:38282", "bid:39183"]}
_SIG_SEARCH_BODY = {
    "status": "Success",
    "data": {
        "total": 1,
        "signature": [
            {
                "reference": "cve:cve-2012-3993",
                "cvss_severity": "high",
                "traffic_type": ["web", "nonweb"],
                "sig_id": "140136",
                "name": "MALWARE OTHER Firefox Proto crmf Request",
                "default_action": "reject",
                "published_date": "2024-10-28 13:09:01",
            }
        ],
    },
}
_ALERT_ONLY_BODY = {"status": "Success", "data": {"enabled": True}}
_OVERRIDES_BODY = {
    "status": "Success",
    "data": {
        "total": 1,
        "overrides": [
            {
                "sig_id": "308",
                "name": "SERVER-OTHER NextFTP client overflow",
                "traffic_type": ["web", "nonweb"],
                "default_action": "alert",
                "status": "enabled",
                "action": "alert",
                "modified_at": "1696478084",
                "modified_by": "user@netskope.com",
            }
        ],
    },
}
_TEMPLATE_BODY = {"status": "Success", "data": {"web": {"template_file_name": "11.html"}}}
_THREAT_HUNTING_BODY = {
    "status": "Success",
    "data": {"beacon_detection": {"enabled": False}, "html_smuggling": {"enabled": False}},
}
_STATUS_ONLY_BODY = {"status": "Success"}


def _ips(client: NetskopeClient) -> IpsResource:
    return IpsResource(client._transport)


def _aips(aclient: AsyncNetskopeClient) -> AsyncIpsResource:
    return AsyncIpsResource(aclient._transport)


class TestIpsStatus:
    """Tests for IpsResource.status / update_status."""

    @respx.mock
    def test_status(self, client: NetskopeClient) -> None:
        route = respx.get(_STATUS_URL).mock(return_value=httpx.Response(200, json=_STATUS_BODY))
        result = _ips(client).status()

        assert result == _STATUS_BODY
        request = route.calls.last.request
        assert request.method == "GET"
        assert dict(request.url.params) == {}

    @respx.mock
    def test_update_status_sends_only_provided_flags(self, client: NetskopeClient) -> None:
        route = respx.patch(_STATUS_URL).mock(return_value=httpx.Response(200, json=_STATUS_BODY))
        result = _ips(client).update_status(web=True, npa=False)

        assert result == _STATUS_BODY
        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"web": True, "npa": False}

    @respx.mock
    def test_update_status_all_flags(self, client: NetskopeClient) -> None:
        route = respx.patch(_STATUS_URL).mock(return_value=httpx.Response(200, json=_STATUS_BODY))
        _ips(client).update_status(web=True, nonweb=False, npa=True)

        assert sent_json(route) == {"web": True, "nonweb": False, "npa": True}

    @respx.mock
    def test_update_status_requires_a_flag_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _ips(client).update_status()
        assert len(respx.calls) == 0


class TestIpsAllowlist:
    """Tests for IpsResource.list_allowlist / update_allowlist."""

    @respx.mock
    def test_list_allowlist(self, client: NetskopeClient) -> None:
        route = respx.get(_ALLOWLIST_URL).mock(
            return_value=httpx.Response(200, json=_ALLOWLIST_BODY)
        )
        result = _ips(client).list_allowlist()

        assert result == _ALLOWLIST_BODY
        request = route.calls.last.request
        assert request.method == "GET"
        assert dict(request.url.params) == {}

    @respx.mock
    def test_update_allowlist_patches_provided_fields(self, client: NetskopeClient) -> None:
        route = respx.patch(_ALLOWLIST_URL).mock(
            return_value=httpx.Response(200, json=_ALLOWLIST_BODY)
        )
        result = _ips(client).update_allowlist(domain=["example.com"])

        assert result == _ALLOWLIST_BODY
        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"domain": ["example.com"]}

    @respx.mock
    def test_update_allowlist_all_fields(self, client: NetskopeClient) -> None:
        route = respx.patch(_ALLOWLIST_URL).mock(
            return_value=httpx.Response(200, json=_ALLOWLIST_BODY)
        )
        _ips(client).update_allowlist(
            src_ids=["69c0661d-3e5d-49d6-88ee-3c1390955004"],
            domain=["example.com"],
            dst_ids=["c9c0661d-3e5d-49d6-88ee-3c1390955004"],
        )

        assert sent_json(route) == {
            "src_ids": ["69c0661d-3e5d-49d6-88ee-3c1390955004"],
            "domain": ["example.com"],
            "dst_ids": ["c9c0661d-3e5d-49d6-88ee-3c1390955004"],
        }

    @respx.mock
    def test_update_allowlist_empty_list_clears_field(self, client: NetskopeClient) -> None:
        route = respx.patch(_ALLOWLIST_URL).mock(
            return_value=httpx.Response(200, json=_ALLOWLIST_BODY)
        )
        _ips(client).update_allowlist(domain=[])

        assert sent_json(route) == {"domain": []}

    @respx.mock
    def test_update_allowlist_requires_a_field_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _ips(client).update_allowlist()
        assert len(respx.calls) == 0


class TestIpsSignatures:
    """Tests for IpsResource.list_signatures / search_signatures."""

    @respx.mock
    def test_list_signatures_without_params(self, client: NetskopeClient) -> None:
        route = respx.get(_SIG_REF_URL).mock(return_value=httpx.Response(200, json=_SIG_REF_BODY))
        result = _ips(client).list_signatures()

        assert result == _SIG_REF_BODY
        assert result["data"] == ["bid:15208", "bid:38282", "bid:39183"]
        request = route.calls.last.request
        assert request.method == "GET"
        assert dict(request.url.params) == {}

    @respx.mock
    def test_list_signatures_with_params(self, client: NetskopeClient) -> None:
        route = respx.get(_SIG_REF_URL).mock(return_value=httpx.Response(200, json=_SIG_REF_BODY))
        _ips(client).list_signatures(limit=32, offset=3, reference="bid")

        params = dict(route.calls.last.request.url.params)
        assert params == {"limit": "32", "offset": "3", "reference": "bid"}

    @respx.mock
    def test_list_signatures_zero_offset_is_sent(self, client: NetskopeClient) -> None:
        route = respx.get(_SIG_REF_URL).mock(return_value=httpx.Response(200, json=_SIG_REF_BODY))
        _ips(client).list_signatures(offset=0)

        assert dict(route.calls.last.request.url.params) == {"offset": "0"}

    @respx.mock
    def test_search_signatures_without_filters(self, client: NetskopeClient) -> None:
        route = respx.post(_SIG_SEARCH_URL).mock(
            return_value=httpx.Response(200, json=_SIG_SEARCH_BODY)
        )
        result = _ips(client).search_signatures(limit=10, offset=0)

        assert result == _SIG_SEARCH_BODY
        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {"limit": 10, "offset": 0}

    @respx.mock
    def test_search_signatures_with_filters(self, client: NetskopeClient) -> None:
        route = respx.post(_SIG_SEARCH_URL).mock(
            return_value=httpx.Response(200, json=_SIG_SEARCH_BODY)
        )
        _ips(client).search_signatures(
            limit=32,
            reference=["bid:15208", "cve:cve-2012-3993"],
            cvss_severity=["critical", "high"],
            traffic_type=["web", "nonweb"],
            sig_id="140136",
            name="MALWARE OTHER Firefox Proto crmf Request",
            keyword="Firefox",
        )

        assert sent_json(route) == {
            "limit": 32,
            "filter": {
                "reference": ["bid:15208", "cve:cve-2012-3993"],
                "cvss_severity": ["critical", "high"],
                "traffic_type": ["web", "nonweb"],
                "sig_id": "140136",
                "name": "MALWARE OTHER Firefox Proto crmf Request",
                "keyword": "Firefox",
            },
        }

    @respx.mock
    def test_search_signatures_invalid_traffic_type_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _ips(client).search_signatures(traffic_type=["email"])
        assert len(respx.calls) == 0


class TestIpsAlertOnlyMode:
    """Tests for IpsResource.get_alert_only_mode / set_alert_only_mode."""

    @respx.mock
    def test_get_alert_only_mode(self, client: NetskopeClient) -> None:
        route = respx.get(_ALERT_ONLY_URL).mock(
            return_value=httpx.Response(200, json=_ALERT_ONLY_BODY)
        )
        result = _ips(client).get_alert_only_mode()

        assert result == _ALERT_ONLY_BODY
        assert route.calls.last.request.method == "GET"

    @respx.mock
    def test_set_alert_only_mode(self, client: NetskopeClient) -> None:
        route = respx.put(_ALERT_ONLY_URL).mock(
            return_value=httpx.Response(200, json=_STATUS_ONLY_BODY)
        )
        result = _ips(client).set_alert_only_mode(True)

        assert result == _STATUS_ONLY_BODY
        assert route.calls.last.request.method == "PUT"
        assert sent_json(route) == {"enabled": True}

    @respx.mock
    def test_set_alert_only_mode_disabled(self, client: NetskopeClient) -> None:
        route = respx.put(_ALERT_ONLY_URL).mock(
            return_value=httpx.Response(200, json=_STATUS_ONLY_BODY)
        )
        _ips(client).set_alert_only_mode(False)

        assert sent_json(route) == {"enabled": False}


class TestIpsSignatureOverrides:
    """Tests for signature override list/update/delete."""

    @respx.mock
    def test_list_signature_overrides(self, client: NetskopeClient) -> None:
        route = respx.get(_OVERRIDES_URL).mock(
            return_value=httpx.Response(200, json=_OVERRIDES_BODY)
        )
        result = _ips(client).list_signature_overrides(limit=10, offset=0)

        assert result == _OVERRIDES_BODY
        params = dict(route.calls.last.request.url.params)
        assert params == {"limit": "10", "offset": "0"}

    @respx.mock
    def test_list_signature_overrides_without_params(self, client: NetskopeClient) -> None:
        route = respx.get(_OVERRIDES_URL).mock(
            return_value=httpx.Response(200, json=_OVERRIDES_BODY)
        )
        _ips(client).list_signature_overrides()

        assert dict(route.calls.last.request.url.params) == {}

    @respx.mock
    def test_update_signature_overrides(self, client: NetskopeClient) -> None:
        route = respx.put(_OVERRIDES_URL).mock(
            return_value=httpx.Response(200, json=_STATUS_ONLY_BODY)
        )
        result = _ips(client).update_signature_overrides(["117", "308"], "disabled")

        assert result == _STATUS_ONLY_BODY
        assert route.calls.last.request.method == "PUT"
        assert sent_json(route) == {"sig_id": ["117", "308"], "override": "disabled"}

    @respx.mock
    def test_update_signature_overrides_validation_no_http(self, client: NetskopeClient) -> None:
        ips = _ips(client)
        with pytest.raises(ValidationError):
            ips.update_signature_overrides([], "disabled")  # empty sig_ids
        with pytest.raises(ValidationError):
            ips.update_signature_overrides(["117"], "block")  # bad override action
        assert len(respx.calls) == 0

    @respx.mock
    def test_delete_signature_overrides(self, client: NetskopeClient) -> None:
        route = respx.post(_DELETE_OVERRIDES_URL).mock(
            return_value=httpx.Response(200, json=_STATUS_ONLY_BODY)
        )
        result = _ips(client).delete_signature_overrides(["117", "308"])

        assert result == _STATUS_ONLY_BODY
        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {"sig_id": ["117", "308"]}

    @respx.mock
    def test_delete_signature_overrides_requires_ids_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _ips(client).delete_signature_overrides([])
        assert len(respx.calls) == 0


class TestIpsNotificationTemplate:
    """Tests for the user notification template endpoints."""

    @respx.mock
    def test_get_notification_template(self, client: NetskopeClient) -> None:
        route = respx.get(_TEMPLATE_URL).mock(return_value=httpx.Response(200, json=_TEMPLATE_BODY))
        result = _ips(client).get_notification_template()

        assert result == _TEMPLATE_BODY
        assert route.calls.last.request.method == "GET"

    @respx.mock
    def test_update_notification_template(self, client: NetskopeClient) -> None:
        route = respx.patch(_TEMPLATE_URL).mock(
            return_value=httpx.Response(200, json=_TEMPLATE_BODY)
        )
        result = _ips(client).update_notification_template("11.html")

        assert result == _TEMPLATE_BODY
        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"web": {"template_file_name": "11.html"}}

    @respx.mock
    def test_update_notification_template_requires_name_no_http(
        self, client: NetskopeClient
    ) -> None:
        with pytest.raises(ValidationError):
            _ips(client).update_notification_template("")
        assert len(respx.calls) == 0


class TestIpsThreatHunting:
    """Tests for the threat hunting config endpoints."""

    @respx.mock
    def test_get_threat_hunting_config(self, client: NetskopeClient) -> None:
        route = respx.get(_THREAT_HUNTING_URL).mock(
            return_value=httpx.Response(200, json=_THREAT_HUNTING_BODY)
        )
        result = _ips(client).get_threat_hunting_config()

        assert result == _THREAT_HUNTING_BODY
        assert route.calls.last.request.method == "GET"

    @respx.mock
    def test_update_threat_hunting_config_wraps_enabled(self, client: NetskopeClient) -> None:
        route = respx.patch(_THREAT_HUNTING_URL).mock(
            return_value=httpx.Response(200, json=_THREAT_HUNTING_BODY)
        )
        result = _ips(client).update_threat_hunting_config(beacon_detection=True)

        assert result == _THREAT_HUNTING_BODY
        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"beacon_detection": {"enabled": True}}

    @respx.mock
    def test_update_threat_hunting_config_both_flags(self, client: NetskopeClient) -> None:
        route = respx.patch(_THREAT_HUNTING_URL).mock(
            return_value=httpx.Response(200, json=_THREAT_HUNTING_BODY)
        )
        _ips(client).update_threat_hunting_config(beacon_detection=False, html_smuggling=True)

        assert sent_json(route) == {
            "beacon_detection": {"enabled": False},
            "html_smuggling": {"enabled": True},
        }

    @respx.mock
    def test_update_threat_hunting_config_requires_a_flag_no_http(
        self, client: NetskopeClient
    ) -> None:
        with pytest.raises(ValidationError):
            _ips(client).update_threat_hunting_config()
        assert len(respx.calls) == 0


class TestAsyncIpsStatus:
    """Tests for AsyncIpsResource.status / update_status."""

    @respx.mock
    async def test_status(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_STATUS_URL).mock(return_value=httpx.Response(200, json=_STATUS_BODY))
        result = await _aips(aclient).status()

        assert result == _STATUS_BODY
        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_update_status(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(_STATUS_URL).mock(return_value=httpx.Response(200, json=_STATUS_BODY))
        await _aips(aclient).update_status(nonweb=True)

        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"nonweb": True}

    @respx.mock
    async def test_update_status_requires_a_flag(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await _aips(aclient).update_status()
        assert len(respx.calls) == 0


class TestAsyncIpsAllowlist:
    """Tests for AsyncIpsResource.list_allowlist / update_allowlist."""

    @respx.mock
    async def test_list_allowlist(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_ALLOWLIST_URL).mock(
            return_value=httpx.Response(200, json=_ALLOWLIST_BODY)
        )
        result = await _aips(aclient).list_allowlist()

        assert result == _ALLOWLIST_BODY
        assert dict(route.calls.last.request.url.params) == {}

    @respx.mock
    async def test_update_allowlist(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(_ALLOWLIST_URL).mock(
            return_value=httpx.Response(200, json=_ALLOWLIST_BODY)
        )
        await _aips(aclient).update_allowlist(src_ids=["a1"], dst_ids=["b2"])

        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"src_ids": ["a1"], "dst_ids": ["b2"]}

    @respx.mock
    async def test_update_allowlist_requires_a_field(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await _aips(aclient).update_allowlist()
        assert len(respx.calls) == 0


class TestAsyncIpsSignatures:
    """Tests for AsyncIpsResource.list_signatures / search_signatures."""

    @respx.mock
    async def test_list_signatures_with_params(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_SIG_REF_URL).mock(return_value=httpx.Response(200, json=_SIG_REF_BODY))
        result = await _aips(aclient).list_signatures(limit=5, reference="cve")

        assert result == _SIG_REF_BODY
        params = dict(route.calls.last.request.url.params)
        assert params == {"limit": "5", "reference": "cve"}

    @respx.mock
    async def test_search_signatures_with_filters(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_SIG_SEARCH_URL).mock(
            return_value=httpx.Response(200, json=_SIG_SEARCH_BODY)
        )
        result = await _aips(aclient).search_signatures(keyword="Firefox", limit=10)

        assert result["data"]["total"] == 1
        assert sent_json(route) == {"limit": 10, "filter": {"keyword": "Firefox"}}

    @respx.mock
    async def test_search_signatures_invalid_traffic_type(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError):
            await _aips(aclient).search_signatures(traffic_type=["smtp"])
        assert len(respx.calls) == 0


class TestAsyncIpsAlertOnlyMode:
    """Tests for AsyncIpsResource alert-only-mode methods."""

    @respx.mock
    async def test_get_alert_only_mode(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_ALERT_ONLY_URL).mock(
            return_value=httpx.Response(200, json=_ALERT_ONLY_BODY)
        )
        result = await _aips(aclient).get_alert_only_mode()

        assert result == _ALERT_ONLY_BODY
        assert route.called

    @respx.mock
    async def test_set_alert_only_mode(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(_ALERT_ONLY_URL).mock(
            return_value=httpx.Response(200, json=_STATUS_ONLY_BODY)
        )
        await _aips(aclient).set_alert_only_mode(False)

        assert route.calls.last.request.method == "PUT"
        assert sent_json(route) == {"enabled": False}


class TestAsyncIpsSignatureOverrides:
    """Tests for AsyncIpsResource signature override methods."""

    @respx.mock
    async def test_list_signature_overrides(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_OVERRIDES_URL).mock(
            return_value=httpx.Response(200, json=_OVERRIDES_BODY)
        )
        result = await _aips(aclient).list_signature_overrides(limit=25)

        assert result == _OVERRIDES_BODY
        assert dict(route.calls.last.request.url.params) == {"limit": "25"}

    @respx.mock
    async def test_update_signature_overrides(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(_OVERRIDES_URL).mock(
            return_value=httpx.Response(200, json=_STATUS_ONLY_BODY)
        )
        await _aips(aclient).update_signature_overrides(["117"], "alert")

        assert sent_json(route) == {"sig_id": ["117"], "override": "alert"}

    @respx.mock
    async def test_update_signature_overrides_validation(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError):
            await _aips(aclient).update_signature_overrides(["117"], "drop")
        assert len(respx.calls) == 0

    @respx.mock
    async def test_delete_signature_overrides(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_DELETE_OVERRIDES_URL).mock(
            return_value=httpx.Response(200, json=_STATUS_ONLY_BODY)
        )
        await _aips(aclient).delete_signature_overrides(["308"])

        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {"sig_id": ["308"]}


class TestAsyncIpsNotificationTemplate:
    """Tests for AsyncIpsResource notification template methods."""

    @respx.mock
    async def test_get_notification_template(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_TEMPLATE_URL).mock(return_value=httpx.Response(200, json=_TEMPLATE_BODY))
        result = await _aips(aclient).get_notification_template()

        assert result == _TEMPLATE_BODY
        assert route.called

    @respx.mock
    async def test_update_notification_template(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(_TEMPLATE_URL).mock(
            return_value=httpx.Response(200, json=_TEMPLATE_BODY)
        )
        await _aips(aclient).update_notification_template("22.html")

        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"web": {"template_file_name": "22.html"}}


class TestAsyncIpsThreatHunting:
    """Tests for AsyncIpsResource threat hunting config methods."""

    @respx.mock
    async def test_get_threat_hunting_config(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_THREAT_HUNTING_URL).mock(
            return_value=httpx.Response(200, json=_THREAT_HUNTING_BODY)
        )
        result = await _aips(aclient).get_threat_hunting_config()

        assert result == _THREAT_HUNTING_BODY
        assert route.called

    @respx.mock
    async def test_update_threat_hunting_config(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(_THREAT_HUNTING_URL).mock(
            return_value=httpx.Response(200, json=_THREAT_HUNTING_BODY)
        )
        await _aips(aclient).update_threat_hunting_config(html_smuggling=False)

        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"html_smuggling": {"enabled": False}}

    @respx.mock
    async def test_update_threat_hunting_config_requires_a_flag(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError):
            await _aips(aclient).update_threat_hunting_config()
        assert len(respx.calls) == 0
