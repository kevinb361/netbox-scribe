---
saga_state_version: 1.0
milestone: v0.2
milestone_name: Network Relationships
status: active
stopped_at: unified network document selected and recorded; REQ-014 retrieval/CLI tracer is next.
last_updated: "2026-07-22T01:35:00Z"
last_activity: 2026-07-21 — selected Design A: opt-in network view publishes one canonical network document plus one derived index.
---

# NetBox Scribe — State

## Current Position

Phase/Milestone: v0.2 Network Relationships
Status: active — interface selected, implementation not started
Last activity: 2026-07-21 — chose one canonical `network.yaml` containing normalized device, interface, and assigned-IP collections, paired atomically with one derived relationship index.

Plain `nbscribe export` remains compatible; `nbscribe export --view network` selects the new view. Partitioned manifests and immutable generation bundles were rejected for the tracer and are documented in decision 0003.

## Active Work

- Decision 0003: `--view network` produces one canonical `network.yaml` with separate device, interface, and assigned-IP collections plus one derived relationship index.
- Rationale: reuse the proven canonical-plus-derived atomic boundary and keep reader consistency implicit; accept larger files and less selective RAG ingestion until measured evidence justifies partitioning.
- Compatibility: plain `nbscribe export` remains device-only and does not request relationship endpoints.
- Next slice: implement the REQ-014 vertical tracer test-first — CLI opt-in plus safe generic paginated retrieval for interfaces and device-assigned IPs, without rendering/publishing the final network schema yet.
- Risk: repo-only implementation; synthetic HTTP transports only, no live NetBox mutation.

## Deferred

- 2026-07-21 — NetBox trademark/name review and package reservation remain required before PyPI distribution, not before local development.
- 2026-07-21 — MCP delivery remains a later capability; v0.1 must prove useful static artifacts first.
- 2026-07-21 — remaining v0.1 audit follow-ups for v0.2: document that synthesized names can collide with source names; test rollback double-fault/no-prior-index; reduce version-fixture brittleness; strengthen the typed agent-index boundary; identify invalid records operationally; add structured logging.
- 2026-07-21 — v0.1.0 audit follow-ups for v0.2: improve redirect diagnostics and pin `follow_redirects=False`; reject output/index path collisions before fetching; handle extreme YAML nesting; improve malformed endpoint diagnostics.
