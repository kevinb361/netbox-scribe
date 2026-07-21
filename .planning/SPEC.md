# NetBox Scribe Specification

## Purpose

Provide controlled, versioned infrastructure context derived from an authoritative NetBox instance.

## Scope

- In scope: read-only export tooling and deterministic machine- and agent-readable artifacts.
- Not in scope: writing to NetBox, network discovery, independent inventory editing, or Git credential management.

## Requirements

### REQ: credential-independent-cli-orientation

The system SHALL expose CLI help and exporter version without requiring NetBox configuration or credentials.

#### Scenario: inspect-before-configuration

- GIVEN NetBox URL and token environment variables are absent
- WHEN an operator runs `nbscribe --help` or `nbscribe --version`
- THEN the command exits successfully
- AND no NetBox connection is attempted

### REQ: safe-paginated-device-retrieval

The system SHALL retrieve every page of device records from the read-only NetBox API while keeping credentials out of operator-facing failures.

#### Scenario: paginated-device-list

- GIVEN NetBox returns multiple valid device pages
- WHEN the client lists devices
- THEN records from every page are returned in API order
- AND the token is sent only to the configured NetBox origin

#### Scenario: unusable-api-response

- GIVEN NetBox rejects authentication, cannot be reached, returns an HTTP error, or returns malformed pagination data
- WHEN the client lists devices
- THEN a specific safe client error is raised
- AND neither the API token nor response content appears in that error

#### Scenario: unsafe-pagination

- GIVEN NetBox returns a cross-origin or repeated pagination URL
- WHEN the client follows pagination
- THEN retrieval stops with a safe response error before credentials leave the configured origin or a loop continues

### REQ: deterministic-canonical-device-yaml

The system SHALL export normalized NetBox device records as canonical YAML with an explicit schema version.

#### Scenario: unchanged-inventory

- GIVEN two exports receive semantically identical device records
- WHEN `nbscribe export` writes each snapshot
- THEN both output files are byte-identical
- AND devices, references, tags, and mapping keys have stable ordering

#### Scenario: canonical-core-fields

- GIVEN a NetBox device contains core identity, placement, platform, address, and tag data
- WHEN the device is normalized
- THEN supported core fields are represented consistently in YAML
- AND unconfigured custom fields are not copied implicitly
