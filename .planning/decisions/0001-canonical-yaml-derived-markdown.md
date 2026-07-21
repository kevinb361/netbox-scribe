# Canonical YAML with derived Markdown views

## Symptom

NetBox data needs a durable representation that scripts and agents can parse exactly while humans and retrieval systems can orient themselves without consuming a raw API dump. Making both YAML and Markdown independently authoritative would create drift, while choosing only one format would either weaken machine contracts or produce inefficient broad-context reads.

References: `README.md`; `.planning/REQUIREMENTS.md` REQ-003 and REQ-006.

## Blast Radius

- Time window / scope: all exported inventory and generated views beginning with schema version 1
- Recovery / reversal mechanism: introduce a new output schema version and migration guidance rather than silently changing the contract
- Frequency: every export and every downstream Git, RAG, or agent consumer
- Not affected: NetBox remains authoritative; this does not define write-back or discovery behavior

## Evidence Links

- `README.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`

## Default Disposition

Schema-versioned YAML is the only canonical exported inventory. Markdown indexes, summaries, diagrams, and future context packs are deterministic derived views. Generated Markdown must identify itself as derived and must not be edited as an independent source of inventory facts.

## Override Path

A future milestone may add another canonical serialization only through a versioned contract, migration plan, and tests proving equivalent semantics. It must not promote generated Markdown to an independently maintained source of truth.

## Sign-Off

Accepted: YES — YAML is canonical and Markdown is derived.   Date: 2026-07-21   Operator: Kevin

> Authorized via the project-creation instruction in this session on 2026-07-21. Default Disposition accepted; Override Path NOT invoked. Recorded by pi on operator instruction.
