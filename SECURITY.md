# Security Policy

## Supported versions

NetBox Scribe is pre-alpha. Security fixes are applied to the latest tagged release only. The project does not yet promise a long-term compatibility or backport window.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities in a public issue, discussion, or pull request.

Use GitHub private vulnerability reporting for this repository. If that feature is unavailable, contact the maintainer privately through the account that owns the repository and include:

- the affected version or commit;
- a minimal reproduction;
- the expected and observed security boundary; and
- whether credentials or real inventory may have been exposed.

Do not include live NetBox tokens, private inventory, or internal URLs. Use synthetic values in reproductions.

You should receive an acknowledgement within seven days. Remediation timing depends on severity and reproducibility. Confirmed credential disclosure or unauthorized cross-origin requests are release blockers.

## Security boundaries

- NetBox access is read-only, but API tokens remain sensitive.
- HTTPS is required by default. `--allow-insecure-http` is an explicit trusted-network exception that sends the token in plaintext.
- Generated snapshots can contain infrastructure details even when they contain no credentials. Review field policy and output before sharing or indexing it.
- NetBox remains authoritative; snapshots are historical context, not proof of current operational state.
