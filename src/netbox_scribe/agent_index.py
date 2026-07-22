"""Token-efficient Markdown views for agents and humans."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from netbox_scribe import __version__
from netbox_scribe.client import DeviceRecord
from netbox_scribe.contracts import SCHEMA_VERSION


def render_network_index(
    document: Mapping[str, Any],
    *,
    canonical_path: Path,
    index_path: Path,
    freshness: str,
) -> str:
    """Render bounded device-interface-address navigation over canonical network data."""
    canonical_link = Path(os.path.relpath(canonical_path, start=index_path.parent)).as_posix()
    devices = document.get("devices", [])
    interfaces = document.get("interfaces", [])
    ip_addresses = document.get("ip_addresses", [])
    interfaces_by_device: dict[int, list[Mapping[str, Any]]] = {}
    for interface in interfaces:
        interfaces_by_device.setdefault(int(interface["device"]["id"]), []).append(interface)
    addresses_by_interface: dict[int, list[Mapping[str, Any]]] = {}
    for address in ip_addresses:
        addresses_by_interface.setdefault(int(address["assigned_object"]["id"]), []).append(address)

    lines = [
        "# NetBox Scribe Network Index",
        "",
        "> Generated view. Canonical network inventory remains authoritative.",
        "",
        "- Source: NetBox",
        f"- Source freshness: {freshness}",
        f"- Schema version: {SCHEMA_VERSION}",
        f"- Exporter version: {__version__}",
        f"- Canonical network: [{canonical_path.name}]({canonical_link})",
        "",
        f"## Devices ({len(devices)})",
        "",
    ]
    for device in devices:
        device_id = int(device["id"])
        lines.append(f"- {_code(str(device['name']))} — NetBox device ID {device_id}")
        for interface in interfaces_by_device.get(device_id, []):
            interface_id = int(interface["id"])
            lines.append(f"  - {_code(str(interface['name']))} — interface ID {interface_id}")
            for address in addresses_by_interface.get(interface_id, []):
                lines.append(
                    f"    - {_code(str(address['address']))} — IP address ID {address['id']}"
                )
    return "\n".join(lines) + "\n"


def render_agent_index(
    devices: list[DeviceRecord],
    *,
    canonical_path: Path,
    index_path: Path,
) -> str:
    """Render a concise, deterministic index over canonical device inventory."""
    freshness_values = [
        value
        for device in devices
        if isinstance((value := device.get("last_updated")), str) and value
    ]
    freshness = max(freshness_values, default="unknown")
    canonical_link = Path(os.path.relpath(canonical_path, start=index_path.parent)).as_posix()

    lines = [
        "# NetBox Scribe Agent Index",
        "",
        "> Generated view. Canonical inventory remains authoritative.",
        "",
        "- Source: NetBox",
        f"- Source freshness: {freshness}",
        f"- Schema version: {SCHEMA_VERSION}",
        f"- Exporter version: {__version__}",
        f"- Canonical inventory: [{canonical_path.name}]({canonical_link})",
        "",
        f"## Devices ({len(devices)})",
        "",
    ]
    for device in sorted(
        devices,
        key=lambda record: (str(record.get("name", "")).casefold(), int(record.get("id", 0))),
    ):
        lines.append(f"- {_code(str(device['name']))} — NetBox ID {device['id']}")
    return "\n".join(lines) + "\n"


def _code(value: str) -> str:
    safe = value.replace("\r", " ").replace("\n", " ")
    delimiter = "``" if "`" in safe else "`"
    return f"{delimiter}{safe}{delimiter}"
