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

#### Scenario: plaintext-token-transport

- GIVEN the configured NetBox URL uses HTTP
- WHEN an export starts without explicit insecure-transport acknowledgement
- THEN configuration fails before any request is sent
- AND trusted-network operators may opt in explicitly with `--allow-insecure-http`

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

#### Scenario: unnamed-device

- GIVEN NetBox returns a valid device ID with a null, empty, or absent name
- WHEN the device is normalized
- THEN its exported name is the deterministic value `device-<id>`
- AND the complete snapshot remains valid

### REQ: atomic-snapshot-publication

The system SHALL publish a complete snapshot atomically and preserve the last valid snapshot when a run fails.

#### Scenario: publication-failure

- GIVEN a valid snapshot already exists
- WHEN fetching, writing, syncing, or replacing the new snapshot fails
- THEN the prior snapshot remains unchanged
- AND temporary publication files are removed

#### Scenario: derived-view-publication-failure

- GIVEN a valid canonical snapshot and agent index already exist
- WHEN either new artifact cannot be published
- THEN canonical YAML never advances beyond its derived index
- AND a failed canonical replacement restores the prior index

### REQ: published-schema-validation

The system SHALL validate every canonical snapshot against its packaged JSON Schema before publication.

#### Scenario: incompatible-schema-version

- GIVEN a snapshot declares an unsupported schema version
- WHEN export validation or `nbscribe validate` evaluates it
- THEN validation fails clearly with the received and expected versions
- AND the invalid snapshot is not published

### REQ: provenance-aware-agent-index

The system SHALL generate a concise Markdown index as a derived view over canonical inventory.

#### Scenario: agent-orientation

- GIVEN a successful device export
- WHEN the agent index is generated
- THEN it identifies itself as derived and links canonical YAML relatively
- AND it states NetBox source, source freshness, schema version, exporter version, device count, names, and NetBox IDs

### REQ: explicit-export-redaction-policy

The system SHALL require explicit inclusion for custom fields and support optional core-field allow/deny configuration.

#### Scenario: conflicting-policy

- GIVEN a field appears in both include and exclude configuration
- WHEN inventory is normalized
- THEN exclusion wins
- AND mandatory device identity remains present

#### Scenario: closed-custom-fields

- GIVEN NetBox returns custom fields
- WHEN none are explicitly included
- THEN no custom field value appears in YAML, Markdown, stdout, or stderr

### REQ: public-history-safety

The project SHALL be publishable without credentials, private infrastructure, or unreviewed legal ambiguity in its tracked tree or reachable Git history.

#### Scenario: public-readiness-scan

- GIVEN every commit and tracked artifact
- WHEN automated secret, private-network, dependency, license, and public-path checks run
- THEN no credential or private infrastructure disclosure remains
- AND intentional maintainer identity/history disclosures are surfaced for operator approval

### REQ: least-privilege-github-ci

The project SHALL run its existing deterministic gate on supported Python versions in GitHub Actions with minimum token permissions.

#### Scenario: pull-request-ci

- GIVEN a push or pull request
- WHEN GitHub Actions executes CI
- THEN Python 3.11 and 3.12 each run the locked `make ci` gate
- AND workflow actions are immutable-SHA pinned with repository contents read-only

### REQ: public-contributor-security-policy

The project SHALL document contribution checks, compatibility expectations, sensitive-data boundaries, and private vulnerability reporting.

#### Scenario: fresh-contributor

- GIVEN a contributor or security reporter arrives without session context
- WHEN they read project entry-point documentation
- THEN they can run the required gate and report changes or vulnerabilities without publishing secrets or real inventory

### REQ: operator-gated-github-publication

The project SHALL provide a reproducible publication handoff while retaining explicit approval for repository creation and public pushes.

#### Scenario: prepared-not-published

- GIVEN public-readiness checks pass
- WHEN preparation completes
- THEN repository settings, security controls, branch protection, and mirror commands are documented
- AND no GitHub resource or public ref is created until the operator approves it

### REQ: public-safe-operator-guidance

The system SHALL provide public-safe guidance and synthetic fixtures for the complete snapshot workflow.

#### Scenario: cold-reader-workflow

- GIVEN an operator has Python, uv, and a read-only NetBox token
- WHEN they follow the project documentation
- THEN they can install, export, validate, review Git changes, and orient an agent or RAG index
- AND all published examples remain synthetic and credential-free
