---
saga_state_version: 1.0
milestone: v0.2
milestone_name: Network Relationships
status: complete
stopped_at: Local redaction hardening verified on harden-network-redaction; changes uncommitted; v0.2.x requirements remain unplanned.
last_updated: "2026-10-17T06:02:59Z"
last_activity: 2026-10-17 — added network redaction guards and reconciled post-release fixes; local gate passed with 125 tests.
---

# NetBox Scribe — State

## Current Position

Phase/Milestone: v0.2 Network Relationships
Status: complete — independent frontier audit and finalization recheck PASS
Last activity: 2026-10-17 — post-release hardening verified locally; v0.2.x expansion remains unplanned.

Plain `nbscribe export` remains compatible; `nbscribe export --view network` selects the new view. Partitioned manifests and immutable generation bundles were rejected for the tracer and are documented in decision 0003.

## Active Work

- 2026-10-17 — local redaction hardening implemented on `harden-network-redaction`, uncommitted.
  Added exporter-layer exclusion/allowlist coverage, deny-precedence and nested-echo checks,
  plus CLI leak checks for YAML and Markdown (audit follow-ups W12/W13).
  Synthetic network output excludes serials and includes only reviewed `owner` custom fields;
  README now states device flags also govern network exports (W11).
  Verification: `make ci` passed with 125 tests; removing device-policy forwarding caused
  both new parameterized cases to fail, and the production source was restored byte-for-byte.
  Executor evidence only; independent re-verification of these audit follow-ups remains pending.
- 2026-10-17 — reconciled landed fixes `3da843c` (safe, actionable validation diagnostics)
  and `4d6fa39` (excluded tags skipped before normalization), both dated 2026-09-13.
  Their regression suites are `tests/test_safe_validation.py` and `tests/test_excluded_tags.py`;
  the unchanged baseline gate passed with 123 tests before this slice.
- Next: define bounded v0.2.x requirements before extending relationships. The separate-policy
  API footgun (W8) and endpoint pagination/origin/filter coverage (W3/W5/W7) remain candidates.

- v0.2 final verdict: **PASS** — 19/19 project requirements PROVEN; no close conditions.
- Release commit `ee43cd0`, annotated tag `v0.2.0`, GitHub release, and both GitHub/Gitea refs are published.
- GitHub Actions run `29921504324` passed required Python 3.11 and 3.12 checks before tagging.
- Gitea Actions workflow `.gitea/workflows/ci.yml` runs the canonical gate on Python 3.12; private run 269 completed successfully on `ci-runner01`.
- PyPI distribution remains a separate explicit-approval workflow; v0.2.x relationship expansion is idle.

## Deferred

- 2026-07-21 — NetBox trademark/name review and package reservation remain required before PyPI distribution, not before local development.
- 2026-07-21 — MCP delivery remains a v0.3 capability; the static relationship artifacts are now proven.
- 2026-07-21 — remaining v0.1 audit follow-ups for v0.2: document that synthesized names can collide with source names; test rollback double-fault/no-prior-index; reduce version-fixture brittleness; strengthen the typed agent-index boundary; identify invalid records operationally; add structured logging.
- 2026-07-21 — v0.1.0 audit follow-ups for v0.2: improve redirect diagnostics and pin `follow_redirects=False`; reject output/index path collisions before fetching; handle extreme YAML nesting; improve malformed endpoint diagnostics.

- 2026-09-11 — **RESOLVED 2026-09-12: agent-index rollback now restores prior bytes exactly.**
  `_publish_snapshot_pair` had captured the prior index with `read_text(encoding="utf-8")`, so
  universal-newline translation turned CRLF into LF and the rollback wrote the translated text.
  Fixed in `c12b515`: byte publication is split into `_publish_bytes_atomically`, the prior
  index is captured with `read_bytes()`, and `mkstemp(text=True)` was dropped so the write side
  translates nothing either. Regression coverage lives in `tests/test_network_exporter.py`,
  which asserts a CRLF prior index is restored byte-identically alongside the existing LF case.
  The standalone counterexample is RETIRED rather than kept: its contract was "exit 0 while the
  defect stands", it exits 1 now, and a counterexample that no longer reproduces its
  counterexample is worthless as a record — the executable guard belongs in the suite, where it
  is actually run. Delivered by a records-free Saga card; this entry is the separate
  record-bearing reconciliation that mode requires.
