#!/usr/bin/env python3
"""Counterexample: agent-index rollback does NOT restore CRLF bytes. Found 2026-09-11.

HISTORICAL EVIDENCE, NOT A TEST. It is not in any runner and must not be added to one:
it reproduces an OPEN defect, so it fails on purpose while the defect stands. A
counterexample that stops reproducing its counterexample is worthless as a record.

  _publish_snapshot_pair captures the prior index with
      previous_index = index_path.read_text(encoding="utf-8")
  which applies universal-newline translation, so a CRLF index is read back as LF.
  The rollback then writes that LF text. "Restore the prior index" does not restore
  the prior bytes.

Reachable from BOTH export views: export_devices and export_network both route through
_publish_snapshot_pair. Scope of the claim: successful index publication, followed by
canonical publication failure, followed by successful restoration.

Found while preparing a Saga usefulness trial that was stopped before execution. Full
provenance: saga `.planning/evidence/usefulness-trial-20260911/`, at netbox-scribe
`4eb767ca91d2df515dbb9f3d3cd1776ea73c0d7e`.

Run:  python3 .planning/evidence/crlf-rollback-counterexample.py
Exit: 0 = defect reproduced (expected today); 1 = it no longer reproduces.
"""

import sys
import tempfile
from pathlib import Path

from netbox_scribe import exporter


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        canonical, index = root / "canonical.yaml", root / "INDEX.md"
        canonical.write_bytes(b"previous canonical\n")
        prior = b"previous index\r\n"
        index.write_bytes(prior)

        publication_error = OSError("publication sentinel")
        real_publish = exporter.publish_text_atomically

        def failing_publish(path: Path, content: str) -> None:
            if path == canonical:
                raise publication_error
            real_publish(path, content)

        exporter.publish_text_atomically = failing_publish  # type: ignore[assignment]
        try:
            exporter._publish_snapshot_pair(
                canonical_path=canonical,
                canonical_content="new canonical\n",
                index_path=index,
                index_content="new index\n",
            )
        except OSError as raised:
            if raised is not publication_error:
                print(f"UNEXPECTED: {raised!r}")
                return 1
        finally:
            exporter.publish_text_atomically = real_publish  # type: ignore[assignment]

        restored = index.read_bytes()
        if restored == prior:
            print("defect NO LONGER reproduces: CRLF bytes were restored exactly")
            return 1
        print(f"defect reproduces: prior={prior!r} restored={restored!r}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
