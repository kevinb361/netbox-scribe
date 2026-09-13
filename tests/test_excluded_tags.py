from __future__ import annotations

from pathlib import Path
from typing import cast

import httpx
import pytest
import yaml

from netbox_scribe.client import NetBoxClient, NetworkRecords
from netbox_scribe.exporter import (
    export_devices,
    export_network,
    render_devices_yaml,
    render_network_yaml,
)
from netbox_scribe.policy import ExportPolicy


class _NetworkClientStub:
    """Minimal stub providing list_network_records for export_network tests."""

    def __init__(self, records: NetworkRecords) -> None:
        self.records = records

    def list_network_records(self) -> NetworkRecords:
        return self.records


# ---- Excluded tags must skip normalization/validation entirely ----


def test_excluded_tags_none_container_is_skipped() -> None:
    """tags=None with exclude_fields={"tags"} must not raise."""
    rendered = render_devices_yaml(
        [{"id": 42, "name": "example-device", "tags": None}],
        policy=ExportPolicy(exclude_fields=frozenset({"tags"})),
    )
    parsed = yaml.safe_load(rendered)
    assert "tags" not in parsed["devices"][0]


def test_excluded_tags_integer_container_is_skipped() -> None:
    """tags=123 (malformed) with exclude_fields={"tags"} must not raise."""
    rendered = render_devices_yaml(
        [{"id": 42, "name": "example-device", "tags": 123}],
        policy=ExportPolicy(exclude_fields=frozenset({"tags"})),
    )
    parsed = yaml.safe_load(rendered)
    assert "tags" not in parsed["devices"][0]


def test_excluded_tags_mixed_malformed_ids_are_skipped() -> None:
    """Mixed malformed tag IDs that would fail sorting must be skipped when excluded."""
    device = {
        "id": 42,
        "name": "example-device",
        "tags": [
            {"id": "not-an-int", "name": "Bad", "slug": "same-slug"},
            {"id": 2, "name": "Good", "slug": "same-slug"},
        ],
    }
    rendered = render_devices_yaml(
        [device],
        policy=ExportPolicy(exclude_fields=frozenset({"tags"})),
    )
    parsed = yaml.safe_load(rendered)
    assert "tags" not in parsed["devices"][0]


# ---- Inclusion allowlist excluding tags ----


def test_include_allowlist_excluding_tags_omits_tags() -> None:
    """include_fields that does not mention 'tags' must omit tags, even malformed."""
    device = {
        "id": 1,
        "name": "router-01",
        "serial": "ABC",
        "tags": None,
    }
    rendered = render_devices_yaml(
        [device],
        policy=ExportPolicy(include_fields=frozenset({"serial"})),
    )
    parsed = yaml.safe_load(rendered)
    assert parsed["devices"][0]["serial"] == "ABC"
    assert "tags" not in parsed["devices"][0]


# ---- Explicit deny overrides include ----


def test_deny_wins_over_include_for_tags() -> None:
    """include_fields={'tags'} + exclude_fields={'tags'} must omit tags, even malformed."""
    device = {
        "id": 1,
        "name": "router-01",
        "tags": None,
    }
    rendered = render_devices_yaml(
        [device],
        policy=ExportPolicy(
            include_fields=frozenset({"tags"}),
            exclude_fields=frozenset({"tags"}),
        ),
    )
    parsed = yaml.safe_load(rendered)
    assert "tags" not in parsed["devices"][0]


# ---- Network export boundary ----


def test_network_export_excluded_tags_none_is_skipped() -> None:
    """Network render with excluded tags and tags=None must not raise."""
    records = NetworkRecords(
        devices=[{"id": 1, "name": "router-01", "tags": None}],
        interfaces=[],
        ip_addresses=[],
    )
    rendered = render_network_yaml(
        records,
        device_policy=ExportPolicy(exclude_fields=frozenset({"tags"})),
    )
    parsed = yaml.safe_load(rendered)
    assert "tags" not in parsed["devices"][0]


def test_network_export_excluded_tags_malformed_is_skipped() -> None:
    """Network render with excluded tags and tags=42 must not raise."""
    records = NetworkRecords(
        devices=[{"id": 1, "name": "router-01", "tags": 42}],
        interfaces=[],
        ip_addresses=[],
    )
    rendered = render_network_yaml(
        records,
        device_policy=ExportPolicy(exclude_fields=frozenset({"tags"})),
    )
    parsed = yaml.safe_load(rendered)
    assert "tags" not in parsed["devices"][0]


# ---- Retained validation for included bad tags ----


def test_included_tags_none_container_still_raises() -> None:
    """When tags is included (default), tags=None must still raise."""
    with pytest.raises(ValueError, match="must be an array"):
        render_devices_yaml([{"id": 42, "name": "example-device", "tags": None}])


def test_included_tags_integer_container_still_raises() -> None:
    """When tags is included (default), tags=123 must still raise."""
    with pytest.raises(ValueError, match="must be an array"):
        render_devices_yaml([{"id": 42, "name": "example-device", "tags": 123}])


def test_included_tags_mixed_malformed_ids_still_raises() -> None:
    """When tags is included (default), mixed malformed IDs must still raise.

    Both tags share the same slug so sorting falls back to comparing IDs,
    which triggers the type error between str and int.
    """
    device = {
        "id": 42,
        "name": "example-device",
        "tags": [
            {"id": "not-an-int", "name": "Bad", "slug": "same-slug"},
            {"id": 2, "name": "Good", "slug": "same-slug"},
        ],
    }
    with pytest.raises(ValueError, match="tags"):
        render_devices_yaml([device])


# ---- Unchanged valid sorted tag output ----


def test_valid_tags_are_still_sorted_when_included() -> None:
    """Default policy must still sort valid tags deterministically."""
    device = {
        "id": 1,
        "name": "router-01",
        "tags": [
            {"id": 8, "name": "Managed", "slug": "managed"},
            {"id": 7, "name": "Access", "slug": "access"},
        ],
    }
    rendered = render_devices_yaml([device])
    parsed = yaml.safe_load(rendered)
    tags = parsed["devices"][0]["tags"]
    assert len(tags) == 2
    assert tags[0]["slug"] == "access"
    assert tags[1]["slug"] == "managed"


# ---- Full export_devices integration with excluded tags ----


def test_export_devices_with_excluded_tags_and_none(tmp_path: Path) -> None:
    """export_devices with excluded tags and tags=None must succeed."""
    output = tmp_path / "devices.yaml"
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
                    "results": [{"id": 42, "name": "example-device", "tags": None}],
                },
            )
        ),
    )
    count = export_devices(
        client,
        output,
        policy=ExportPolicy(exclude_fields=frozenset({"tags"})),
    )
    assert count == 1
    parsed = yaml.safe_load(output.read_text())
    assert "tags" not in parsed["devices"][0]


# ---- Full export_network integration with excluded tags ----


def test_export_network_with_excluded_tags_and_none(tmp_path: Path) -> None:
    """export_network with excluded tags and tags=None must succeed."""
    output = tmp_path / "network.yaml"
    records = NetworkRecords(
        devices=[{"id": 1, "name": "router-01", "tags": None}],
        interfaces=[],
        ip_addresses=[],
    )
    count = export_network(
        cast(NetBoxClient, _NetworkClientStub(records)),
        output,
        device_policy=ExportPolicy(exclude_fields=frozenset({"tags"})),
    )
    assert count.devices == 1
    parsed = yaml.safe_load(output.read_text())
    assert "tags" not in parsed["devices"][0]
