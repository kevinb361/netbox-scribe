# Requirements: NetBox Scribe

## Requirements

- [x] **REQ-001** — an installable `nbscribe` CLI exposes help and version output without requiring NetBox credentials (milestone: v0.1) (depends: none) (evidence: `tests/test_cli.py`; `make ci`; credential-free CLI smoke checks)
- [x] **REQ-002** — the client retrieves every page of synthetic NetBox device results and reports authentication, transport, and malformed-response failures without exposing the API token (milestone: v0.1) (depends: REQ-001) (evidence: `tests/test_client.py`; `make ci` with 13 tests)
- [x] **REQ-003** — `nbscribe export` normalizes device records into schema-versioned canonical YAML with stable ordering and byte-identical output for unchanged input (milestone: v0.1) (depends: REQ-002) (evidence: `tests/test_exporter.py`; `tests/test_cli.py::test_export_command_writes_canonical_yaml`; `make ci` with 15 tests)
- [ ] **REQ-004** — an export is published atomically so a failed run cannot leave a partial snapshot or replace the last valid snapshot (milestone: v0.1) (depends: REQ-003)
- [ ] **REQ-005** — every canonical snapshot validates against a published JSON Schema and incompatible schema versions fail clearly (milestone: v0.1) (depends: REQ-003)
- [ ] **REQ-006** — the exporter generates a concise Markdown agent index that links canonical records and states source type, snapshot freshness, schema version, and exporter version (milestone: v0.1) (depends: REQ-003)
- [ ] **REQ-007** — configuration supports explicit field and custom-field inclusion or exclusion, and synthetic tests prove denied values and credentials never appear in output or logs (milestone: v0.1) (depends: REQ-002)
- [ ] **REQ-008** — public-safe documentation and synthetic fixtures demonstrate installation, read-only NetBox token configuration, export, validation, Git usage, and agent/RAG consumption (milestone: v0.1) (depends: REQ-004, REQ-005, REQ-006, REQ-007)
