from __future__ import annotations

import pytest

from netbox_scribe.validation import SnapshotValidationError, validate_snapshot_text


def test_validation_rejects_incompatible_schema_version_clearly() -> None:
    snapshot = """schema_version: 2
source: netbox
devices: []
"""

    with pytest.raises(SnapshotValidationError, match="unsupported schema version 2; expected 1"):
        validate_snapshot_text(snapshot)
