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
