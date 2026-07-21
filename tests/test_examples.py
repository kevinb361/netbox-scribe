from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

import httpx

from netbox_scribe.client import NetBoxClient
from netbox_scribe.exporter import export_devices
from netbox_scribe.policy import ExportPolicy

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "examples"


def test_synthetic_example_outputs_match_production_export(tmp_path: Path) -> None:
    fixture = cast(
        dict[str, Any],
        json.loads((EXAMPLES / "netbox-devices-page.json").read_text(encoding="utf-8")),
    )
    generated_canonical = tmp_path / "inventory/devices.yaml"
    generated_index = tmp_path / "agent/INDEX.md"
    policy = ExportPolicy(include_custom_fields=frozenset({"owner"}))
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=fixture))

    with NetBoxClient("https://netbox.example", "synthetic-token", transport=transport) as client:
        export_devices(
            client,
            generated_canonical,
            agent_index=generated_index,
            policy=policy,
        )

    expected_canonical = EXAMPLES / "output/inventory/devices.yaml"
    expected_index = EXAMPLES / "output/agent/INDEX.md"
    assert generated_canonical.read_bytes() == expected_canonical.read_bytes()
    assert generated_index.read_bytes() == expected_index.read_bytes()


def test_public_docs_and_examples_contain_no_private_networks_or_credentials() -> None:
    public_files = [ROOT / "README.md", ROOT / ".env.example", *EXAMPLES.rglob("*.*")]
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in public_files)

    private_network = re.compile(
        r"(?<![\d.])(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?![\d.])"
    )
    credential_assignment = re.compile(r"NETBOX_TOKEN=[A-Za-z0-9_-]{20,}")
    assert private_network.search(corpus) is None
    assert credential_assignment.search(corpus) is None
