# Public GitHub publication handoff

This document records the publication procedure and the controls applied to the public repository.

## Publication record

Published at <https://github.com/kevinb361/netbox-scribe> on 2026-07-21 after explicit operator approval. The initial CI run passed, `main` branch protection requires both Python matrix checks, and the annotated `v0.1.0` tag is available as a GitHub release.

## Pre-publication decisions

The operator must explicitly resolve these items:

1. **History identity:** the five commits through `v0.1.0` expose the maintainer name and Gmail address in Git metadata, and each revision contains an obsolete local profile path in `DESIGN.md`. The prepared `DESIGN.md` removes the path, while tracked audit/traceability evidence quotes it when documenting the review; a full-history mirror also retains the original file content in earlier revisions. Neither disclosure is a credential or infrastructure detail; both become permanent public history if mirrored.
2. **Project name:** no published NetBox trademark-usage policy was located during the readiness review. Keep the README's independent-project disclaimer. Confirm naming with NetBox Labs before package publication if greater certainty is required.
3. **Package reservation:** PyPI returned 404 for `netbox-scribe` during review. Availability is not reservation; package publication is a separate approval and credentialed workflow.
4. **Planning evidence:** the complete tracked `.planning/` directory is part of the public tree, including decision, audit, and traceability history. Review it as public project documentation rather than treating it as local agent state.

Preserving the annotated `v0.1.0` tag requires publishing its reachable history. Do not use a squashed import unless intentionally replacing public release history and tags.

## Repository settings

Recommended repository:

- Name: `netbox-scribe`
- Visibility: public
- Default branch: `main`
- Description: `Versioned, AI-ready infrastructure context from NetBox`
- Topics: `netbox`, `inventory`, `gitops`, `infrastructure`, `python`, `rag`
- Issues: enabled
- Discussions, wiki, projects, and merge queue: disabled initially
- Merge methods: squash merge enabled; merge commits and rebase merge disabled
- Automatically delete head branches: enabled

Security settings:

- Enable private vulnerability reporting.
- Enable dependency graph, Dependabot alerts, secret scanning, and push protection where available.
- Set Actions workflow permissions to read-only by default.
- Allow GitHub-owned actions and `astral-sh/setup-uv`; the workflow pins both actions to full commit SHAs.

Protect `main` after the first CI run:

- Require the `Python 3.11` and `Python 3.12` checks.
- Require branches to be up to date and conversations to be resolved.
- Block force pushes and branch deletion.
- Do not require approving reviews until a second maintainer can satisfy the rule.

## Publication commands

Only run after the preparation commit is present, the working tree is clean, the operator approves public publication, and the operator creates the empty GitHub repository without a generated README, license, or `.gitignore`:

```bash
test -z "$(git status --porcelain)"
git remote add github git@github.com:<owner>/netbox-scribe.git
git push github main
git push github --tags
```

Confirm that the public refs match the private source:

```bash
git fetch github
git rev-parse main github/main
git rev-parse v0.1.0 github/v0.1.0^{}
```

After the first push:

1. Watch the `CI` workflow and require both matrix checks before protection is enabled.
2. Create a GitHub release from the existing annotated `v0.1.0` tag; do not upload locally built artifacts unless a reproducible release workflow is added.
3. Re-run GitHub secret scanning and inspect every public file while logged out.
4. Add the final GitHub URL to package metadata and README badges in a later patch.

## Verified preparation evidence

- Gitleaks 8.30.1 scanned the complete reachable history with no findings.
- A full-history regex scan found no credentials or private IP addresses.
- `uv export --frozen --all-groups --no-emit-project -o /tmp/nbscribe-requirements.txt` followed by `uvx pip-audit --strict -r /tmp/nbscribe-requirements.txt` reported no known vulnerabilities.
- Real snapshots, `.env`, build output, caches, and close-out logs are ignored and untracked.
- GitHub workflow syntax and permissions were checked against current GitHub documentation.
- Workflow action versions were checked against their current signed releases before pinning.
- `make ci` runs a public-readiness check for required tracked policies, forbidden generated paths, local-profile leakage in `DESIGN.md`, and broken or untracked local Markdown links.
