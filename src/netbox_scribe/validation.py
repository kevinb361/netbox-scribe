"""Canonical snapshot schema validation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from importlib.resources import files
from typing import Any, cast

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

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
        raise SnapshotValidationError(f"unsupported schema version; expected {SCHEMA_VERSION}")

    schema_name = (
        "network.schema.json"
        if "interfaces" in document or "ip_addresses" in document
        else "devices.schema.json"
    )
    schema_resource = files("netbox_scribe.schemas.v1").joinpath(schema_name)
    schema = cast(dict[str, Any], json.loads(schema_resource.read_text(encoding="utf-8")))
    # Only schema-owned property names may enter a diagnostic, never instance keys/messages.
    fields = set(schema["properties"])
    for definition in schema["$defs"].values():
        fields.update(definition.get("properties", {}))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(document),
        key=lambda error: (
            tuple(
                (0, part) if isinstance(part, int) else (1, part if part in fields else "?")
                for part in error.absolute_path
            ),
            str(error.validator),
        ),
    )
    if errors:
        raise SnapshotValidationError(_schema_diagnostic(errors[0], document, fields))
    return document


def record_location(resource: str, record: object, position: int) -> str:
    """Locate a record using a caller-owned resource label and a bounded integer only."""
    record_id = record.get("id") if isinstance(record, Mapping) else None
    if type(record_id) is int and 0 < record_id <= 2**63 - 1:
        return f"{resource} id={record_id}"
    return f"{resource} record #{position + 1}"


def _schema_diagnostic(error: ValidationError, document: dict[str, Any], fields: set[str]) -> str:
    path = list(error.absolute_path)
    location = "root"
    if (
        len(path) >= 2
        and isinstance(path[0], str)
        and path[0] in ("devices", "interfaces", "ip_addresses")
        and isinstance(path[1], int)
    ):
        resource, position = path[0], path[1]
        location = record_location(resource, document[resource][position], position)
        path = path[2:]
    if error.validator == "required":
        # required and properties come from the packaged schema, not the rejected record.
        required = cast(list[str], error.validator_value)
        instance = cast(dict[str, Any], error.instance)
        path.append(sorted(key for key in required if key not in instance)[0])
    field = ""
    for part in path[:8]:
        if isinstance(part, int):
            field += f"[{part + 1}]"
        elif part in fields:
            field += ("." if field else "") + part
        else:
            break
        if part == "custom_fields":
            break
    if field:
        location += f" field={field[:96]}"
    problem = {
        "required": "required field is missing",
        "additionalProperties": "remove fields not allowed by the schema",
        "minLength": "must not be empty",
        "minimum": "must be at least 1",
        "const": "must match the schema constant",
    }.get(str(error.validator), "does not satisfy the schema")
    if error.validator == "const":
        problem = f"must be {error.validator_value}"
    if error.validator == "type":
        problem = {
            "string": "must be a string",
            "integer": "must be an integer",
            "boolean": "must be a boolean",
            "object": "must be a mapping",
            "array": "must be an array",
        }.get(str(error.validator_value), "has an invalid type")
    return f"snapshot violates schema at {location}: {problem}"
