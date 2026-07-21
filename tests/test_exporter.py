from __future__ import annotations

from netbox_scribe.exporter import render_devices_yaml


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
