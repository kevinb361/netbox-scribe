# NetBox Scribe

**Versioned, AI-ready infrastructure context from NetBox.**

NetBox Scribe exports authoritative NetBox data into deterministic YAML and concise Markdown. The snapshot is designed for Git review, offline inspection, RAG indexing, and controlled use by coding agents without giving every agent credentials to a live NetBox instance.

> [!IMPORTANT]
> NetBox Scribe is an independent project and is not affiliated with or endorsed by NetBox Labs. It is pre-alpha and currently exports devices only.

## Why

NetBox is excellent at modeling and querying current infrastructure state. Git and agentic workflows benefit from a complementary representation that is:

- readable without a database or live API;
- stable enough to produce meaningful diffs;
- explicit about source, freshness, and schema version;
- sanitized before reaching AI systems; and
- bounded enough for agents to navigate without ingesting an API dump.

NetBox remains the source of truth. YAML is the canonical exported representation. Markdown is a generated view and must not be edited as independent inventory.

## Install

Python 3.11 or newer and [uv](https://docs.astral.sh/uv/) are recommended:

```bash
uv tool install .
nbscribe --version
```

For development:

```bash
uv sync --dev
uv run nbscribe --help
make ci
```

## Configure read-only access

Create a dedicated NetBox API token with read-only permissions. Keep the token outside Git and pass it through the environment, not a command-line argument:

```bash
cp .env.example .env
chmod 600 .env
# Edit .env, then load it into the current shell:
set -a
. ./.env
set +a
```

Required variables:

- `NETBOX_URL` — NetBox base URL, including a deployment path prefix when applicable.
- `NETBOX_TOKEN` — dedicated read-only API token.

NetBox Scribe does not call write endpoints. Errors omit the token and response body. Pagination is restricted to the configured origin so a malicious `next` URL cannot receive credentials.

HTTPS is required by default because every API request carries the token. For an isolated, trusted network where TLS is unavailable, HTTP requires explicit acknowledgement:

```bash
nbscribe export --allow-insecure-http
```

This override sends the token in plaintext and must not be used across untrusted networks.

## Export

```bash
nbscribe export
```

Default output:

```text
snapshot/
├── inventory/
│   └── devices.yaml    # Canonical, schema-versioned YAML
└── agent/
    └── INDEX.md        # Generated orientation and provenance
```

Override either path when needed:

```bash
nbscribe export \
  --output build/inventory/devices.yaml \
  --agent-index build/agent/INDEX.md
```

Each artifact uses a same-directory temporary file and atomic replacement. When both artifacts are enabled, the derived index is published first and rolled back if canonical publication fails; canonical YAML never advances beyond its index. A failed fetch, validation, write, or replacement preserves the last valid canonical snapshot.

## Control exported fields

Device identity (`id` and `name`) is always present. If NetBox returns an unnamed device, the export uses the deterministic name `device-<id>`; NetBox itself is not modified. Optional core fields are included by default and can be restricted with repeatable options:

```bash
nbscribe export \
  --include-field display \
  --include-field site \
  --exclude-field description
```

Custom fields are excluded by default. Include only reviewed fields:

```bash
nbscribe export \
  --include-custom-field owner \
  --include-custom-field support_group \
  --exclude-custom-field private_note
```

Exclusion wins when a field appears in both lists. Unknown core field names fail before NetBox is contacted.

## Validate

Every export is checked against the packaged JSON Schema before publication. Existing files can be checked directly:

```bash
nbscribe validate snapshot/inventory/devices.yaml
```

An unsupported schema version or invalid record exits non-zero with a bounded error.

## Version snapshots with Git

NetBox Scribe does not manage Git credentials, commits, or pushes. Keep that boundary explicit:

```bash
git add snapshot/
git diff --cached
git commit -m "chore: update NetBox inventory snapshot"
```

Because canonical output is sorted and deterministic, unchanged NetBox input remains byte-identical. Review the diff before committing, especially when custom fields are enabled.

## Use with agents and RAG

Give an agent the Markdown index first. It provides provenance, source freshness, versions, device names, NetBox IDs, and a relative link to canonical YAML. Source freshness is the newest `last_updated` value among exported devices, or `unknown` when NetBox supplies none; it is not the export time. The agent can then open only the exact inventory it needs.

For RAG systems, index both output directories:

- Markdown provides compact orientation and retrieval-friendly prose.
- YAML provides exact structured evidence.
- Git commit identity records which snapshot the agent used.

Treat snapshots as bounded historical context, not proof of live state. Query NetBox directly when the answer requires current operational state.

## Synthetic example

The `examples` directory contains a public-safe synthetic NetBox response and its expected YAML and Markdown output. It demonstrates deterministic sorting, explicit custom-field inclusion, provenance, and freshness without containing real infrastructure data.

```bash
python -m json.tool examples/netbox-devices-page.json >/dev/null
nbscribe validate examples/output/inventory/devices.yaml
```

## Current scope and non-goals

Current scope:

- paginated device retrieval;
- deterministic, schema-versioned YAML;
- atomic publication;
- generated Markdown agent index;
- explicit field/custom-field policy; and
- safe validation and error handling.

Not currently in scope:

- writing back to NetBox;
- network discovery;
- interfaces, addresses, prefixes, VLANs, cables, or virtual machines;
- Git pushes or credential management;
- a web UI; or
- an embedded LLM dependency.

Roadmap and evidence are tracked with [Saga](https://github.com/earendil-works/saga) in [`.planning/`](.planning/).

## License

MIT. See [`LICENSE`](LICENSE).
