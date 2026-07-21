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
