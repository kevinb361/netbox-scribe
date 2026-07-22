"""Canonical snapshot schema validation."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, cast

import yaml
from jsonschema import Draft202012Validator

from netbox_scribe.contracts import SCHEMA_VERSION


class SnapshotValidationError(ValueError):
    """A canonical snapshot does not satisfy its published contract."""


def validate_snapshot_text(content: str) -> dict[str, Any]:
    """Parse and validate canonical snapshot text, returning its document."""
    try:
        document = yaml.safe_load(content)
    except yaml.YAMLError:
        raise SnapshotValidationError("snapshot is not valid YAML") from None
    if not isinstance(document, dict):
        raise SnapshotValidationError("snapshot root must be a mapping")

    version = document.get("schema_version")
    if version != SCHEMA_VERSION:
        raise SnapshotValidationError(
            f"unsupported schema version {version}; expected {SCHEMA_VERSION}"
        )

    schema_name = (
        "network.schema.json"
        if "interfaces" in document or "ip_addresses" in document
        else "devices.schema.json"
    )
    schema_resource = files("netbox_scribe.schemas.v1").joinpath(schema_name)
    schema = cast(dict[str, Any], json.loads(schema_resource.read_text(encoding="utf-8")))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(document), key=lambda error: list(error.path)
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "root"
        raise SnapshotValidationError(f"snapshot violates schema at {location}: {first.message}")
    return document
