from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from netbox_scribe.client import NetBoxClient, NetworkRecords
from netbox_scribe.exporter import export_network, render_network_yaml
from netbox_scribe.policy import NetworkExportPolicy, ResourcePolicy
from netbox_scribe.validation import validate_snapshot_text


class _NetworkClientStub:
    def __init__(self, records: NetworkRecords) -> None:
        self.records = records

    def list_network_records(self) -> NetworkRecords:
        return self.records


@pytest.mark.parametrize(
    "previous_index", [b"last-valid-index\n", b"last-valid-index\r\n"], ids=["lf", "crlf"]
)
def test_network_export_rolls_back_index_when_canonical_publication_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, previous_index: bytes
) -> None:
    output = tmp_path / "inventory/network.yaml"
    index = tmp_path / "agent/NETWORK.md"
    output.parent.mkdir()
    index.parent.mkdir()
    previous_output = b"last-valid-network\n"
    output.write_bytes(previous_output)
    index.write_bytes(previous_index)
    records = NetworkRecords(
        devices=[{"id": 1, "name": "router-01"}],
        interfaces=[{"id": 2, "name": "eth0", "device": {"id": 1}}],
        ip_addresses=[],
    )
    from netbox_scribe import exporter

    real_publish = exporter.publish_text_atomically

    def fail_canonical(path: Path, content: str) -> None:
        if path == output:
            assert index.read_bytes() != previous_index
            raise OSError("simulated network publication failure")
        real_publish(path, content)

    monkeypatch.setattr(exporter, "publish_text_atomically", fail_canonical)

    with pytest.raises(OSError, match="simulated network publication failure"):
        export_network(cast(NetBoxClient, _NetworkClientStub(records)), output, agent_index=index)

    assert output.read_bytes() == previous_output
    assert index.read_bytes() == previous_index


def test_network_export_rejects_dangling_device_reference_before_publication(
    tmp_path: Path,
) -> None:
    output = tmp_path / "network.yaml"
    output.write_text("last-valid-network\n")
    records = NetworkRecords(
        devices=[{"id": 1, "name": "router-01"}],
        interfaces=[{"id": 2, "name": "eth0", "device": {"id": 999}}],
        ip_addresses=[],
    )

    with pytest.raises(ValueError, match="interface 2 references missing device 999"):
        export_network(cast(NetBoxClient, _NetworkClientStub(records)), output)

    assert output.read_text() == "last-valid-network\n"


@pytest.mark.parametrize(
    ("records", "message"),
    [
        (
            NetworkRecords(
                devices=[{"id": 1, "name": "a"}, {"id": 1, "name": "b"}],
                interfaces=[],
                ip_addresses=[],
            ),
            "duplicate device ids",
        ),
        (
            NetworkRecords(
                devices=[{"id": 1, "name": "router-01"}],
                interfaces=[{"id": 2, "name": "eth0", "device": {"id": 1}}],
                ip_addresses=[
                    {
                        "id": 3,
                        "address": "192.0.2.1/24",
                        "assigned_object_type": "dcim.interface",
                        "assigned_object_id": 999,
                    }
                ],
            ),
            "IP address 3 references missing interface 999",
        ),
    ],
)
def test_network_yaml_rejects_ambiguous_or_dangling_relationships(
    records: NetworkRecords, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        render_network_yaml(records)


def test_network_policy_includes_only_explicit_related_fields_and_deny_wins() -> None:
    records = NetworkRecords(
        devices=[{"id": 1, "name": "router-01"}],
        interfaces=[
            {
                "id": 2,
                "name": "eth0",
                "device": {"id": 1},
                "description": "allowed-interface-description",
                "mac_address": "denied-mac",
                "custom_fields": {"owner": "allowed-owner", "secret": "denied-secret"},
            }
        ],
        ip_addresses=[
            {
                "id": 3,
                "address": "192.0.2.1/24",
                "assigned_object_type": "dcim.interface",
                "assigned_object_id": 2,
                "dns_name": "allowed.example.test",
                "description": "denied-ip-description",
            }
        ],
    )
    policy = NetworkExportPolicy(
        interfaces=ResourcePolicy(
            include_fields=frozenset({"description", "mac_address"}),
            exclude_fields=frozenset({"mac_address"}),
            include_custom_fields=frozenset({"owner", "secret"}),
            exclude_custom_fields=frozenset({"secret"}),
        ),
        ip_addresses=ResourcePolicy(
            include_fields=frozenset({"dns_name", "description"}),
            exclude_fields=frozenset({"description"}),
        ),
    )

    rendered = render_network_yaml(records, policy=policy)

    assert "allowed-interface-description" in rendered
    assert "allowed-owner" in rendered
    assert "allowed.example.test" in rendered
    assert "denied-mac" not in rendered
    assert "denied-secret" not in rendered
    assert "denied-ip-description" not in rendered


def test_network_yaml_is_deterministic_and_valid_under_reordered_input() -> None:
    devices = [{"id": 2, "name": "switch-02"}, {"id": 1, "name": "router-01"}]
    interfaces = [
        {"id": 20, "name": "eth1", "device": {"id": 2}},
        {"id": 10, "name": "eth0", "device": {"id": 1}},
    ]
    addresses = [
        {
            "id": 200,
            "address": "192.0.2.2/24",
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": 20,
        },
        {
            "id": 100,
            "address": "192.0.2.1/24",
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": 10,
        },
    ]

    first = render_network_yaml(NetworkRecords(devices, interfaces, addresses))
    second = render_network_yaml(
        NetworkRecords(
            list(reversed(devices)), list(reversed(interfaces)), list(reversed(addresses))
        )
    )

    assert first == second
    document = validate_snapshot_text(first)
    assert [record["id"] for record in document["devices"]] == [1, 2]
    assert [record["id"] for record in document["interfaces"]] == [10, 20]
    assert [record["id"] for record in document["ip_addresses"]] == [100, 200]
