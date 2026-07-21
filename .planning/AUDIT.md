# Audit Log: NetBox Scribe

---

## Audit: v0.1 First Useful Snapshot — 2026-07-21 (post-close re-audit after pre-commit remediation)

Auditor: Claude Opus 4.8 (`claude-opus-4-8`, 1M context) via Claude Code — independent post-close
verification of the three pre-commit findings. Supersedes the PASS-CONDITIONAL entry of the same date.
Scope: v0.1 First Useful Snapshot — installable CLI exports deterministic, validated, AI-ready device
context from a read-only NetBox API (REQ-001..REQ-008)
Files reviewed: 31 files — tracked: 15 changed, 1827 insertions(+), 58 deletions(-) since `217d2b0`
(1496 insertions excluding `uv.lock`); untracked/new: 16 files, 638 lines. Under the 50-file single-pass
limit.

Method: re-read all 8 source modules, all 5 test modules, `README.md`, `.env.example`, decision `0002`,
and the planning spine; fresh `make ci`; and **five adversarial probe runs driving the real code paths** —
eight `nbscribe validate` error shapes at the process level (non-UTF-8 in two byte positions, directory,
missing, unreadable, deeply nested YAML, BOM, valid snapshot), a mutation test of both committed example
byte assertions, a production-vs-raw agent-index divergence probe, an identity-collision reproduction with
determinism check under input reversal, and eight adversarial CLI failure cases with token-leak and
traceback assertions on every one. No prior-run claim was inherited; each fix was re-derived from behavior.

`make ci` this session: black clean (15 files), ruff clean, mypy clean (15 source files),
`pytest -n auto` → **33 passed** (was 32).

### Pre-commit findings — status

| ID   | Finding                                                         | Status this pass                                                                                                                                                                                                                                                                                                                                                                         |
| ---- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S1   | `nbscribe validate` emitted a raw traceback on a non-UTF-8 file | **FIXED & independently re-tested.** `cli.py:90-92` catches `UnicodeError` ahead of `(OSError, SnapshotValidationError)`. Probed with `\xff\xfe` leading bytes and a trailing lone `\x80`: rc 1, stderr exactly `error: snapshot is not valid UTF-8`, no traceback. Pinned by `tests/test_cli.py:200-211`. See the note below — this is a _better_ fix than the one recommended          |
| A1   | Decision `0002` overclaimed collision resistance                | **FIXED.** `decisions/0002-...:20` now says the fallback is "unique among synthesized identities", states that a source device may already carry the same literal name, and instructs consumers to key on the NetBox ID. Behavior re-reproduced and matches the wording. The code half was deliberately not changed (`device-<id>` retained). Residual doc gap → A1-r below              |
| TC-A | Example verification bypassed the production projection         | **FIXED & independently re-tested.** `tests/test_examples.py:18-39` builds a real `NetBoxClient` over `httpx.MockTransport` and calls `export_devices`, then byte-compares both committed artifacts. Both assertions mutation-tested live (one-char edit → correct failure line; restore → pass). Divergence re-proved: `export_devices` → `` `device-7` ``, raw renderer → `` `None` `` |

**Note on the S1 fix quality.** The prior audit recommended widening `cli.py:90` to `(OSError, ValueError)`.
The implementer instead caught `UnicodeError` and emitted a purpose-written message. That is the stronger
choice: `SnapshotValidationError` is the only other `ValueError` reachable from `validate_snapshot_text`
and it is already caught with its own message, so the narrower catch loses nothing while replacing a
decode exception's repr with a bounded operator sentence. Verified by re-reading `validation.py:19-43`.

### Correctness

- **[warning] A1-r — the collision caveat reached the decision record but not the operator docs.**
  `README.md:87` still says only "If NetBox returns an unnamed device, the export uses the deterministic
  name `device-<id>`", and the "Use with agents and RAG" section (`README.md:129-139`) tells the reader to
  hand an agent the index first without stating that exported names are not unique. Reproduced this pass:
  a page containing a device genuinely named `device-7` alongside an unnamed device with id 7 exports two
  records both named `device-7`, and the index renders two lines distinguished only by the trailing NetBox
  ID. Determinism holds (sort key is `(name.casefold(), id)`; byte-identical under input reversal) and the
  v1 schema has no uniqueness constraint, so this validates. The residual is now honestly recorded where
  future-you looks second and absent where an agent consumer looks first. **Fix:** one sentence in
  `README.md` under the identity rule — names may collide, key on NetBox ID.
- **[info] A2 — a name is judged usable by `.strip()` but exported unstripped.** `exporter.py:151-156`:
  `"  router-01  "` passes the emptiness guard and is exported verbatim, then appears padded inside the
  index code span. Deterministic, so not a correctness break — but the guard and the value disagree about
  what the name is. Unchanged this pass.

### Safety

- **[info] S5 — `nbscribe validate` still emits a raw traceback on deeply nested YAML.** Reproduced at the
  process level: a file of 60,000 nested `[` produces a five-frame `RecursionError` traceback from
  `yaml/reader.py` and exits 1. `RecursionError` is not a `ValueError`, so neither the applied `UnicodeError`
  catch nor the originally recommended `(OSError, ValueError)` widening covers it — this is a genuinely
  separate class from S1, not an incomplete fix. Reachability matches S3: only when an operator validates a
  file they did not generate. Blast radius is a local read of a file the operator named. Track with S3; if
  `validate` ever grows an untrusted-input story, bound both together (nesting/size limit before parse).
- **[info] S3 — `validate_snapshot_text` calls `yaml.safe_load` on operator-supplied text**
  (`validation.py:22`) before any size or version check. `SafeLoader` expands aliases, so a hostile snapshot
  could expand in memory before `validation.py:29` looks at `schema_version`. Unchanged; same reachability
  as S5. Do not fix for v0.1.
- **[info] S2 — the pair rollback filters on `OSError` only** (`exporter.py:99`). A non-`OSError` escaping
  canonical publication would leave the index advanced against a stale canonical. The prior pass searched
  for a data-driven trigger and found none (PyYAML escapes non-printables to `\uXXXX` before the file
  write). Recording the reasoning; widen the filter only if `publish_text_atomically` grows a
  non-filesystem failure mode.
- **[info] S4 — `publish_text_atomically` fsyncs the file but not the parent directory**
  (`exporter.py:78-82`). Acceptable for a re-runnable snapshot tool.
- Re-confirmed clean this pass: the token `probe-secret-token` appeared in no stdout or stderr across eight
  injected CLI failure cases; `Traceback` appeared in none of them except S5; the read-only client still has
  no write verbs; `_ensure_safe_next_url` still runs before the next credentialed request
  (`client.py:69-70`); every client failure still raises `from None`.

### Test Coverage

The suite grew 32 → 33 and the added test is the right one — `test_validate_command_reports_non_utf8_snapshot_without_traceback`
asserts the _exact_ stderr string rather than a substring, so a regression to a raw traceback cannot pass.
`test_examples.py` was converted rather than extended, which is the correct call: it now proves the shipped
path instead of a parallel one, and I mutation-tested both of its byte assertions to confirm they are live
rather than vacuous. Remaining gaps, all carried:

- **[warning] TC-B — the rollback's two hardest branches are still untested.** `exporter.py:100-108`: the
  double-fault path (canonical fails _and_ index restore fails → bounded `OSError` with a distinct message)
  and the no-prior-index path (index must be unlinked, not left behind). Confirmed absent — no test in
  `tests/test_exporter.py` names either branch. Both behaved correctly under manual injection in the prior
  pass, but nothing in the suite pins the one path that decides whether a partial snapshot survives.
- **[warning] TC-C — version-string brittleness persists.** Two test-visible literal `0.1.0.dev0` sites
  remain: `tests/test_cli.py:123` inside the exact-index comparison, and `examples/output/agent/INDEX.md:8`,
  which `tests/test_examples.py:39` now byte-compares. A version bump breaks two tests and requires
  regenerating a committed fixture. (`tests/test_cli.py:39` was correctly converted to a pattern; these two
  were not.)
- **[info] TC-D — still no test covers the A1 collision** (a real `device-<n>` name alongside an unnamed
  device with id `n`). Worth one case wherever A1-r lands.

### Architecture Fit

Still clean and appropriately small. `contracts.py` holds `SCHEMA_VERSION` as the single source of truth;
`client → exporter → {validation, agent_index, policy}` remains acyclic; the CLI holds no business logic.
None of the three fixes strained the layering — S1 is one branch in a CLI error handler, A1 touched only a
planning record, and TC-A moved a test onto the production entry point, which if anything tightened the
coupling between example and shipped behavior in the right direction.

- **[warning] AR1 — the policy boundary is still upheld by convention rather than construction.**
  `_agent_index_record` (`exporter.py:112-117`) is a hand-written projection and `render_agent_index` has no
  guard; called with raw records it renders `` `None` `` — re-reproduced this pass. TC-A closed the hole for
  the _shipped_ path and now for the _example_ path too, but the renderer remains a public function
  accepting unprojected input, so a third caller would reintroduce it. Cheapest durable fix: give the
  projection a named type, or validate at the top of `render_agent_index`, so the boundary is a type error
  rather than a review comment.
- **[info] AR2 — `last_updated` remains un-denyable and is the one raw-source read in the projection**
  (`exporter.py:114`). It is not in `OPTIONAL_DEVICE_FIELDS`, so `--exclude-field last_updated` exits 2 with
  `unknown device field(s)`. Deliberate and correct (REQ-006 requires freshness) but undocumented.
- **[info] AR3 — `--exclude-field name` / `--exclude-field id` are silently accepted and ignored**
  (`policy.py:40` subtracts `MANDATORY_DEVICE_FIELDS`; `exporter.py:203-205` keeps identity regardless).
  Specified in `SPEC.md` and tested, so it is a deliberate accept-and-ignore — but neither `README.md` nor
  `--help` says so, and an operator excluding identity for a redaction reason gets silence.

### Operability

- **[warning] OP1 — `device record has no usable integer id` identifies no record** (`exporter.py:150`).
  Correct behavior (whole export aborts rc 1, prior snapshot pair intact) but against a NetBox with
  thousands of devices the operator cannot find the offending record. Include the zero-based result index
  and, when present, the record's `url` or `display` — both non-sensitive and already in hand.
- **[warning] OP2 — still no logging anywhere in the package.** One `logging` call per decision point (page
  fetched, N devices normalized, fields dropped by policy, index published, canonical published) would make
  a surprising Git diff debuggable without a debugger. Not blocking for v0.1; it becomes real debt the
  moment v0.2 adds prefixes, VLANs, interfaces, and cables.
- **[info] OP5 (new) — the `output == agent_index` guard fires only after a full NetBox fetch.**
  `exporter.py:47-48` raises `ValueError("canonical output and agent index must use different paths")`, but
  it sits after `client.list_devices()` at `exporter.py:38`. Verified: `nbscribe export --output X
--agent-index X` against an unreachable NetBox reports `error: NetBox request failed` first — the config
  error is masked, and against a reachable NetBox a large inventory is fetched and normalized before the
  run is refused. `README.md:104` promises unknown field names fail before NetBox is contacted; this
  configuration error does not get the same treatment. Move the comparison to the top of `export_devices`
  or into `main()` beside the `ExportPolicy` construction.
- **[info] OP6 (new) — nothing documents how `examples/` was generated.** The policy that produced the
  committed artifacts (`include_custom_fields={"owner"}`) exists only at `tests/test_examples.py:25`;
  `README.md:141-147` describes what the example demonstrates but not the flags. Regenerating the fixture
  after a schema or renderer change requires reading the test to recover the command. One line in the
  README, or a comment in the test naming the equivalent CLI invocation.
- **[info] OP3 — `_code` produces unbalanced Markdown when a name starts or ends with a backtick**
  (`agent_index.py:50-53`). Re-measured this pass: `` `lead `` → ` ```lead`` ` (3-open / 2-close → not a
  code span, renders literally); `` trail` `` → ` ``trail``` ` (2-open / 3-close → same); ` ``both`` ` →
  ` ````both```` ` (balanced, but the inner backticks are absorbed into the delimiter runs and the rendered
  name is `both` — silent data loss). ``double`tick`` is handled correctly. No injection — newlines are
  flattened and `]`, `(`, `|`, `*` are inert inside a span — so this is cosmetic corruption of an AI-facing
  artifact by an unusual device name. Standard fix: delimiter one longer than the longest internal backtick
  run, plus a space pad when the value starts or ends with a backtick.
- **[info] OP4 — rollback remains the strongest operability property here.** Snapshots are Git-tracked,
  output is deterministic and sorted, `snapshot/` is gitignored by default, and `README.md:119-131`
  documents the review-the-diff-then-commit loop. `close_out_auditor` is configured in
  `.planning/config.json`, so the loop's frontier-verify gate is not a dead end.
  `.planning/.close-out-auditor.log` is still a gitignored 0-byte file — harmless, but wire it or drop it.

### ASSERTED Items from TRACEABILITY.md

None. All 8 requirements classify **PROVEN** — every evidence artifact was located, re-read, or
re-executed in this session (`make ci`: 33 passed, black/ruff/mypy clean; the three remediations
independently re-derived from behavior; credential-free CLI and README example commands re-run by hand;
`.env.example` read directly and confirmed placeholder-only; both example byte assertions mutation-tested).
No requirement was passed on a restated claim.

One carried accuracy note: the `make ci with N tests` counts embedded in the REQ-002/005/006/007/008
evidence lines are historical snapshots and the suite is now 33. Every named artifact resolves, so no
classification changes.

### Verdict

**PASS** — v0.1 closes clean. This upgrades the prior PASS-CONDITIONAL: both of its named conditions are
discharged, and the third pre-commit finding (TC-A) was fixed as well.

- Critical findings: **0**
- Warnings: **6** (A1-r, TC-B, TC-C, AR1, OP1, OP2)
- Info: **12** (A2, S2, S3, S4, S5, TC-D, AR2, AR3, OP3, OP4, OP5, OP6)

Count note: five of the six warnings (TC-B, TC-C, AR1, OP1, OP2) are already carried on `STATE.md` as v0.2
follow-ups and are not conditions on this close. The one genuinely new warning is **A1-r**. Three of the
info items are new this pass (S5, OP5, OP6).

Rationale: all three remediations do what they claim, and I verified each by executing the code rather than
reading the diff. The `validate` non-UTF-8 path is bounded with an exact-string test behind it and the
chosen catch is narrower and better than the one recommended. Decision `0002` now states the identity
residual honestly and I reproduced the collision it describes. The synthetic example is verified through
`export_devices`, and I mutation-tested both byte assertions to confirm the test is load-bearing rather
than decorative — the example now proves the shipped path, which was the point. `make ci` is green at 33
tests with black, ruff, and mypy clean, no token appeared in any of eight adversarial CLI failure streams,
and no export path produced a traceback. Nothing in the remediation regressed the atomicity, determinism,
or redaction properties the milestone was built on.

Not blocking, but pick up at the head of v0.2: **A1-r** (one README sentence — names may collide, key on
NetBox ID; pair it with TC-D's single test case) and **S5**/**OP5**/**OP6**, all cheap. `A1-r` is not yet
on `STATE.md`'s deferred list — add it there when convenient; this audit did not edit `STATE.md` or
`ROADMAP.md`.

Close-out path: `/saga-spec merge` to bake the verified behavior into the spec library. Not performed by
this audit.

---

## Audit: v0.1.0 Release Hardening — 2026-07-21 (independent pre-release audit)

Auditor: Claude Opus 4.8 (`claude-opus-4-8`, 1M context) via Claude Code — independent frontier audit,
invoked directly by the operator rather than through `saga-loop`. `.planning/config.json` carries a
populated `close_out_auditor`, so no configuration warning applies.

Scope: v0.1.0 Release Hardening — require encrypted token transport by default, dogfood the build, and
publish the first release tag. One requirement: REQ-009.

Files reviewed: 13 files changed, 152 insertions(+), 23 deletions(-) since `2332025` (`git diff --shortstat`).
Production code in scope is `src/netbox_scribe/client.py` (+17) and `src/netbox_scribe/cli.py` (+26);
the rest is tests, docs, planning, version, and lockfile. **All milestone changes are uncommitted working
tree** — there is no milestone commit yet, so a release tag would have nothing to point at.

Method: `make ci` re-run (black/ruff/mypy clean, `pytest -n auto` → 36 passed); the built wheel installed
into a throwaway venv and exercised there; the CLI driven end-to-end against real local HTTP servers; a
15-case URL/scheme matrix and a 10-case pagination matrix probed against the client; every failure path
inspected for token content in both the message and the full formatted traceback.

### Correctness

- [critical] **C1 — a malicious or compromised NetBox response exfiltrates the API token to an arbitrary
  origin.** `src/netbox_scribe/client.py:92-93`: `_ensure_safe_next_url` returns early when
  `candidate.is_relative_url` is true. `httpx.URL("//evil.example/api/x/").is_relative_url` is **True**
  (no scheme) while its `.host` is `evil.example`, so the guard short-circuits; `list_devices` then calls
  `self._client.base_url.join(next_url)` at `client.py:71`, which resolves to `https://evil.example/api/x/`,
  and the client's default `Authorization: Token …` header rides along.
  Reproduced end-to-end this session with two real localhost servers: the foreign origin received
  `Authorization: Token E2E-SECRET-TOKEN-9999` and the export exited **0** with a valid-looking snapshot.
  This is not gated by `--allow-insecure-http` — it fires on the default HTTPS path, which is precisely the
  path this milestone exists to harden. The existing test
  `tests/test_client.py::test_list_devices_rejects_cross_origin_pagination_before_sending_credentials`
  only covers the _absolute_-URL form (`https://untrusted.example/…`) and passes, which is why this went
  unnoticed.
  Fix: delete the `is_relative_url` early return and compare the **resolved** URL's origin instead —
  `resolved = self._client.base_url.join(next_url)`, then reject unless
  `(resolved.scheme, resolved.host, resolved.port) == self._origin`, wrapping the join in
  `except (httpx.InvalidURL, ValueError)` → `NetBoxResponseError`. Validated against a 10-case matrix this
  session: it rejects `//evil.example/…`, absolute cross-origin, and same-host scheme downgrade, while still
  allowing `api/…?page=2`, `/api/…?page=2`, and `https://netbox.example:443/api/x` (httpx normalizes the
  default port, so no false rejection). This one change also closes S1.
- [warning] **C2 — `README.md:59` and `.planning/SPEC.md` assert a guarantee the code does not provide.**
  README: "Pagination is restricted to the configured origin so a malicious `next` URL cannot receive
  credentials." SPEC REQ `netbox-device-retrieval`: "retrieval stops with a safe response error before
  credentials leave the configured origin." Both are false today per C1. Fix the code first, then leave the
  text as-is; do not weaken the docs to match the bug.

### Safety

- [warning] **S1 — malformed `next` values escape as an unhandled `httpx.InvalidURL`.**
  `src/netbox_scribe/client.py:91` constructs `httpx.URL(next_url)` outside any `try`. `httpx.InvalidURL`
  subclasses `Exception`, not `ValueError`, so `cli.py:130`'s
  `except (NetBoxClientError, SnapshotValidationError, OSError, ValueError)` does not catch it. Reproduced
  at the process level with a server returning `"next": ":://bad"`: rc 1 with a **raw traceback** on stderr
  exposing internal file paths and httpx internals. This violates the project's own bounded-error contract
  (`tests/test_cli.py` asserts "no traceback" on three other failure paths). Mitigating: no token appeared
  in the traceback, and both prior snapshot files stayed byte-intact with no `.tmp` residue, so REQ-004
  holds. Fixed by the same rewrite as C1.
- [info] **S2 — `httpx.Client` runs with `trust_env=True` (verified at runtime).** `HTTPS_PROXY` /
  `ALL_PROXY` in the operator's environment therefore route the credentialed connection through a proxy.
  For HTTPS this is a CONNECT tunnel, so the token is not exposed to the proxy, and this is normal httpx
  behavior — but since "encrypted token transport" is the milestone's headline control, one README sentence
  noting that proxy environment variables are honored would close the loop.
- [info] **S3 — userinfo in a same-origin `next` is accepted.** `https://attacker:x@netbox.example/api/x/`
  passes the origin check (userinfo is not part of the origin tuple) and httpx will derive a Basic
  credential from it. No exfiltration — the host is unchanged — and the request would simply fail auth. Low
  value, but stripping userinfo from resolved pagination URLs is a one-liner if you are touching this code
  for C1 anyway.
- [info] **S4 — redirect downgrade is genuinely closed (verified, no action).** `follow_redirects` is
  `False` (confirmed at runtime). A NetBox server answering `302 → http://evil.example/…` produces
  `NetBoxResponseError: NetBox returned a malformed response` with zero further requests. Worth an explicit
  test so a future `follow_redirects=True` cannot land quietly.
- [info] **S5 — the HTTPS gate itself is placed correctly and behaves under adversarial input.**
  `client.py:51-55` runs _before_ `httpx.Client(...)` is constructed at `client.py:57`, so on rejection no
  token-bearing client object ever exists — stronger than checking at request time. The 15-case matrix
  (`HTTP://`, `HtTp://`, leading whitespace, schemeless, empty, `file:`, `ftp:`, hostless `https:///`,
  `http://u:p@host`, loopback) issued **zero** requests and leaked no token in any message. No action.

### Test Coverage

- [warning] **TC1 — the exporter-version assertion is now self-referential.**
  `tests/test_cli.py:118` changed from a literal `0.1.0.dev0` to an f-string interpolating
  `netbox_scribe.__version__`. The assertion can no longer fail on a wrong version — it compares the value
  to itself. Version pinning for the release now rests solely on the byte-compare of
  `examples/output/agent/INDEX.md` in `tests/test_examples.py`. That happens to hold (I verified the file
  reads `0.1.0`), but the CLI test no longer guards it. Either restore a literal or add an explicit
  `assert __version__ == "0.1.0"`-style release check.
- [warning] **TC2 — no automated test that default HTTP rejection preserves a pre-existing snapshot pair.**
  This is a headline REQ-009 claim and a headline `STATE.md` dogfood claim, yet
  `tests/test_cli.py::test_export_command_rejects_http_without_explicit_override` asserts only rc, stderr
  text, and token absence. I proved preservation manually (prior files byte-identical, md5 `6504e217…` /
  `a6a79038…`, no residue), but nothing in CI would catch a regression that starts truncating the output
  before the transport check.
- [warning] **TC3 — no test for a protocol-relative `next`.** The direct cause of C1 shipping unnoticed.
  Add `//evil.example/api/dcim/devices/` and a same-host scheme downgrade
  (`http://netbox.example/…` from an HTTPS base) to the cross-origin test, asserting the credentialed
  request count stays at 1.
- [info] **TC4 — the HTTP-rejection CLI test depends on the working directory.** It calls `main(["export"])`
  with no `--output`/`--agent-index`, so it inherits the defaults `snapshot/inventory/devices.yaml` and
  `snapshot/agent/INDEX.md`. It passes because nothing is written — but if the guard ever regresses, the
  test writes into the developer's real `snapshot/` tree instead of failing cleanly. Point it at `tmp_path`.
- [info] **TC5 — the override test under-asserts.**
  `tests/test_client.py::test_client_allows_explicit_insecure_http_override` checks `len(requests) == 1` but
  not that the request scheme was `http` nor that the `Authorization` header was actually present. Both are
  one line each and make the test say what it means.

### Architecture Fit

- [info] **AR1 — the gate lives in the right layer (no action).** Enforcement is in `NetBoxClient.__init__`
  with `allow_insecure_http=False` defaulted, and the CLI flag is a pass-through. Library consumers get the
  secure default for free; the CLI cannot accidentally be the only enforcement point. This is the correct
  split and it should stay that way.
- [info] **AR2 — the origin invariant is expressed in two incompatible shapes.** `self._origin` is derived
  from the _base_ URL while `_ensure_safe_next_url` reasons about the _unresolved_ candidate, with an
  `is_relative_url` short-circuit bridging them. That mismatch is the C1 bug. Comparing one resolved URL
  against one origin tuple collapses two rules into one and removes the class of defect rather than the
  instance.

### Operability

- [warning] **OP1 — still no structured logging.** Already carried on `STATE.md` as a v2 follow-up, so not
  a new condition on this close, but it is felt here: the C1 leak is invisible in operator-facing output.
  A single line naming each pagination URL before it is fetched would have made this trivially observable.
- [info] **OP2 — the rejection message is good (no action).** `error: HTTPS is required for NetBox
credentials; pass --allow-insecure-http only for a trusted network` names the exact escape hatch, exits 1,
  writes nothing, and leaves no residue. Reproduced from a clean wheel install.
- [info] **OP3 — release hygiene verified.** `git check-ignore` confirms `snapshot/` (`.gitignore:19`) and
  `dist/` (`.gitignore:11`) are ignored and `git ls-files` shows neither is tracked, so the 11 real homelab
  hostnames in the dogfood snapshot cannot reach the public repo. The wheel packages
  `netbox_scribe/schemas/v1/devices.schema.json` (2516 bytes, resolved via `importlib.resources` from a
  clean venv) and reports `nbscribe 0.1.0`. Version is consistently `0.1.0` across `pyproject.toml:7`,
  `netbox_scribe.__version__`, the wheel filename and `dist-info`, `examples/output/agent/INDEX.md`, and
  `snapshot/agent/INDEX.md`.

### ASSERTED Items from TRACEABILITY.md

- **REQ-002** — _confirmed gap, and worse than a missing artifact._ The requirement claims failures are
  reported "without exposing the API token." The evidence tests exist and pass, and the error-message half
  of the claim is solid (no token in any message or traceback across eight failure shapes). But the
  pagination half is falsified by C1 with a live end-to-end capture of the token reaching an
  attacker-chosen origin. Fix C1 and add TC3, then REQ-002 returns to PROVEN.

### Verdict

**FAIL**

- Critical findings: **1** (C1)
- Warnings: **6** (C2, S1, TC1, TC2, TC3, OP1)
- Info: **10** (S2, S3, S4, S5, TC4, TC5, AR1, AR2, OP2, OP3)

Rationale: REQ-009 itself is genuinely well built. The HTTPS gate is placed before client construction
rather than before request dispatch, it holds against every scheme-confusion input I threw at it, it fails
closed with an actionable message, it writes nothing on rejection, and the override is explicit and
narrowly scoped. Every dogfood claim in `STATE.md` reproduced independently: default HTTP rejection
preserved both prior artifacts byte-for-byte, the explicit override exported and validated twice with
byte-identical, token-free output, the version chain is 0.1.0 everywhere, and the wheel carries its schema
and works from a clean venv. On its own terms the requirement passes.

The milestone does not, and the reason is narrow and specific. v0.1.0 exists to make credential transport
safe before the first public tag. On the default HTTPS path, a NetBox server that returns a
protocol-relative `next` — through compromise, misconfiguration, or a proxy rewriting URLs — hands the
operator's API token to a host of its choosing, and the export exits 0 as though nothing happened. Tagging
0.1.0 would publish a tool whose README promises exactly the protection it does not have. That is a
release blocker, not a follow-up.

The fix is small and I validated a candidate this session: replace the `is_relative_url` short-circuit at
`client.py:92-93` with a resolved-origin comparison wrapped in `except (httpx.InvalidURL, ValueError)`.
One change closes C1 and S1, restores C2's docs to truth, and returns REQ-002 to PROVEN. Add TC3 alongside
it so the protocol-relative and scheme-downgrade cases are pinned; TC1 and TC2 are cheap and belong in the
same slice.

Conditions to clear before tagging 0.1.0:

1. Fix C1 (and S1 falls out of the same rewrite).
2. Add TC3; re-run `make ci`.
3. Re-run `/saga-verify` and confirm REQ-002 returns to PROVEN.
4. TC1 and TC2 in the same slice — both are a few lines and both guard release-critical claims.

OP1, C2's residual doc polish, S2/S3/S4 hardening, and TC4/TC5 are not conditions on this close; carry them
into v0.2. This audit did not edit `ROADMAP.md` or `STATE.md` and created no Git tag.

---

## Audit: v0.1.0 Release Hardening — 2026-07-21 (post-remediation re-audit)

Auditor: Claude Opus 4.8 (`claude-opus-4-8`, 1M context) via Claude Code — independent frontier re-audit,
invoked directly by the operator. Supersedes the **FAIL** entry of the same date. `.planning/config.json`
carries a populated `close_out_auditor`, so no configuration warning applies.

Scope: v0.1.0 Release Hardening — require encrypted token transport by default, dogfood the build, and
publish the first release tag. One requirement: REQ-009. The release-blocking finding C1 was filed against
REQ-002 (milestone v0.1, already shipped), so both are in scope for discharge.

Files reviewed: 14 files changed, 452 insertions(+), 68 deletions(-) since `2332025`. Production code in
scope is `src/netbox_scribe/client.py` (+27) and `src/netbox_scribe/cli.py` (+26); the rest is tests (+135),
docs, planning, version, and lockfile. Well under the 50-file single-pass limit. **All milestone changes
remain uncommitted working tree** — see the release-readiness note below.

Method: no prior-run claim was inherited, and the previous audit's own proposed fix was not accepted on the
strength of the diff. Every finding was re-derived by executing code:

- `make ci` re-run: black clean (15 files), ruff clean, mypy clean (15 source files), `pytest -n auto` →
  **39 passed** (was 36).
- **Two real TLS servers on localhost** (self-signed cert, `httpx.HTTPTransport(verify=cert)`) — one
  impersonating NetBox and returning attacker-chosen `next` values, one acting as the attacker origin and
  recording every request it receives including headers. 24 hostile `next` values, 3 same-origin positive
  controls. This is the same harness shape that captured the original leak, rebuilt from scratch.
- **Process-level CLI probe** against real localhost HTTP servers: default rejection with a pre-existing
  snapshot pair, virgin workspace, explicit override, opt-in ordering, off-origin redirect, 10 hostile base
  URLs, HTTPS case-correctness.
- **Mutation testing** of all three fixes in an isolated copy of the tree.
- **Clean-venv wheel install**, exercised from `cwd=/tmp` with no source tree reachable.
- REQ-002 and REQ-007 re-derived from behavior (25-page pagination, 14 failure shapes, 6 policy scenarios).

### Prior findings — status

| ID  | Finding                                                     | Status this pass                                                                                                                                                                                                                                                                                                                                                  |
| --- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1  | Token exfiltration via protocol-relative `next` (critical)  | **FIXED & independently re-verified.** Does not reproduce. `client.py:90-97` resolves the candidate with `base_url.join` and compares the resolved origin; `client.py:71,76` requests that same resolved URL, so checked-URL and fetched-URL cannot diverge. Across 24 hostile values the attacker origin received **zero** requests. Mutation-tested — see below |
| S1  | Malformed `next` escaped as unhandled `httpx.InvalidURL`    | **FIXED & re-tested.** Wrapped in `except (httpx.InvalidURL, ValueError)` → `NetBoxResponseError("NetBox returned a malformed pagination URL") from None`. Probed with malformed port, unterminated IPv6, tab/newline/NUL injection, and a 200 KB path: bounded message, no traceback, `__cause__ is None`                                                        |
| C2  | README/SPEC asserted a pagination guarantee the code lacked | **DISCHARGED by fixing the code, not the docs.** `README.md:59` is now a true statement. `SPEC.md` gained a `plaintext-token-transport` scenario under the retrieval REQ                                                                                                                                                                                          |
| TC1 | Exporter-version assertion was self-referential             | **FIXED.** `tests/test_cli.py:40` now asserts `__version__ == "0.1.0"` outright, and line 123 interpolates `{__version__}` in the index comparison. Mutation 3 confirms the pin is live                                                                                                                                                                           |
| TC2 | No test that HTTP rejection preserves a pre-existing pair   | **FIXED.** `tests/test_cli.py::test_export_command_rejects_http_without_explicit_override` seeds both files, then asserts byte preservation _and_ an exact directory listing, so residue fails the test too                                                                                                                                                       |
| TC3 | No test for a protocol-relative `next`                      | **FIXED.** The cross-origin test is now parametrized over absolute, protocol-relative, and same-host scheme-downgrade forms, asserting the credentialed request count stays at 1                                                                                                                                                                                  |
| TC4 | HTTP-rejection test depended on the working directory       | **FIXED.** The test now passes `--output`/`--agent-index` under `tmp_path`; a guard regression writes into the temp tree, not the developer's real `snapshot/`                                                                                                                                                                                                    |
| TC5 | Override test under-asserted                                | **FIXED.** Now asserts `requests[0].url.scheme == "http"` and `Authorization == "Token explicit-http-secret"` alongside the count                                                                                                                                                                                                                                 |
| AR2 | Origin invariant expressed in two incompatible shapes       | **DISCHARGED structurally.** One resolved URL is now compared against one origin tuple. This is why inputs the fix was never written against (IDN homoglyph, percent-encoded host, userinfo confusion) also fail closed                                                                                                                                           |
| S4  | Redirect downgrade closed but untested                      | **CARRIED.** Behavior re-verified live (see OP4); still no test pinning `follow_redirects=False`                                                                                                                                                                                                                                                                  |
| S2  | `trust_env=True` honors proxy environment variables         | **CARRIED**, unchanged. Still worth one README sentence                                                                                                                                                                                                                                                                                                           |
| S3  | Userinfo in a same-origin `next` is accepted                | **CARRIED**, unchanged. Re-confirmed harmless: host is unchanged, so no exfiltration                                                                                                                                                                                                                                                                              |
| OP1 | No structured logging                                       | **CARRIED**, already on `STATE.md` as a v0.2 follow-up                                                                                                                                                                                                                                                                                                            |

**Mutation testing — are the new tests load-bearing?** Each fix was reverted in an isolated copy of the tree
and the suite re-run. Baseline copy: green. Reverting `_ensure_safe_next_url` to the pre-fix
`is_relative_url` short-circuit → reds
`test_list_devices_rejects_cross_origin_pagination_before_sending_credentials[//untrusted.example/…]` and
`test_list_devices_rejects_malformed_pagination_url_cleanly`. Removing the HTTPS gate → reds
`test_client_rejects_insecure_http_before_any_request` and
`test_export_command_rejects_http_without_explicit_override` (the latter with the exact diagnostic
`assert 'HTTPS is required' in 'error: NetBox request failed\n'`). Returning the version to `0.1.0.dev0` →
reds `test_version_does_not_require_netbox_credentials` and
`test_synthetic_example_outputs_match_production_export`. All three fixes are pinned by tests that fail
when the fix is absent.

Worth stating plainly: of the three parametrized cross-origin cases, only the protocol-relative one is
load-bearing against the C1 regression. The absolute and same-host-scheme-downgrade forms were already
rejected by the old code's origin comparison, so they are regression coverage rather than proof of a closed
hole. The scheme-downgrade rejection is nonetheless real and was verified live against the TLS harness.

### Correctness

- **[info] N1 — a hostile `next` that resolves back onto the configured origin still costs one extra
  credentialed request.** `///attacker:port/…`, `\\attacker:port\…`, a space-prefixed absolute URL, `://`,
  and `""` all resolve per RFC 3986 to a _path on the NetBox origin_. The guard correctly allows them
  (same origin), the client fetches once more, and the repeated-URL guard at `client.py:72-73` terminates
  the loop with `NetBox returned a repeated pagination URL`. Verified: the attacker origin received nothing
  in all five cases. Notable sub-case — `"next": ""` is truthy-checked as non-`None`, so it re-requests the
  base root rather than terminating; bounded only by `seen_urls`. No credential leaves the configured
  origin, so this is not a leak, but an explicit `if not next_url.strip(): break` would be one line if v0.2
  broadens pagination.

### Safety

- Re-confirmed clean: the token appeared in **no** message, traceback, artifact, stdout, or stderr across
  24 hostile pagination values, 14 client failure shapes (including servers that echo the token verbatim in
  a 401 body, a 500 body, and a transport-error string), 19 hostile base URLs, and 6 policy scenarios.
  Every client failure still raises `from None` with `__cause__ is None`.
- The HTTPS gate remains correctly placed — `client.py:51-55` runs _before_ `httpx.Client(...)` is
  constructed at `client.py:57`, so on rejection no token-bearing client object ever exists. Re-verified
  that `https`/`HTTPS`/`HtTpS` bases construct with **zero** requests issued at construction time and then
  issue exactly one credentialed GET on `list_devices()`.
- The read-only client still has no write verbs; the probe server recorded only `GET`.

### Test Coverage

The suite grew 36 → 39 and the added tests are the right ones. Remaining gaps:

- **[warning] TC-C — version-fixture brittleness is only half discharged.** TC1's fix made
  `tests/test_cli.py` a real pin, which is the important half. But `examples/output/agent/INDEX.md:8` still
  carries the literal `0.1.0` and is byte-compared by `tests/test_examples.py:39`. Mutation 3 demonstrates
  the cost concretely: a version bump reds two tests, one of which requires regenerating a committed
  fixture. Already carried on `STATE.md` as a v0.2 follow-up; recording that the remediation narrowed it
  rather than closed it.
- **[warning] S4 (carried) — still no test pins `follow_redirects=False`.** The behavior is correct and I
  re-verified it live, but a future `follow_redirects=True` would reopen a credential-forwarding path with
  a green suite. One test.
- **[info] TC-B (carried) — the rollback's double-fault and no-prior-index branches remain untested.**
  `exporter.py:100-108`. Unchanged this pass; on `STATE.md` for v0.2.

### Architecture Fit

Unchanged and still clean. `NetBoxConfigurationError` is a well-placed addition — it subclasses
`NetBoxClientError`, so the CLI's existing `except` tuple catches it without modification, and it
distinguishes "your configuration is unsafe" from "NetBox misbehaved" for any library consumer that cares.
Enforcement lives in `NetBoxClient.__init__` with the CLI flag as a pass-through, so library consumers get
the secure default for free.

### Operability

- **[warning] OP4 (new) — an off-origin redirect is correctly refused but misreported.** Verified with a
  real server answering `302 → http://<attacker>/api/dcim/devices/`: the attacker origin received nothing,
  rc 1, prior snapshot byte-intact, no token, no traceback. The security outcome is right. But the operator
  sees `error: NetBox returned a malformed response`, because the empty 302 body fails JSON parsing — the
  message describes the symptom, not the cause. Reverse proxies redirect routinely (trailing-slash
  canonicalization, http→https), so a correctly configured NetBox behind one produces a message that sends
  the operator hunting for a payload bug. Pair the fix with S4's missing test: detect `response.is_redirect`
  and raise a named error. **Not a condition on this close.**
- **[info] V1 (new) — `__version__` is derived from install metadata, not a source literal.**
  `src/netbox_scribe/__init__.py` resolves `importlib.metadata.version("netbox-scribe")`. The 0.1.0 pin is
  real and I verified it at six sites (`pyproject.toml:7`, installed `__version__`, wheel filename,
  `dist-info` directory, wheel `METADATA`, `examples/output/agent/INDEX.md:8`), but it is indirect: with an
  editable install the value is captured at install time, so a `pyproject.toml` bump without a re-sync
  leaves a stale `__version__` that `tests/test_cli.py:40` would still accept. `uv run` re-syncs, so CI is
  correct today. A source tree with no install yields `0+unknown`, which that assertion would catch. Noting
  it because "explicitly pinned" is worth stating precisely: pinned by declaration and by two tests, not by
  a literal in the package.
- **[info] OP5 — release hygiene re-verified.** `git ls-files` confirms neither `snapshot/` nor `dist/` is
  tracked. A word-boundary scan of every tracked file for RFC1918 literals, secret-assignment patterns, and
  homelab hostnames is clean — the only hits were the word "homelab" inside planning prose describing the
  policy. The wheel packages `netbox_scribe/schemas/v1/devices.schema.json` (2516 bytes, resolved via
  `importlib.resources` from a clean venv) and reports `nbscribe 0.1.0`.

### ASSERTED Items from TRACEABILITY.md

None. All 9 requirements classify **PROVEN**. **REQ-002 returned to PROVEN from ASSERTED** — the
exfiltration that falsified it was re-tested from behavior against a rebuilt two-server TLS harness and
does not reproduce, and the pagination and error-reporting halves of the requirement were both re-derived
independently rather than accepted from the remediation's own tests.

### Verdict

**PASS**

- Critical findings: **0**
- Warnings: **3** (TC-C, S4, OP4) — none new-and-blocking; TC-C and S4 are carried, OP4 is new
- Info: **6** (N1, V1, OP5, TC-B, S2, S3)

All four conditions from the prior audit are discharged, and TC4, TC5, and C2 were fixed as well —
seven findings closed against four required.

Rationale: the fix is the right fix, not merely a passing one. The original defect was structural — the
guard reasoned about the _unresolved_ candidate while the origin came from the _resolved_ base, bridged by
an `is_relative_url` short-circuit — and the remediation collapses both to a single resolved-origin
comparison whose result is then reused as the actual request URL. That removes the class of defect rather
than the instance, which is why 24 hostile inputs fail closed, including several the fix was never written
against. I verified this by executing code, not by reading the diff: two real TLS servers, an attacker
origin recording headers, and zero requests reaching it in every case. Positive controls still paginate, so
the guard is not passing by refusing everything. Mutation testing confirms all three fixes are pinned by
tests that go red without them. `make ci` is green at 39 with black, ruff, and mypy clean; the 0.1.0 wheel
builds, installs into a clean venv, carries its schema, and enforces the HTTPS gate from `cwd=/tmp`. Nothing
in the remediation regressed atomicity, determinism, or redaction — all three were re-derived through the
installed wheel.

The three warnings are diagnosability and test-durability, not correctness. OP4 is the one I would fix
first: it is a real operator-facing wrong answer in a configuration (NetBox behind a reverse proxy) that is
more common than the attack it sits next to, and it pairs naturally with S4's missing test.

**Release-readiness note, not a finding:** the entire milestone is still uncommitted working tree. The code
passes; there is simply nothing yet for a `v0.1.0` tag to point at. Commit the milestone first, then tag.
Per instruction, this audit did not edit `ROADMAP.md` or `STATE.md` and created no Git tag.

---

## Audit: v0.1.1 Public GitHub Readiness — 2026-07-21 (independent public-readiness audit)

Auditor: Claude Opus 4.8 (`claude-opus-4-8`, 1M context) via Claude Code — independent frontier audit,
invoked directly by the operator rather than through `saga-loop`. `.planning/config.json` carries a
populated `close_out_auditor`, so no configuration warning applies.

Scope: v0.1.1 Public GitHub Readiness — public-safety audit of the complete reachable history and public
tree, least-privilege GitHub CI, public security/contribution policy, and an operator-gated publication
handoff. Four requirements: REQ-010..REQ-013.

Files reviewed: 7 tracked files changed, 76 insertions(+), 17 deletions(-) (`git diff HEAD --shortstat`),
plus 4 new untracked files totalling 196 lines (`.github/workflows/ci.yml` 46, `CONTRIBUTING.md` 48,
`SECURITY.md` 27, `docs/PUBLICATION.md` 75). Whole-repository scans additionally covered all 5 reachable
commits and the 43-file materialized public tree.

Method note: this audit did not read the milestone's claims and agree with them. Every scanner, pin, gate,
and reachability assertion in `STATE.md` and `docs/PUBLICATION.md` was re-executed. Two of the re-runs were
deliberately constructed differently from the originals — see **M1** and **M2** — because the original
invocations could have produced a clean result without examining this project at all.

### Correctness

- [critical] **D3 — the entire v0.1.1 deliverable is uncommitted, and the handoff does not say so.**
  `git ls-files --others --exclude-standard` returns `.github/workflows/ci.yml`, `CONTRIBUTING.md`,
  `SECURITY.md`, and `docs/PUBLICATION.md`; the `DESIGN.md` remediation is an unstaged working-tree change.
  `docs/PUBLICATION.md:56-60` instructs the operator to `git remote add github …` then `git push github
main` with no intervening commit step. Executed literally today, that publishes `a71831f` — a repository
  with **no CI workflow, no `SECURITY.md`, no `CONTRIBUTING.md`, no publication doc, and the old
  `DESIGN.md`** — and then `docs/PUBLICATION.md:63-67`'s `git rev-parse main github/main` check would
  _pass_, because both sides would agree on the wrong commit. The verification step cannot catch this class
  of error. Fix: commit the milestone first, and add an explicit "working tree is clean and every v0.1.1
  artifact is tracked" precondition above the command block — `git status --porcelain` returning empty is
  the check that actually discriminates. This is the same failure mode the v0.1.0 audit flagged in its
  closing note; it has now recurred, which argues for making it a standing line item in the handoff rather
  than a per-audit observation.

- [critical] **D1 — `docs/PUBLICATION.md` §1 materially understates the obsolete-path exposure.** The text
  reads "The initial commit also contains an obsolete local profile path in `DESIGN.md`." In fact
  `/home/kevin/.agent-profile/DESIGN.md` appears in **all five commits, including `HEAD`** — at
  `DESIGN.md:6` (`source:` frontmatter) and `DESIGN.md:64` (prose) of `a71831f`, verified by `git grep`
  across `git rev-list --all`. The distinction is not pedantic: "in the initial commit" implies a
  history-only residue that a squash or a shallow import would drop, whereas the truth is that it is in the
  currently committed tree and, absent D3's fix, would publish as _live content_ rather than as history.
  Fix: correct the sentence to "all five commits including `HEAD`" and state that the working-tree
  remediation must be committed before mirroring.

- [warning] **D2 — `README.md`'s Saga link is dead.** `README.md:158` links
  `https://github.com/earendil-works/saga`, which returns **HTTP 404**. The `earendil-works` org exists and
  has 12 public repositories, none named `saga`; a GitHub-wide search for that repository name returns 0
  results, and Saga's only reachable origin on this machine is `gitea:kevin/saga.git` (private). A public
  README's first outbound link 404-ing is exactly the kind of defect a cold reader hits in the first minute.
  Fix: point at Saga's real public home if one exists, or describe it without a hyperlink
  ("tracked with Saga in `.planning/`"). This sits inside REQ-012's named evidence ("README entry-point
  links"), which is why it is recorded here rather than left as a nit.

- [info] **C1 — README's install path assumes a clone that it never instructs.** `README.md:31-34` opens with
  `uv tool install .` — a local-path install — but nothing above it tells a reader arriving from the GitHub
  landing page to clone first. `CONTRIBUTING.md:11` has `git clone <repository-url>` with the placeholder
  still unresolved. Cheap fix once the real URL exists: a `git clone` line above the install block and the
  concrete URL substituted into `CONTRIBUTING.md`.

### Safety

- [info] **S1 — no secret, credential, or private-infrastructure disclosure in history or the public tree.**
  This is the headline REQ-010 claim and it holds under independent re-derivation. Gitleaks 8.30.1 over
  `--all --full-history` (5 commits, 315.84 KB) and over the materialized public tree (43 files,
  309.22 KB): no leaks in either. An independent `git grep` across all five commits for credential shapes
  (`Bearer …`, `Token <hex40>`, `AKIA…`, `ghp_`/`gho_`/`github_pat_`, PEM headers, `password=`/`secret=`/
  `api_key=`) surfaced only four synthetic fixture strings in `tests/test_client.py` — `"auth-failure-
secret"` and siblings, which exist precisely to be asserted _absent_ from error output. The decisive
  evidence is not the scanners, though: the 11 real device names, both real IP literals, the `NETBOX_URL`
  host, and the 40-character `NETBOX_TOKEN` from `.env` were each searched directly against the full public
  corpus and against `git log --all -p`. **Zero matches.** Of 85 distinct tokens lifted from the live
  dogfood snapshot, the only overlaps were generic schema vocabulary (`status`, `manufacturer`) and vendor
  or role words (`Router`, `Switch`, `Ruckus`) that appear in synthetic fixtures. Scanners find secret
  _shapes_; this finds the specific private strings this repository has actually handled, which is the
  stronger test.

- [info] **S2 — the ignored-file assumptions are demonstrated, not assumed.** `git ls-files -i -c
--exclude-standard` is empty, so nothing ignored is simultaneously tracked. `git check-ignore -v`
  attributes each sensitive path to a specific rule: `.env`→`.gitignore:15`, `.env.local`→`:16`,
  `snapshot/…`→`:19`, `dist/…`→`:11`, `build/…`→`:12`, `config.yaml`→`:18`,
  `.planning/.close-out-auditor.log`→`:20`. The `.env.*` / `!.env.example` negation is ordered correctly and
  `.env.example` resolves as not-ignored, which matters because it is a tracked file that a naive rule
  ordering would silently drop. The live `snapshot/` artifacts are mode `0600` and untracked.

- [info] **S3 — `--allow-insecure-http` is documented honestly in the public-facing surface.**
  `SECURITY.md:24` states plainly that the override "sends the token in plaintext"; `README.md:64` repeats
  the warning. The dogfood environment does use plaintext HTTP against an RFC1918 address, which is exactly
  the trusted-network case the flag exists for — worth noting only because it means the override is a lived
  path rather than a theoretical one, so its documentation carries real weight.

- [info] **S4 — the redirect follow-up carried on `STATE.md` is hardening, not an open credential leak.**
  `client.py:57-62` constructs `httpx.Client(...)` without `follow_redirects`. Verified empirically against
  the pinned httpx 0.28.1: the default is `False`, so a `3xx` is never followed and the token is never
  re-sent to a redirect target. A redirect instead falls through `response.is_error` (false for 3xx) into
  `_parse_page`, producing `NetBox returned a malformed response` — which is the misleading-diagnostic
  defect already recorded as v0.1.0 finding OP4. The deferred item is worth doing for explicitness and
  message quality; it is not a live security gap, and publishing it in a public `AUDIT.md` discloses no
  exploitable path.

- [info] **S5 — the approval gate is procedural, not technical.** The local `gh` CLI is authenticated as
  `kevinb361` with `repo` and `workflow` scopes. Any agent or script with shell access in this environment
  could create the public repository and push without further credentials. Nothing is wrong with the repo
  here — but "no GitHub resource exists" is a fact about restraint, not about an enforced control. Worth
  the operator knowing when deciding how much of this workflow to hand to automation.

- [info] **S6 — a private mirror already holds the full history.** `origin` is
  `gitea:kevin/netbox-scribe.git` (self-hosted Gitea over SSH, port 2222), and `refs/remotes/origin/main`
  is at `a71831f` — the same commit as local `main`. Not a GitHub resource and not a REQ-013 violation. It
  matters for one reason: if the operator ever elects to rewrite history to scrub the author email or the
  `/home/kevin` path, the Gitea copy and the annotated `v0.1.0` tag must be handled in the same operation,
  or the rewrite will be silently incomplete.

### Test Coverage

- [info] **TC1 — both CI matrix legs were reproduced locally, and the 3.12 leg was run against the public
  tree.** 3.11.14 (project venv): `make ci` → black clean 15 files, ruff clean, mypy clean 15 source files,
  `pytest -n auto` **39 passed**. 3.12.3: executed inside the materialized public-tree copy with
  `UV_FROZEN=1` and an isolated `UV_PROJECT_ENVIRONMENT` → identical results, **39 passed**. The second run
  is the more informative one: it proves the published tree is self-sufficient — it syncs from the frozen
  lock, type-checks, and passes every test with `.env`, `snapshot/`, `dist/`, and all caches absent. A
  hidden dependency on an ignored file would have failed there and nowhere else.

- [info] **TC2 — the public-safety property has a test behind it, not just a scan.**
  `tests/test_examples.py::test_public_docs_and_examples_contain_no_private_networks_or_credentials` runs in
  the standard gate, so the docs/examples safety invariant regresses loudly rather than depending on
  someone remembering to re-run Gitleaks. That is the right shape for this class of check.

- [warning] **TC3 — nothing in the gate would catch D2 or D3.** There is no link check over `README.md` and
  no assertion that the publication-critical files are tracked. Both defects found in this audit are
  precisely the kind the suite is blind to. A dozen-line test that walks `README.md`'s relative links and a
  `git status --porcelain`-empty precondition in the handoff would close both cheaply. Not blocking — but
  D2 and D3 are the evidence that the gap is real rather than hypothetical.

### Architecture Fit

- [info] **AR1 — the CI workflow is genuinely least-privilege and correctly supply-chain-pinned.**
  Top-level `permissions: contents: read` with no job-level widening; no `pull_request_target`; no `secrets`
  reference anywhere in the file; `persist-credentials: false` on checkout, so no `GITHUB_TOKEN` remains in
  `.git/config` for `make ci` to reach — which is the control that actually matters given that `make ci`
  executes repository-supplied code on fork pull requests. `concurrency` with `cancel-in-progress` and
  `timeout-minutes: 10` bound cost. **Both SHAs were verified against the live GitHub API rather than
  eyeballed:** `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` is exactly `refs/tags/v7.0.1`
  and `astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9` is exactly `refs/tags/v9.0.0`; both are
  the current latest release of their project (published 2026-07-20 and 2026-07-21). `zizmor` 1.27.0 at
  `--persona=auditor`, its strictest setting, reports no findings. `yamllint -d relaxed` flags one 82-char
  line and nothing else. Note that REQ-011's own wording says "pinned major action versions" while the
  workflow does the strictly stronger thing and pins immutable full SHAs — the requirement understates its
  own implementation.

- [info] **AR2 — the job name and the branch-protection plan agree.** `name: Python ${{
matrix.python-version }}` renders as `Python 3.11` and `Python 3.12`, which are verbatim the required
  checks named in `docs/PUBLICATION.md:47`. This is a small thing that is wrong surprisingly often, and
  getting it wrong means branch protection silently guards nothing.

- [info] **AR3 — dependency licensing is clean for MIT redistribution.** Runtime tree: httpx BSD-3-Clause,
  jsonschema MIT, PyYAML MIT, httpcore BSD-3-Clause, idna BSD-3-Clause, h11/anyio/attrs/referencing/
  rpds-py/jsonschema-specifications MIT, typing-extensions PSF-2.0. See **I2** for the one non-MIT-family
  entry.

- [info] **I2 — `certifi` is MPL-2.0, and that is fine here.** MPL-2.0 is file-level weak copyleft: its
  obligations attach to modifications of certifi's own files. This project neither vendors nor modifies it;
  it is a transitive dependency of httpx resolved at install time. No source-disclosure obligation is
  triggered on this MIT codebase. Recorded because "one MPL dep in the tree" is the sort of thing that
  looks alarming later if nobody wrote down why it was cleared.

### Operability

- [info] **OP1 — `.planning/AUDIT.md` is tracked and will publish 567+ lines of self-critique.** Including
  this section. It names deferred, currently-unfixed items — redirect diagnostics, output/index path
  collisions, extreme YAML nesting, malformed-endpoint diagnostics. None is exploitable (see **S4** for the
  redirect case), the only infrastructure fact disclosed is the _count_ "11 real homelab hostnames" with no
  hostname, and for a pre-alpha tool this transparency is arguably an asset. But it is a deliberate choice
  and it is not currently written down as one. Recommend a single line in `docs/PUBLICATION.md`
  acknowledging that `.planning/` publishes in full, so the decision is made rather than inherited.

- [info] **OP2 — the handoff's own evidence list is accurate apart from D1.** Each of the six bullets under
  "Verified preparation evidence" was re-checked this pass: Gitleaks across five commits (confirmed),
  full-history regex scan (confirmed), `pip-audit --strict` (confirmed, though see **M1** for how it was
  re-run), ignored/untracked sensitive files (confirmed mechanically), workflow syntax and permissions
  (confirmed), action versions checked against current signed releases before pinning (confirmed exactly).
  The list is unusually honest for this kind of document.

- [info] **OP3 — PyPI `netbox-scribe` returns HTTP 404.** Unclaimed, and `docs/PUBLICATION.md:14` correctly
  states that availability is not reservation. No action before publication.

- [info] **M1 — methodological correction: bare `pip-audit --strict` does not necessarily audit this
  project.** With no `-r`/`-e` argument it audits the ambient environment, which under an ephemeral runner
  can contain none of this project's dependencies and report clean regardless. Re-run against
  `uv export --frozen --all-groups` (505 hash-pinned lines, runtime + dev): **no known vulnerabilities**.
  Same verdict, but now the verdict is about this project. Worth pinning the explicit form into any future
  dependency-audit step so the check cannot silently degrade to a no-op.

- [info] **M2 — methodological correction: "scanned the tree" ≠ "scanned the tree that ships".** This pass
  materialized `git ls-files ∪ git ls-files --others --exclude-standard` (43 files) into a scratch
  directory and scanned _that_, so the exclusion of `.env`, `snapshot/`, `dist/`, and caches is demonstrated
  by construction rather than trusted from `.gitignore`. It is also the artifact the 3.12 CI reproduction
  ran against (**TC1**), which is why that run doubles as a self-sufficiency proof.

### ASSERTED Items from TRACEABILITY.md

- None. This session's `/saga-verify` pass classifies all 13 requirements **PROVEN**, with v0.1.1's four at
  **PROVEN 4 · ASSERTED 0 · OPEN 0 · WAIVED 0**. Every v0.1.1 evidence artifact was re-executed rather than
  read, so no classification rests on a claim inherited from a prior pass. REQ-013 is marked PROVEN with an
  explicit defect annotation pointing at D1 and D3 — mechanically its named artifact exists and the
  approval gate demonstrably holds, but the artifact contains an error that this audit, not the traceability
  table, is the right place to gate on.

### Explicit judgment: disclosed Gmail metadata and the obsolete `/home/kevin` path

The operator asked for a ruling on each. They are not the same call.

**Gmail commit metadata — PASS.** All five commits and the annotated `v0.1.0` tag carry
`Kevin Blalock <kevin.blalock@gmail.com>` as author, committer, and tagger. This is the maintainer's own
chosen public identity, it already agrees with `LICENSE:3` ("Copyright (c) 2026 Kevin Blalock") and
`pyproject.toml:12`, and attributed authorship in commit metadata is the norm for open-source publication
rather than an exception to it. It is not a credential, not infrastructure, and not third-party personal
data. `docs/PUBLICATION.md` §1 already surfaces it for acknowledgement, which is the correct handling. No
remediation is warranted. If the operator nonetheless prefers not to publish the address, the only complete
options are a full history rewrite — which invalidates the annotated `v0.1.0` tag, must be replayed onto the
Gitea mirror (**S6**), and buys nothing security-wise — or switching to a GitHub `noreply` address for
future commits while accepting the existing five. That is a preference decision, not a finding.

**Obsolete `/home/kevin/.agent-profile/DESIGN.md` path — CONDITIONAL ACCEPTANCE GATE.** On its merits the
string is harmless: a local username and a dotfile path, no hostname, no address, no credential, nothing an
attacker gains from. Published as history alone it would be a clean pass. It is conditional for two reasons
that are about accuracy and sequencing rather than sensitivity. First, D1 — the handoff describes it as
confined to the initial commit when it is in every commit including `HEAD`, so the operator would be
accepting a smaller exposure than the real one. Second, D3 — because the remediation is uncommitted, a push
today republishes the path as _current content_, not as history. Both conditions are cheap and mechanical:
commit the corrected `DESIGN.md`, and fix one sentence in `docs/PUBLICATION.md`. Once done, the residue is
history-only and the gate clears to PASS.

### Verdict

**PASS-CONDITIONAL**

- Critical findings: **2** (D3, D1) — must fix before milestone close
- Warnings: **2** (D2, TC3) — fix before shipping
- Info: **16** (C1, S1, S2, S3, S4, S5, S6, TC1, TC2, AR1, AR2, AR3, I2, OP1, OP2, OP3 — plus methodology
  notes M1, M2)

Rationale: the substance of this milestone is sound and it survived being re-derived rather than re-read.
There are no secrets and no private infrastructure anywhere in the five reachable commits or in the tree
that would publish — and I am confident in that not because two Gitleaks runs came back clean, but because
the 11 real device names and 2 real IP literals this project has actually touched were searched directly
against the whole public corpus and the full patch history and matched nothing. The CI workflow is the best
part of the milestone: least-privilege by construction, both action pins verified byte-for-byte against the
live GitHub API and both at current latest, zizmor clean at its strictest persona, and both matrix legs
reproduced locally — with the 3.12 leg deliberately run inside the materialized public tree, which
simultaneously proves the published artifact is self-sufficient. Dependencies audit clean against an
explicit frozen export, licensing is compatible, and the approval gate holds: no GitHub remote, no
repository (404), zero global search hits, nothing pushed.

What holds it back is not security, it is publication mechanics. Every artifact this milestone produced is
still untracked, and the handoff's command block does not tell the operator to commit before pushing — so
the documented procedure, followed exactly, publishes a repository missing its CI, its security policy, and
its contributing guide, and the handoff's own `git rev-parse` verification would pass while it happened,
because both sides would agree on the same wrong commit. Alongside it, the one sentence in that handoff
describing the `/home/kevin` residue is wrong in the direction that understates the exposure. Neither is
hard to fix. Both must be fixed before this milestone closes, because the deliverable of v0.1.1 is a
_correct publication procedure_, and a procedure that publishes the wrong tree has not met that bar.

The v0.1.0 audit closed with the identical observation — "the entire milestone is still uncommitted" — and
it has now recurred at v0.1.1. That is a process signal, not a coincidence: the commit step deserves to be
an explicit precondition in the handoff rather than something each audit rediscovers.

Conditions on close:

1. Commit the v0.1.1 working tree — the four untracked files and the `DESIGN.md` fix — before any mirror.
2. Correct `docs/PUBLICATION.md` §1 to say all five commits including `HEAD`, and add a
   `git status --porcelain`-empty precondition above the publication command block.
3. Fix or remove the 404 `README.md` Saga link (D2).

Per instruction, this audit did not edit `ROADMAP.md` or `STATE.md`, created no GitHub resource, added no
remote, pushed nothing, and rewrote no history.

---

## Audit: v0.1.1 Public GitHub Readiness — 2026-07-21 (post-remediation re-audit at `3318077`)

Auditor: Claude Opus 4.8 (`claude-opus-4-8`, 1M context) via Claude Code — independent re-audit invoked
directly by the operator after the CONDITIONAL findings above were remediated and committed privately.

Scope: re-verify the three conditions on close from the preceding audit against the **committed** tree, and
re-derive the underlying security, privacy, dependency, CI, and approval-gate evidence rather than accept it
from the prior pass. Four requirements: REQ-010..REQ-013.

State audited: `HEAD = 3318077` ("docs: prepare public GitHub publication", 12 files, +622/−72),
`git status --porcelain` **empty** at session start, `git ls-files --others --exclude-standard` **empty**.
Six reachable commits; annotated tag `v0.1.0` → `a71831f`. Public tree materialized at **44 files**.

Method note: every scanner, pin, and reachability claim was re-executed, not read. Two prior methodological
corrections (**M1**, **M2**) were re-applied rather than trusted — `pip-audit` with an explicit `-r` against
a frozen export, and Gitleaks pointed at a materialized copy of the tree that would actually ship.

### Prior conditions on close — status

- **D3 (critical) — RESOLVED.** The entire deliverable is now in a commit. `git show --stat 3318077`
  accounts for `.github/workflows/ci.yml` (new, 46 lines), `CONTRIBUTING.md` (new, 48), `SECURITY.md`
  (new, 27), `docs/PUBLICATION.md` (new, 76), the `DESIGN.md` remediation (−3/+2 frontmatter, one prose
  line), the `README.md` fix, and the five planning records. Working tree clean; nothing untracked.
  The handoff also gained the mechanical guard the finding asked for: `docs/PUBLICATION.md:45` now conditions
  the command block on "the preparation commit is present, the working tree is clean, the operator approves",
  and `:48` makes that testable with `test -z "$(git status --porcelain)"` as the first command in the block.
  Executed literally today, the documented procedure now publishes `3318077` — CI, security policy,
  contributing guide, and sanitized `DESIGN.md` included.

- **D1 (critical) — RESOLVED, with a residual (see E1).** `docs/PUBLICATION.md:9` now reads "the five commits
  through `v0.1.0` … each revision contains an obsolete local profile path in `DESIGN.md`. The prepared
  current tree removes the path, but a full-history mirror retains it in earlier revisions." Verified exactly:
  `git grep` across `git rev-list --all` places the path at `DESIGN.md:6` (`source:` frontmatter) and
  `DESIGN.md:64` (prose) in `217d2b0`, `1e07d2a`, `4b4e41e`, `2332025`, and `a71831f` — five commits, the last
  of which is precisely `v0.1.0` — and **nowhere in `DESIGN.md` at `HEAD`**, where the frontmatter now reads
  `extends: project-local operational interface baseline` with no `source:` key and the Overview line no
  longer names an inherited file. The sentence is now accurate about which revisions carry it and about the
  direction of the exposure, which is what D1 was about. Operator acceptance is explicit and un-defaulted:
  §1 opens "The operator must explicitly resolve these items", the item states plainly that both disclosures
  "become permanent public history if mirrored", and no acceptance is recorded as already granted.

- **D2 (warning) — RESOLVED.** The 404 hyperlink is gone. `README.md:178` now reads "Roadmap, requirements,
  and verification evidence are tracked in `.planning/`; this audit links that directory as [`.planning/`](../.planning/). A
  link check across all 15 Markdown files in the materialized public tree found **0 broken local links**
  (6 resolved) and exactly **1 external link**, `https://docs.astral.sh/uv/` → **HTTP 200**. For the record,
  `https://github.com/earendil-works/saga` still returns 404; it is simply no longer referenced anywhere in
  the tree. The only surviving mention of Saga is `CLAUDE.md:25` describing `.planning/` as files of record,
  unlinked.

### Correctness

- [warning] **E1 — `docs/PUBLICATION.md` §1 still slightly understates the obsolete-path exposure, in the same
  direction D1 did.** "The prepared current tree removes the path" is true of `DESIGN.md` and false of the
  tree. At `HEAD`, `git grep -c "/home/<user>"` returns **5 occurrences in `.planning/AUDIT.md`** (including
  the D1 finding itself at `:609` and the acceptance-gate section at `:795`) and **2 in
  `.planning/TRACEABILITY.md`**. Both files are tracked, so both publish, and the path therefore ships as
  _current content_ — quoted inside the audit record rather than sitting in `DESIGN.md`, but current content
  all the same. This matters only because the approval gate is procedural (**S5** in the prior pass: nothing
  technically prevents a push), which makes the accuracy of the disclosure the actual control. An operator
  reading §1 today would accept a marginally smaller exposure than the one that exists. Fix is one clause:
  note that the path also remains quoted in `.planning/AUDIT.md` and `.planning/TRACEABILITY.md` as part of
  the published audit record. On merits the string remains what the prior pass judged it — a local username
  and a dotfile path, no host, no address, no credential — so this is an accuracy defect, not a safety one.
  Related and unimplemented: prior finding **OP1** recommended stating in the handoff that `.planning/`
  publishes in full. Doing both is a single sentence.

- [warning] **E2 — the handoff's evidence list has already drifted behind the tree it describes.**
  `docs/PUBLICATION.md:71` says "Gitleaks 8.30.1 scanned all five commits with no findings." Six commits are
  now reachable, and the one outside that claim is the publication commit itself — the commit that introduces
  every file the operator is about to publish. The claim is not wrong about what was done; it is wrong about
  what it now covers. This session's re-run closes the gap (6 commits, 389.58 KB, no leaks), but the document
  will drift again on the next commit. Fix: phrase the evidence bullets against "all reachable commits"
  rather than a frozen count, or restate the count at the moment of publication. This is the third instance
  in two audits of a static sentence in this document falling out of step with the repository — D1 was the
  first, E1 the second.

- [info] **E3 — M1's methodological correction did not land in the document.** `docs/PUBLICATION.md:73` still
  records the bare form, `pip-audit --strict`. A reader re-running the documented check literally re-creates
  the no-op risk the prior audit identified: with no `-r`/`-e` argument it audits the ambient environment.
  Re-run correctly this session against `uv export --frozen --all-groups` (505 lines, 421 hash-pinned):
  **no known vulnerabilities**. Worth writing the explicit form into the bullet so the check cannot silently
  degrade.

- [info] **E5 — the committed `AUDIT.md` contains a statement that its own commit falsified.** Line 609 reads
  "appears in **all five commits, including `HEAD`**", which was true when written against `a71831f` and
  became false the moment `3318077` landed, since that commit both records the finding and removes the path.
  Dated audit records are allowed to be historical, but a public reader hits the contradiction with no marker.
  This section resolves it; no edit to the prior section is needed or appropriate.

- [info] **C1 — carried forward, unchanged.** `README.md:31-34` still opens with `uv tool install .` without a
  preceding `git clone`, and `CONTRIBUTING.md:11` still carries the literal `git clone <repository-url>`
  placeholder. Both are cheap to fix once the real URL exists, and `docs/PUBLICATION.md:67` already schedules
  that patch.

### Safety

- [info] **S1 — no secret, credential, or private-infrastructure disclosure, re-derived independently.**
  Gitleaks 8.30.1 over `--all --full-history`: **6 commits, 389.58 KB, no leaks**. Gitleaks over the
  materialized 44-file public tree: 354.41 KB, no leaks. Neither result is suppressed — no `.gitleaksignore`,
  `gitleaks.toml`, or `.gitleaks.toml` exists in the working tree or anywhere in `git ls-files`. An
  independent `git grep` across all six commits for credential shapes (`Bearer …`, `Token <hex40>`, `AKIA…`,
  `ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_`, `github_pat_`, PEM private-key headers, quoted `password=`/`secret=`/
  `api_key=`) surfaced only the four synthetic fixture literals in `tests/test_client.py`. A full-history grep
  for RFC1918 and `172.16/12` address literals returned **zero matches in every commit**. The decisive check
  is again the targeted one: 27 candidate private strings drawn from `.env` and the live dogfood snapshot —
  the `NETBOX_URL`, its host literal, the 40-character `NETBOX_TOKEN`, every real device name, every real
  address — were searched against the full public-tree corpus and against `git log --all -p`. Exactly four
  matched, all generic vendor/role vocabulary (`Router`, `Switch`, `Server`, `Ruckus`) occurring in synthetic
  fixtures and audit prose. **The token, the URL, and the host literal matched nothing in either corpus.**

- [info] **S2 — ignore-rule assumptions re-demonstrated.** `git ls-files -i -c --exclude-standard` is empty.
  `git check-ignore -v` attributes each sensitive path to a specific rule: `.env`→`.gitignore:15`,
  `.env.local`→`:16`, `snapshot/…`→`:19`, `dist/…`→`:11`, `build/…`→`:12`, `config.yaml`→`:18`,
  `.planning/.close-out-auditor.log`→`:20`. The `.env.*` / `!.env.example` negation is still ordered correctly
  and `.env.example` resolves as not-ignored, as does `examples/output/…`. Live `snapshot/` artifacts are mode
  `0600` and untracked.

- [info] **S3 — the public tree grew by exactly the intended four files.** 44 files now versus 43 in the prior
  pass. `git ls-files` is 44 and `git ls-files --others --exclude-standard` is 0, where previously the split
  was 40/4 — the same content, now all tracked. Nothing unexpected entered the publishable set.

- [info] **S4 — `AGENTS.md` publishes as a symlink to `CLAUDE.md`.** Tracked as a symlink (mode 120000) and
  materialized as one. GitHub renders it as a link rather than following it; harmless, but it means the
  cross-CLI convention is visible to a public reader and `CLAUDE.md` — which contains the project's internal
  agent instructions — is unavoidably part of the published surface. Already true before this milestone;
  noted because the file's audience changes on publication.

- [info] **S5 — the approval gate remains procedural, not technical.** The local `gh` CLI is authenticated as
  `kevinb361` with `repo` and `workflow` scopes. Nothing in this environment prevents an agent or script with
  shell access from creating the repository and pushing. Unchanged, and the reason **E1** is worth fixing.

- [info] **S6 — the private mirror is now one commit behind local `main`.** `refs/remotes/origin/main` is
  `a71831f` while `refs/heads/main` is `3318077`; the publication commit has not been pushed to Gitea either.
  This is correct for an audit that was told to push nothing, and `docs/PUBLICATION.md` pushes from the local
  clone, so the mirror lag cannot cause the wrong tree to publish. It matters for one case only: if the
  operator ever mirrors to GitHub _from the Gitea copy_ rather than from this working clone, they would
  publish `a71831f` — the exact tree D3 warned about. Worth a line in the handoff if that path is ever
  considered.

### Test Coverage

- [info] **TC1 — both matrix legs reproduced, the 3.12 leg inside the public tree.** 3.11.14 (project venv):
  `make ci` → black clean 15 files, ruff clean, mypy clean 15 source files, `pytest -n auto` **39 passed**.
  3.12.3: executed inside the materialized 44-file public-tree copy with `UV_FROZEN=1` and an isolated
  `UV_PROJECT_ENVIRONMENT`, syncing from the frozen lock → identical results, **39 passed**. The second run
  again doubles as a self-sufficiency proof: the published tree builds, type-checks, and tests with `.env`,
  `snapshot/`, `dist/`, and every cache absent.

- [info] **TC2 — the public-safety property still has a test behind it.**
  `tests/test_examples.py::test_public_docs_and_examples_contain_no_private_networks_or_credentials` runs in
  the standard gate on both legs, so the docs/examples invariant regresses loudly rather than depending on
  someone remembering to re-run a scanner.

- [warning] **E4 — TC3 carried forward: the gate still cannot catch the defects this audit found.** There is
  no link check over `README.md`, and no test asserting that publication-critical files are tracked. The
  clean-tree precondition landed in the handoff prose (`docs/PUBLICATION.md:48`), which is a real improvement
  because it is mechanically checkable — but it is checked by the operator reading the document, not by CI.
  E1 and E2 are both documentation-accuracy defects, and both would be caught by a dozen-line test that walks
  Markdown links and asserts `git status --porcelain` empty plus the presence of the four artifacts. Not
  blocking; the evidence that the gap is real is that it has now produced findings in two consecutive audits.

### Architecture Fit

- [info] **AR1 — the CI workflow is unchanged, still least-privilege, and its pins are still current.** Both
  SHAs were re-verified against the live GitHub API this session rather than eyeballed:
  `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` resolves to `refs/tags/v7.0.1` exactly and
  `astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9` to `refs/tags/v9.0.0` exactly, both still the
  current latest release of their project (published 2026-07-20 and 2026-07-21). Top-level
  `permissions: contents: read`, no job-level widening, no `pull_request_target`, no `secrets` reference,
  `persist-credentials: false` on checkout, `concurrency` with `cancel-in-progress`, `timeout-minutes: 10`.
  `zizmor` 1.27.0 at `--persona=auditor` → **no findings**. `yamllint -d relaxed` → one 82-char line at
  `ci.yml:36` and nothing else. The workflow remains the strongest part of this milestone.

- [info] **AR2 — job names and branch protection still agree.** `name: Python ${{ matrix.python-version }}`
  renders `Python 3.11` and `Python 3.12`, verbatim the required checks at `docs/PUBLICATION.md:38`.

- [info] **AR3 — dependency licensing re-checked and clean for MIT redistribution.** Runtime tree: httpx
  BSD-3-Clause, jsonschema MIT, PyYAML MIT, httpcore BSD-3-Clause, idna BSD-3-Clause, h11/anyio/attrs/
  referencing/rpds-py/jsonschema-specifications MIT, typing-extensions PSF-2.0, certifi MPL-2.0.
  Dev-only additions carry MIT/BSD/Apache-2.0, plus `pathspec` (MPL-2.0, a `black` dependency). Neither
  MPL-2.0 package is vendored or modified, so no source-disclosure obligation attaches — same reasoning as
  **I2** in the prior pass, now covering `pathspec` as well.

### Operability

- [info] **OP1 — carried forward and still unimplemented.** `.planning/AUDIT.md` is tracked and will publish
  in full — now 800+ lines of self-critique including this section, and including the deferred, currently
  unfixed items (redirect diagnostics, output/index path collisions, extreme YAML nesting, malformed-endpoint
  diagnostics). None is exploitable, and for a pre-alpha tool the transparency is arguably an asset. But the
  choice is still not written down anywhere, and it is the same sentence that fixes **E1**.

- [info] **OP2 — this audit's own outputs leave the tree dirty, by design.** Writing
  `.planning/TRACEABILITY.md` and this `AUDIT.md` section makes `git status --porcelain` non-empty, which
  means `docs/PUBLICATION.md:48`'s precondition will now fail until these records are committed. That is the
  precondition working as intended rather than a defect, but it is worth stating plainly: the audit records
  must be committed before publication, and the audit that verifies the commit cannot itself be inside it.
  Per instruction, nothing was committed by this pass.

- [info] **OP3 — the approval gate holds, verified read-only.** `git remote -v` shows one remote,
  `origin → gitea:kevin/netbox-scribe.git` (private self-hosted Gitea over SSH). `git for-each-ref` shows
  exactly three refs: `refs/heads/main 3318077`, `refs/remotes/origin/main a71831f`, `refs/tags/v0.1.0
dd5f4c5`. `gh api repos/kevinb361/netbox-scribe` → **HTTP 404**. A global GitHub search for repositories
  named `netbox-scribe` → **0 results**; a broader `netbox scribe` search → **1 result**, the unrelated
  `liamhoganson/PortScriber` (last pushed 2025-02-04). PyPI `netbox-scribe` → **HTTP 404**, still unclaimed.
  No GitHub repository, no GitHub remote, no public ref, nothing pushed — including to Gitea.

### ASSERTED Items from TRACEABILITY.md

- None. This session's `/saga-verify` pass classifies all 13 requirements **PROVEN**, with v0.1.1's four at
  **PROVEN 4 · ASSERTED 0 · OPEN 0 · WAIVED 0**. Every v0.1.1 evidence artifact was re-executed against the
  committed tree, so no classification rests on a claim inherited from a prior pass — which is the specific
  thing that changed, since the previous pass could only verify a working tree. REQ-013 remains PROVEN with
  two prose-accuracy annotations (**E1**, **E2**) recorded here rather than as a status downgrade: its named
  artifact exists, names the required settings and commands, and its approval gate demonstrably holds.

### Explicit judgment: disclosed Gmail metadata and the obsolete local path

**Gmail commit metadata — PASS, unchanged.** All six commits and the annotated `v0.1.0` tag carry
`Kevin Blalock <kevin.blalock@gmail.com>` as author, committer, and tagger. It agrees with `LICENSE` and
`pyproject.toml`, it is the maintainer's chosen public identity, and attributed authorship is the norm for
open-source publication. Not a credential, not infrastructure, not third-party personal data.
`docs/PUBLICATION.md` §1 surfaces it for acknowledgement, which is correct handling. No remediation warranted.

**Obsolete local profile path — PASS on merits, one accuracy clause short of complete.** The substantive
condition from the prior pass is met: the path is out of `DESIGN.md` at `HEAD`, it is confined to the five
revisions through `v0.1.0`, and §1 now describes that correctly, so a full-history mirror publishes it as
history rather than as live configuration. What remains is **E1** — the same string is still quoted in the
tracked audit record, so "the current tree removes the path" overstates the removal by a small margin. The
string itself is harmless; the reason to fix it is that the operator's acceptance is the only control here,
and an acceptance gate should not describe a smaller exposure than the real one.

### Verdict

**CONDITIONAL**

- Critical findings: **0** — all three prior conditions on close (D3, D1, D2) verified remediated in `HEAD`
- Warnings: **3** (E1, E2, E4)
- Info: **17** (E3, E5, C1, S1, S2, S3, S4, S5, S6, TC1, TC2, AR1, AR2, AR3, OP1, OP2, OP3 — of which E3, E5,
  S3, S4, OP2 are new this pass and the remainder are carried forward or re-derived confirmations)

Rationale: the milestone's blocking defects are genuinely fixed, and fixed in the way that matters. The
deliverable is in a commit, the working tree is clean, and the handoff now gates its own command block on a
mechanically checkable precondition rather than on the operator noticing. Followed literally today, the
documented procedure publishes `3318077` — with CI, security policy, contributing guide, and a sanitized
`DESIGN.md` — instead of the `a71831f` tree the previous audit caught it publishing. The history wording is
now exactly right about scope: five commits through `v0.1.0`, verified commit by commit, with `HEAD`'s
`DESIGN.md` clean. The dead Saga link is gone and every remaining link in the public tree resolves.

The security substance survived independent re-derivation rather than being re-read. Six commits and the
44-file materialized public tree are Gitleaks-clean with no suppression file anywhere; a full-history grep
for RFC1918 literals returns zero matches in every commit; and — the check that actually decides it — the
real token, the real NetBox URL, its host, and every real device name were searched against both the whole
public corpus and the full patch history and matched nothing, with the only overlaps being the words
`Router`, `Switch`, `Server`, and `Ruckus`. Dependencies audit clean against an explicit 505-line frozen
export, licensing is compatible, both action pins re-verified byte-for-byte against the live GitHub API and
both still current, zizmor clean at its strictest persona, and both matrix legs green with the 3.12 leg run
inside the public tree. The approval gate holds absolutely: one private Gitea remote, three refs, no GitHub
repository, zero global search hits, nothing pushed anywhere.

What holds it at CONDITIONAL is narrow and is not about security. Two sentences in `docs/PUBLICATION.md` are
inaccurate in the same direction as the defect this remediation was meant to close: §1 claims the current
tree removes the obsolete path when the path is still quoted in tracked, publishing audit records, and the
evidence list still says "all five commits" when six are reachable and the uncovered one is the publication
commit itself. Neither is a safety issue — the path is a username and a dotfile name, and the sixth commit
scans clean. They matter because this milestone's deliverable is a _correct publication procedure_ whose only
enforcement is an operator reading that document, which makes the document's accuracy the control. Both fixes
are one clause each, and one of them also discharges the standing OP1 recommendation to state that
`.planning/` publishes in full.

Conditions on close:

1. Amend `docs/PUBLICATION.md` §1 to note that the obsolete path also remains quoted in `.planning/AUDIT.md`
   and `.planning/TRACEABILITY.md`, and — same sentence — that `.planning/` publishes in full (**E1**,
   **OP1**).
2. Restate the "Verified preparation evidence" scan claim against all reachable commits rather than a frozen
   count of five, and record the explicit `pip-audit --strict -r <frozen export>` form (**E2**, **E3**).

Recommended, not blocking: add the dozen-line link-and-tracked-artifact test that would have caught this
audit's findings and the previous one's (**E4**), and fill the `<repository-url>` placeholder and missing
`git clone` line once the real URL exists (**C1**).

Per instruction, this audit did not edit `ROADMAP.md` or `STATE.md`, created no remote or public resource,
pushed nothing, and rewrote no history. It wrote `.planning/TRACEABILITY.md` and this section only, and
committed nothing.
