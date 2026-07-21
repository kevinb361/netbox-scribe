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
                "tags": [],
            }
        ],
    }
    output = tmp_path / "inventory" / "devices.yaml"

    with _netbox_server(payload) as base_url:
        monkeypatch.setenv("NETBOX_URL", base_url)
        monkeypatch.setenv("NETBOX_TOKEN", "cli-test-secret")

        exit_code = main(["export", "--output", str(output)])
        first_export = output.read_bytes()
        second_exit_code = main(["export", "--output", str(output)])
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
            }
        ],
    }
    assert capsys.readouterr().out.count("Exported 1 device") == 2


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
