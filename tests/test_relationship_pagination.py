"""Pagination across relationship endpoints via NetBoxClient.list_network_records()."""

from __future__ import annotations

import httpx
import pytest

from netbox_scribe.client import NetBoxClient


@pytest.mark.parametrize(
    "target_path,initial_url,page1,page2",
    [
        (
            "/api/dcim/interfaces/",
            "api/dcim/interfaces/",
            [{"id": 10, "name": "eth0", "type": "other"}],
            [{"id": 11, "name": "eth1", "type": "other"}],
        ),
        (
            "/api/ipam/ip-addresses/",
            "api/ipam/ip-addresses/?assigned_object_type=dcim.interface",
            [
                {
                    "id": 20,
                    "address": "192.0.2.1/24",
                    "assigned_object_type": "dcim.interface",
                    "assigned_object_id": 10,
                }
            ],
            [
                {
                    "id": 21,
                    "address": "192.0.2.2/24",
                    "assigned_object_type": "dcim.interface",
                    "assigned_object_id": 11,
                }
            ],
        ),
    ],
)
def test_list_network_records_paginates_target(
    target_path: str,
    initial_url: str,
    page1: list[dict[str, object]],
    page2: list[dict[str, object]],
) -> None:
    requests: list[httpx.Request] = []
    base = httpx.URL("https://netbox.example/")
    first_url = base.join(initial_url)
    next_url = first_url.copy_add_param("offset", "1")
    interface_url = base.join("api/dcim/interfaces/")
    ip_url = base.join("api/ipam/ip-addresses/?assigned_object_type=dcim.interface")
    expected_urls = [base.join("api/dcim/devices/")]
    if target_path == "/api/dcim/interfaces/":
        expected_urls.extend([first_url, next_url, ip_url])
    else:
        expected_urls.extend([interface_url, first_url, next_url])

    def handler(request: httpx.Request) -> httpx.Response:
        if len(requests) >= len(expected_urls):
            raise AssertionError(f"too many requests ({len(requests)} >= {len(expected_urls)})")
        assert request.url == expected_urls[len(requests)]
        requests.append(request)
        path = request.url.path
        if path == "/api/dcim/devices/":
            return httpx.Response(
                200, json={"count": 0, "next": None, "previous": None, "results": []}
            )
        if path == target_path:
            offset = request.url.params.get("offset")
            if offset == "1":
                return httpx.Response(
                    200, json={"count": 2, "next": None, "previous": None, "results": page2}
                )
            return httpx.Response(
                200, json={"count": 2, "next": str(next_url), "previous": None, "results": page1}
            )
        return httpx.Response(200, json={"count": 0, "next": None, "previous": None, "results": []})

    with NetBoxClient(
        "https://netbox.example", "test-token", transport=httpx.MockTransport(handler)
    ) as client:
        network = client.list_network_records()

    actual = network.interfaces if target_path == "/api/dcim/interfaces/" else network.ip_addresses
    assert actual == page1 + page2
    assert network.devices == []
    if target_path == "/api/dcim/interfaces/":
        assert network.ip_addresses == []
    else:
        assert network.interfaces == []
    assert [request.url for request in requests] == expected_urls
    assert all(r.headers["Authorization"] == "Token test-token" for r in requests)
    if target_path == "/api/ipam/ip-addresses/":
        for req in requests:
            if req.url.path == target_path:
                assert req.url.params["assigned_object_type"] == "dcim.interface"
