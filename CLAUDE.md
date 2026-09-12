# NetBox Scribe

Turn NetBox into versioned, AI-ready infrastructure context.

## What It Does

NetBox Scribe reads NetBox through its REST API and exports deterministic, schema-versioned YAML plus generated Markdown context for humans, Git, RAG systems, and coding agents. NetBox remains authoritative; exported artifacts are read-only snapshots, not a competing source of truth.

## Change Policy

- Development project; freely editable in small, reviewable slices.
- Keep the repository and fixtures public-safe. Never commit real inventory, API tokens, internal URLs, employer data, or homelab identifiers.
- NetBox access is read-only by design. Do not add write-back behavior without an explicit new milestone and security review.
- Canonical inventory is YAML. Markdown and future context packs are generated views and must not become independently edited inventory.
- Output must be deterministic, schema-versioned, atomic, and useful in Git diffs.
- AI-facing output must include provenance and freshness while supporting field redaction.

## Layout

```text
src/netbox_scribe/   Python package and CLI
tests/               Unit/integration tests with synthetic fixtures
schemas/             Versioned output schemas
examples/            Synthetic example configuration and output
.planning/            Saga files of record
design/               Reserved design tokens/examples for any future UI
```

## Commands

```bash
uv sync --dev
make format
make lint
make type
make test
make ci
uv run nbscribe --help
```

Tests use synthetic HTTP fixtures only unless a test is explicitly marked as live and opt-in.

## Design / UI

- A web UI is not part of the initial scope.
- Read `DESIGN.md` before any future UI/design changes.
- If `DESIGN.md` is absent, use `~/.agent-profile/DESIGN.md`.
- Default style: graphite/moss/amber, low-light, operational, no blue SaaS sludge or RGB gamer glow.
- For browser UI, start from `design/tokens.css` and inspect `design/component-examples.html`.
- Smoke check UI changes in a browser before calling them done.

## Browser Smoke Checklist

- Page renders without console errors.
- Text is readable on laptop brightness, including muted metadata.
- Focus states are visible.
- Primary, warning, and danger actions are visually distinct.
- Empty/loading/error states are not raw default browser output.
- Mobile/narrow viewport does not break the main path.

## Known Issues

- **Agent-index CRLF not restored:** `_publish_snapshot_pair` reads the prior index with `read_text(encoding="utf-8")`, which applies universal-newline translation. CRLF indices become LF on read and remain LF on restore. Reachable from both `export_devices` and `export_network`. Reproduced at 4eb767c; counterexample at `.planning/evidence/crlf-rollback-counterexample.py`. Deferred — no repair authorized.

## Cross-CLI

`AGENTS.md` is a symlink to this file. Codex reads AGENTS.md; Claude Code reads CLAUDE.md.
