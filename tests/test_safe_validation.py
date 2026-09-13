from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

from netbox_scribe.cli import main
from netbox_scribe.client import NetBoxClient
from netbox_scribe.validation import SnapshotValidationError, validate_snapshot_text

SECRET = "SYNTHETIC-REJECTED-SECRET\x1b[31m\n" + "x" * 2000


def _assert_safe(message: str) -> None:
    assert "SYNTHETIC" not in message
    assert "synthetic-token" not in message
    assert "\x1b" not in message
    assert all(32 <= ord(char) < 127 for char in message.rstrip("\n"))
    assert len(message) <= 256


@pytest.mark.parametrize("version", [2, SECRET, {SECRET: SECRET}, [SECRET], None])
def test_schema_version_is_not_echoed(version: object) -> None:
    with pytest.raises(SnapshotValidationError) as error:
        validate_snapshot_text(yaml.safe_dump({"schema_version": version}))
    assert str(error.value) == "unsupported schema version; expected 1"
    _assert_safe(str(error.value))


@pytest.mark.parametrize(
    ("record", "location", "problem"),
    [
        (
            {"id": 42, "name": SECRET, "serial": {SECRET: SECRET}},
            "id=42 field=serial",
            "must be a string",
        ),
        (
            {"id": 42, "name": SECRET, "site": {"id": SECRET}},
            "id=42 field=site.id",
            "must be an integer",
        ),
        (
            {"id": 42, "name": SECRET, "tags": [{"name": [SECRET]}]},
            "id=42 field=tags[1].name",
            "must be a string",
        ),
        ({"id": 42}, "id=42 field=name", "required field is missing"),
        ({"id": 42, "name": ""}, "id=42 field=name", "must not be empty"),
        ({"id": SECRET, "name": SECRET}, "record #1 field=id", "must be an integer"),
        ({"id": True, "name": SECRET}, "record #1 field=id", "must be an integer"),
        (
            {"id": 10**100, "name": SECRET, "serial": [SECRET]},
            "record #1 field=serial",
            "must be a string",
        ),
        (
            {"id": 42, "name": SECRET, SECRET: SECRET},
            "id=42",
            "remove fields not allowed by the schema",
        ),
        (
            {"id": 42, "name": SECRET, "site": {SECRET: SECRET}},
            "id=42 field=site",
            "remove fields not allowed by the schema",
        ),
        (
            {"id": 42, "name": SECRET, "custom_fields": [SECRET]},
            "id=42 field=custom_fields",
            "must be a mapping",
        ),
    ],
)
def test_schema_diagnostics_use_only_structural_labels(
    record: dict[str, Any], location: str, problem: str
) -> None:
    content = yaml.safe_dump({"schema_version": 1, "source": "netbox", "devices": [record]})
    with pytest.raises(SnapshotValidationError) as error:
        validate_snapshot_text(content)
    assert str(error.value) == f"snapshot violates schema at devices {location}: {problem}"
    _assert_safe(str(error.value))


def test_adversarial_keys_and_error_order_are_safe_and_deterministic() -> None:
    record = {"id": 42, "name": SECRET, "serial": [SECRET], "display": [SECRET]}
    for candidate in (record, dict(reversed(list(record.items())))):
        document = {"schema_version": 1, "source": "netbox", "devices": [candidate]}
        with pytest.raises(SnapshotValidationError) as error:
            validate_snapshot_text(yaml.safe_dump(document, sort_keys=False))
        assert str(error.value) == (
            "snapshot violates schema at devices id=42 field=display: must be a string"
        )
    # Unknown YAML keys of different types must never enter the diagnostic.
    adversarial = {
        "schema_version": 1,
        "source": "netbox",
        "devices": [],
        SECRET: SECRET,
        7: SECRET,
    }
    with pytest.raises(SnapshotValidationError) as error:
        validate_snapshot_text(yaml.safe_dump(adversarial, sort_keys=False))
    assert str(error.value) == (
        "snapshot violates schema at root: remove fields not allowed by the schema"
    )
    _assert_safe(str(error.value))


@pytest.mark.parametrize("view", ["devices", "network"])
@pytest.mark.parametrize(
    ("resource", "changes", "flags", "diagnostic"),
    [
        (
            "devices",
            {"serial": {SECRET: SECRET}},
            [],
            "snapshot violates schema at devices id=42 field=serial: must be a string",
        ),
        (
            "devices",
            {"status": {"value": [SECRET]}},
            [],
            "snapshot violates schema at devices id=42 field=status.value: must be a string",
        ),
        (
            "devices",
            {"id": SECRET},
            [],
            "invalid record at devices record #2 field=id: must be a positive integer",
        ),
        (
            "devices",
            {"id": True},
            [],
            "invalid record at devices record #2 field=id: must be a positive integer",
        ),
        (
            "devices",
            {"tags": None},
            [],
            "invalid record at devices id=42 field=tags: must be an array",
        ),
        (
            "devices",
            {"tags": [{"slug": "same", "id": 1}, {"slug": "same", "id": SECRET}]},
            [],
            "invalid record at devices id=42 field=tags[2].id: must be an integer",
        ),
        (
            "devices",
            {"tags": [{"slug": "same", "id": {}}, {"slug": "same", "id": {SECRET: SECRET}}]},
            [],
            "invalid record at devices id=42 field=tags[1].id: must be an integer",
        ),
        (
            "interfaces",
            {"device": {"id": SECRET}},
            [],
            "invalid record at interfaces id=52 field=device.id: must be a positive integer",
        ),
        (
            "interfaces",
            {"id": SECRET},
            [],
            "invalid record at interfaces record #2 field=id: must be a positive integer",
        ),
        (
            "interfaces",
            {"mtu": SECRET},
            ["--include-interface-field", "mtu"],
            "snapshot violates schema at interfaces id=52 field=mtu: must be an integer",
        ),
        (
            "interfaces",
            {"device": {"id": 999}},
            [],
            "invalid record at interfaces id=52 field=device.id: references missing device",
        ),
        (
            "ip_addresses",
            {"address": {SECRET: SECRET}},
            [],
            "invalid record at ip_addresses id=62 field=address: must be a non-empty string",
        ),
        (
            "ip_addresses",
            {"assigned_object_type": SECRET},
            [],
            "invalid record at ip_addresses id=62 field=assigned_object_type: "
            "must be dcim.interface",
        ),
        (
            "ip_addresses",
            {"assigned_object_id": SECRET},
            [],
            "invalid record at ip_addresses id=62 field=assigned_object_id: "
            "must be a positive integer",
        ),
        (
            "ip_addresses",
            {"dns_name": {SECRET: SECRET}},
            ["--include-ip-address-field", "dns_name"],
            "snapshot violates schema at ip_addresses id=62 field=dns_name: must be a string",
        ),
        (
            "ip_addresses",
            {"assigned_object_id": 999},
            [],
            "invalid record at ip_addresses id=62 field=assigned_object.id: "
            "references missing interface",
        ),
        (
            "ip_addresses",
            {"id": 10**100, "assigned_object_id": 999},
            [],
            "invalid record at ip_addresses record #2 field=assigned_object.id: "
            "references missing interface",
        ),
    ],
)
def test_cli_invalid_export_preserves_existing_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    view: str,
    resource: str,
    changes: dict[str, Any],
    flags: list[str],
    diagnostic: str,
) -> None:
    # Device-only runs of network cases still exercise the corresponding malformed device field.
    if view == "devices" and resource != "devices":
        resource, changes, flags = "devices", {"description": [SECRET]}, []
        diagnostic = "snapshot violates schema at devices id=42 field=description: must be a string"
    resources: dict[str, list[dict[str, Any]]] = {
        "devices": [{"id": 1, "name": "a"}, {"id": 42, "name": SECRET}],
        "interfaces": [{"id": 2, "device": {"id": 1}}, {"id": 52, "device": {"id": 42}}],
        "ip_addresses": [
            {
                "id": 3,
                "address": "192.0.2.1/24",
                "assigned_object_type": "dcim.interface",
                "assigned_object_id": 2,
            },
            {
                "id": 62,
                "address": SECRET,
                "assigned_object_type": "dcim.interface",
                "assigned_object_id": 52,
            },
        ],
    }
    resources[resource][1].update(changes)
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        requests.append(request.url.path)
        key = request.url.path.rstrip("/").split("/")[-1].replace("-", "_")
        return httpx.Response(200, json={"results": resources[key], "next": None})

    def client_factory(base_url: str, token: str, **kwargs: Any) -> NetBoxClient:
        return NetBoxClient(base_url, token, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("netbox_scribe.cli.NetBoxClient", client_factory)
    monkeypatch.setenv("NETBOX_URL", "https://netbox.example")
    monkeypatch.setenv("NETBOX_TOKEN", "synthetic-token")
    output, index = tmp_path / "inventory.yaml", tmp_path / "INDEX.md"
    previous_output = b"schema_version: 1\r\nsource: netbox\r\ndevices: []\r\n"
    previous_index = b"# Last valid synthetic index\r\n\r\n"
    output.write_bytes(previous_output)
    index.write_bytes(previous_index)
    exit_code = main(
        ["export", "--view", view, "--output", str(output), "--agent-index", str(index), *flags]
    )
    captured = capsys.readouterr()
    assert output.read_bytes() == previous_output
    assert index.read_bytes() == previous_index
    assert set(tmp_path.iterdir()) == {output, index}
    assert requests
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == f"error: {diagnostic}\n"
    _assert_safe(captured.err)


@pytest.mark.parametrize(
    ("document", "diagnostic"),
    [
        ({"devices": [SECRET]}, "devices record #1: must be a mapping"),
        ({"devices": SECRET}, "root field=devices: must be an array"),
        ({"source": SECRET}, "root field=source: must be netbox"),
        (
            {
                "interfaces": [
                    {"id": 52, "name": SECRET, "device": {"id": 0, "type": "dcim.device"}}
                ],
                "ip_addresses": [],
            },
            "interfaces id=52 field=device.id: must be at least 1",
        ),
        (
            {
                "interfaces": [{"id": 52, "name": SECRET, "device": {"id": 42, "type": SECRET}}],
                "ip_addresses": [],
            },
            "interfaces id=52 field=device.type: must be dcim.device",
        ),
        (
            {
                "interfaces": [{"id": 52, "name": SECRET, "device": {"type": "dcim.device"}}],
                "ip_addresses": [],
            },
            "interfaces id=52 field=device.id: required field is missing",
        ),
        (
            {
                "interfaces": [],
                "ip_addresses": [
                    {
                        "id": 62,
                        "address": SECRET,
                        "assigned_object": {"type": "dcim.interface", "id": 52},
                        SECRET: SECRET,
                    }
                ],
            },
            "ip_addresses id=62: remove fields not allowed by the schema",
        ),
        (
            {
                "interfaces": [],
                "ip_addresses": [
                    {"id": 62, "address": SECRET, "assigned_object": {"type": SECRET, "id": 52}}
                ],
            },
            "ip_addresses id=62 field=assigned_object.type: must be dcim.interface",
        ),
        (
            {
                "interfaces": [
                    {
                        "id": 52,
                        "name": SECRET,
                        "device": {"id": 42, "type": "dcim.device"},
                        "enabled": SECRET,
                    }
                ],
                "ip_addresses": [],
            },
            "interfaces id=52 field=enabled: must be a boolean",
        ),
    ],
)
def test_validate_cli_sanitizes_network_and_document_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], document: dict[str, Any], diagnostic: str
) -> None:
    snapshot = tmp_path / "snapshot.yaml"
    snapshot.write_text(
        yaml.safe_dump({"schema_version": 1, "source": "netbox", "devices": [], **document})
    )
    previous = snapshot.read_bytes()
    assert main(["validate", str(snapshot)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"error: snapshot violates schema at {diagnostic}\n"
    assert snapshot.read_bytes() == previous
    _assert_safe(captured.err)


def test_validate_cli_does_not_echo_untrusted_schema_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot = tmp_path / "snapshot.yaml"
    snapshot.write_text(yaml.safe_dump({"schema_version": SECRET}))
    assert main(["validate", str(snapshot)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: unsupported schema version; expected 1\n"
    _assert_safe(captured.err)
