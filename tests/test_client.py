from __future__ import annotations

import httpx
import pytest

from netbox_scribe.client import (
    NetBoxAuthenticationError,
    NetBoxClient,
    NetBoxConfigurationError,
    NetBoxResponseError,
    NetBoxTransportError,
)


def test_client_rejects_insecure_http_before_any_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)

    with pytest.raises(NetBoxConfigurationError, match="HTTPS is required") as captured:
        NetBoxClient("http://netbox.example", "http-secret-token", transport=transport)

    assert requests == []
    assert "http-secret-token" not in str(captured.value)


def test_client_allows_explicit_insecure_http_override() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"count": 0, "next": None, "previous": None, "results": []},
        )

    client = NetBoxClient(
        "http://netbox.example",
        "explicit-http-secret",
        allow_insecure_http=True,
        transport=httpx.MockTransport(handler),
    )

    assert client.list_devices() == []
    assert len(requests) == 1
    assert requests[0].url.scheme == "http"
    assert requests[0].headers["Authorization"] == "Token explicit-http-secret"


def test_list_devices_retrieves_every_page() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.params.get("offset") == "1":
            return httpx.Response(
                200,
                json={
                    "count": 2,
                    "next": None,
                    "previous": "https://netbox.example/api/dcim/devices/?limit=1",
                    "results": [{"id": 2, "name": "switch-01"}],
                },
            )
        return httpx.Response(
            200,
            json={
                "count": 2,
                "next": "https://netbox.example/api/dcim/devices/?limit=1&offset=1",
                "previous": None,
                "results": [{"id": 1, "name": "router-01"}],
            },
        )

    client = NetBoxClient(
        "https://netbox.example",
        "test-secret-token",
        transport=httpx.MockTransport(handler),
    )

    devices = client.list_devices()

    assert devices == [
        {"id": 1, "name": "router-01"},
        {"id": 2, "name": "switch-01"},
    ]
    assert len(requests) == 2
    assert all(
        request.headers["Authorization"] == "Token test-secret-token" for request in requests
    )


@pytest.mark.parametrize(
    "next_url",
    [
        "https://untrusted.example/api/dcim/devices/?offset=1",
        "//untrusted.example/api/dcim/devices/?offset=1",
        "http://netbox.example/api/dcim/devices/?offset=1",
    ],
)
def test_list_devices_rejects_cross_origin_pagination_before_sending_credentials(
    next_url: str,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "count": 1,
                "next": next_url,
                "previous": None,
                "results": [{"id": 1, "name": "router-01"}],
            },
        )

    client = NetBoxClient(
        "https://netbox.example",
        "cross-origin-secret",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(NetBoxResponseError, match="different origin"):
        client.list_devices()

    assert len(requests) == 1


def test_list_devices_rejects_malformed_pagination_url_cleanly() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "count": 0,
                "next": "https://netbox.example:bad/",
                "previous": None,
                "results": [],
            },
        )

    client = NetBoxClient(
        "https://netbox.example",
        "malformed-next-secret",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(NetBoxResponseError, match="malformed pagination URL") as captured:
        client.list_devices()

    assert "malformed-next-secret" not in str(captured.value)
    assert captured.value.__cause__ is None


def test_list_devices_rejects_repeated_pagination_url() -> None:
    requests: list[httpx.Request] = []
    repeated = "https://netbox.example/api/dcim/devices/?offset=1"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) > 2:
            raise AssertionError("pagination loop was not rejected")
        return httpx.Response(
            200,
            json={"count": 1, "next": repeated, "previous": None, "results": []},
        )

    client = NetBoxClient(
        "https://netbox.example",
        "test-token",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(NetBoxResponseError, match="repeated pagination"):
        client.list_devices()

    assert len(requests) == 2


def test_list_devices_reports_authentication_failure_without_token() -> None:
    secret = "auth-failure-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": f"invalid token {secret}"})

    client = NetBoxClient(
        "https://netbox.example",
        secret,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(NetBoxAuthenticationError, match="authentication failed") as captured:
        client.list_devices()

    assert secret not in str(captured.value)


def test_list_devices_reports_transport_failure_without_token() -> None:
    secret = "transport-failure-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"connection failed with {secret}", request=request)

    client = NetBoxClient(
        "https://netbox.example",
        secret,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(NetBoxTransportError, match="request failed") as captured:
        client.list_devices()

    assert secret not in str(captured.value)
    assert captured.value.__cause__ is None


def test_list_devices_reports_http_failure_without_response_content() -> None:
    secret = "http-failure-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": f"internal error {secret}"})

    client = NetBoxClient(
        "https://netbox.example",
        "test-token",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(NetBoxResponseError, match="HTTP 500") as captured:
        client.list_devices()

    assert secret not in str(captured.value)


def test_list_devices_reports_malformed_json_without_response_content() -> None:
    secret = "malformed-response-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=f"not-json {secret}")

    client = NetBoxClient(
        "https://netbox.example",
        "test-token",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(NetBoxResponseError, match="malformed response") as captured:
        client.list_devices()

    assert secret not in str(captured.value)
    assert captured.value.__cause__ is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"results": "not-a-list", "next": None},
        {"results": [], "next": 42},
        {"results": ["not-an-object"], "next": None},
    ],
)
def test_list_devices_rejects_malformed_payload_shapes(payload: object) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = NetBoxClient(
        "https://netbox.example",
        "test-token",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(NetBoxResponseError, match="malformed response"):
        client.list_devices()
