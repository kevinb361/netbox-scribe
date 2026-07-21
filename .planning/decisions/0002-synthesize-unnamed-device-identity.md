# Unnamed NetBox devices use a stable exported identity

## Symptom
NetBox device names may be null or absent, while the v1 snapshot schema requires every exported device to have a non-empty `name`. Passing such records through caused an uncaught exception and prevented the entire snapshot from being produced.

References: `.planning/AUDIT.md` finding C1 and `tests/test_exporter.py` unnamed-device coverage.

## Blast Radius
- Time window / scope: every device snapshot containing an unnamed record.
- Recovery / reversal mechanism: change the v1 normalization rule and regenerate snapshots, or introduce a later schema version with nullable names.
- Frequency: every export; the fallback is used only when the source name is null, absent, or empty.
- Not affected: named devices, NetBox source data, NetBox IDs, and read-only API behavior.

## Evidence Links
- `.planning/AUDIT.md` — independently reproduced null-name and missing-name failures.
- `src/netbox_scribe/exporter.py` — canonical device normalization.
- `tests/test_exporter.py` — deterministic fallback contract.

## Default Disposition
Preserve every valid-ID device by exporting its source name when usable and otherwise synthesizing `device-<NetBox ID>`. The fallback is deterministic, unique among synthesized identities, schema-compatible, and visibly synthetic. A source device may already use the same literal name, so consumers must use the NetBox ID—not the exported name—as the unique key. Records without a usable integer ID fail with a bounded operator error rather than being skipped or assigned unstable identity.

## Override Path
To preserve nullable source names literally, introduce a new schema version that makes the identity contract explicit, update the agent index and downstream consumers, regenerate fixtures, and supersede this record. To skip unnamed devices instead, add an explicit policy with warnings and completeness metadata rather than silently dropping records.

## Sign-Off
Accepted: YES — use `device-<id>` as the exported name for unnamed devices.   Date: 2026-07-21   Operator: Kevin Blalock

> Authorized via the active coding session (“do it”) on 2026-07-21. Default Disposition accepted; Override Path NOT invoked. Recorded by the coding agent on operator instruction.
