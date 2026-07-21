"""Read-only NetBox API client."""

from __future__ import annotations

from typing import Any, cast

import httpx

DeviceRecord = dict[str, Any]


class NetBoxClientError(RuntimeError):
    """Base class for safe, operator-facing NetBox failures."""


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
    ) -> None:
        normalized_base_url = base_url.rstrip("/") + "/"
        base = httpx.URL(normalized_base_url)
        self._origin = (base.scheme, base.host, base.port)
        self._client = httpx.Client(
            base_url=normalized_base_url,
            headers={"Authorization": f"Token {token}", "Accept": "application/json"},
            transport=transport,
            timeout=timeout,
        )

    def list_devices(self) -> list[DeviceRecord]:
        """Return every device from the paginated NetBox device endpoint."""
        devices: list[DeviceRecord] = []
        next_url: str | None = "api/dcim/devices/"
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
            page_devices, next_url = _parse_page(response)
            if next_url is not None:
                self._ensure_safe_next_url(next_url)
            devices.extend(page_devices)

        return devices

    def _ensure_safe_next_url(self, next_url: str) -> None:
        candidate = httpx.URL(next_url)
        if candidate.is_relative_url:
            return
        if (candidate.scheme, candidate.host, candidate.port) != self._origin:
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
