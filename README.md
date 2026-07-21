# NetBox Scribe

**Versioned, AI-ready infrastructure context from NetBox.**

NetBox Scribe exports authoritative NetBox data into deterministic YAML and generated, token-efficient Markdown. The resulting snapshot is designed for Git review, offline inspection, RAG indexing, and controlled use by coding agents without giving every agent credentials to a live NetBox instance.

> [!IMPORTANT]
> NetBox Scribe is an independent project and is not affiliated with or endorsed by NetBox Labs. It is currently pre-alpha.

## Why

NetBox is excellent at modeling and querying current infrastructure state. Git and agentic workflows benefit from a complementary representation that is:

- readable without a database or live API
- stable enough to produce meaningful diffs
- partitioned into bounded context files
- explicit about provenance and freshness
- sanitized before reaching AI systems
- schema-versioned for scripts and long-term use

NetBox remains the source of truth. NetBox Scribe produces read-only snapshots and derived views.

## Planned output

```text
snapshot/
├── inventory/          # Canonical, schema-versioned YAML
├── views/              # Generated human-readable Markdown
├── agent/              # Bounded indexes and context packs
└── manifest.json       # Schema, provenance and freshness metadata
```

## Initial scope

The first milestone will provide a Python CLI that:

1. reads NetBox using a read-only API token;
2. retrieves paginated inventory data;
3. writes deterministic and atomic YAML snapshots;
4. generates concise Markdown orientation;
5. validates output against a published schema; and
6. applies explicit field and custom-field redaction policy.

It will not write to NetBox, perform network discovery, operate a web UI, or push Git repositories.

## Status

Planning and initial implementation are tracked with [Saga](https://github.com/earendil-works/saga) in [`.planning/`](.planning/).

## License

MIT. See [`LICENSE`](LICENSE).
