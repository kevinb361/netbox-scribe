from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from netbox_scribe.client import NetBoxClient, NetBoxResponseError
from netbox_scribe.exporter import export_devices, publish_text_atomically, render_devices_yaml
from netbox_scribe.policy import ExportPolicy


def test_render_devices_yaml_normalizes_and_sorts_records() -> None:
    devices = [
        {
            "id": 20,
            "name": "switch-01",
            "display": "Switch 01",
            "status": {"value": "active", "label": "Active"},
            "role": {"id": 4, "name": "Access Switch", "slug": "access-switch"},
            "device_type": {
                "id": 9,
                "model": "ICX 7150-C12P",
                "slug": "icx7150-c12p",
                "manufacturer": {"id": 3, "name": "Ruckus", "slug": "ruckus"},
            },
            "site": {"id": 1, "name": "Home", "slug": "home"},
            "location": None,
            "rack": None,
            "tenant": None,
            "platform": {"id": 2, "name": "FastIron", "slug": "fastiron"},
            "serial": "00123",
            "asset_tag": None,
            "description": "Office access switch",
            "primary_ip4": {
                "id": 30,
                "address": "192.0.2.20/24",
                "dns_name": "switch-01.example.test",
                "description": "Management",
            },
            "primary_ip6": None,
            "tags": [
                {"id": 8, "name": "Managed", "slug": "managed"},
                {"id": 7, "name": "Access", "slug": "access"},
            ],
            "custom_fields": {"secret_note": "must-not-be-copied-implicitly"},
        },
        {
            "id": 10,
            "name": "router-01",
            "display": "Router 01",
            "status": {"value": "active", "label": "Active"},
            "role": None,
            "device_type": None,
            "site": None,
            "location": None,
            "rack": None,
            "tenant": None,
            "platform": None,
            "serial": "",
            "asset_tag": None,
            "description": "",
            "primary_ip4": None,
            "primary_ip6": None,
            "tags": [],
        },
    ]

    rendered = render_devices_yaml(devices)

    assert rendered == """schema_version: 1
source: netbox
devices:
  - id: 10
    name: router-01
    display: Router 01
    status:
      value: active
      label: Active
  - id: 20
    name: switch-01
    display: Switch 01
    status:
      value: active
      label: Active
    role:
      id: 4
      name: Access Switch
      slug: access-switch
    device_type:
      id: 9
      model: ICX 7150-C12P
      slug: icx7150-c12p
      manufacturer:
        id: 3
        name: Ruckus
        slug: ruckus
    site:
      id: 1
      name: Home
      slug: home
    platform:
      id: 2
      name: FastIron
      slug: fastiron
    serial: '00123'
    description: Office access switch
    primary_ip4:
      id: 30
      address: 192.0.2.20/24
      dns_name: switch-01.example.test
      description: Management
    tags:
      - id: 7
        name: Access
        slug: access
      - id: 8
        name: Managed
        slug: managed
"""
    assert "custom_fields" not in rendered
    assert "must-not-be-copied-implicitly" not in rendered


@pytest.mark.parametrize("source_name", [None, ""])
def test_unnamed_devices_receive_stable_exported_identity(source_name: object) -> None:
    rendered = render_devices_yaml([{"id": 42, "name": source_name, "display": "Patch Panel"}])

    assert "id: 42\n    name: device-42" in rendered


def test_devices_with_missing_name_receive_stable_exported_identity() -> None:
    rendered = render_devices_yaml([{"id": 42, "display": "Patch Panel"}])

    assert "id: 42\n    name: device-42" in rendered


def test_device_without_usable_id_fails_cleanly() -> None:
    with pytest.raises(ValueError, match="device record has no usable integer id"):
        render_devices_yaml([{"id": None, "name": None}])


def test_export_policy_accepts_mandatory_identity_names_but_cannot_exclude_them() -> None:
    policy = ExportPolicy(
        include_fields=frozenset({"id", "name"}),
        exclude_fields=frozenset({"id", "name"}),
    )

    rendered = render_devices_yaml(
        [{"id": 1, "name": "router-01", "serial": "hidden"}], policy=policy
    )

    assert "id: 1" in rendered
    assert "name: router-01" in rendered
    assert "hidden" not in rendered


def test_export_policy_includes_only_allowed_fields_and_deny_wins() -> None:
    device = {
        "id": 1,
        "name": "router-01",
        "serial": "allowed-serial",
        "description": "denied-description",
        "custom_fields": {
            "owner": "allowed-owner",
            "secret_note": "denied-custom-secret",
            "api_token": "denied-token-value",
        },
    }
    policy = ExportPolicy(
        include_fields=frozenset({"serial", "description"}),
        exclude_fields=frozenset({"description"}),
        include_custom_fields=frozenset({"owner", "secret_note", "api_token"}),
        exclude_custom_fields=frozenset({"secret_note", "api_token"}),
    )

    rendered = render_devices_yaml([device], policy=policy)

    assert "serial: allowed-serial" in rendered
    assert "owner: allowed-owner" in rendered
    assert "denied-description" not in rendered
    assert "denied-custom-secret" not in rendered
    assert "denied-token-value" not in rendered


def test_atomic_publication_preserves_last_snapshot_and_removes_residue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "inventory" / "devices.yaml"
    output.parent.mkdir()
    output.write_text("last-valid-snapshot\n")

    def fail_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        publish_text_atomically(output, "partial-new-snapshot\n")

    assert output.read_text() == "last-valid-snapshot\n"
    assert list(output.parent.iterdir()) == [output]


def test_failed_index_publication_does_not_advance_canonical_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "inventory" / "devices.yaml"
    index = tmp_path / "agent" / "INDEX.md"
    output.parent.mkdir()
    index.parent.mkdir()
    output.write_text("last-valid-canonical\n")
    index.write_text("last-valid-index\n")
    client = NetBoxClient(
        "https://netbox.example",
        "test-token",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "count": 1,
                    "next": None,
                    "previous": None,
                    "results": [{"id": 1, "name": "router-01"}],
                },
            )
        ),
    )
    real_publish = publish_text_atomically

    def fail_index(path: Path, content: str) -> None:
        if path == index:
            raise OSError("simulated index failure")
        real_publish(path, content)

    monkeypatch.setattr("netbox_scribe.exporter.publish_text_atomically", fail_index)

    with pytest.raises(OSError, match="simulated index failure"):
        export_devices(client, output, agent_index=index)

    assert output.read_text() == "last-valid-canonical\n"
    assert index.read_text() == "last-valid-index\n"


def test_failed_canonical_publication_rolls_back_agent_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "inventory" / "devices.yaml"
    index = tmp_path / "agent" / "INDEX.md"
    output.parent.mkdir()
    index.parent.mkdir()
    output.write_text("last-valid-canonical\n")
    index.write_text("last-valid-index\n")
    client = NetBoxClient(
        "https://netbox.example",
        "test-token",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "count": 1,
                    "next": None,
                    "previous": None,
                    "results": [{"id": 1, "name": "router-01"}],
                },
            )
        ),
    )
    real_publish = publish_text_atomically

    def fail_canonical(path: Path, content: str) -> None:
        if path == output:
            raise OSError("simulated canonical failure")
        real_publish(path, content)

    monkeypatch.setattr("netbox_scribe.exporter.publish_text_atomically", fail_canonical)

    with pytest.raises(OSError, match="simulated canonical failure"):
        export_devices(client, output, agent_index=index)

    assert output.read_text() == "last-valid-canonical\n"
    assert index.read_text() == "last-valid-index\n"


def test_failed_fetch_does_not_replace_last_snapshot(tmp_path: Path) -> None:
    output = tmp_path / "devices.yaml"
    output.write_text("last-valid-snapshot\n")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "simulated failure"})

    client = NetBoxClient(
        "https://netbox.example",
        "test-token",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(NetBoxResponseError, match="HTTP 500"):
        export_devices(client, output)

    assert output.read_text() == "last-valid-snapshot\n"
