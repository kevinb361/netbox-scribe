"""Canonical inventory normalization and serialization."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from netbox_scribe.agent_index import render_agent_index
from netbox_scribe.client import DeviceRecord, NetBoxClient
from netbox_scribe.contracts import SCHEMA_VERSION
from netbox_scribe.policy import ExportPolicy
from netbox_scribe.validation import validate_snapshot_text


class _CanonicalDumper(yaml.SafeDumper):
    """Safe YAML dumper with stable, readable sequence indentation."""

    def ignore_aliases(self, data: Any) -> bool:
        return True

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        super().increase_indent(flow, indentless=False)


def export_devices(
    client: NetBoxClient,
    output: Path,
    *,
    agent_index: Path | None = None,
    policy: ExportPolicy | None = None,
) -> int:
    """Write canonical devices and an optional derived agent index."""
    devices = client.list_devices()
    effective_policy = policy or ExportPolicy()
    normalized = [_normalize_device(device, effective_policy) for device in devices]
    content = _render_devices_yaml(normalized)
    validate_snapshot_text(content)

    if agent_index is None:
        publish_text_atomically(output, content)
    else:
        if output == agent_index:
            raise ValueError("canonical output and agent index must use different paths")
        index_devices = [
            _agent_index_record(source, normalized_device)
            for source, normalized_device in zip(devices, normalized, strict=True)
        ]
        index_content = render_agent_index(
            index_devices,
            canonical_path=output,
            index_path=agent_index,
        )
        _publish_snapshot_pair(
            canonical_path=output,
            canonical_content=content,
            index_path=agent_index,
            index_content=index_content,
        )
    return len(devices)


def publish_text_atomically(output: Path, content: str) -> None:
    """Replace an output file only after its complete content is durable."""
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent,
        prefix=f".{output.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def _publish_snapshot_pair(
    *,
    canonical_path: Path,
    canonical_content: str,
    index_path: Path,
    index_content: str,
) -> None:
    """Publish the index first and roll it back if canonical publication fails."""
    previous_index = index_path.read_text(encoding="utf-8") if index_path.exists() else None
    publish_text_atomically(index_path, index_content)
    try:
        publish_text_atomically(canonical_path, canonical_content)
    except OSError as publication_error:
        try:
            if previous_index is None:
                index_path.unlink(missing_ok=True)
            else:
                publish_text_atomically(index_path, previous_index)
        except OSError:
            raise OSError(
                "canonical publication failed and the prior agent index could not be restored"
            ) from None
        raise publication_error


def _agent_index_record(source: DeviceRecord, normalized: Mapping[str, Any]) -> DeviceRecord:
    record: DeviceRecord = {"id": normalized["id"], "name": normalized["name"]}
    freshness = source.get("last_updated")
    if isinstance(freshness, str) and freshness:
        record["last_updated"] = freshness
    return record


def render_devices_yaml(devices: list[DeviceRecord], *, policy: ExportPolicy | None = None) -> str:
    """Normalize NetBox devices and serialize canonical, deterministic YAML."""
    effective_policy = policy or ExportPolicy()
    normalized = [_normalize_device(device, effective_policy) for device in devices]
    return _render_devices_yaml(normalized)


def _render_devices_yaml(normalized: list[dict[str, Any]]) -> str:
    ordered = sorted(
        normalized,
        key=lambda device: (str(device["name"]).casefold(), int(device["id"])),
    )
    document = {
        "schema_version": SCHEMA_VERSION,
        "source": "netbox",
        "devices": ordered,
    }
    return yaml.dump(
        document,
        Dumper=_CanonicalDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100,
    )


def _normalize_device(device: DeviceRecord, policy: ExportPolicy) -> dict[str, Any]:
    device_id = device.get("id")
    if not isinstance(device_id, int) or isinstance(device_id, bool) or device_id <= 0:
        raise ValueError("device record has no usable integer id")
    source_name = device.get("name")
    name = (
        source_name
        if isinstance(source_name, str) and source_name.strip()
        else f"device-{device_id}"
    )
    normalized: dict[str, Any] = {
        "id": device_id,
        "name": name,
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

    for field in tuple(normalized):
        if field not in {"id", "name"} and not policy.allows_field(field):
            del normalized[field]

    custom_fields = _mapping(device.get("custom_fields"))
    allowed_custom = {
        name: custom_fields[name]
        for name in sorted(custom_fields)
        if policy.allows_custom_field(name)
    }
    if allowed_custom:
        normalized["custom_fields"] = allowed_custom

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
