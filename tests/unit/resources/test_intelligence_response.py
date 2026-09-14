"""Typed ATP and NSIQ operations retain provenance without replaying submissions."""

from __future__ import annotations

import base64
import inspect
import json
from functools import partial

import httpx
import pytest
import respx
from pydantic import ValidationError as ModelValidationError

from netskope import NetskopeClient
from netskope.exceptions import APIError, ResponseValidationError, ValidationError
from netskope.models.atp import (
    AtpFileScan,
    AtpFileSubmission,
    AtpSubmissionReport,
    AtpUrlScan,
    AtpUrlSubmission,
)
from netskope.models.nsiq import (
    RecategorizationRequest,
    UrlFalsePositive,
    UrlFalsePositiveRequest,
    UrlLookup,
    UrlRecategorization,
)
from tests.unit.resources.conftest import contract_router

BASE = "https://t.goskope.com"
# A benign text member named sample.exe, ZipCrypto-encrypted with password infected.
ARCHIVE = base64.b64decode(
    "UEsDBAoACQAAAMNyKV0dmP5SNAAAACgAAAAKABwAc2FtcGxlLmV4ZVVUCQADzqOhas6joWp1eAsA"
    "AQT1AQAABAAAAAAYutMo+qaQL8/kSDAG8FcXL8iBw+jUOO6NowntO5VRFfREeUS7Y6jU885JKAWc"
    "akk+hhsVUEsHCB2Y/lI0AAAAKAAAAFBLAQIeAwoACQAAAMNyKV0dmP5SNAAAACgAAAAKABgAAAAA"
    "AAEAAACkgQAAAABzYW1wbGUuZXhlVVQFAAPOo6FqdXgLAAEE9QEAAAQAAAAAUEsFBgAAAAABAAEA"
    "UAAAAIgAAAAAAA=="
)
REPORT = {
    "status": "Ok",
    "jobid": "job-7",
    "md5": "0" * 32,
    "sha256": "0" * 64,
    "requests_served": "007",
    "verdict": "non-malicious",
    "network": {"future": ["0009", False]},
    "process_tree": [{"pid": "001"}],
}


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_sandbox_uses_binary_multipart_and_required_query(client, aclient, asynchronous):
    body = {"status": "Ok", "jobid": "job-7", "requests_served": "007"}
    route = respx.post(BASE + "/api/v2/atp/scans/filescan").respond(200, json=body)
    resource = (aclient if asynchronous else client).atp.with_response
    result = resource.scan_file(AtpFileScan(filename="sample.zip", content=ARCHIVE))
    if inspect.isawaitable(result):
        result = await result
    assert result.parse().job_id == "job-7"
    assert result.json() == body
    assert route.call_count == 1
    request = route.calls[0].request
    assert dict(request.url.params) == {"scantype": "sandbox"}
    assert request.headers["content-type"].startswith("multipart/form-data; boundary=")
    assert b'name="file"; filename="sample.zip"' in request.content
    assert ARCHIVE in request.content
    assert base64.b64encode(ARCHIVE) not in request.content


CASES = [
    (
        "atp.with_response.scan_url",
        (AtpUrlScan(url="https://example.test/path?q=007"),),
        "POST",
        "/api/v2/atp/tpaas/urlscan/submission/scan",
        {"url": "https://example.test/path?q=007"},
        {"status": "Ok", "submission_id": "submission-7", "url_sha256": "0008"},
        202,
    ),
    (
        "atp.with_response.get_report",
        ("a/b",),
        "GET",
        "/api/v2/atp/scans/reports/a%2Fb",
        None,
        REPORT,
        200,
    ),
    (
        "atp.with_response.get_submission_report",
        ("a/b",),
        "GET",
        "/api/v2/atp/tpaas/submission/a%2Fb/reports",
        None,
        {
            "report": {"type": "bundle", "objects": [{"id": "007", "future": False}]},
            "processtree": '[{"pid":"001"}]',
        },
        200,
    ),
    (
        "nsiq.with_response.url_lookup",
        (UrlLookup(urls=["example.test"]),),
        "POST",
        "/api/v2/nsiq/urllookup",
        {"query": {"urls": ["example.test"]}},
        {
            "query": {"urls": ["example.test"]},
            "result": [
                {
                    "url": "example.test",
                    "dynamic_classification": "false",
                    "categories": [{"id": "007", "name": "Business"}],
                }
            ],
        },
        200,
    ),
    (
        "nsiq.with_response.recategorize",
        (
            RecategorizationRequest(
                recat_requests=[
                    UrlRecategorization(url="example.test", suggested_categories=["Business"])
                ],
                email="",
                justification="Partner",
            ),
        ),
        "POST",
        "/api/v2/nsiq/url/recategorizations",
        {
            "email": "",
            "justification": "Partner",
            "recat_requests": [{"url": "example.test", "suggested_categories": ["Business"]}],
        },
        {
            "status": "Created",
            "data": {"task_id": "007", "urls": [{"id": "008", "status": "received"}]},
        },
        201,
    ),
    (
        "nsiq.with_response.report_url_false_positive",
        (
            UrlFalsePositiveRequest(
                user_email="one@example.test",
                fp_data=[UrlFalsePositive(incident_id="007", url="example.test")],
            ),
        ),
        "POST",
        "/api/v2/nsiq/falsepositives/url",
        {
            "user_email": "one@example.test",
            "fp_data": [{"incident_id": "007", "url": "example.test"}],
        },
        {
            "status": "Created",
            "data": [{"incident_id": "007", "tickets": [{"system": "recat", "ticket_id": "008"}]}],
        },
        201,
    ),
]


def method(client, path):
    result = client
    for key in path.split("."):
        result = getattr(result, key)
    return result


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "name,args,verb,path,payload,body,status", CASES, ids=[case[0] for case in CASES]
)
@respx.mock
async def test_typed_intelligence_operations_use_canonical_wire_contract(
    client, aclient, asynchronous, name, args, verb, path, payload, body, status
):
    route = respx.route(method=verb, url=BASE + path).respond(status, json=body)
    response = method(aclient if asynchronous else client, name)(*args)
    if inspect.isawaitable(response):
        response = await response
    parsed = response.parse()
    assert response.parse() is parsed
    assert response.json() == body
    assert route.call_count == 1
    request = route.calls[0].request
    assert not request.url.params
    assert (json.loads(request.content) if request.content else None) == payload


@pytest.mark.parametrize(
    "model,payload",
    [
        (AtpFileScan, {"filename": "sample.exe", "content": ARCHIVE}),
        (AtpFileScan, {"filename": "sample.zip", "content": b"not a ZIP"}),
        (AtpFileScan, {"filename": "sample.zip", "content": ARCHIVE, "scan_type": "realtime"}),
        (AtpUrlScan, {"url": "example.test"}),
        (AtpUrlScan, {"url": "file:///tmp/sample"}),
        (UrlLookup, {"urls": []}),
        (UrlLookup, {"urls": [""]}),
        (UrlLookup, {"urls": ["example.test"], "category": "unknown"}),
        (RecategorizationRequest, {"recat_requests": []}),
        (
            RecategorizationRequest,
            {
                "recat_requests": [{"url": "example.test", "suggested_categories": ["Business"]}],
                "current_category": "Malware",
            },
        ),
        (UrlFalsePositiveRequest, {"fp_data": [{"incident_id": "007"}]}),
        (
            UrlFalsePositiveRequest,
            {"user_email": "one@example.test", "fp_data": [{"url": "example.test"}]},
        ),
        (
            UrlFalsePositiveRequest,
            {
                "user_email": "one@example.test",
                "fp_data": [{"incident_id": "007", "reason": "Partner"}],
            },
        ),
    ],
)
def test_invalid_or_ambiguous_request_models_fail_before_http(model, payload):
    with pytest.raises(ModelValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("submission", ["file", "url", "recategorization", "false-positive"])
@respx.mock
async def test_submissions_do_not_retry_on_server_failure(
    client, aclient, asynchronous, submission
):
    c = aclient if asynchronous else client
    if submission == "file":
        path = "/api/v2/atp/scans/filescan"
        call = partial(
            c.atp.with_response.scan_file, AtpFileScan(filename="sample.zip", content=ARCHIVE)
        )
    elif submission == "url":
        path = "/api/v2/atp/tpaas/urlscan/submission/scan"
        call = partial(c.atp.with_response.scan_url, AtpUrlScan(url="https://example.test"))
    elif submission == "recategorization":
        path = "/api/v2/nsiq/url/recategorizations"
        call = partial(
            c.nsiq.with_response.recategorize,
            RecategorizationRequest(
                recat_requests=[
                    UrlRecategorization(url="example.test", suggested_categories=["Business"])
                ]
            ),
        )
    else:
        path = "/api/v2/nsiq/falsepositives/url"
        call = partial(
            c.nsiq.with_response.report_url_false_positive,
            UrlFalsePositiveRequest(
                user_email="one@example.test", fp_data=[UrlFalsePositive(incident_id="007")]
            ),
        )
    route = respx.post(BASE + path).respond(503, json={"message": "Busy"})
    with pytest.raises(APIError):
        result = call()
        if inspect.isawaitable(result):
            await result
    assert route.call_count == 1


@respx.mock
def test_lookup_is_explicitly_retry_safe_and_keeps_request_body():
    route = respx.post(BASE + "/api/v2/nsiq/urllookup").mock(
        side_effect=[
            httpx.Response(503, json={"message": "Busy"}),
            httpx.Response(200, json={"result": [{"url": "example.test"}]}),
        ]
    )
    with NetskopeClient(tenant="t.goskope.com", api_token="tok", backoff_factor=0) as client:
        result = client.nsiq.with_response.url_lookup(UrlLookup(urls=["example.test"])).parse()
    assert result[0].url == "example.test"
    assert route.call_count == 2
    assert all(not call.request.url.params for call in route.calls)


@respx.mock
def test_model_construct_does_not_bypass_file_validation(client):
    request = AtpFileScan.model_construct(
        filename="sample.zip", content=b"unverified", scan_type="sandbox"
    )
    with pytest.raises(ValidationError):
        client.atp.with_response.scan_file(request)
    assert not respx.calls


@respx.mock
def test_success_with_invalid_receipt_never_causes_a_second_submission(client):
    route = respx.post(BASE + "/api/v2/atp/tpaas/urlscan/submission/scan").respond(
        202,
        json={"submission_id": 7, "sensitive": "response-secret"},
        headers={"x-request-id": "request-7"},
    )
    response = client.atp.with_response.scan_url(AtpUrlScan(url="https://example.test"))
    with pytest.raises(ResponseValidationError) as error:
        response.parse()
    assert error.value.request_id == "request-7"
    assert "response-secret" not in str(error.value)
    assert route.call_count == 1


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.


class TestAtpAcknowledgementsAreSparse:
    def test_models_require_nothing(self) -> None:
        """``TssScanAPIResponse`` (atp/atpsvc.yaml:16-31), ``ScanInProgress``
        (atp/urlscan.yaml:43-55) and ``GetReportResponse``
        (atp/tpaassvc.yaml:64-70) declare no ``required`` list."""
        assert AtpFileSubmission.model_validate({"status": "Ok", "md5": "0" * 32}).job_id is None
        assert (
            AtpUrlSubmission.model_validate({"status": "Ok", "message": "queued"}).submission_id
            is None
        )
        assert AtpSubmissionReport.model_validate({"processtree": "[]"}).report == {}

    def test_submission_report_without_report_parses(self, contract_client: NetskopeClient) -> None:
        with contract_router() as mock:
            mock.get("/api/v2/atp/tpaas/submission/s1/reports").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "processtree": '[{"track": true, "pid": 1140, '
                        '"process_name": "WINWORD.EXE"}]'
                    },
                )
            )
            report = contract_client.atp.with_response.get_submission_report("s1").parse()
        assert report.report == {} and report.process_tree is not None
