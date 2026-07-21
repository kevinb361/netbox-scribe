# Traceability: NetBox Scribe

| Requirement | Claim | Status | Evidence |
|---|---|---|---|
| REQ-001 | installable credential-independent CLI help/version | **PROVEN** | `tests/test_cli.py`; `make ci` (2 tests); `env -u NETBOX_URL -u NETBOX_TOKEN uv run nbscribe --help/--version` |
| REQ-002 | safe paginated NetBox device retrieval | **PROVEN** | `tests/test_client.py` covers multi-page retrieval, auth/transport/HTTP/malformed failures, repeated pages, same-origin enforcement, and token-safe errors; `make ci` (13 tests) |
| REQ-003 | deterministic canonical YAML export | **PROVEN** | `tests/test_exporter.py` pins normalized schema-versioned YAML and stable ordering; `tests/test_cli.py::test_export_command_writes_canonical_yaml` proves two byte-identical CLI exports; `make ci` (15 tests) |
| REQ-004 | atomic snapshot publication | **OPEN** | Not implemented |
| REQ-005 | published schema validation | **OPEN** | Not implemented |
| REQ-006 | provenance-aware Markdown agent index | **OPEN** | Not implemented |
| REQ-007 | configurable redaction with leak tests | **OPEN** | Not implemented |
| REQ-008 | public-safe end-to-end documentation | **OPEN** | Not implemented |
