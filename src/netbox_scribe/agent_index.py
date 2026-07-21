"""Token-efficient Markdown views for agents and humans."""

from __future__ import annotations

import os
from pathlib import Path

from netbox_scribe import __version__
from netbox_scribe.client import DeviceRecord
from netbox_scribe.contracts import SCHEMA_VERSION


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
