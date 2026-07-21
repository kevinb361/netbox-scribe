"""Canonical inventory normalization and serialization."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from netbox_scribe.client import DeviceRecord, NetBoxClient

SCHEMA_VERSION = 1


class _CanonicalDumper(yaml.SafeDumper):
    """Safe YAML dumper with stable, readable sequence indentation."""

    def ignore_aliases(self, data: Any) -> bool:
        return True

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        super().increase_indent(flow, indentless=False)


def export_devices(client: NetBoxClient, output: Path) -> int:
    """Write the current canonical device inventory and return its record count."""
    devices = client.list_devices()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_devices_yaml(devices), encoding="utf-8")
    return len(devices)


def render_devices_yaml(devices: list[DeviceRecord]) -> str:
    """Normalize NetBox devices and serialize canonical, deterministic YAML."""
    normalized = sorted(
        (_normalize_device(device) for device in devices),
        key=lambda device: (str(device["name"]).casefold(), int(device["id"])),
    )
    document = {
        "schema_version": SCHEMA_VERSION,
        "source": "netbox",
        "devices": normalized,
    }
    return yaml.dump(
        document,
        Dumper=_CanonicalDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100,
    )


def _normalize_device(device: DeviceRecord) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "id": device["id"],
        "name": device["name"],
    }
    _copy_scalar(normalized, device, "display")
    _copy_reference(normalized, device, "status", ("value", "label"))
    _copy_reference(normalized, device, "role", ("id", "name", "slug"))

    device_type = _reference(device.get("device_type"), ("id", "model", "slug"))
    if device_type is not None:
        manufacturer = _reference(
            _mapping(device.get("device_type")).get("manufacturer"),
            ("id", "name", "slug"),
        )
        if manufacturer is not None:
            device_type["manufacturer"] = manufacturer
        normalized["device_type"] = device_type

    for field in ("site", "location", "rack", "tenant", "platform"):
        _copy_reference(normalized, device, field, ("id", "name", "slug"))

    for field in ("serial", "asset_tag", "description"):
        _copy_scalar(normalized, device, field)

    for field in ("primary_ip4", "primary_ip6"):
        _copy_reference(
            normalized,
            device,
            field,
            ("id", "address", "dns_name", "description"),
        )

    tags = [
        reference
        for tag in device.get("tags", [])
        if (reference := _reference(tag, ("id", "name", "slug"))) is not None
    ]
    if tags:
        normalized["tags"] = sorted(
            tags,
            key=lambda tag: (
                str(tag.get("slug", tag.get("name", ""))).casefold(),
                tag.get("id", 0),
            ),
        )

    return normalized


def _copy_scalar(target: dict[str, Any], source: Mapping[str, Any], field: str) -> None:
    value = source.get(field)
    if value not in (None, ""):
        target[field] = value


def _copy_reference(
    target: dict[str, Any],
    source: Mapping[str, Any],
    field: str,
    fields: tuple[str, ...],
) -> None:
    value = _reference(source.get(field), fields)
    if value is not None:
        target[field] = value


def _reference(value: object, fields: tuple[str, ...]) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    reference = {field: value[field] for field in fields if value.get(field) not in (None, "")}
    return reference or None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
