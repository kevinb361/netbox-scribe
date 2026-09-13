"""Canonical inventory normalization and serialization."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from netbox_scribe.agent_index import render_agent_index, render_network_index
from netbox_scribe.client import DeviceRecord, NetBoxClient, NetworkRecords
from netbox_scribe.contracts import SCHEMA_VERSION
from netbox_scribe.policy import ExportPolicy, NetworkExportPolicy, ResourcePolicy
from netbox_scribe.validation import (
    SnapshotValidationError,
    record_location,
    validate_snapshot_text,
)


@dataclass(frozen=True, slots=True)
class NetworkExportCounts:
    devices: int
    interfaces: int
    ip_addresses: int


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
    normalized = [
        _normalize_device(device, effective_policy, position)
        for position, device in enumerate(devices)
    ]
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


def export_network(
    client: NetBoxClient,
    output: Path,
    *,
    agent_index: Path | None = None,
    policy: NetworkExportPolicy | None = None,
    device_policy: ExportPolicy | None = None,
) -> NetworkExportCounts:
    """Write the canonical network document and optional derived index."""
    records = client.list_network_records()
    content = render_network_yaml(records, policy=policy, device_policy=device_policy)
    document = validate_snapshot_text(content)
    if agent_index is None:
        publish_text_atomically(output, content)
    else:
        if output == agent_index:
            raise ValueError("canonical output and agent index must use different paths")
        index_content = render_network_index(
            document,
            canonical_path=output,
            index_path=agent_index,
            freshness=_network_freshness(records),
        )
        _publish_snapshot_pair(
            canonical_path=output,
            canonical_content=content,
            index_path=agent_index,
            index_content=index_content,
        )
    return NetworkExportCounts(
        devices=len(records.devices),
        interfaces=len(records.interfaces),
        ip_addresses=len(records.ip_addresses),
    )


def _network_freshness(records: NetworkRecords) -> str:
    values = [
        value
        for record in records.devices + records.interfaces + records.ip_addresses
        if isinstance((value := record.get("last_updated")), str) and value
    ]
    return max(values, default="unknown")


def render_network_yaml(
    records: NetworkRecords,
    *,
    policy: NetworkExportPolicy | None = None,
    device_policy: ExportPolicy | None = None,
) -> str:
    """Normalize and deterministically render the canonical network document."""
    effective_policy = policy or NetworkExportPolicy()
    devices = [
        _normalize_device(device, device_policy or ExportPolicy(), position)
        for position, device in enumerate(records.devices)
    ]
    interfaces = [
        _normalize_interface(interface, effective_policy.interfaces, position)
        for position, interface in enumerate(records.interfaces)
    ]
    ip_addresses = [
        _normalize_ip_address(address, effective_policy.ip_addresses, position)
        for position, address in enumerate(records.ip_addresses)
    ]
    _validate_network_relationships(devices, interfaces, ip_addresses)
    document = {
        "schema_version": SCHEMA_VERSION,
        "source": "netbox",
        "devices": sorted(devices, key=lambda record: int(record["id"])),
        "interfaces": sorted(interfaces, key=lambda record: int(record["id"])),
        "ip_addresses": sorted(ip_addresses, key=lambda record: int(record["id"])),
    }
    return yaml.dump(
        document,
        Dumper=_CanonicalDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100,
    )


def publish_text_atomically(output: Path, content: str) -> None:
    """Replace an output file only after its complete content is durable."""
    _publish_bytes_atomically(output, content.encode("utf-8"))


def _publish_bytes_atomically(output: Path, content: bytes) -> None:
    """Atomically replace an output with exact bytes after flushing them to disk."""
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent,
        prefix=f".{output.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
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
    previous_index = index_path.read_bytes() if index_path.exists() else None
    publish_text_atomically(index_path, index_content)
    try:
        publish_text_atomically(canonical_path, canonical_content)
    except OSError as publication_error:
        try:
            if previous_index is None:
                index_path.unlink(missing_ok=True)
            else:
                _publish_bytes_atomically(index_path, previous_index)
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
    normalized = [
        _normalize_device(device, effective_policy, position)
        for position, device in enumerate(devices)
    ]
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


def _normalize_device(device: DeviceRecord, policy: ExportPolicy, position: int) -> dict[str, Any]:
    location = record_location("devices", device, position)
    device_id = _positive_id(device.get("id"), location, "id")
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

    try:
        source_tags = iter(device.get("tags", []))
    except TypeError:
        raise _invalid_record(location, "tags", "must be an array") from None
    tags = [
        reference
        for tag in source_tags
        if (reference := _reference(tag, ("id", "name", "slug"))) is not None
    ]
    if tags:
        try:
            normalized["tags"] = sorted(
                tags,
                key=lambda tag: (
                    str(tag.get("slug", tag.get("name", ""))).casefold(),
                    tag.get("id", 0),
                ),
            )
        except TypeError:
            # Mixed malformed IDs can fail sorting before schema validation is reached.
            for index, tag in enumerate(tags):
                if "id" in tag and type(tag["id"]) is not int:
                    raise _invalid_record(
                        location, f"tags[{index + 1}].id", "must be an integer"
                    ) from None
            raise _invalid_record(location, "tags", "cannot order tag references") from None

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


def _validate_network_relationships(
    devices: list[dict[str, Any]],
    interfaces: list[dict[str, Any]],
    ip_addresses: list[dict[str, Any]],
) -> None:
    device_ids = _unique_ids(devices, "devices")
    interface_ids = _unique_ids(interfaces, "interfaces")
    _unique_ids(ip_addresses, "ip_addresses")
    for position, interface in enumerate(interfaces):
        if interface["device"]["id"] not in device_ids:
            raise _invalid_record(
                record_location("interfaces", interface, position),
                "device.id",
                "references missing device",
            )
    for position, address in enumerate(ip_addresses):
        if address["assigned_object"]["id"] not in interface_ids:
            raise _invalid_record(
                record_location("ip_addresses", address, position),
                "assigned_object.id",
                "references missing interface",
            )


def _unique_ids(records: list[dict[str, Any]], resource: str) -> set[int]:
    ids: set[int] = set()
    for position, record in enumerate(records):
        record_id = int(record["id"])
        if record_id in ids:
            raise _invalid_record(record_location(resource, record, position), "id", "duplicate id")
        ids.add(record_id)
    return ids


def _normalize_interface(
    record: DeviceRecord, policy: ResourcePolicy, position: int
) -> dict[str, Any]:
    location = record_location("interfaces", record, position)
    interface_id = _positive_id(record.get("id"), location, "id")
    device_id = _positive_id(_mapping(record.get("device")).get("id"), location, "device.id")
    name = record.get("name")
    normalized: dict[str, Any] = {
        "id": interface_id,
        "name": name if isinstance(name, str) and name.strip() else f"interface-{interface_id}",
        "device": {"type": "dcim.device", "id": device_id},
    }
    for field in ("description", "mac_address", "mtu", "enabled"):
        if policy.allows_field(field):
            _copy_scalar(normalized, record, field)
    _copy_allowed_custom_fields(normalized, record, policy)
    return normalized


def _normalize_ip_address(
    record: DeviceRecord, policy: ResourcePolicy, position: int
) -> dict[str, Any]:
    location = record_location("ip_addresses", record, position)
    address_id = _positive_id(record.get("id"), location, "id")
    address = record.get("address")
    if not isinstance(address, str) or not address:
        raise _invalid_record(location, "address", "must be a non-empty string")
    if record.get("assigned_object_type") != "dcim.interface":
        raise _invalid_record(location, "assigned_object_type", "must be dcim.interface")
    interface_id = _positive_id(record.get("assigned_object_id"), location, "assigned_object_id")
    normalized: dict[str, Any] = {
        "id": address_id,
        "address": address,
        "assigned_object": {"type": "dcim.interface", "id": interface_id},
    }
    for field in ("dns_name", "description"):
        if policy.allows_field(field):
            _copy_scalar(normalized, record, field)
    for field in ("status", "role", "tenant"):
        if policy.allows_field(field):
            _copy_reference(normalized, record, field, ("id", "name", "slug", "value", "label"))
    _copy_allowed_custom_fields(normalized, record, policy)
    return normalized


def _copy_allowed_custom_fields(
    normalized: dict[str, Any], record: DeviceRecord, policy: ResourcePolicy
) -> None:
    custom_fields = _mapping(record.get("custom_fields"))
    allowed = {
        name: custom_fields[name]
        for name in sorted(custom_fields)
        if policy.allows_custom_field(name)
    }
    if allowed:
        normalized["custom_fields"] = allowed


def _positive_id(record_id: object, location: str, field: str) -> int:
    if not isinstance(record_id, int) or isinstance(record_id, bool) or record_id <= 0:
        raise _invalid_record(location, field, "must be a positive integer")
    return record_id


def _invalid_record(location: str, field: str, problem: str) -> SnapshotValidationError:
    """All arguments are structural labels or safe locations, never raw record values."""
    return SnapshotValidationError(f"invalid record at {location} field={field}: {problem}")


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
