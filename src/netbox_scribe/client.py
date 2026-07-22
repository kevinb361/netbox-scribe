"""Read-only NetBox API client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import httpx

DeviceRecord = dict[str, Any]


@dataclass(frozen=True, slots=True)
class NetworkRecords:
    """Raw records needed for the device-interface-address relationship view."""

    devices: list[DeviceRecord]
    interfaces: list[DeviceRecord]
    ip_addresses: list[DeviceRecord]


class NetBoxClientError(RuntimeError):
    """Base class for safe, operator-facing NetBox failures."""


class NetBoxConfigurationError(NetBoxClientError):
    """NetBox client configuration would expose credentials or cannot be used."""


class NetBoxAuthenticationError(NetBoxClientError):
    """NetBox rejected the configured API token."""


class NetBoxTransportError(NetBoxClientError):
    """NetBox could not be reached safely."""


class NetBoxResponseError(NetBoxClientError):
    """NetBox returned an unusable response."""


class NetBoxClient:
    """Retrieve inventory records from NetBox without write capabilities."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
        allow_insecure_http: bool = False,
    ) -> None:
        normalized_base_url = base_url.rstrip("/") + "/"
        try:
            base = httpx.URL(normalized_base_url)
        except (httpx.InvalidURL, ValueError):
            raise NetBoxConfigurationError("NetBox URL is invalid") from None
        if base.scheme not in {"http", "https"} or not base.host:
            raise NetBoxConfigurationError("NetBox URL must use HTTP or HTTPS")
        if base.scheme != "https" and not allow_insecure_http:
            raise NetBoxConfigurationError(
                "HTTPS is required for NetBox credentials; pass --allow-insecure-http "
                "only for a trusted network"
            )
        self._origin = (base.scheme, base.host, base.port)
        self._client = httpx.Client(
            base_url=normalized_base_url,
            headers={"Authorization": f"Token {token}", "Accept": "application/json"},
            transport=transport,
            timeout=timeout,
        )

    def list_devices(self) -> list[DeviceRecord]:
        """Return every device from the paginated NetBox device endpoint."""
        return self._list_records("api/dcim/devices/")

    def list_network_records(self) -> NetworkRecords:
        """Return raw records for the device-interface-address relationship view."""
        return NetworkRecords(
            devices=self.list_devices(),
            interfaces=self._list_records("api/dcim/interfaces/"),
            ip_addresses=self._list_records(
                "api/ipam/ip-addresses/?assigned_object_type=dcim.interface"
            ),
        )

    def _list_records(self, initial_url: str) -> list[DeviceRecord]:
        records: list[DeviceRecord] = []
        next_url: str | None = initial_url
        seen_urls: set[httpx.URL] = set()

        while next_url is not None:
            request_url = self._client.base_url.join(next_url)
            if request_url in seen_urls:
                raise NetBoxResponseError("NetBox returned a repeated pagination URL")
            seen_urls.add(request_url)
            try:
                response = self._client.get(request_url)
            except httpx.TransportError:
                raise NetBoxTransportError("NetBox request failed") from None
            if response.status_code in {401, 403}:
                raise NetBoxAuthenticationError("NetBox authentication failed")
            if response.is_error:
                raise NetBoxResponseError(f"NetBox returned HTTP {response.status_code}")
            page_records, next_url = _parse_page(response)
            if next_url is not None:
                self._ensure_safe_next_url(next_url)
            records.extend(page_records)

        return records

    def _ensure_safe_next_url(self, next_url: str) -> None:
        try:
            candidate = self._client.base_url.join(next_url)
            candidate_origin = (candidate.scheme, candidate.host, candidate.port)
        except (httpx.InvalidURL, ValueError):
            raise NetBoxResponseError("NetBox returned a malformed pagination URL") from None
        if candidate_origin != self._origin:
            raise NetBoxResponseError("NetBox pagination points to a different origin")

    def close(self) -> None:
        """Release network resources owned by the client."""
        self._client.close()

    def __enter__(self) -> NetBoxClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _parse_page(response: httpx.Response) -> tuple[list[DeviceRecord], str | None]:
    try:
        payload = response.json()
    except ValueError:
        raise NetBoxResponseError("NetBox returned a malformed response") from None

    if not isinstance(payload, dict):
        raise NetBoxResponseError("NetBox returned a malformed response")

    results = payload.get("results")
    next_url = payload.get("next")
    if (
        not isinstance(results, list)
        or not all(isinstance(record, dict) for record in results)
        or (next_url is not None and not isinstance(next_url, str))
    ):
        raise NetBoxResponseError("NetBox returned a malformed response")

    return cast(list[DeviceRecord], results), next_url
