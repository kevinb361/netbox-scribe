"""Explicit allow/deny policy for exported inventory fields."""

from __future__ import annotations

from dataclasses import dataclass, field

MANDATORY_DEVICE_FIELDS = frozenset({"id", "name"})
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
