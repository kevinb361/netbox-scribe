"""Explicit allow/deny policy for exported inventory fields."""

from __future__ import annotations

from dataclasses import dataclass, field

MANDATORY_DEVICE_FIELDS = frozenset({"id", "name"})
OPTIONAL_INTERFACE_FIELDS = frozenset({"description", "mac_address", "mtu", "enabled"})
OPTIONAL_IP_ADDRESS_FIELDS = frozenset({"dns_name", "description", "status", "role", "tenant"})

OPTIONAL_DEVICE_FIELDS = frozenset(
    {
        "display",
        "status",
        "role",
        "device_type",
        "site",
        "location",
        "rack",
        "tenant",
        "platform",
        "serial",
        "asset_tag",
        "description",
        "primary_ip4",
        "primary_ip6",
        "tags",
    }
)


@dataclass(frozen=True, slots=True)
class ResourcePolicy:
    """Closed-by-default optional and custom fields for one related resource."""

    include_fields: frozenset[str] = field(default_factory=frozenset)
    exclude_fields: frozenset[str] = field(default_factory=frozenset)
    include_custom_fields: frozenset[str] = field(default_factory=frozenset)
    exclude_custom_fields: frozenset[str] = field(default_factory=frozenset)

    def allows_field(self, name: str) -> bool:
        return name in self.include_fields and name not in self.exclude_fields

    def allows_custom_field(self, name: str) -> bool:
        return name in self.include_custom_fields and name not in self.exclude_custom_fields


@dataclass(frozen=True, slots=True)
class NetworkExportPolicy:
    """Independent interface and IP-address export controls."""

    interfaces: ResourcePolicy = field(default_factory=ResourcePolicy)
    ip_addresses: ResourcePolicy = field(default_factory=ResourcePolicy)

    def __post_init__(self) -> None:
        _reject_unknown(self.interfaces, OPTIONAL_INTERFACE_FIELDS, "interface")
        _reject_unknown(self.ip_addresses, OPTIONAL_IP_ADDRESS_FIELDS, "IP address")


def _reject_unknown(policy: ResourcePolicy, allowed: frozenset[str], label: str) -> None:
    unknown = (policy.include_fields | policy.exclude_fields) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"unknown {label} field(s): {names}")


@dataclass(frozen=True, slots=True)
class ExportPolicy:
    """Closed-by-default custom fields with explicit optional-field control."""

    include_fields: frozenset[str] | None = None
    exclude_fields: frozenset[str] = field(default_factory=frozenset)
    include_custom_fields: frozenset[str] = field(default_factory=frozenset)
    exclude_custom_fields: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        configured = self.exclude_fields | (self.include_fields or frozenset())
        unknown = configured - OPTIONAL_DEVICE_FIELDS - MANDATORY_DEVICE_FIELDS
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"unknown device field(s): {names}")

    def allows_field(self, name: str) -> bool:
        included = self.include_fields is None or name in self.include_fields
        return included and name not in self.exclude_fields

    def allows_custom_field(self, name: str) -> bool:
        return name in self.include_custom_fields and name not in self.exclude_custom_fields
