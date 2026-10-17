from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from netbox_scribe.client import NetBoxClient, NetBoxResponseError
from netbox_scribe.exporter import export_network
from netbox_scribe.policy import ExportPolicy, NetworkExportPolicy
from netbox_scribe.validation import validate_snapshot_text

ENDPOINTS = ("/api/dcim/interfaces/", "/api/ipam/ip-addresses/")
BASE_URL = "https://netbox.example"
TOKEN = "synthetic-relationship-token"


def _initial_url(endpoint: str) -> httpx.URL:
    url = httpx.URL(BASE_URL + endpoint)
    if endpoint == ENDPOINTS[1]:
        url = url.copy_add_param("assigned_object_type", "dcim.interface")
    return url


def _earlier_urls(endpoint: str) -> list[httpx.URL]:
    urls = [httpx.URL(BASE_URL + "/api/dcim/devices/")]
    if endpoint == ENDPOINTS[1]:
        urls.append(_initial_url(ENDPOINTS[0]))
    return urls


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize(
    ("next_url", "message"),
    [
        ("https://untrusted.example/next/", "different origin"),
        ("//untrusted.example/next/", "different origin"),
        ("http://netbox.example/next/", "different origin"),
        ("https://netbox.example:8443/next/", "different origin"),
        ("https://netbox.example:bad/next/", "malformed pagination URL"),
    ],
)
def test_relationship_pagination_rejects_unsafe_next_before_credentials_leave_origin(
    endpoint: str, next_url: str, message: str
) -> None:
    expected = [*_earlier_urls(endpoint), _initial_url(endpoint)]
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url in expected, "unsafe pagination URL was fetched"
        assert len(requests) <= len(expected), "unexpected repeated request"
        return httpx.Response(
            200,
            json={"results": [], "next": next_url if request.url.path == endpoint else None},
        )

    with (
        NetBoxClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler)) as client,
        pytest.raises(NetBoxResponseError, match=message) as captured,
    ):
        client.list_network_records()

    assert [request.url for request in requests] == expected
    assert all(request.headers["Authorization"] == f"Token {TOKEN}" for request in requests)
    assert TOKEN not in str(captured.value)
    assert captured.value.__cause__ is None


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("repeat_initial", [True, False], ids=["initial-page", "later-page"])
def test_relationship_pagination_rejects_loops_without_refetching_a_page(
    endpoint: str, repeat_initial: bool
) -> None:
    initial = _initial_url(endpoint)
    repeated = initial if repeat_initial else initial.copy_add_param("offset", "1")
    expected = [*_earlier_urls(endpoint), initial]
    if not repeat_initial:
        expected.append(repeated)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert len(requests) <= len(expected), "pagination loop attempted another fetch"
        return httpx.Response(
            200,
            json={"results": [], "next": str(repeated) if request.url.path == endpoint else None},
        )

    with (
        NetBoxClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler)) as client,
        pytest.raises(NetBoxResponseError, match="repeated pagination URL"),
    ):
        client.list_network_records()

    assert [request.url for request in requests] == expected
    assert all(request.headers["Authorization"] == f"Token {TOKEN}" for request in requests)


@pytest.mark.parametrize("assignment", [None, "virtualization.vminterface", "dcim.interface"])
def test_network_export_enforces_assignment_scope_after_paginated_http_response(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    assignment: str | None,
) -> None:
    """A server ignoring its filter must not bypass validation or publish a partial pair."""
    output, index = tmp_path / "network.yaml", tmp_path / "NETWORK.md"
    previous_output, previous_index = b"previous-network\r\n", b"previous-index\r\n"
    output.write_bytes(previous_output)
    index.write_bytes(previous_index)
    denied = ("SYNTHETIC-DENIED-SERIAL", "SYNTHETIC-DENIED-MAC", "denied.example")
    requests: list[httpx.Request] = []
    first_ip = _initial_url(ENDPOINTS[1])
    second_ip = first_ip.copy_add_param("offset", "1")
    expected_urls = [*_earlier_urls(ENDPOINTS[1]), first_ip, second_ip]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert [r.url for r in requests] == expected_urls[: len(requests)]
        assert len(requests) <= len(expected_urls), "unexpected request"
        if request.url.path == "/api/dcim/devices/":
            return httpx.Response(
                200, json={"results": [{"id": 1, "name": "device-01", "serial": denied[0]}]}
            )
        if request.url.path == ENDPOINTS[0]:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 2, "name": "eth0", "device": {"id": 1}, "mac_address": denied[1]}
                    ]
                },
            )
        assert request.url.params["assigned_object_type"] == "dcim.interface"
        record = {
            "id": 3 if request.url == first_ip else 4,
            "address": "192.0.2.1/24" if request.url == first_ip else "192.0.2.2/24",
            "assigned_object_type": "dcim.interface" if request.url == first_ip else assignment,
            "assigned_object_id": 2,
            "dns_name": denied[2],
        }
        return httpx.Response(
            200,
            json={
                "results": [record],
                "next": str(second_ip) if request.url == first_ip else None,
            },
        )

    policy = NetworkExportPolicy(devices=ExportPolicy(include_fields=frozenset()))
    with NetBoxClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler)) as client:
        if assignment != "dcim.interface":
            with pytest.raises(
                ValueError,
                match="ip_addresses id=4 field=assigned_object_type: must be dcim.interface",
            ) as captured:
                export_network(client, output, agent_index=index, policy=policy)
            assert output.read_bytes() == previous_output
            assert index.read_bytes() == previous_index
            assert not any(value in str(captured.value) for value in (*denied, TOKEN, "192.0.2.2"))
        else:
            counts = export_network(client, output, agent_index=index, policy=policy)
            assert (counts.devices, counts.interfaces, counts.ip_addresses) == (1, 1, 2)
            document = validate_snapshot_text(output.read_text())
            assert document["devices"] == [{"id": 1, "name": "device-01"}]
            assert [address["id"] for address in document["ip_addresses"]] == [3, 4]
            assert output.read_bytes() != previous_output
            assert index.read_bytes() != previous_index

    assert [request.url for request in requests] == expected_urls
    assert all(request.headers["Authorization"] == f"Token {TOKEN}" for request in requests)
    captured_output = capsys.readouterr()
    surfaces = output.read_text() + index.read_text() + captured_output.out + captured_output.err
    assert not any(value in surfaces + caplog.text for value in (*denied, TOKEN))
