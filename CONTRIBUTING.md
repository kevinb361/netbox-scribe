# Contributing

NetBox Scribe is pre-alpha. Focused bug reports, security fixes, tests, and small vertical features are welcome.

## Development setup

Requirements: Python 3.11 or newer, uv, and Make.

```bash
git clone <repository-url>
cd netbox-scribe
uv sync --dev
make ci
```

`make ci` is the required local gate. It checks formatting, lint, strict typing, and the parallel test suite.

## Change expectations

- Keep NetBox access read-only.
- Preserve deterministic output for unchanged input.
- Validate canonical YAML before publication.
- Keep custom fields closed by default and test denied-value behavior.
- Use synthetic fixtures only. Never commit tokens, real inventory, internal URLs, private addresses, or organization-specific names.
- Add tests at the CLI or artifact boundary when behavior changes.
- Update public documentation when flags, schemas, security boundaries, or output contracts change.

Run the complete gate immediately before opening a pull request:

```bash
make ci
git diff --check
```

## Pull requests

Keep pull requests narrow and explain:

1. the operator-visible behavior being changed;
2. the security or compatibility implications;
3. the verification commands and results; and
4. any schema or deterministic-output changes.

Breaking schema changes require a new schema version and migration guidance. Generated Markdown must remain a derived view of canonical YAML.

## Security reports

Do not open a public issue for a suspected vulnerability. Follow [`SECURITY.md`](SECURITY.md).
