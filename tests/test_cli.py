from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast

import pytest
import yaml

from netbox_scribe import __version__
from netbox_scribe.cli import main


def test_help_does_not_require_netbox_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("NETBOX_URL", raising=False)
    monkeypatch.delenv("NETBOX_TOKEN", raising=False)

    exit_code = main(["--help"])

    assert exit_code == 0
    assert "Versioned, AI-ready infrastructure context" in capsys.readouterr().out


def test_version_does_not_require_netbox_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("NETBOX_URL", raising=False)
    monkeypatch.delenv("NETBOX_TOKEN", raising=False)

    exit_code = main(["--version"])

    assert exit_code == 0
    assert __version__ == "0.2.0"
    assert re.fullmatch(r"nbscribe \d+\.\d+\.\d+(?:\.dev\d+)?\n", capsys.readouterr().out)


def test_export_command_writes_canonical_yaml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 1,
                "name": "router-01",
                "display": "Router 01",
                "status": {"value": "active", "label": "Active"},
                "last_updated": "2026-07-21T18:00:00Z",
                "description": "cli-denied-description",
                "custom_fields": {
                    "owner": "cli-allowed-owner",
                    "secret_note": "cli-denied-secret",
                },
                "tags": [],
            }
        ],
    }
    output = tmp_path / "inventory" / "devices.yaml"
    agent_index = tmp_path / "agent" / "INDEX.md"

    with _netbox_server(payload) as base_url:
        monkeypatch.setenv("NETBOX_URL", base_url)
        monkeypatch.setenv("NETBOX_TOKEN", "cli-test-secret")
        command = [
            "export",
            "--allow-insecure-http",
            "--output",
            str(output),
            "--agent-index",
            str(agent_index),
            "--exclude-field",
            "description",
            "--include-custom-field",
            "owner",
            "--include-custom-field",
            "secret_note",
            "--exclude-custom-field",
            "secret_note",
        ]

        exit_code = main(command)
        first_export = output.read_bytes()
        second_exit_code = main(command)
        second_export = output.read_bytes()

    assert exit_code == 0
    assert second_exit_code == 0
    assert first_export == second_export
    assert yaml.safe_load(output.read_text()) == {
        "schema_version": 1,
        "source": "netbox",
        "devices": [
            {
                "id": 1,
                "name": "router-01",
                "display": "Router 01",
                "status": {"value": "active", "label": "Active"},
                "custom_fields": {"owner": "cli-allowed-owner"},
            }
        ],
    }
    captured = capsys.readouterr()
    assert captured.out.count("Exported 1 device") == 2
    combined_output = output.read_text() + agent_index.read_text() + captured.out + captured.err
    assert "cli-denied-description" not in combined_output
    assert "cli-denied-secret" not in combined_output
    assert "cli-test-secret" not in combined_output
    assert agent_index.read_text() == f"""# NetBox Scribe Agent Index

> Generated view. Canonical inventory remains authoritative.

- Source: NetBox
- Source freshness: 2026-07-21T18:00:00Z
- Schema version: 1
- Exporter version: {__version__}
- Canonical inventory: [devices.yaml](../inventory/devices.yaml)

## Devices (1)

- `router-01` — NetBox ID 1
"""


def test_network_view_fetches_relationships_and_writes_canonical_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    resources = {
        "/api/dcim/devices/": [
            {
                "id": 1,
                "name": "router-01",
                "last_updated": "2026-07-21T18:00:00Z",
                "serial": "denied-network-serial",
                "custom_fields": {
                    "owner": "included-network-owner",
                    "private_note": "denied-network-note",
                },
            }
        ],
        "/api/dcim/interfaces/": [
            {
                "id": 2,
                "name": "eth0",
                "device": {"id": 1, "name": "router-01"},
                "last_updated": "2026-07-21T19:00:00Z",
            }
        ],
        "/api/ipam/ip-addresses/": [
            {
                "id": 3,
                "address": "192.0.2.1/24",
                "assigned_object_type": "dcim.interface",
                "assigned_object_id": 2,
            }
        ],
    }
    output = tmp_path / "snapshot/inventory/network.yaml"
    index = tmp_path / "snapshot/agent/NETWORK.md"
    monkeypatch.chdir(tmp_path)

    with _netbox_resource_server(resources) as (base_url, requests):
        monkeypatch.setenv("NETBOX_URL", base_url)
        monkeypatch.setenv("NETBOX_TOKEN", "network-cli-secret")
        exit_code = main(
            [
                "export",
                "--view",
                "network",
                "--allow-insecure-http",
                "--exclude-field",
                "serial",
                "--include-custom-field",
                "owner",
            ]
        )

    assert exit_code == 0
    index_text = index.read_text()
    assert "- Source freshness: 2026-07-21T19:00:00Z" in index_text
    assert "- `router-01` — NetBox device ID 1" in index_text
    assert "  - `eth0` — interface ID 2" in index_text
    assert "    - `192.0.2.1/24` — IP address ID 3" in index_text
    assert [request.partition("?")[0] for request in requests] == list(resources)
    document = yaml.safe_load(output.read_text())
    assert document["schema_version"] == 1
    assert document["devices"][0]["id"] == 1
    assert document["devices"][0]["custom_fields"] == {"owner": "included-network-owner"}
    assert "denied-network-serial" not in output.read_text()
    assert "denied-network-note" not in output.read_text()
    assert document["interfaces"][0]["device"] == {"type": "dcim.device", "id": 1}
    assert document["ip_addresses"][0]["assigned_object"] == {
        "type": "dcim.interface",
        "id": 2,
    }
    captured = capsys.readouterr()
    assert "Exported network: 1 device, 1 interface, 1 IP address" in captured.out
    assert "network-cli-secret" not in captured.out + captured.err + output.read_text()


def test_export_command_handles_unnamed_device_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": 7, "name": None, "last_updated": "2026-07-21T19:00:00Z"}],
    }
    output = tmp_path / "snapshot/inventory/devices.yaml"
    index = tmp_path / "snapshot/agent/INDEX.md"
    monkeypatch.chdir(tmp_path)

    with _netbox_server(payload) as base_url:
        monkeypatch.setenv("NETBOX_URL", base_url)
        monkeypatch.setenv("NETBOX_TOKEN", "unnamed-test-secret")
        exit_code = main(["export", "--allow-insecure-http"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert yaml.safe_load(output.read_text())["devices"][0]["name"] == "device-7"
    assert "`device-7` — NetBox ID 7" in index.read_text()
    assert "Traceback" not in captured.err
    assert "unnamed-test-secret" not in captured.out + captured.err


def test_export_command_rejects_http_without_explicit_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "inventory/devices.yaml"
    index = tmp_path / "agent/INDEX.md"
    output.parent.mkdir()
    index.parent.mkdir()
    output.write_text("last-valid-canonical\n")
    index.write_text("last-valid-index\n")
    monkeypatch.setenv("NETBOX_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("NETBOX_TOKEN", "http-cli-secret")

    exit_code = main(["export", "--output", str(output), "--agent-index", str(index)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "HTTPS is required" in captured.err
    assert "--allow-insecure-http" in captured.err
    assert "http-cli-secret" not in captured.out + captured.err
    assert output.read_text() == "last-valid-canonical\n"
    assert index.read_text() == "last-valid-index\n"
    assert list(output.parent.iterdir()) == [output]
    assert list(index.parent.iterdir()) == [index]


def test_export_command_reports_filesystem_failure_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": 1, "name": "router-01"}],
    }
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("file")
    output = blocked_parent / "devices.yaml"
    index = tmp_path / "agent/INDEX.md"

    with _netbox_server(payload) as base_url:
        monkeypatch.setenv("NETBOX_URL", base_url)
        monkeypatch.setenv("NETBOX_TOKEN", "filesystem-test-secret")
        exit_code = main(
            [
                "export",
                "--allow-insecure-http",
                "--output",
                str(output),
                "--agent-index",
                str(index),
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err.startswith("error: ")
    assert "Traceback" not in captured.err
    assert "filesystem-test-secret" not in captured.out + captured.err
    assert not index.exists()


def test_validate_command_reports_incompatible_schema_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot = tmp_path / "devices.yaml"
    snapshot.write_text("schema_version: 2\nsource: netbox\ndevices: []\n")

    exit_code = main(["validate", str(snapshot)])

    assert exit_code == 1
    assert "unsupported schema version 2; expected 1" in capsys.readouterr().err


def test_validate_command_reports_non_utf8_snapshot_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot = tmp_path / "devices.yaml"
    snapshot.write_bytes(b"\xff\xfe")

    exit_code = main(["validate", str(snapshot)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == "error: snapshot is not valid UTF-8\n"
    assert "Traceback" not in captured.err


def test_validate_command_reports_schema_violation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot = tmp_path / "devices.yaml"
    snapshot.write_text("schema_version: 1\nsource: netbox\ndevices:\n  - id: 1\n")

    exit_code = main(["validate", str(snapshot)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "snapshot violates schema" in captured.err
    assert "Traceback" not in captured.err


@contextmanager
def _netbox_resource_server(
    resources: Mapping[str, list[dict[str, object]]],
) -> Iterator[tuple[str, list[str]]]:
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            path = self.path.partition("?")[0]
            records = resources[path]
            body = json.dumps(
                {
                    "count": len(records),
                    "next": None,
                    "previous": None,
                    "results": records,
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = cast(tuple[str, int], server.server_address)
        yield f"http://{host}:{port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@contextmanager
def _netbox_server(payload: Mapping[str, object]) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = cast(tuple[str, int], server.server_address)
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
