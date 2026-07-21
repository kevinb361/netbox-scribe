# v0.2 uses one canonical network document

## Symptom

The first relationship export must represent devices, device interfaces, and assigned IP addresses without weakening the existing guarantee that canonical data and its derived index do not expose mixed generations. Partitioning each resource into a separate YAML file is attractive for Git and RAG, but it requires every reader to understand a commit manifest or generation pointer to obtain atomic semantics.

References: `.planning/REQUIREMENTS.md` REQ-015..REQ-018; `.planning/SPEC.md` requirements `deterministic-canonical-relationship-artifacts`, `atomic-relationship-snapshot-set`, and `bounded-relationship-agent-navigation`.

## Blast Radius

- Time window / scope: every opt-in v0.2 network relationship export and every consumer of its canonical schema.
- Recovery / reversal mechanism: before public release, replace this decision and update the schema/fixtures together; after release, introduce a new schema version and migration guidance rather than silently repartitioning the contract.
- Frequency: the canonical shape is consumed on every relationship export and read.
- Not affected: plain device-only `nbscribe export`, its existing `devices.yaml`, or later decisions about prefixes, VLANs, cables, and virtual machines.

## Evidence Links

- `.planning/REQUIREMENTS.md` — REQ-014 through REQ-019
- `.planning/SPEC.md` — v0.2 relationship scenarios
- `.planning/STATE.md` — v0.2 export-interface design checkpoint
- `src/netbox_scribe/exporter.py` — proven canonical-plus-derived pair publication boundary

## Default Disposition

An explicit network view will produce one schema-versioned canonical YAML document containing separate normalized collections for devices, interfaces, and assigned IP addresses. Relationships use typed NetBox IDs between those collections. One bounded Markdown index is derived from that document and published with it using the canonical-plus-derived atomic boundary. The existing device-only export remains the default.

This chooses a deep, difficult-to-misuse interface and strong reader consistency over resource-level files. Selective RAG ingestion and smaller per-resource Git diffs are deferred until real inventory evidence shows that the unified document is inadequate.

## Override Path

To partition resources later, first provide measured size or retrieval evidence that the unified document is operationally inadequate. Open a new decision that defines reader consistency, schema migration, canonical links, and rollback semantics for either a manifest-committed resource set or immutable generation bundle. Do not split files behind the existing schema version.

## Sign-Off

Accepted: YES — use one canonical network document plus one derived relationship index for v0.2.   Date: 2026-07-21   Operator: Kevin Blalock

> Authorized via selection of Design A in the active coding session on 2026-07-21. Default Disposition accepted; Override Path NOT invoked. Recorded by Pi on operator instruction.
