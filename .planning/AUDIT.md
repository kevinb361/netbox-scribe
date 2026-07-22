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

---

## Audit: v0.1.1 Public GitHub Readiness — 2026-07-21 (post-remediation re-audit at `5c31f27`)

Auditor: Claude Opus 4.8 (`claude-opus-4-8`, 1M context) via Claude Code — independent re-audit of the
committed tree after the E1/E2 wording corrections and the E4 mechanical gate. Supersedes nothing; the
`3318077` entry above stands as the record of that commit.
Scope: v0.1.1 Public GitHub Readiness — public-safety audit, GitHub CI, security/contribution policy, and
publication handoff (REQ-010..REQ-013).
Files reviewed: since `v0.1.0` (`a71831f`) — **14 files changed, 1014 insertions(+), 84 deletions(-)**.
Since the previous audited commit `3318077` — **6 files changed, 464 insertions(+), 84 deletions(-)**
(`.planning/AUDIT.md`, `.planning/STATE.md`, `.planning/TRACEABILITY.md`, `Makefile`,
`docs/PUBLICATION.md`, `scripts/check_public_readiness.py`). Under the 50-file single-pass limit.

Method: no claim in this section is inherited from a prior audit section or from `TRACEABILITY.md`. The two
corrected sentences were checked against the repository state they describe rather than read for plausibility.
The new gate was **mutation-probed across 14 cases in a throwaway `git clone --no-hardlinks` of `5c31f27`**,
never in the working repository, and its coverage boundaries were mapped by deliberately constructing the
cases it does _not_ catch. Security substance was re-derived from scratch: Gitleaks over both full history
and the materialized public tree, an independent credential-shape grep across every reachable commit, a
targeted search for 25 real private strings, a frozen-export dependency audit, live GitHub-API resolution of
both action pins, `zizmor` at `--persona=auditor` on two versions including one run online with a token, and
both CI matrix legs end to end. Nothing was committed, pushed, or created.

`.planning/config.json` carries a populated `close_out_auditor` key — no WARN.

`make ci` this session: black clean (**16** files — `scripts/check_public_readiness.py` is now in black's
scope), ruff clean, mypy clean (15 source files), `pytest -n auto` → **39 passed**, `public-check` →
_Public readiness checks passed (45 tracked files)_. **The checker passes with itself tracked**, which is the
non-trivial half of that claim: it walks `git ls-files`, and `scripts/check_public_readiness.py` is in that
set.

### Prior conditions on close — status

| ID      | Condition from the `3318077` audit                                                                                                      | Status this pass                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------- | --------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **E1**  | Amend `docs/PUBLICATION.md` §1 to note the obsolete path also remains quoted in tracked audit records                                   | **FIXED & independently verified.** §1 now reads "The prepared `DESIGN.md` removes the path, while tracked audit/traceability evidence quotes it when documenting the review; a full-history mirror also retains the original file content in earlier revisions." Checked against reality rather than accepted: `DESIGN.md` carries the literal twice in each of the five commits `217d2b0`, `1e07d2a`, `4b4e41e`, `2332025`, `a71831f`, and **zero** times at `3318077` and at `5c31f27`; at `HEAD` the literal survives in exactly one tracked file, `.planning/AUDIT.md` (5 occurrences), while `TRACEABILITY.md` carries only the redacted form. The new wording is therefore accurate and, if anything, errs one notch _toward_ overstating exposure — which is the correct direction for an acceptance gate |
| **OP1** | Same sentence: state that `.planning/` publishes in full                                                                                | **NOT DONE.** No sentence in `docs/PUBLICATION.md` says the planning directory publishes in its entirety. "Tracked audit/traceability evidence" implies it to a careful reader and is not inaccurate, but the ~1,400 lines of self-critique that ship as public content are still never named as a decision. Non-blocking; see **F1**                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| **E2**  | Restate the Gitleaks evidence claim against all reachable commits rather than a frozen count of five                                    | **FIXED & independently verified.** The bullet now reads "Gitleaks 8.30.1 scanned the complete reachable history with no findings" — no count to go stale. Re-executed: **7 commits, 436.52 KB, no leaks**. The sentence is now true and stays true as commits land, which was the actual defect                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **E3**  | Record the explicit `pip-audit --strict -r <frozen export>` form                                                                        | **NOT DONE.** `docs/PUBLICATION.md:73` still records the bare `pip-audit --strict`. Re-run correctly this session against `uv export --frozen` (505 lines) → _no known vulnerabilities_. See **F2** — this is the one residual worth a condition                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **E4**  | Add the link-and-tracked-artifact check that would have caught this audit's findings and the previous one's (recommended, not blocking) | **DONE, and stronger than recommended.** Delivered as `scripts/check_public_readiness.py` wired into `make ci` via a `public-check` target, so it runs on both CI matrix legs, not only locally. Mutation-proven across 14 cases — see Test Coverage. It enforces four distinct properties, three more than the "dozen-line test" the recommendation asked for                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **E5**  | Prior `AUDIT.md` line 609 contradicts its own commit (info; no edit expected)                                                           | **Resolved as expected.** No edit was made to the historical section, which is correct — dated audit records are historical documents. The `3318077` section resolves it in prose and this section carries it no further                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **C1**  | Fill the `<repository-url>` placeholder and the missing `git clone` line once the real URL exists                                       | **Carried, unchanged and correctly deferred.** `README.md:31-34` still opens with `uv tool install .` with no preceding clone; `CONTRIBUTING.md:11` still has the literal `git clone <repository-url>`. Both are blocked on a URL that by design does not exist yet, and `docs/PUBLICATION.md` already schedules the patch                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |

### Correctness

- [warning] **F2 — the documented dependency-audit command still no-ops if re-run literally.**
  `docs/PUBLICATION.md:73` records `pip-audit --strict` with no `-r` or `-e`. Invoked exactly as written it
  audits whatever environment happens to be active, which for a reader following the handoff is very likely
  not the project's locked set. The underlying fact is not in doubt — this session re-ran the correct form,
  `pip-audit --strict -r` against a 505-line `uv export --frozen`, and got _no known vulnerabilities_ — so
  the risk is not a hidden vulnerability today. The risk is that a verification step whose recorded form
  cannot fail is not a verification step. This is the third consecutive audit to find a static sentence in
  this document out of step with what it claims, and it is the residual clause of the prior pass's own
  condition 2. Fix is the argument: `pip-audit --strict -r <(uv export --frozen)`, or the two-line form.

- [info] **F1 — `.planning/` still publishes in full without the handoff ever saying so.**
  Standing since **OP1** two audits ago. At `HEAD` the planning spine is ~1,400 lines of `AUDIT.md` plus
  `TRACEABILITY.md`, `SPEC.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, and two decision records, all
  tracked and all public on push. That includes this section, including its own criticisms, including the
  deferred-and-still-unfixed items listed in `STATE.md` (redirect diagnostics, output/index path collisions,
  extreme YAML nesting, malformed-endpoint diagnostics). For a pre-alpha tool the transparency is defensible
  and arguably an asset — the point is that it should be a recorded decision in the operator's pre-publication
  checklist rather than a side effect of what happens to be tracked. One sentence in §1.

- [info] **F3 — README's install path still assumes a clone it never instructs.** Verbatim carry of **C1**.
  Re-confirmed at `README.md:31-34` and `CONTRIBUTING.md:11`. Correctly deferred to the URL-fill patch.

- [info] **F4 — the handoff's ref-verification commands print rather than assert.**
  `docs/PUBLICATION.md` verifies the push with `git rev-parse main github/main` and
  `git rev-parse v0.1.0 github/v0.1.0^{}`, which emit two SHAs each and leave the comparison to the reader's
  eye. The preceding command block sets the precedent for doing better — `test -z "$(git status --porcelain)"`
  is a real assertion that exits non-zero. A `test "$(git rev-parse main)" = "$(git rev-parse github/main)"`
  form would match it. Cosmetic relative to F2; noted because the same document already demonstrates the
  better pattern one section earlier.

### Safety

- [info] **G1 — no secret, credential, or private-infrastructure disclosure. Re-derived, not re-read.**
  Gitleaks 8.30.1 over `--log-opts="--all"`: **7 commits, 436.52 KB, no leaks** — now including `5c31f27`,
  the commit that introduces the gate script itself. Gitleaks over the materialized public tree (44 regular
  files + the `AGENTS.md` symlink): 362.01 KB, no leaks. Neither result is suppressed: no `.gitleaksignore`,
  `gitleaks.toml`, `.gitleaks.toml`, or `.secretsignore` exists in the working tree or anywhere in
  `git ls-files`. An independent `git grep -E` across every reachable commit for `ghp_`/`gho_`/`ghu_`/`ghs_`/
  `ghr_`, `github_pat_`, `AKIA[0-9A-Z]{16}`, PEM private-key headers, `Bearer <20+>`, and `Token <hex40>`
  matched **only audit prose enumerating those patterns** — not a single literal. A full-history grep for
  RFC1918 and `172.16/12` address literals returned **0 matches across all 7 commits**.
  The decisive check is again the targeted one, not the scanner: 25 candidate private strings pulled
  programmatically from `.env` and the live untracked dogfood snapshot — the `NETBOX_URL`, its host literal,
  the 40-character `NETBOX_TOKEN`, every real device name — were searched against the full public-tree corpus
  and against `git log --all -p` (7,009 lines / 563,793 chars), with values compared in memory and never
  printed. Exactly **4** matched, all generic vendor/role vocabulary: `Router`, `Switch`, `Server`, `Ruckus`.
  **The token, the URL, and the host literal matched nothing in either corpus.** Scanners find secret
  _shapes_; this finds the specific private strings this project has actually handled.

- [info] **G2 — the obsolete profile path is where the corrected §1 says it is.** Per-commit count of the
  literal in `DESIGN.md`: `217d2b0` 2, `1e07d2a` 2, `4b4e41e` 2, `2332025` 2, `a71831f` 2, `3318077` **0**,
  `5c31f27` **0**. At `HEAD`, `git grep -c` across the whole tree finds it in exactly one file,
  `.planning/AUDIT.md` (5 occurrences), all inside sections analyzing the disclosure. On merits it remains
  what two prior passes judged it: a local username and a dotfile name — no host, no address, no credential.

- [info] **G3 — ignore rules demonstrated, not assumed.** `git ls-files -i -c --exclude-standard` is empty.
  `git ls-files --others --exclude-standard` returns **0** — the tracked set and the working set now agree
  exactly, so nothing is sitting untracked waiting to be swept in. `git check-ignore -v` attributes each
  sensitive path to a specific rule: `.env`→`.gitignore:15`, `dist`→`:11`, `snapshot`→`:19`,
  `.planning/.close-out-auditor.log`→`:20`. Live `snapshot/` artifacts are mode `0600` and untracked. The
  publishable set is 45 paths, up 1 from the prior pass's 44 — exactly the gate script, nothing else.

- [info] **G4 — the mechanical gate now enforces three of these properties instead of trusting them.**
  What was previously an auditor's `check-ignore` transcript is now a `make ci` failure: `.env`,
  `dist/`, `snapshot/`, and `.planning/.close-out-auditor.log` becoming tracked each fail the build. This is
  the substantive security improvement in `5c31f27` — the ignore rules had a second line of defense only as
  long as someone ran an audit. Note the scope boundary, which is correct: the checker guards against these
  paths being _tracked_, not against `.gitignore` being weakened, since a weakened ignore rule only matters
  once something is actually added.

- [info] **G5 — the approval gate remains procedural, not technical.** Unchanged and worth restating because
  it is why document accuracy is the real control here. The local `gh` CLI is authenticated as `kevinb361`
  with a token carrying repo scope; nothing in this environment technically prevents an agent or script with
  shell access from creating the repository and pushing. The controls that exist are the operator's reading
  of `docs/PUBLICATION.md` and the absence of a GitHub remote.

- [info] **G6 — the private mirror is now two commits behind local `main`.** `refs/remotes/origin/main` is
  `a71831f` (= `v0.1.0`) while `refs/heads/main` is `5c31f27`; neither `3318077` nor `5c31f27` has been
  pushed to Gitea. Correct for an audit told to push nothing, and harmless for the documented procedure,
  which mirrors from this working clone. It matters in exactly one scenario, now one commit worse than last
  pass: mirroring to GitHub _from the Gitea copy_ would publish the `a71831f` tree — no CI, no `SECURITY.md`,
  no `CONTRIBUTING.md`, no gate script, and a `DESIGN.md` still carrying the obsolete path. Worth one line in
  the handoff if that path is ever considered.

- [info] **G7 — `AGENTS.md` publishes as a symlink to `CLAUDE.md`.** Tracked as mode `120000` and
  materialized as a symlink by `git archive`. GitHub renders it as a link rather than following it. Harmless,
  but it means `CLAUDE.md` — the project's internal agent instructions — is unavoidably part of the published
  surface. Re-verified public-safe this pass: it contains no IPs, hostnames, employer names, or credentials.

### Test Coverage

- [info] **H1 — the new gate was proven by mutation, and it holds.** Fourteen cases in a throwaway clone of
  `5c31f27`. Required-artifact enforcement: untracking `SECURITY.md` → `required public artifact is not
tracked: SECURITY.md`, exit 1. Forbidden-path enforcement: force-adding `.env`, `dist/wheel.txt`,
  `snapshot/inventory/devices.yaml`, and `.planning/.close-out-auditor.log` each → `sensitive/generated path
is tracked: <path>`, exit 1. `DESIGN.md` enforcement: appending an absolute local path fails, and appending
  only a `~/.agent-profile/…` reference **also** fails — so both halves of the disjunction at
  `check_public_readiness.py:34` are live, not one dead branch riding on the other. Link enforcement: a broken
  relative link in `README.md` fails by name and target, and so does one buried in the 1,100-line
  `.planning/AUDIT.md`, so large tracked files are genuinely walked rather than skipped.

- [info] **H2 — valid links are not masked, and findings do not short-circuit.** The two properties the
  request singled out, both probed directly. Adding five valid links (relative, `#anchor`, `https://`,
  `mailto:`, and a `#fragment`-suffixed relative path) alongside one broken link produced findings for the
  broken targets **only** — no false positive on any valid form, and fragment-stripping before resolution
  works. Separately, mutating four failure classes simultaneously (untracked `LICENSE`, tracked `.env`,
  `DESIGN.md` path, broken link) reported **all four in one run** before exiting 1: `findings` accumulates
  and is printed in full, so a first failure never hides the rest. Independently of the checker, all **7**
  local Markdown link targets in the tracked tree were re-resolved this session — including reference-style
  and raw-HTML forms the checker does not parse — and every one resolves to a **tracked** path. The gate and
  the independent walk agree.

- [warning] **N1 — the checker validates filesystem existence, not tracked-ness, which is a weaker
  property than its own purpose.** `_broken_local_links` resolves each target and calls `.exists()`. Two
  probe-confirmed consequences: a link to `snapshot/inventory/devices.yaml` — present on the developer's
  disk, gitignored, and absent from every public clone — **passes**; and a link to an absolute path such as
  `/etc/hostname` **passes** because `pathlib` lets an absolute component override the base, and the file
  happens to exist on the runner. Both forms are green locally and 404 for every public reader, which is
  precisely the class of defect this script exists to prevent. No live instance exists at `HEAD` — the
  independent walk in **H2** confirms all 7 targets are tracked — so this is a latent gap, not a current
  break. The fix is roughly one line, replacing the existence test with membership in the `tracked` set the
  function already receives as an argument and currently only uses to enumerate Markdown files.

- [info] **N2 — `scripts/` sits outside `mypy`'s configured scope.** `pyproject.toml:56` pins
  `files = ["src", "tests"]`, so `make type` reports 15 source files and never sees the gate script, even
  though `make ci` executes it. black and ruff use default discovery and do cover it — which is why the black
  count moved 15 → 16 and nobody noticed the typing hole. Pointed at explicitly, the script passes
  `mypy --strict` cleanly today; the gap is that nothing keeps it that way. One-word fix:
  `files = ["src", "tests", "scripts"]`.

- [info] **N3 — the checker raises an uncaught traceback outside a Git checkout.** Run inside the
  materialized `git archive` tree — i.e. a source tarball, which is exactly how a sdist consumer receives
  this project — `subprocess.run(..., check=True)` raises `CalledProcessError` and prints a stack trace
  rather than a bounded message. It still exits non-zero, so `make ci` fails correctly; the defect is
  operability, not correctness, and it is a two-line `try/except` producing something like
  `public-readiness error: not a Git checkout`. Note the irony: the rest of this codebase is unusually
  disciplined about bounded operator errors — `cli.py` catches `UnicodeError` specifically to avoid exactly
  this shape — so the gate script is the one file that does not follow the project's own convention.

- [warning] **N4 — Markdown links inside fenced code blocks are checked as if they were real, and this
  audit reproduced it accidentally.** The regex at `check_public_readiness.py:23` is applied to raw file
  text with no fence awareness, so an inline link written as an _example_ is resolved as a _reference_.
  Probed deliberately: a fenced `[example]` + `(does-not-exist.md)` pair fails the gate. It then happened
  for real — the first draft of this very finding embedded that example verbatim in prose, and
  `make ci` failed with `broken local link in .planning/AUDIT.md: does-not-exist.md`. That is the strongest
  available evidence that the false positive is reachable in practice rather than theoretical: the file that
  documents the gap tripped the gap. The workaround is to write example targets inside angle brackets, which
  `:38` skips — this finding now does. No unintended instance exists in the tracked tree at `HEAD`. Upgraded
  from info because the tree is documentation-heavy, `.planning/` is walked in full, and the failure mode is
  a build break on prose rather than on code.

- [info] **N5 — reference-style and raw-HTML links are not parsed.** `[ref]: does-not-exist.md` and
  `<a href="does-not-exist.md">` both pass. The single inline-link regex is a reasonable scope choice for a
  60-line script and the tracked tree uses no other form; recorded so the coverage boundary is documented
  rather than assumed. The independent walk in **H2** covered all three forms and found nothing.

- [info] **N6 — `DESIGN.md` is read unconditionally but is not in `REQUIRED`.** Deleting it produces a
  `FileNotFoundError` traceback rather than a finding. Same two-line fix family as **N3**; adding the path to
  `REQUIRED` would also close it, though `DESIGN.md` is arguably not a required _public_ artifact.

- [info] **H3 — the pre-existing public-safety test still runs in the gate on both legs.**
  `tests/test_examples.py::test_public_docs_and_examples_contain_no_private_networks_or_credentials` and
  `test_synthetic_example_outputs_match_production_export` both execute under `pytest -n auto` on 3.11 and
  3.12, so the docs/examples invariant and the committed-example byte contract regress loudly. The new
  checker complements these rather than duplicating them — it guards tracked-ness and links, they guard
  content.

- [info] **H4 — the gate script itself has no unit tests.** Deliberate and defensible at 60 lines with no
  branching logic worth pinning, and this pass substituted 14 behavioral probes for them. Recorded only
  because the probes live in this document and a scratch directory rather than in `tests/`, so the next
  change to the script has no regression net. If `N1` gets fixed, that edit is the natural moment to add
  three or four cases.

### Architecture Fit

- [info] **AR1 — the workflow re-audited clean, and both pins are still current.** SHAs re-resolved against
  the live GitHub API rather than eyeballed: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` →
  `refs/tags/v7.0.1` exactly, still the latest release (published 2026-07-20);
  `astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9` → `refs/tags/v9.0.0` exactly, still the
  latest (published 2026-07-21). Top-level `permissions: contents: read`, no job-level widening, no
  `pull_request_target`, no `secrets` reference, `persist-credentials: false`, `concurrency` with
  `cancel-in-progress`, `timeout-minutes: 10`, `UV_FROZEN: "1"`, `uv sync --frozen --dev`.
  `zizmor --persona=auditor` → **no findings**, run twice: 1.27.0 to match the prior pass, and **1.28.0 in
  online mode with a GitHub token**, which enables audits that offline mode silently skips. `yamllint -d
relaxed` → one 82-char line at `ci.yml:36`, nothing else. The workflow remains the strongest artifact in
  this milestone.

- [info] **AR2 — a note on the audit toolchain, not the project.** `zizmor` **1.27.0 — the exact version
  every prior audit of this project used — is now yanked from PyPI** under advisory GHSA-f42p-wjw5-97qh.
  That does not retroactively invalidate the earlier clean results, and re-running 1.28.0 online reproduces
  **no findings**, so the conclusion is unchanged. Recorded so that "zizmor 1.27.0 clean" in the earlier
  sections is not later mistaken for a current, reproducible claim.

- [info] **AR3 — `public-check` is wired at the right level.** It is a `make ci` prerequisite, not a separate
  CI step, so it runs identically in the local gate and on both GitHub matrix legs (`run: make ci`) with no
  second place to keep in sync. Both legs were reproduced this session: **3.11.14 → 39 passed**, gate clean,
  45 tracked files; **3.12.3 → 39 passed**, gate clean, 45 tracked files, executed inside an isolated clone
  containing no `.env`, no `snapshot/`, no `dist/`, and no caches — so the second run doubles as a
  self-sufficiency proof that the published tree builds, type-checks, tests, and self-audits alone.

- [info] **AR4 — job names and branch protection still agree.** `name: Python ${{ matrix.python-version }}`
  renders `Python 3.11` and `Python 3.12`, verbatim the required checks named in `docs/PUBLICATION.md`.

- [info] **AR5 — dependency licensing re-checked and clean for MIT redistribution.** Runtime tree: httpx,
  httpcore, idna BSD-3-Clause; jsonschema, PyYAML, h11, anyio, attrs, referencing, rpds-py,
  jsonschema-specifications MIT; typing-extensions PSF-2.0; certifi MPL-2.0. Dev-only additions carry
  MIT/BSD/Apache-2.0 plus `pathspec` (MPL-2.0, a `black` dependency). Neither MPL-2.0 package is vendored or
  modified, so no source-disclosure obligation attaches. `pip-audit --strict -r` against a 505-line
  `uv export --frozen` → _no known vulnerabilities_.

### Operability

- [info] **OP-A — this audit's own outputs leave the tree dirty, by design.** Writing
  `.planning/TRACEABILITY.md` and this section makes `git status --porcelain` non-empty, so
  `docs/PUBLICATION.md`'s clean-tree precondition will fail until these records are committed. That is the
  precondition working, not a defect — but it means the publication sequence is: commit these audit records,
  then publish. The audit that verifies a commit cannot be inside it. Per instruction, nothing was committed.

- [info] **OP-B — the clean-tree check is deliberately absent from the mechanical gate, and that is right.**
  The prior pass's **E4** suggested the automated test assert `git status --porcelain` empty. The
  implementer did not, and shouldn't have: every developer run and every CI run on a PR branch would fail.
  The clean-tree assertion belongs where it already lives — inside the publication command block at
  `docs/PUBLICATION.md`, as a real `test -z` that exits non-zero at the moment it matters. The gate checks
  the four properties that are true at all times; the handoff checks the one that is only true at publish
  time. Correct split.

- [info] **OP-C — the approval gate holds, verified read-only.** `git remote -v` → one remote,
  `origin → gitea:kevin/netbox-scribe.git` (private self-hosted Gitea over SSH). `git for-each-ref` → exactly
  three refs: `refs/heads/main 5c31f27`, `refs/remotes/origin/main a71831f`, `refs/tags/v0.1.0 dd5f4c5`
  (annotated, → `a71831f`). `gh api repos/kevinb361/netbox-scribe` → **HTTP 404**, as do
  `kevin-blalock/netbox-scribe` and `kevinblalock/netbox-scribe`. `gh search repos "netbox-scribe"` → **0
  results**; the broader `netbox scribe` → **0 results**; both sanity-checked against `gh search repos
"netbox"`, which returns the expected upstream projects, so the empty results are real rather than a
  silently failing command. PyPI `netbox-scribe` → **HTTP 404**, still unclaimed. No GitHub repository, no
  GitHub remote, no public ref, nothing pushed anywhere — including to Gitea.

### ASSERTED Items from TRACEABILITY.md

- None. This session's `/saga-verify` pass classifies all 13 requirements **PROVEN**, with v0.1.1's four at
  **PROVEN 4 · ASSERTED 0 · OPEN 0 · WAIVED 0**. Every v0.1.1 evidence artifact was re-executed against the
  committed tree at `5c31f27`. REQ-013 remains PROVEN with the two unwritten clauses (**F1**, **F2**)
  recorded here as follow-ups rather than as a status downgrade: its named artifact exists, names every
  required setting and command, and its approval gate demonstrably holds.

### Release-blocking vs. optional

Stated explicitly, because the residual list is long and almost none of it blocks anything:

**Release-blocking correctness or security findings: 0.** Nothing found this pass makes the tree at
`5c31f27` unsafe or incorrect to publish. The secret, privacy, dependency, license, workflow-security, and
approval-gate substance was re-derived independently and is clean. Both prior conditions' substantive halves
(**E1**, **E2**) are fixed and verified against the repository state they describe.

**One condition worth holding for: F2.** A verification step whose documented form cannot fail is not a
verification step. It is a one-clause edit to a document whose accuracy _is_ the control for this milestone,
and it is the unfinished half of the prior pass's own condition 2.

**Optional follow-ups, none blocking:** **N1** (tracked-ness vs. existence in the link check — the one with
real latent value), **N4** (fence-aware link scanning — the only finding this audit reproduced by accident),
**N2** (mypy scope), **N3**/**N6** (bounded errors in the gate script), **F1** (state that `.planning/`
publishes in full), **F4** (assert rather than print the ref comparison), **H4** (tests for the gate script),
**N5** (documented coverage boundary), **F3**/**C1** (URL fill, blocked on a URL that does not exist yet),
**G6** (a line about never mirroring from Gitea).

No finding in this section is stylistic. Formatting, prose quality, and structural preferences were
deliberately not raised.

### Verdict

**CONDITIONAL**

- Critical findings: **0**
- Release-blocking findings: **0**
- Warnings: **3** (F2, N1, N4)
- Info: **18** (F1, F3, F4, G1–G7, H1–H4, N2, N3, N5, N6, AR1–AR5, OP-A–OP-C)

Active counts — Warnings 3 · Info 18 · Conditions on close 1 · Release-blocking 0.

Rationale: the remediation did what it was supposed to do, and the part that mattered most was the part
that was only _recommended_. `5c31f27` converts three previously auditor-verified properties into build
failures: required public artifacts must stay tracked, forbidden generated paths must stay untracked, and
`DESIGN.md` must stay free of local profile paths — plus a fourth, link integrity, that neither prior audit
had any mechanical coverage for. It runs inside `make ci`, so it executes on both GitHub matrix legs rather
than only when someone remembers, and it passes with itself in the tracked set. Fourteen mutation probes in
a scratch clone confirm each rule fires on its own, that valid relative, anchor, fragment, `https://`, and
`mailto:` links are not masked, and that four simultaneous failures all report before exit. This closes the
loop that produced findings in two consecutive audits.

The two corrected sentences hold up against the repository rather than merely reading better. The obsolete
path is present twice in `DESIGN.md` in exactly the five commits through `v0.1.0` and zero times at the last
two commits, surviving at `HEAD` only as quoted text in one tracked audit file — which is what §1 now says,
erring if anything toward overstating the exposure. The Gitleaks bullet no longer carries a count that goes
stale on the next commit, and the re-run covers all seven.

The security substance was re-derived, not re-read. Seven commits and the 44-file materialized public tree
are Gitleaks-clean with no suppression file anywhere; a credential-shape grep across every commit matches
only prose describing the patterns; RFC1918 literals are absent from all seven commits; and the check that
actually decides it — 25 real private strings from `.env` and the live snapshot searched against both the
whole public corpus and the full patch history — matched exactly four times, all on the generic words
`Router`, `Switch`, `Server`, and `Ruckus`. The token, the URL, and the host matched nothing. Dependencies
audit clean against an explicit 505-line frozen export, licensing compatible, both action pins re-resolved
byte-for-byte against the live GitHub API and both still current, zizmor clean at its strictest persona on
two versions including one online run, and both matrix legs green at 39 passed with the 3.12 leg executed
inside an isolated clone. The approval gate holds absolutely: one private Gitea remote, three refs, no
GitHub repository under any plausible owner, zero global search hits against a search sanity-checked to be
working, PyPI unclaimed, nothing pushed anywhere.

What holds this at CONDITIONAL is one clause, and it is deliberately narrow. The prior pass's condition 2
had two halves; the stale-count half is fixed and the `pip-audit -r` half is not. `docs/PUBLICATION.md:73`
still records a command that, run exactly as written, audits the ambient environment instead of the locked
set — a step that cannot fail. The fact it asserts is true; this session verified it with the correct form.
But this milestone's deliverable is a _correct publication procedure_ whose only enforcement is an operator
following the document, which makes an unfalsifiable step in the evidence list a defect in the deliverable
itself, not a nit about the deliverable's prose. It is one clause.

The one optional item worth doing soon is **N1**: the new link check asks whether a target exists on the
runner's disk rather than whether it exists in the published tree, so a link to a gitignored or absolute
local path passes locally and 404s for every public reader — the exact defect class the script was written
to prevent. No such link exists today; all seven current targets were independently confirmed tracked. It is
about a one-line change, and the moment to make it is before someone adds a link to `snapshot/`.

Conditions on close:

1. Record the explicit `pip-audit --strict -r <frozen export>` form in `docs/PUBLICATION.md`'s evidence list,
   discharging the outstanding half of the previous audit's condition 2 (**F2**, **E3**).

Recommended, not blocking: change `_broken_local_links` to test membership in the tracked set rather than
filesystem existence (**N1**); add `scripts` to `mypy`'s `files` (**N2**); bound the gate script's non-Git
and missing-`DESIGN.md` failures (**N3**, **N6**); state in §1 that `.planning/` publishes in full (**F1**,
**OP1**); assert rather than print the post-push ref comparison (**F4**); and fill the `<repository-url>`
placeholder and `git clone` line once the real URL exists (**F3**, **C1**).

Per instruction, this audit did not edit `ROADMAP.md` or `STATE.md`, created no remote, repository, or other
resource, pushed nothing, and rewrote no history. All mutation testing was confined to a throwaway clone in
a scratch directory. It wrote `.planning/TRACEABILITY.md` and this section only, and committed nothing.

---

## Audit: v0.1.1 Public GitHub Readiness — 2026-07-21 (post-remediation re-audit at `2cfa7cd`)

Auditor: Claude Opus 4.8 (`claude-opus-4-8`, 1M context) via Claude Code — independent re-audit of the
committed tree after the F2 condition and the F1/N1 recommendations were addressed. Supersedes nothing; the
`5c31f27` entry above stands as the record of that commit.
Scope: v0.1.1 Public GitHub Readiness — public-safety audit, GitHub CI, security/contribution policy, and
publication handoff (REQ-010..REQ-013).
Files reviewed: since `v0.1.0` (`a71831f`) — **14 files changed, 1399 insertions(+), 90 deletions(-)**.
Since the previous audited commit `5c31f27` — **5 files changed, 490 insertions(+), 111 deletions(-)**
(`.planning/AUDIT.md`, `.planning/STATE.md`, `.planning/TRACEABILITY.md`, `docs/PUBLICATION.md`,
`scripts/check_public_readiness.py`). Only two of those are non-planning files, and both are small: a
5-line documentation change and an 11-line change to the gate script. Under the 50-file single-pass limit.

Method: no claim in this section is inherited from a prior audit section or from `TRACEABILITY.md`. The
discharged condition was tested by **copying the two commands out of `docs/PUBLICATION.md` and running them
verbatim**, not by reading whether the sentence looked better. The hardened link check was
**mutation-probed across 29 cases in a throwaway `git clone --no-hardlinks` of `2cfa7cd`**, never in the
working repository, with the clone reset between cases and verified clean at the end. Security substance was
re-derived from scratch: Gitleaks over both full history and the materialized public tree, an independent
credential-shape grep across every reachable commit, a targeted search for 25 real private strings, the
frozen-export dependency audit, live GitHub-API resolution of both action pins, `zizmor --persona=auditor`
offline and online, and both CI matrix legs end to end. Nothing was committed, pushed, or created.

`.planning/config.json` carries a populated `close_out_auditor` key — no WARN.

`make ci` this session: black clean (**16** files), ruff clean, mypy clean (15 source files),
`pytest -n auto` → **39 passed**, `public-check` → _Public readiness checks passed (45 tracked files)_.

### Prior conditions on close — status

| ID             | Condition from the `5c31f27` audit                                                                                | Status this pass                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| -------------- | ----------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **F2**/**E3**  | Record the explicit `pip-audit --strict -r` form against a frozen export in `docs/PUBLICATION.md`'s evidence list | **FIXED & verified by execution.** `docs/PUBLICATION.md:74` now reads `uv export --frozen --all-groups --no-emit-project -o /tmp/nbscribe-requirements.txt` followed by `uvx pip-audit --strict -r /tmp/nbscribe-requirements.txt`. Both were copied out of the document and run exactly as written: the export produced a **505-line** requirements file and the audit reported _No known vulnerabilities found_. This is the point that mattered — the recorded step now consumes an explicit locked input and can therefore fail. Three consecutive audits found a static sentence in this document out of step with what it claimed; this pass found none                                                         |
| **F1**/**OP1** | State in the pre-publication decisions that `.planning/` publishes in full                                        | **FIXED.** A new numbered item 4, "Planning evidence", states that the complete tracked `.planning/` directory is part of the public tree — including decision, audit, and traceability history — and instructs the operator to review it as public project documentation rather than as local agent state. Verified against reality: `git ls-files .planning` returns 9 tracked files and all 9 materialize in `git archive HEAD`, so the sentence describes what actually publishes. Standing since two audits ago; now closed                                                                                                                                                                                      |
| **N1**         | Test link targets for membership in the tracked set rather than filesystem existence (recommended, not blocking)  | **DONE, and probe-proven.** `_broken_local_links` now resolves each target, rejects anything outside the repository root via `relative_to`, and requires the resulting path to be a tracked file or the prefix of a tracked directory. All four rejection classes the request named were driven to failure in the scratch clone — missing, outside-root, ignored-or-untracked file, untracked directory — and all six acceptance classes pass: tracked file, tracked file with fragment, tracked directory with and without a trailing slash, nested tracked file, and `https://`/anchor/`mailto:` links. The error message was updated in step, and `docs/PUBLICATION.md:78` was updated to match. See Test Coverage |
| **N4**         | Fence-aware link scanning                                                                                         | **Not done; unchanged and still a warning.** Re-probed: inline-link syntax inside a fenced code block still fails the gate. No unintended instance exists at `HEAD`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **N2**         | Add `scripts` to `mypy`'s `files`                                                                                 | **Not done.** `pyproject.toml:56` still pins `files = ["src", "tests"]`. Pointed at explicitly, `mypy --strict scripts/check_public_readiness.py` passes cleanly today — including the new code — so the gap is that nothing keeps it that way                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| **N3**/**N6**  | Bound the gate script's non-Git and missing-`DESIGN.md` failures                                                  | **Not done.** Re-probed: both still raise an uncaught traceback. Both still exit **1**, so `make ci` fails correctly in each case; the defect remains operability, not correctness                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **F4**         | Assert rather than print the post-push ref comparison                                                             | **Not done.** `docs/PUBLICATION.md:58-61` still emits SHAs for the reader to compare by eye                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| **F3**/**C1**  | Fill the `<repository-url>` placeholder and the missing `git clone` line                                          | **Carried, unchanged and correctly deferred.** `README.md:26-29` still opens with `uv tool install .` with no preceding clone; `CONTRIBUTING.md:10` still has the literal placeholder (prior sections cited this as `:11`; the correct line is 10). Both are blocked on a URL that by design does not exist yet                                                                                                                                                                                                                                                                                                                                                                                                       |
| **E5**         | Prior historical `AUDIT.md` contradiction (info; no edit expected)                                                | **Resolved as expected.** No edit was made to any historical section, which is correct — dated audit records are historical documents                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |

### Correctness

- [info] **F6 — the documented dependency-audit chain now works verbatim, which is the whole point of the
  fix.** Not asserted from the diff: the two commands at `docs/PUBLICATION.md:74` were extracted from the
  document and executed as written in a shell that had no prior requirements file. `uv export --frozen
--all-groups --no-emit-project` emitted 505 lines, and `uvx pip-audit --strict -r` against that file
  returned _No known vulnerabilities found_. The `--frozen` flag means a lockfile drift would abort rather
  than silently re-resolve, `--all-groups` covers the dev tree that `make ci` actually installs, and
  `--no-emit-project` keeps the unpublished local package out of the audit input. The previous form could
  not fail; this one can, and its failure modes are the right ones.

- [info] **F7 — the tracked-ness rewrite is correct on the boundary cases, not just the happy path.** Read
  after probing, to explain the probe results rather than to substitute for them. `relative_to(ROOT)` raising
  `ValueError` is what catches absolute and above-root targets, and the empty-string sentinel it sets is then
  rejected by an explicit `not published_path` test rather than by accident — worth noting because
  `"".startswith` logic elsewhere in the expression would have silently passed. The directory case is handled
  by prefix match against the tracked set, which is why a link to a tracked directory passes and a link to an
  untracked one does not. `.resolve()` follows symlinks, so the tracked `AGENTS.md` symlink resolves to
  tracked `CLAUDE.md` and passes; a symlink escaping the repository would be caught by the same `ValueError`
  path. `candidate.exists()` is retained on top of tracked-ness, so a tracked-but-deleted file still fails —
  the check is now the conjunction of both properties, which is strictly stronger than either.

- [info] **F5 — `CONTRIBUTING.md` describes a `make ci` that is one step out of date.** New this pass.
  `CONTRIBUTING.md:16` reads "It checks formatting, lint, strict typing, and the parallel test suite" —
  accurate before `5c31f27` and incomplete since, because `make ci` now also runs the public-readiness gate.
  A contributor whose PR fails on a broken link or an accidentally tracked artifact will get an error from a
  step the contributing guide never mentions. One clause. Recorded rather than made a condition because the
  gate itself is correct, self-describing in its error text, and named by `docs/PUBLICATION.md:78`; the
  omission costs a contributor confusion, not safety.

- [info] **F4 — the handoff's ref-verification commands still print rather than assert.** Verbatim carry.
  `docs/PUBLICATION.md:58-61` verifies the push with `git rev-parse main github/main` and
  `git rev-parse v0.1.0 github/v0.1.0^{}`, which emit two SHAs each and leave the comparison to the reader's
  eye, while the preceding block sets the better precedent with a real `test -z` assertion. Cosmetic; noted
  because the same document already demonstrates the better pattern one section earlier.

- [info] **F3 — README's install path still assumes a clone it never instructs.** Verbatim carry of **C1**.
  Re-confirmed at `README.md:26-29` and `CONTRIBUTING.md:10`. Correctly deferred to the URL-fill patch.

### Safety

- [info] **G1 — no secret, credential, or private-infrastructure disclosure. Re-derived, not re-read.**
  Gitleaks 8.30.1 over `--log-opts="--all"`: **8 commits, 492.75 KB, no leaks** — now including `2cfa7cd`.
  Gitleaks over the materialized public tree (44 regular files + the `AGENTS.md` symlink): 396.81 KB, no
  leaks. Neither result is suppressed: no `.gitleaksignore`, `gitleaks.toml`, `.gitleaks.toml`, or
  `.secretsignore` exists in the working tree or anywhere in `git ls-files`. An independent `git grep -E`
  across every reachable commit for GitHub token prefixes, `github_pat_`, `AKIA[0-9A-Z]{16}`, PEM
  private-key headers, `Bearer <20+>`, and `Token <hex40>` returned **zero matches** — note this is one
  fewer class of result than the prior pass, which matched audit prose enumerating the patterns; the current
  regex is anchored on the token bodies, so even the prose does not match. A full-history grep for RFC1918
  and `172.16/12` address literals returned **0 matches across all 8 commits**.
  The decisive check is again the targeted one, not the scanner: 25 candidate private strings pulled
  programmatically from `.env` and the live untracked dogfood snapshot — the `NETBOX_URL`, its host literal,
  the 40-character `NETBOX_TOKEN`, every real device name — were searched against the full public-tree corpus
  (395,691 chars) and against `git log --all -p` (7,693 lines / 645,881 chars), with values compared in
  memory and never printed. Exactly **4** matched, all generic vendor/role vocabulary: `Router`, `Switch`,
  `Server`, `Ruckus`. **The token, the URL, and the host literal matched nothing in either corpus.**

- [info] **G2 — the obsolete profile path is where the corrected §1 says it is.** Per-commit count of the
  literal in `DESIGN.md`, re-derived across all eight commits: `217d2b0` 2, `1e07d2a` 2, `4b4e41e` 2,
  `2332025` 2, `a71831f` 2, `3318077` **0**, `5c31f27` **0**, `2cfa7cd` **0**. At `HEAD`, `git grep -c`
  across the whole tree finds the literal in exactly one file, `.planning/AUDIT.md` (5 occurrences), all
  inside sections analyzing the disclosure; `TRACEABILITY.md` carries only the redacted form, and this
  section adds no new occurrence. On merits it remains what three prior passes judged it: a local username
  and a dotfile name — no host, no address, no credential.

- [info] **G3 — ignore rules demonstrated, not assumed.** `git ls-files -i -c --exclude-standard` is empty.
  `git ls-files --others --exclude-standard` returns **0**, so the tracked set and the working set agree
  exactly and nothing is sitting untracked waiting to be swept in. `git check-ignore -v` attributes each
  sensitive path to a specific rule: `.env`→`.gitignore:15`, `dist`→`:11`, `snapshot`→`:19`,
  `.planning/.close-out-auditor.log`→`:20`. Live `snapshot/` artifacts and `.env` are all mode `0600` and
  untracked. The publishable set is **45 paths, unchanged from the prior pass** — this commit added no files.

- [info] **G4 — the mechanical gate got strictly stronger without losing anything.** The four properties it
  enforced at `5c31f27` all still fire, re-probed individually this pass: required artifacts must stay
  tracked, `.env`/`dist/`/`snapshot/`/the close-out log must stay untracked, `DESIGN.md` must stay free of
  local profile paths, and local links must resolve. The fourth is now the stronger property: a link must
  resolve **into the published tree**, not merely onto the developer's disk. That closes the one gap where
  the gate could be green locally and 404 for every public reader.

- [info] **G5 — the approval gate remains procedural, not technical.** Unchanged and worth restating because
  it is why document accuracy is the real control here. The local `gh` CLI is authenticated as `kevinb361`
  with a token carrying `repo` and `workflow` scopes; nothing in this environment technically prevents an
  agent or script with shell access from creating the repository and pushing. The controls that exist are the
  operator's reading of `docs/PUBLICATION.md` and the absence of a GitHub remote.

- [info] **G6 — the private mirror is now three commits behind local `main`.** `refs/remotes/origin/main` is
  `a71831f` (= `v0.1.0`) while `refs/heads/main` is `2cfa7cd`; none of `3318077`, `5c31f27`, or `2cfa7cd`
  has been pushed to Gitea. Correct for an audit told to push nothing, and harmless for the documented
  procedure, which mirrors from this working clone. It matters in exactly one scenario, now one commit worse
  than last pass: mirroring to GitHub _from the Gitea copy_ would publish the `a71831f` tree — no CI, no
  `SECURITY.md`, no `CONTRIBUTING.md`, no gate script, and a `DESIGN.md` still carrying the obsolete path.
  Worth one line in the handoff if that path is ever considered.

- [info] **G7 — `AGENTS.md` publishes as a symlink to `CLAUDE.md`.** Tracked as mode `120000` and
  materialized as a symlink by `git archive`. GitHub renders it as a link rather than following it. Harmless,
  but it means `CLAUDE.md` — the project's internal agent instructions — is unavoidably part of the published
  surface. Re-verified public-safe this pass: no IPs, hostnames, employer names, or credentials.

### Test Coverage

- [info] **H1 — the N1 fix was proven by mutation across every class the remediation claimed.** 29 probes in
  a throwaway clone of `2cfa7cd`, each applied and reverted, with the clone verified clean at the end.
  **Rejections, all confirmed:** a missing target; an absolute path outside the repository that _does_ exist
  on the runner (`/etc/hostname` — the exact case the prior audit flagged); a relative target above the
  repository root; a gitignored file present on the developer's disk (`snapshot/inventory/devices.yaml`, the
  other flagged case); an untracked but non-ignored file present on disk; an untracked directory; and a
  gitignored directory. **Acceptances, all confirmed:** a tracked file; a tracked file with a `#fragment`;
  a tracked directory with and without a trailing slash; a nested tracked file; a tracked file reached by
  parent traversal from a subdirectory; the tracked `AGENTS.md` symlink; and `https://`, anchor-only, and
  `mailto:` links. The other three rules were re-probed independently and still fire: untracking
  `SECURITY.md` or `LICENSE`, force-adding `.env`, and appending a local profile path to `DESIGN.md` each
  fail with a specific message and exit 1.

- [info] **H2 — valid links are not masked, and findings do not short-circuit.** Six valid link forms
  (tracked file, anchor, `https://`, `mailto:`, tracked directory, and a tracked file with a fragment) added
  alongside a single broken link produced a finding for **the broken one only** — no false positive on any
  valid form under the new stricter rule, which is the specific regression risk a tracked-ness check
  introduces. Separately, violating four rule classes simultaneously (untracked `LICENSE`, tracked `.env`,
  `DESIGN.md` path, plus broken and ignored-target links) reported **six findings spanning all four classes
  in one run** before exiting 1: `findings` accumulates and prints in full, so a first failure never hides
  the rest.

- [info] **H5 — the independent link walk agrees with the gate.** Run separately from the checker and
  covering forms it does not parse — inline, reference-style, image, and raw-HTML. Eight candidate local
  targets exist in the tracked tree; **seven are real links and every one resolves to a tracked path**. The
  eighth is the string inside a backtick code span in this file's own **N5** finding — prose describing the
  raw-HTML parser gap, not a link. So the one apparent discrepancy between the two methods is an artifact of
  the audit documenting itself, not a defect.

- [warning] **N4 — Markdown links inside fenced code blocks are still checked as if they were real.**
  Unchanged from the prior pass and re-probed this session: a fenced inline-link pair still fails the gate.
  The regex is applied to raw file text with no fence awareness, so an inline link written as an _example_
  is resolved as a _reference_. The prior audit reproduced this accidentally while drafting the finding
  itself. The workaround remains writing example targets inside angle brackets, which the checker skips. No
  unintended instance exists in the tracked tree at `HEAD`. Kept at warning because the tree is
  documentation-heavy, `.planning/` is walked in full, and the failure mode is a build break on prose rather
  than on code — but note it fails **closed**, so it costs a false alarm, never a missed leak.

- [info] **N7 — a link to the repository root itself is now rejected.** New this pass, and a direct
  consequence of the N1 fix rather than a pre-existing gap: a target resolving to the repository root yields
  the path `.`, which is neither a tracked path nor a prefix of one, so it is reported as broken. A
  contributor writing a link to the repository root from inside `docs/` would hit it, and that link would in
  fact work on GitHub. No instance exists at `HEAD`; links to tracked _subdirectories_ are unaffected and
  were probe-confirmed to pass. Trivially fixable by treating an empty or `.` published path as tracked.
  Recorded so the new boundary is documented rather than discovered later.

- [info] **N2 — `scripts/` still sits outside `mypy`'s configured scope.** `pyproject.toml:56` pins
  `files = ["src", "tests"]`, so `make type` reports 15 source files and never sees the gate script even
  though `make ci` executes it. Pointed at explicitly, `mypy --strict scripts/check_public_readiness.py`
  passes cleanly today, including the new `relative_to`/prefix logic — so the code is fine and the gap is
  that nothing keeps it that way. This is the change that most deserved the type check, and it got it only
  because an auditor ran it by hand. One-word fix.

- [info] **N3/N6 — the gate script still raises uncaught tracebacks in two bounded situations.** Re-probed:
  run inside the materialized `git archive` tree — i.e. a source tarball, which is how an sdist consumer
  receives this project — `subprocess.run(..., check=True)` raises `CalledProcessError`; with `DESIGN.md`
  absent, the unconditional read raises `FileNotFoundError`. Both **exit 1**, so `make ci` fails correctly in
  each case and neither is a correctness or safety defect. The rest of this codebase is unusually disciplined
  about bounded operator errors, so the gate script remains the one file not following the project's own
  convention.

- [info] **N5 — reference-style and raw-HTML links are still not parsed.** Re-probed and unchanged. A
  reasonable scope choice for a 79-line script, and the independent walk in **H5** covered all three forms
  and found nothing. Recorded so the coverage boundary stays documented rather than assumed.

- [info] **H3 — the pre-existing public-safety tests still run in the gate on both legs.**
  `tests/test_examples.py::test_public_docs_and_examples_contain_no_private_networks_or_credentials` and
  `test_synthetic_example_outputs_match_production_export` both execute under `pytest -n auto` on 3.11 and
  3.12, so the docs/examples invariant and the committed-example byte contract regress loudly. The checker
  complements these rather than duplicating them — it guards tracked-ness and links, they guard content.

- [info] **H4 — the gate script still has no unit tests, and this change was the moment to add them.** The
  prior pass predicted that if N1 got fixed, that edit would be the natural moment to add three or four
  cases. N1 was fixed and no cases were added, so the new tracked-ness logic — the most intricate code in the
  file, with a `try`/`except` and a prefix match — has a regression net that lives in a scratch directory and
  in this document rather than in `tests/`. Still defensible at 79 lines, and the 29 probes substitute for it
  today. Recorded as the standing follow-up it now demonstrably is.

### Architecture Fit

- [info] **AR1 — the workflow re-audited clean, and both pins are still current.** SHAs re-resolved against
  the live GitHub API rather than eyeballed: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` →
  `refs/tags/v7.0.1` exactly, still the latest release (published 2026-07-20);
  `astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9` → `refs/tags/v9.0.0` exactly, still the
  latest (published 2026-07-21). Parsed under `yaml.safe_load` rather than skimmed: top-level
  `permissions: contents: read`, no job-level widening, no `pull_request_target`, no `secrets` reference,
  `persist-credentials: false`, `concurrency` with `cancel-in-progress`, `timeout-minutes: 10`,
  `UV_FROZEN: "1"`, `uv sync --frozen --dev`. `zizmor 1.28.0 --persona=auditor` → **no findings**, run twice:
  once offline and once **online with a GitHub token**, which enables audits offline mode silently skips.
  `yamllint -d relaxed` → one 82-char line at `ci.yml:36`, nothing else. The workflow is untouched by this
  commit and remains the strongest artifact in the milestone.

- [info] **AR2 — `public-check` is wired at the right level, and the hardened rule inherits that.** It is a
  `make ci` prerequisite rather than a separate CI step, so the stricter link rule runs identically in the
  local gate and on both GitHub matrix legs with no second place to keep in sync. Both legs were reproduced
  this session: **3.11.14 → 39 passed**, gate clean, 45 tracked files; **3.12.3 → 39 passed**, gate clean,
  45 tracked files, executed inside an isolated clone containing no `.env`, no `snapshot/`, no `dist/`, and
  no caches. The 3.12 run doubles as a self-sufficiency proof — the published tree builds, type-checks,
  tests, and self-audits alone — and as a check that the new tracked-ness rule does not depend on developer
  working-tree state, since that clone has none.

- [info] **AR3 — job names and branch protection still agree.** `name: Python ${{ matrix.python-version }}`
  renders `Python 3.11` and `Python 3.12`, verbatim the required checks named in `docs/PUBLICATION.md`.

- [info] **AR4 — dependency licensing re-checked and clean for MIT redistribution.** Runtime set enumerated
  from a `--no-dev` frozen export (13 distributions): httpx, httpcore, idna BSD-3-Clause; jsonschema, PyYAML,
  h11, anyio, attrs, referencing, rpds-py, jsonschema-specifications MIT; typing-extensions PSF-2.0; certifi
  MPL-2.0. Dev-only additions carry MIT/BSD/Apache-2.0 plus `pathspec` (MPL-2.0, a `black` dependency).
  Neither MPL-2.0 package is vendored or modified, so no source-disclosure obligation attaches.

- [info] **AR5 — the `.planning/`-publishes decision is now recorded where an operator will read it.** The
  new §4 sits in the numbered pre-publication decision list beside history identity, project name, and
  package reservation — i.e. among the items the document already tells the operator they must explicitly
  resolve — rather than buried in the evidence list at the end. For a pre-alpha tool the transparency is
  defensible and arguably an asset; the point of the finding was always that it should be a decision rather
  than a side effect of what happens to be tracked, and it now is.

### Operability

- [info] **OP-A — this audit's own outputs leave the tree dirty, by design.** Writing
  `.planning/TRACEABILITY.md` and this section makes `git status --porcelain` non-empty, so
  `docs/PUBLICATION.md`'s clean-tree precondition will fail until these records are committed. That is the
  precondition working, not a defect — but it means the publication sequence is: commit these audit records,
  then publish. The audit that verifies a commit cannot be inside it. Per instruction, nothing was committed.

- [info] **OP-B — the clean-tree check remains correctly absent from the mechanical gate.** Unchanged
  judgment: every developer run and every CI run on a PR branch would fail if it were there. The clean-tree
  assertion belongs where it already lives — inside the publication command block, as a real `test -z` that
  exits non-zero at the moment it matters. The gate checks the four properties that are true at all times;
  the handoff checks the one that is only true at publish time.

- [info] **OP-C — the approval gate holds, verified read-only.** `git remote -v` → one remote,
  `origin → gitea:kevin/netbox-scribe.git` (private self-hosted Gitea over SSH). `git for-each-ref` → exactly
  three refs: `refs/heads/main 2cfa7cd`, `refs/remotes/origin/main a71831f`, `refs/tags/v0.1.0 dd5f4c5`
  (annotated, → `a71831f`). `gh api repos/kevinb361/netbox-scribe` → **HTTP 404**, as do
  `kevin-blalock/netbox-scribe` and `kevinblalock/netbox-scribe`. `gh search repos "netbox-scribe"` → **0
  results**; the broader `netbox scribe` → **0 results**; both sanity-checked against `gh search repos
"netbox"`, which returns the expected upstream projects, so the empty results are real rather than a silently
  failing command. PyPI `netbox-scribe` → **HTTP 404**, still unclaimed. No GitHub repository, no GitHub
  remote, no public ref, nothing pushed anywhere — including to Gitea.

### ASSERTED Items from TRACEABILITY.md

- None. This session's `/saga-verify` pass classifies all 13 requirements **PROVEN**, with v0.1.1's four at
  **PROVEN 4 · ASSERTED 0 · OPEN 0 · WAIVED 0**. Every v0.1.1 evidence artifact was re-executed against the
  committed tree at `2cfa7cd`.

### Release-blocking vs. optional

**Release-blocking correctness or security findings: 0.** Nothing found this pass makes the tree at
`2cfa7cd` unsafe or incorrect to publish. The secret, privacy, dependency, license, workflow-security, and
approval-gate substance was re-derived independently and is clean.

**Conditions on close: 0.** The prior pass's single condition (**F2**) is discharged and was verified by
executing the documented commands rather than by reading the sentence. Both standing recommendations that
carried real value — **F1**/**OP1** and **N1** — were also done, and N1 was verified by 29 mutation probes
covering every rejection and acceptance class.

**Optional follow-ups, none blocking:** **N4** (fence-aware link scanning — the only warning, and it fails
closed), **N2** (mypy scope, most relevant now that untested-by-mypy logic just changed), **H4** (unit tests
for the gate script), **N7** (accept a link to the repository root), **N3**/**N6** (bounded errors in the
gate script), **F5** (`CONTRIBUTING.md`'s `make ci` description), **F4** (assert rather than print the ref
comparison), **N5** (documented coverage boundary), **F3**/**C1** (URL fill, blocked on a URL that does not
exist yet), **G6** (a line about never mirroring from Gitea).

No finding in this section is stylistic, and none rests on this document's own self-reference. Formatting,
prose quality, and structural preferences were deliberately not raised.

### Verdict

**PASS**

- Critical findings: **0**
- Release-blocking findings: **0**
- Conditions on close: **0**
- Warnings: **1** (N4)
- Info: **24** (F3–F7, G1–G7, H1–H5, N2, N3, N5, N6, N7, AR1–AR5, OP-A–OP-C)

Active counts — Warnings 1 · Info 24 · Conditions on close 0 · Release-blocking 0.

Rationale: the one condition held over from the previous pass is discharged, and it was tested the way a
condition about a procedure should be tested. `docs/PUBLICATION.md` no longer records a dependency audit that
cannot fail; it records `uv export --frozen --all-groups --no-emit-project` followed by
`pip-audit --strict -r` against that file, and those two commands were lifted out of the document and run
verbatim — 505 lines exported, no known vulnerabilities. `--frozen` aborts on lockfile drift, `--all-groups`
covers the tree `make ci` installs, `--no-emit-project` keeps the unpublished local package out of the input.
That is a verification step. Three consecutive audits found a stale or unfalsifiable sentence in this
document; this pass found none.

The two recommendations that carried real value were done as well. `.planning/` publishing in full is now a
numbered pre-publication decision beside history identity and package reservation, rather than a side effect
of what happens to be tracked — verified against reality, since all 9 tracked planning files materialize in
`git archive HEAD`. And the link check now asks whether a target exists in the **published tree** rather than
on the runner's disk. That was the last place the gate could be green locally and 404 for every public
reader, and it was closed by mutation-proof rather than by inspection: 29 probes in a throwaway clone, all
four rejection classes confirmed — missing, outside-root, ignored-or-untracked file, untracked directory —
and all acceptance classes confirmed, including tracked directories with and without trailing slashes, nested
files, parent traversal, the `AGENTS.md` symlink, and `https://`/anchor/`mailto:` forms. The regression risk
a stricter rule introduces was probed directly: six valid link forms beside one broken link produced exactly
one finding, and four simultaneous rule violations produced six findings in a single run with no
short-circuit. An independent walk over inline, reference-style, image, and raw-HTML forms agrees with the
gate on every real link in the tree.

The security substance was re-derived, not re-read. Eight commits and the 44-file materialized public tree
are Gitleaks-clean with no suppression file anywhere; a credential-shape grep across every commit returns
zero matches; RFC1918 literals are absent from all eight commits; and the check that actually decides it — 25
real private strings from `.env` and the live snapshot searched against both the whole public corpus and the
full patch history — matched exactly four times, all on the generic words `Router`, `Switch`, `Server`, and
`Ruckus`. The token, the URL, and the host matched nothing. The obsolete profile path is present twice in
`DESIGN.md` in exactly the five commits through `v0.1.0` and zero times in the last three, surviving at
`HEAD` only as quoted text in this file — which is what §1 says. Dependencies audit clean against the
explicit 505-line frozen export, licensing compatible with MIT redistribution, both action pins re-resolved
byte-for-byte against the live GitHub API and both still current, zizmor clean at its strictest persona both
offline and online, `yamllint` clean but for one long line, and both matrix legs green at 39 passed with the
3.12 leg executed inside an isolated clone containing none of the developer's working state. The approval
gate holds absolutely: one private Gitea remote, three refs, no GitHub repository under any plausible owner,
zero global search hits against a search sanity-checked to be working, PyPI unclaimed, nothing pushed
anywhere.

What remains is a short list of things that are worth doing and block nothing. The only warning is **N4**,
and it fails closed — inline-link syntax inside a fenced code block trips the gate, which costs a false alarm
on prose and can never cost a missed leak. **N2** is more interesting than its size: the one file whose logic
just changed is the one file `mypy` is not configured to see, and it passes only because an auditor pointed
`mypy --strict` at it by hand. **H4** is the same observation from the test side — the previous pass predicted
that fixing N1 would be the moment to add unit cases for the gate script, N1 was fixed, and the cases still
live in a scratch directory and in this document. **N7** is new and is a consequence of the fix rather than a
pre-existing gap: a link to the repository root is now rejected, which no current file does and which is a
one-line accommodation. None of these affects whether this tree is safe or correct to publish.

The milestone's deliverable is a correct publication procedure whose only enforcement is an operator
following the document and a gate that runs on every commit. Both now hold up under execution rather than
under reading.

Conditions on close: none.

Recommended, not blocking: make the link scanner fence-aware (**N4**); add `scripts` to `mypy`'s `files`
(**N2**); add unit cases for the gate script's tracked-ness logic (**H4**); accept a link to the repository
root (**N7**); bound the gate script's non-Git and missing-`DESIGN.md` failures (**N3**, **N6**); mention the
public-readiness step in `CONTRIBUTING.md`'s `make ci` description (**F5**); assert rather than print the
post-push ref comparison (**F4**); and fill the `<repository-url>` placeholder and `git clone` line once the
real URL exists (**F3**, **C1**).

Per instruction, this audit did not edit `ROADMAP.md` or `STATE.md`, created no remote, repository, or other
resource, pushed nothing, and rewrote no history. All mutation testing was confined to a throwaway clone in
a scratch directory. It wrote `.planning/TRACEABILITY.md` and this section only, and committed nothing.

---

## Audit: v0.2 Network Relationships — 2026-07-21 (independent frontier close-out)

> **Superseded** by the post-remediation re-audit at the end of this file. Critical finding C1 below has since
> been fixed and independently re-verified; its ASSERTED classification of REQ-019 no longer holds. Retained
> for the finding history (W1–W10, I1–I6 are carried forward and re-checked in the newer entry).

Auditor: Claude Opus 4.8 (`claude-opus-4-8`, 1M context) via Claude Code — independent frontier review of
work executed locally by a deep model. `.planning/config.json` carries a populated `close_out_auditor`
(`claude -p --allowedTools Read,Grep,Glob,Bash,Write,Edit --permission-mode acceptEdits`), so no
frontier-verify-gate warning applies to this project.

Scope: v0.2 Network Relationships — opt-in device → interface → assigned-IP tracer in one deterministic,
validated, atomic, redacted network document (REQ-014..REQ-019).

Files reviewed: 13 files changed, 585 insertions(+), 41 deletions(-) against `c70a628` (`git diff --shortstat`),
plus 6 untracked new files not counted by that diff: `src/netbox_scribe/schemas/v1/network.schema.json`,
`tests/test_network_exporter.py`, `examples/netbox-interfaces-page.json`,
`examples/netbox-ip-addresses-page.json`, `examples/output/inventory/network.yaml`,
`examples/output/agent/NETWORK.md`. Effective review surface: 19 files.

Method: nothing was accepted from a checkbox or from a requirement's own `evidence:` note. Three probe suites
(A: retrieval/publication edges; B: 26-check CLI end-to-end against a loopback HTTP NetBox stub; C: 19
relationship-integrity record shapes) were written to `/tmp` and executed against the working tree. `make ci`
→ **48 passed**, all gates clean. A wheel was built and installed into a clean Python 3.11 venv to verify
schema packaging and validation outside the source tree. No live NetBox was contacted; no GitHub resource was
touched; `ROADMAP.md` and `STATE.md` were not edited; nothing was committed.

### Correctness

- **[critical] C1 — the operator's device redaction policy is silently discarded in the network view:**
  `src/netbox_scribe/exporter.py:124` hardcodes `_normalize_device(device, ExportPolicy())`, and
  `src/netbox_scribe/cli.py:163` forwards only `network_policy` to `export_network()`. The `ExportPolicy`
  built from `--include-field` / `--exclude-field` / `--include-custom-field` / `--exclude-custom-field` at
  `cli.py:88-95` is constructed, validated (unknown names still correctly rejected with exit 2), and then
  dropped for `--view network`.

  Probe B, verbatim: `nbscribe export --view network --exclude-field serial` exited **0** and the resulting
  `network.yaml` still contained `serial: DEVICE-SERIAL-SHOULD-BE-DENIABLE`. `--include-custom-field
support_contract` exited 0 and emitted no device custom fields. Both flags are accepted and neither has any
  effect. There is no warning, no error, and no note in `README.md`.

  This violates `.planning/SPEC.md:270` — "The system SHALL apply explicit field and custom-field policy
  independently to **devices**, interfaces, and IP addresses" — and REQ-019's own "denied values … never enter
  published artifacts". Blast radius: every optional device field an operator explicitly denies (`serial`,
  `asset_tag`, `description`, `primary_ip4`, `primary_ip6`, `site`, `rack`, `tenant`, `platform`, `tags`)
  reaches a Git-committed, RAG-ingested artifact anyway. Mitigating: device **custom** fields remain
  closed-by-default, so no custom-field value leaks; the exposure is limited to standard fields the operator
  asked to withhold. It is still a silent redaction bypass in a tool whose stated purpose is publishing
  infrastructure context to Git and agents, and silence is what makes it critical rather than a warning.

  Fix: give `render_network_yaml` a device-policy parameter, thread it from `export_network` and `cli.py`,
  and add a CLI test asserting the denied value is absent from `network.yaml`. Roughly five lines plus a test.

- **[warning] W1 — documented scope filtering is delegated to the server and is actually a hard abort:**
  `README.md:127` states "The network view excludes unassigned and VM-assigned addresses", and `SPEC.md`
  scenario `relationship-scope` says only device-assigned addresses "enter `network.yaml`". The implementation
  does not filter: `client.py:83-85` appends `?assigned_object_type=dcim.interface` and trusts NetBox to
  honour it; if any non-`dcim.interface` record comes back, `exporter.py:351-352` raises and the **entire**
  export fails. Probe C confirmed the abort. On a NetBox version or proxy that ignores the parameter the
  operator gets a total export failure where the documentation promised an exclusion. Either filter
  client-side and document it, or change the wording to "requests only device-assigned addresses and rejects
  anything else".

- **[info] I1 — freshness is a lexical string maximum:** `exporter.py:110-116` takes `max()` over raw
  `last_updated` strings across all three collections. Mixed offsets or formats sort incorrectly. Consistent
  with the pre-existing device index, so not a regression, but the network view now mixes three resources
  whose timestamp formats are not guaranteed to agree.

### Safety

- **[warning] W2 — pagination is bounded against loops but not against length:** `client.py:88-111` rejects a
  repeated URL and a cross-origin `next`, but has no page cap, no record cap and no elapsed-time cap. Probe A
  fed distinct `next` URLs and the client followed **5001 pages and accumulated 5000 records without
  stopping**; `seen_urls` also grows one `httpx.URL` per page. A misbehaving, compromised or simply
  pathological NetBox drives unbounded memory and runtime. Pre-existing from v0.1, but REQ-014 now applies the
  same loop to three endpoints instead of one, so the exposure tripled inside this milestone. A
  `max_pages` guard with a clear `NetBoxResponseError` is cheap.

- **[warning] W4 — "atomic pair" is in-process only, and the rename is not durable:**
  `exporter.py:151-168` fsyncs the temporary file but never fsyncs the parent directory after `os.replace`,
  so the rename itself can be lost on power failure. `exporter.py:171-193` publishes the index first and the
  canonical second with no journal, marker or generation stamp, and rolls back only on `OSError`. A `SIGKILL`,
  OOM kill or power loss between the two `os.replace` calls leaves a new index paired with an old canonical
  **permanently and undetectably** — nothing in the artifacts records which generation each file belongs to.
  REQ-017's "a failure preserves the complete prior pair" holds for in-process `OSError` and for the
  integrity-abort path (both verified), not for process death. Worth stating explicitly in `README.md` at
  minimum; decision 0003's override path already contemplates generation stamps if this matters later.

- **[info] I2 — index injection is handled:** Probe C fed NetBox-controlled names containing embedded newlines
  and backticks through `render_network_index`. `agent_index.py:98-101` collapses newlines and switches to a
  double-backtick delimiter, so a hostile interface name cannot forge index bullets. Called out because it is
  the kind of thing that is usually missing and is not mentioned in the requirement evidence.

### Test Coverage

- **[warning] W3 — REQ-014's headline claim ("retrieves every page") has no regression test on the two new
  endpoints:** `tests/test_client.py::test_list_network_records_retrieves_each_relationship_resource` returns
  `"next": None` for all three resources; `tests/test_cli.py::test_network_view_fetches_relationships_…` is
  single-page too. Multi-page interface and IP retrieval is proven only by this audit's Probe A. The behavior
  is correct today because `_list_records` is shared with the device path, but nothing in the suite would
  catch a future per-resource retrieval change that breaks paging for interfaces or addresses.

- **[warning] W5 — same-origin and loop guards are untested on the relationship endpoints:** every hostile
  pagination test in `tests/test_client.py` targets `api/dcim/devices/`. REQ-014 explicitly claims the
  controls apply "to every resource" and `SPEC.md:201` repeats it. Probe A verified it; the suite does not.

- **[warning] W6 — the two rollback edge cases deferred from the v0.1 audit into v0.2 are still untested:**
  `STATE.md` "Deferred" carries "test rollback double-fault/no-prior-index" as a v0.2 follow-up. Neither
  exists in `tests/`. Probe A verified both behave correctly — first-run failure leaves no orphan index and no
  canonical; the double fault raises `canonical publication failed and the prior agent index could not be
restored` and preserves the prior canonical. So this is a discharge-of-commitment gap, not a defect: the
  code is right, the guard is missing.

- **[warning] W7 — no test covers a server that ignores the assignment filter:** see W1. No fixture returns an
  unassigned or `virtualization.vminterface` address from the client layer, so the documented scope guarantee
  is unexercised end to end.

- **[info] I3 — where coverage is genuinely strong:** relationship integrity is the best-tested part of this
  milestone. Probe C's 19 hostile record shapes — dangling both directions, duplicate ids in all three
  collections, string/bool/zero/negative/missing ids, empty address, wrong and missing `assigned_object_type`
  — all failed closed with specific messages before any write, and the prior pair survived intact.

### Architecture Fit

- **[warning] W8 — two policy types with opposite defaults is what made C1 invisible:** `ExportPolicy`
  (`policy.py:67-88`) defaults `include_fields=None`, meaning "all optional fields allowed"; `ResourcePolicy`
  (`policy.py:32-45`) defaults `include_fields=frozenset()`, meaning "nothing allowed". The network view mixes
  both — devices through the open-by-default type, interfaces and IPs through the closed-by-default one. A
  reviewer scanning `render_network_yaml` sees `ExportPolicy()` and reads it as "the default policy" rather
  than "the operator's policy has been discarded". Whatever fix lands for C1, the two types should either be
  unified or the asymmetry should be named in a comment at `exporter.py:124`.

- **[info] I4 — the shared publication boundary was reused correctly:** `export_network` reuses
  `_publish_snapshot_pair` unchanged, and generalizing `list_devices` into `_list_records` was a clean
  extraction with no behavior change on the device path (Probe B confirmed byte-identical device output). The
  index is derived from the **validated** document rather than from raw records, which is the right coupling.
  Decision 0003's unified-document choice is honoured by the implementation.

### Operability

- **[warning] W9 — the double-fault error discards both underlying causes:** `exporter.py:190-192` raises a
  new `OSError` with `from None`, dropping the original canonical failure and the restore failure. The
  operator gets no errno and no path. Worse, at that moment `NETWORK.md` holds the **new** content while
  `network.yaml` holds the **old** content (Probe A captured exactly this state), and the message does not say
  which file is stale or which one to restore. Chain the original exception and name both paths.

- **[warning] W10 — v0.2 artifacts are stamped `Exporter version: 0.1.0`:** `pyproject.toml:9` and
  `__init__.py` still carry `0.1.0`, so every `NETWORK.md` this milestone produces claims to come from a build
  that cannot produce network views at all. REQ-018 requires the index to state the exporter version precisely
  so a consumer can reason about the artifact; right now that field cannot distinguish v0.1.0 output from v0.2
  output. Bump before close or before any tag.

- **[info] I5 — no structured logging, still:** `STATE.md` carries "add structured logging" as a deferred v0.1
  follow-up. A failed network export prints one line to stderr and exits 1; there is no record of how many
  pages were fetched per resource, which is exactly what an operator would want when a large export dies
  partway. Not blocking; noted because W2 makes it more relevant than it was in v0.1.

- **[info] I6 — the public-readiness gate cannot see this milestone yet:** `scripts/check_public_readiness.py`
  enumerates `git ls-files`, so all six new v0.2 files are invisible to it until they are committed. The
  `tests/test_examples.py` leak scan reads `examples/` from the filesystem and does cover the four new example
  artifacts. `network.schema.json` and `test_network_exporter.py` are covered by neither; this audit scanned
  both by hand for RFC 1918 ranges, operator/host identifiers and mail addresses — clean. Re-run
  `make public-check` after the first commit of this milestone.

### ASSERTED Items from TRACEABILITY.md

- **REQ-019 — confirmed gap.** The audit did not find the missing evidence; it found the counter-evidence.
  `--exclude-field serial` is accepted and ignored in the network view (finding C1). The interface and
  IP-address half of the requirement is genuinely proven — closed-by-default omission of 7 optional values,
  deny-precedence on all four flag families, unknown-field rejection with exit 2, zero token leakage into
  artifacts, stdout or stderr, and production-generated public-safe fixtures. The device half is not.

### Verdict

**PASS-CONDITIONAL** — do not mark v0.2 shipped until C1 is fixed and `/saga-verify` is re-run.

- Critical findings: **1** (C1 — must fix before milestone close)
- Warnings: **10** (W1–W10 — fix before shipping; W3/W5/W6 are the coverage items that would have caught this
  class of defect locally)
- Info: **6** (I1–I6 — track for later)

Assessment: five of six v0.2 requirements are independently proven from behavior, and REQ-016's integrity
layer is stronger than its evidence note claims — 19 hostile record shapes all fail closed before publication,
which is the hard part of a relationship tracer and it was done well. The atomic-pair boundary was reused
rather than reinvented, the index is derived from the validated document, and Markdown injection from
NetBox-controlled names is already neutralized. The determinism, packaging and public-safety claims survived
being re-derived from a clean wheel install.

The single critical defect is not in the new relationship code at all — it is the seam where the new
publication path meets the old device normalizer. `render_network_yaml` calls `_normalize_device(device,
ExportPolicy())` and the operator's policy never arrives. Every local test passes because no local test asks
the network view to honour a device denial, and the requirement text itself only names interfaces and IP
addresses, so the checkbox was defensible on its own wording. `SPEC.md:270` is not, and it names devices
explicitly.

That is the general shape of the risk here: the milestone was verified against the sentence it wrote for
itself rather than against the sentence it inherited. The fix is small. The habit worth keeping is that a new
publication path must re-prove **every** redaction guarantee the old one made, not only the new ones.

Per instruction, this audit did not edit `ROADMAP.md` or `STATE.md`, did not commit, push, mutate any GitHub
resource, or contact a live NetBox. All probes ran against loopback stubs and mock transports in scratch
directories. It wrote `.planning/TRACEABILITY.md` and this section only.

---

## Audit: v0.2 Network Relationships — 2026-07-21 (post-remediation re-audit of C1 / REQ-019)

Auditor: Claude Opus 4.8 (`claude-opus-4-8`) via Claude Code — independent frontier re-audit after the local
remediation of critical finding C1. Supersedes the v0.2 close-out entry above. `.planning/config.json` carries
a populated `close_out_auditor`, so no frontier-verify-gate warning applies to this project.

Scope: v0.2 Network Relationships — opt-in device → interface → assigned-IP tracer in one deterministic,
validated, atomic, redacted network document (REQ-014..REQ-019).

Files reviewed: 10 tracked files changed, 588 insertions(+), 16 deletions(-) against `c70a628`
(`git diff HEAD --shortstat`), plus 6 untracked new files not counted by that diff
(`src/netbox_scribe/schemas/v1/network.schema.json` 125L, `tests/test_network_exporter.py` 185L,
`examples/netbox-interfaces-page.json` 23L, `examples/netbox-ip-addresses-page.json` 25L,
`examples/output/inventory/network.yaml` 69L, `examples/output/agent/NETWORK.md` 18L). Effective review
surface: **16 files** — under the 50-file single-pass limit.

Method: nothing was accepted from the remediation note, from `STATE.md`, from a checkbox, or from a
requirement's own `evidence:` note. The prior pass's ASSERTED classification of REQ-019 was itself treated as
unproven and re-tested from scratch. Two wheels were built — one from the working tree and one from
`git archive HEAD` (the pre-v0.2 code) — and installed into two separate clean Python 3.11 venvs. **All 41
CLI invocations below drive an installed `nbscribe` binary as a subprocess against a loopback HTTP NetBox
stub on `127.0.0.1`, not the source tree.** Four probe suites, 68 assertions, all passing:

- **R1** — redaction through the public CLI (39 checks, 12 exports).
- **R2** — device-view regression, working-tree build vs. pre-v0.2 build (5 cases, 10 exports).
- **R3** — relationship integrity and atomicity (19 checks, 18 exports, 14 hostile record shapes).
- **R4** — adversarial leak hunt with a device canary echoed back through nested relationship blobs (5 checks).

`make ci` re-run: `black --check` clean (17 files), `ruff` clean, `mypy` clean (16 source files),
`pytest -n auto` → **48 passed**, `public-check` → _Public readiness checks passed (46 tracked files)_. Saga
spine lint clean, exit 0.

### Correctness

- **[resolved] C1 — device redaction policy now reaches the network publication path.** The previous audit
  found `render_network_yaml` hardcoding `_normalize_device(device, ExportPolicy())`, so
  `--exclude-field serial` was accepted and silently ignored under `--view network`. The fix threads a
  `device_policy` parameter through `export_network` (`exporter.py:75-85`) into `render_network_yaml`
  (`exporter.py:120-130`), and `cli.py:162-169` forwards the operator's `ExportPolicy` as `device_policy=`.
  Independently re-verified through the installed CLI, not by reading the diff:

  | Probe | Command (abbreviated)                                                                                                                       | Result                                                                                                                                                                                    |
  | ----- | ------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
  | R1-P1 | `--view network --exclude-field serial`                                                                                                     | exit 0; denied serial absent from `network.yaml`, `NETWORK.md`, stdout and stderr; non-denied `asset_tag` still present, so the exclusion is targeted rather than a wholesale device wipe |
  | R1-P2 | `--view network --include-custom-field owner`                                                                                               | `owner` values present; `secret_note` and `billing_code` absent as both keys and values on every surface                                                                                  |
  | R1-P3 | `--view network` (no custom-field flags)                                                                                                    | zero device custom fields — closed by default, as on the device view                                                                                                                      |
  | R1-P4 | `--include-custom-field owner --exclude-custom-field owner`                                                                                 | deny wins; value absent                                                                                                                                                                   |
  | R1-P5 | `--view network --include-field site`                                                                                                       | allowlist honoured; `serial` and `asset_tag` values dropped                                                                                                                               |
  | R4    | canary in 8 device fields, echoed back inside the interface record's nested `device` blob and the IP record's nested `assigned_object` blob | zero occurrences on any surface; published document reduced to `id`/`name` plus typed references                                                                                          |

  R4 is the check that matters most: it closes the sideways route. `_normalize_interface`
  (`exporter.py:336-349`) and `_normalize_ip_address` (`exporter.py:352-374`) extract only
  `{"type", "id"}` from their parent references, so a NetBox brief-serializer that inlines the whole device
  object into the interface payload cannot smuggle a denied device value back in.

- **[resolved] plain device export is unchanged.** R2 ran the same loopback stub, the same five argument
  shapes, against the pre-v0.2 wheel and the working-tree wheel, comparing exit code, `devices.yaml`,
  `INDEX.md`, stdout and stderr. **5/5 byte-identical**, including the policy cases (`--exclude-field serial`,
  `--include-custom-field owner`, `--include-field` allowlisting, deny precedence). REQ-014's
  "without changing plain `nbscribe export`" is now proven by differential comparison against the actual
  prior build, not by inspection.

- **[warning] W11 (new) — the public guidance still does not say device flags apply to `--view network`.**
  `README.md:117-138` documents the network view and the `--include-interface-*` / `--include-ip-address-*`
  families, but never states that `--exclude-field` / `--include-custom-field` also govern the devices inside
  `network.yaml`. That silence is exactly the gap C1 lived in: an operator reading only the network section
  has no reason to believe device redaction applies there, and REQ-019 explicitly claims _public guidance_
  proves denied values never enter published artifacts. One sentence fixes it.

### Safety

- **[info] I7 (new) — the closed-by-default asymmetry is unchanged but is now correctly overridden.** Device
  optional fields remain open-by-default (`ExportPolicy.include_fields = None`) while interface and IP
  optional fields are closed-by-default (`ResourcePolicy.include_fields = frozenset()`). That means a bare
  `nbscribe export --view network` still publishes device `serial`, `asset_tag`, `description` and so on. This
  is deliberate parity with the device view and is not a regression — but combined with W11 it is the shape an
  operator is most likely to get wrong.

- **[warning] W1 (carried, re-checked) — an out-of-scope address aborts the export rather than being skipped.**
  `README.md:126` says the network view "excludes unassigned and VM-assigned addresses". The exclusion is
  server-side (`?assigned_object_type=dcim.interface`); client-side, `_normalize_ip_address`
  (`exporter.py:357-358`) _raises_ on anything else. R3 confirmed: a `virtualization.vminterface` address and
  an address with no `assigned_object_type` both exit 1 with
  `IP address 100 is not assigned to a device interface`, and the whole export is lost. Failing closed is the
  right default for a redaction-sensitive tool, but a NetBox version that ignores or renames that query
  parameter turns a filter into an outage, and the README's wording does not warn about it.

- **[warning] W4 (carried) — the atomic pair is not crash-durable.** `_publish_snapshot_pair`
  (`exporter.py:177-199`) performs two independent `os.replace` calls. Process death between them leaves a new
  `NETWORK.md` paired with an old `network.yaml` permanently and undetectably; nothing in the artifacts stamps
  a generation. Holds for in-process `OSError` (tested) and for the integrity-abort path (R3 confirmed across
  14 shapes), not for power loss. Unchanged this pass.

- **[info] I8 (new) — device `name` cannot be redacted, in either view.** `_normalize_device`
  (`exporter.py:293-295`) exempts `id` and `name` from policy, and `network.schema.json` requires both with
  `minLength: 1`. Correct — the relationship graph is meaningless without stable identities — but it means the
  tool cannot produce a hostname-anonymized export, which is worth stating before anyone points it at a
  customer inventory.

### Test Coverage

- **[warning] W12 (new) — the C1 regression guard does not leak-scan the index.**
  `tests/test_cli.py:135-213` is the only test that would catch a device-policy regression in the network
  view. It asserts `"denied-network-serial" not in output.read_text()` and the same for the denied custom
  value — both against `network.yaml` only. `index_text` is asserted positively (freshness, hierarchy) but is
  never scanned for the denied values. The index happens to be safe because it renders from the validated
  document (R1/R4 confirmed), but the guard for the defect that just shipped a critical finding covers one of
  the two published artifacts. Add `assert "denied-network-serial" not in index_text` and the same for the
  custom value; it is a two-line change.

- **[warning] W13 (new) — no exporter-layer test asserts `device_policy` is honoured.**
  `tests/test_network_exporter.py` has five tests; none passes `device_policy` to `export_network` or
  `render_network_yaml`. The regression guard exists only at the CLI layer. More pointedly,
  `tests/test_examples.py:62` calls `export_network(client, output, agent_index=index, policy=policy)` with
  no `device_policy` — the repository's own example generator exercises the open-default path, and
  `examples/output/inventory/network.yaml:15` accordingly publishes `serial: SYNTHETIC-001`. Harmless with
  synthetic data, but it means the shipped example demonstrates the network view _without_ device redaction.

- **[warning] W3 (carried, still open) — REQ-014's "retrieves every page" has no regression test on the two
  new endpoints.** `tests/test_client.py:54-100` still returns `"next": None` for all three resources, and the
  CLI network test is single-page. R1 proved two-page retrieval on all three endpoints through the installed
  binary; the suite would not catch a future per-resource retrieval change that breaks paging.

- **[warning] W5 (carried, still open) — same-origin and loop guards remain untested on the relationship
  endpoints.** Every hostile-pagination test in `tests/test_client.py` targets `api/dcim/devices/`. REQ-014
  and `SPEC.md:201` both claim the controls apply to every resource. The behavior is correct because
  `_list_records` is shared, but nothing pins that.

- **[warning] W6 (carried, still open) — the two rollback edge cases deferred from the v0.1 audit are still
  untested.** `STATE.md` "Deferred" carries "test rollback double-fault/no-prior-index" as a v0.2 follow-up.
  Neither exists in `tests/`. Behavior was verified correct by the previous audit's Probe A; the guard is
  missing.

- **[warning] W7 (carried, still open) — no test covers a server that ignores the assignment filter.** See W1.
  No client-layer fixture returns an unassigned or VM-assigned address, so the documented scope guarantee is
  unexercised end to end.

- **[info] I3 (carried, re-confirmed) — relationship integrity remains the best-tested part of the milestone.**
  R3 drove 14 hostile record shapes through the _public CLI_ this pass (the previous audit drove 19 through
  the render function). All 14 exited 1 with a specific `error:` line, no traceback, and left both prior
  artifacts byte-identical; a subsequent good export recovered cleanly. `--output`/`--agent-index` collision is
  rejected, and `nbscribe validate` accepts the published `network.yaml` from a clean venv.

### Architecture Fit

- **[warning] W8 (carried, partially addressed) — the two-policy asymmetry is now in the public signature.**
  The fix is minimal and correct, but `export_network(client, output, *, agent_index, policy, device_policy)`
  now takes **two** policy objects with **opposite defaults**: `policy=None` → `NetworkExportPolicy()` = fully
  closed for interfaces and IPs; `device_policy=None` → `ExportPolicy()` = fully **open** for devices. A
  library caller who carefully constructs a closed `NetworkExportPolicy` and forgets `device_policy` gets the
  exact C1 behavior back. `tests/test_examples.py:62` is that caller today (W13). The durable fix is to fold
  devices into the policy object — `NetworkExportPolicy(devices=..., interfaces=..., ip_addresses=...)` — so
  there is one policy argument and one default. Failing that, a comment at `exporter.py:129` naming the
  asymmetry is the minimum.

- **[info] I4 (carried, re-confirmed) — the shared publication boundary is still reused correctly.**
  `export_network` reuses `_publish_snapshot_pair` unchanged; the index is derived from the **validated**
  document rather than raw records, which is precisely why the C1 fix propagated to `NETWORK.md` for free.
  Decision 0003's unified-document choice is honoured.

- **[info] I2 (carried) — index injection remains handled.** `agent_index.py:98-101` collapses newlines and
  switches to a double-backtick delimiter, so a hostile NetBox-controlled name cannot forge index bullets.

### Operability

- **[close condition] CC1 / W10 — v0.2 artifacts are still stamped `Exporter version: 0.1.0`.**
  `pyproject.toml:7` remains `version = "0.1.0"`, so `examples/output/agent/NETWORK.md:8` and every
  `NETWORK.md` this milestone produces claim to come from a build that cannot produce network views at all.
  REQ-018 requires the index to state the exporter version so a consumer can reason about the artifact; right
  now that field cannot distinguish v0.1.0 output from v0.2 output. The rendering mechanism is correct — this
  is release hygiene, but it is a **factually false provenance claim in a v0.2 requirement's own output** and
  should not survive the milestone close. Bump `pyproject.toml`, regenerate the examples, re-run `make ci`.

- **[close condition] CC2 / I6 — the public-readiness gate has still never seen this milestone.**
  `make public-check` reported _46 tracked files_ this pass; the six new v0.2 files are untracked and
  `scripts/check_public_readiness.py` enumerates `git ls-files`. `tests/test_examples.py` reads `examples/`
  from the filesystem and does cover the four new example artifacts, but `network.schema.json` and
  `tests/test_network_exporter.py` are covered by neither. This audit scanned both by hand for RFC 1918
  ranges, operator/host identifiers and mail addresses — clean — but a hand scan is not the gate. Commit the
  six files and re-run `make public-check` before close.

- **[warning] W9 (carried, still open) — the double-fault error discards both underlying causes.**
  `exporter.py:196-198` raises a new `OSError` with `from None`, dropping the original canonical failure and
  the restore failure. No errno, no path, and no statement of which of the two files is stale — at that moment
  `NETWORK.md` holds new content while `network.yaml` holds old content. Chain the original exception and name
  both paths.

- **[info] I5 (carried, still open) — no structured logging.** A failed network export prints one line to
  stderr and exits 1; there is no record of how many pages were fetched per resource. Carried as a deferred
  v0.1 follow-up in `STATE.md`.

- **[info] I9 (new) — `--output`/`--agent-index` collision is still rejected after the fetch, not before.**
  R3 confirmed the rejection works (`canonical output and agent index must use different paths`, exit 1), but
  `export_network` raises it only after `client.list_network_records()` has already pulled all three
  resources. Carried in `STATE.md` as a v0.1.0 follow-up ("reject output/index path collisions before
  fetching"); still open. Wasted work, not a safety issue.

### ASSERTED Items from TRACEABILITY.md

- **REQ-019 — gap closed, upgraded to PROVEN.** The previous pass classified this ASSERTED because the audit
  found counter-evidence: `--exclude-field serial` accepted and ignored in the network view. This pass
  re-tested the claim from scratch through an installed wheel rather than accepting the remediation note. All
  six device-policy probes (R1-P1..P5, R4) pass, the interface/IP half re-proves, and the adversarial nested-
  echo route is closed. The fresh `TRACEABILITY.md` records **0 ASSERTED, 0 OPEN, 0 WAIVED** across all 19
  requirements.

### Verdict

**PASS-CONDITIONAL** — the critical defect is fixed and independently verified; two mechanical close
conditions remain before v0.2 may be marked shipped.

- Critical findings: **0** (C1 resolved and re-verified)
- Close conditions: **2** (CC1 exporter-version bump; CC2 commit the six untracked files and re-run
  `make public-check`)
- Warnings: **10** (W1, W3, W5, W6, W7, W8, W9, W11, W12, W13 — of which W11/W12/W13 are new and W12/W13
  directly guard the defect that was just fixed)
- Info: **7** (I2, I3, I4, I5, I7, I8, I9 carried or new — track for later)

**Close conditions (must be discharged before v0.2 is marked shipped):**

1. **CC1** — bump `pyproject.toml` off `0.1.0`, regenerate `examples/output/agent/NETWORK.md` and `INDEX.md`,
   re-run `make ci`. A v0.2 artifact must not claim to come from a build that cannot produce it.
2. **CC2** — commit the six untracked v0.2 files and re-run `make public-check` so the readiness gate actually
   covers `network.schema.json` and `tests/test_network_exporter.py`.

**Optional follow-ups (do not block the close; candidates for v0.2.x):**

- W12 — add two leak assertions against `index_text` in `tests/test_cli.py:194-213`.
- W13 — add an exporter-layer test that `device_policy` is honoured; consider passing one in
  `tests/test_examples.py` so the shipped example demonstrates device redaction in the network view.
- W11 — one README sentence stating that `--exclude-field` / `--include-custom-field` also govern devices
  under `--view network`.
- W8 — fold devices into `NetworkExportPolicy` so `export_network` takes one policy object with one default,
  or comment the asymmetry at `exporter.py:129`.
- W3, W5, W7 — pagination, same-origin and assignment-filter regression tests on the two new endpoints.
- W6 — the two rollback edge-case tests carried from the v0.1 audit.
- W9 — chain the original exception and name both paths in the double-fault error.
- W1 — document that an out-of-scope address aborts rather than being skipped, or degrade to skip-with-count.
- W4, I5, I8, I9 — durability stamping, structured logging, the un-redactable device name, and pre-fetch path
  collision rejection.

Assessment: the remediation is small, correct, and lands exactly where the defect was — at the seam where the
new publication path met the old device normalizer. It was re-verified adversarially rather than accepted:
R2's differential comparison against a build of the pre-v0.2 code proves the device view did not move, and
R4's nested-echo canary closes the one route by which a denied device value could have re-entered sideways.
All six v0.2 requirements are now independently proven from behavior, through an installed wheel, with no
live NetBox contacted.

The residual risk has shifted from the code to the guards around it. The single test that would catch a C1
regression scans one of the two published artifacts (W12), the exporter layer has no such test at all (W13),
and the library signature still has the open-by-default trap that made C1 possible in the first place (W8) —
with the repository's own example generator sitting in that trap. None of that blocks the close, but if v0.2.x
extends this model to prefixes, VLANs and cables, those are the guards to build first.

Per instruction, this audit did not edit `ROADMAP.md` or `STATE.md`, did not commit, push, or mutate any
GitHub resource, and did not contact a live NetBox. All probes ran against loopback stubs in `/tmp` scratch
directories. It wrote `.planning/TRACEABILITY.md` and this section only.

---

## Audit: v0.2 Network Relationships — 2026-07-21 (close-condition re-audit after CC1 / CC2 remediation)

Auditor: Claude Opus 4.8 (`claude-opus-4-8`) via Claude Code — independent frontier re-audit invoked directly
by the operator after remediation of the two close conditions. Supersedes the **PASS-CONDITIONAL** entry above.
`.planning/config.json` carries a populated `close_out_auditor`, so no frontier-verify-gate warning applies.

Scope: v0.2 Network Relationships — opt-in device → interface → assigned-IP tracer in one deterministic,
validated, atomic, redacted network document (REQ-014..REQ-019), plus discharge of close conditions CC1
(exporter-version provenance) and CC2 (public-readiness gate coverage).

Files reviewed: 23 staged files against `c70a628` — 17 modified, 6 added, 1624 insertions(+), 156 deletions(-)
(`git diff HEAD --shortstat`). `git diff` against the index is empty and `git ls-files --others
--exclude-standard` is empty, so the review surface and the tracked tree are now the same set. Under the
50-file single-pass limit.

Method: nothing was accepted from `STATE.md`, from a checkbox, from a requirement's own `evidence:` note, or
from the previous audit's verdict — including its own PASS on REQ-019, which was re-tested from scratch. Two
wheels were built and installed into two separate clean Python 3.11 venvs: the working tree at 0.2.0 and
`git archive HEAD` at 0.1.0 (pre-bump). **All 23 CLI invocations below drive an installed `nbscribe` binary as
a subprocess against loopback HTTP NetBox stubs on `127.0.0.1`, not the source tree.** Two probe suites,
55 assertions, all passing:

- **V1** — v0.2 behavior and version provenance through the public CLI (35 assertions, 13 invocations).
- **V2** — differential device-view comparison across the CC1 bump, 0.1.0 wheel vs. 0.2.0 wheel (20
  assertions, 10 invocations).

One V1 assertion failed on first run and was a probe-authoring error, not a product defect: it expected
`schema_version: v1` where the canonical form is `schema_version: 1`. Corrected and re-verified.

`make ci` re-run: `black --check` clean (17 files), `ruff` clean, `mypy` clean (16 source files),
`pytest -n auto` → **48 passed**, `public-check` → _Public readiness checks passed (**52 tracked files**)_.
Saga spine lint clean, exit 0.

### Close conditions — status

| ID  | Condition                                                                           | Status this pass                                                                                                                                                                                                                                             |
| --- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| CC1 | v0.2 artifacts stamped `Exporter version: 0.1.0`                                    | **DISCHARGED & independently re-verified.** `0.2.0` at 10 version sites plus two freshly generated indexes; the pin is mutation-tested load-bearing at three test sites; V2 proves the bump changed the provenance stamp and nothing else                    |
| CC2 | Public-readiness gate had never seen the six untracked v0.2 files                   | **DISCHARGED.** `make public-check` enumerates **52 tracked files** (was 46), including `src/netbox_scribe/schemas/v1/network.schema.json` and `tests/test_network_exporter.py`. Untracked set empty; unstaged diff empty. Scan-depth caveat recorded as I10 |
| C1  | Device redaction policy did not reach the network publication path (prior critical) | **STILL CLOSED.** Re-tested from behavior rather than carried: six device-policy probes plus the nested-echo canary, all through the 0.2.0 wheel                                                                                                             |

### Correctness

- **[resolved] CC1 / W10 — the exporter-version provenance claim is now true.** `pyproject.toml:7` is
  `version = "0.2.0"`. The chain was re-derived at **10 sites**, all agreeing: `pyproject.toml:7`,
  `uv.lock:368`, the wheel filename, the sdist filename, the `netbox_scribe-0.2.0.dist-info/` directory, the
  wheel `METADATA` `Version:` field, the installed `netbox_scribe.__version__`, `nbscribe --version` from a
  clean venv, `examples/output/agent/INDEX.md:8`, and `examples/output/agent/NETWORK.md:8`. A **fresh** network
  export from the installed wheel stamps `- Exporter version: 0.2.0` with no `0.1.0` residue on any line, as
  does a fresh device export. The only surviving `0.1.0` strings in the tracked tree are in
  `docs/PUBLICATION.md`, where they correctly name the shipped v0.1.0 release tag and its history — not a
  stale exporter claim.

  **The pin is load-bearing, not cosmetic.** `pyproject.toml` was reverted to `0.1.0` in an isolated copy and
  the suite re-run: **3 failed, 45 passed** — `tests/test_cli.py::test_version_does_not_require_netbox_credentials`
  (the literal `assert __version__ == "0.2.0"` at `tests/test_cli.py:40`, which correctly replaced the v0.1.0
  release's `0.1.0` literal), plus both example byte-comparisons in `tests/test_examples.py`. A future bump
  cannot silently skip the fixtures.

  **The bump changed nothing else.** Probe V2 ran the 0.1.0 baseline wheel and the 0.2.0 wheel against the same
  loopback stub across five argument shapes (plain, `--exclude-field serial`, `--include-custom-field owner`,
  `--include-field site`, deny precedence). `devices.yaml` is **byte-identical in all five**; stdout and stderr
  are identical in all five; and the `INDEX.md` unified diff is **exactly** `-- Exporter version: 0.1.0` /
  `+- Exporter version: 0.2.0` in all five. REQ-003 and REQ-006 survive the release-hygiene change by
  measurement, not assumption.

- **[resolved] C1 remains closed under re-test.** The prior pass's PASS on REQ-019 was not carried. Through the
  installed 0.2.0 CLI: `--view network --exclude-field serial` → exit 0 with the denied serial absent from
  `network.yaml`, `NETWORK.md`, stdout **and** stderr while non-denied `asset_tag` survives (targeted, not a
  wholesale device wipe); `--include-custom-field owner` → `owner` present with `secret_note` and
  `billing_code` absent as both keys and values; bare `--view network` → zero device custom fields;
  include+exclude on the same custom field → deny wins; `--include-field site` → `serial` and `asset_tag`
  dropped. A canary planted in eight device fields (`serial`, `asset_tag`, `description`, `display`,
  `primary_ip4.dns_name`, `site`, `tags[].name`, `custom_fields.owner`) **and echoed back inside the interface
  record's nested `device` blob and the IP record's nested `assigned_object` blob** appears **zero** times on
  any surface. The sideways reentry route stays shut because `_normalize_interface` (`exporter.py:336-349`) and
  `_normalize_ip_address` (`exporter.py:352-374`) extract only `{"type", "id"}` from their parent references.

- **[warning] W11 (carried, still open) — the public guidance still does not say device flags apply to
  `--view network`.** `README.md` documents the network view and the `--include-interface-*` /
  `--include-ip-address-*` families but never states that `--exclude-field` / `--include-custom-field` also
  govern the devices inside `network.yaml`. Re-confirmed by grep this pass. That silence is the gap C1 lived
  in. One sentence fixes it. Not a condition on this close.

### Safety

- **[info] I10 (new) — `public-check` enumerates the two new non-example files but does not content-scan
  them.** CC2 is discharged as written: `scripts/check_public_readiness.py:47-54` builds its set from
  `git ls-files`, so `network.schema.json` and `tests/test_network_exporter.py` are now inside the gate and
  subject to its forbidden-path and forbidden-prefix assertions (`.env`, `dist/`, `snapshot/`,
  `.planning/.close-out-auditor.log`). Worth stating precisely, though: the gate's _content_ checks are the
  `DESIGN.md` local-path check and the tracked-local-link scan over `*.md` only. So of the six new files, the
  four under `examples/` are additionally content-scanned by
  `tests/test_examples.py::test_public_docs_and_examples_contain_no_private_networks_or_credentials` (RFC 1918
  and credential-assignment regexes over every `examples/` file), and `examples/output/agent/NETWORK.md`
  additionally has its `../inventory/network.yaml` canonical link resolved by the gate — but
  `network.schema.json` and `tests/test_network_exporter.py` get enumeration and path assertions only. Both
  were hand-scanned this pass for RFC 1918 literals, mail addresses, `/home/` paths and operator identifiers:
  **zero hits**. A hand scan is still not a gate; if the file set grows, extend the content scan beyond
  `examples/`. Not a blocker — neither file can carry inventory data by construction.

- **[warning] W1 (carried) — an out-of-scope address aborts the export rather than being skipped.**
  `_normalize_ip_address` (`exporter.py:357-358`) raises on any `assigned_object_type` other than
  `dcim.interface`, while `README.md` describes it as an exclusion. Failing closed is right for a
  redaction-sensitive tool, but a NetBox that ignores or renames the `?assigned_object_type=` query parameter
  turns a filter into an outage. Unchanged this pass.

- **[warning] W4 (carried) — the atomic pair is not crash-durable.** `_publish_snapshot_pair` performs two
  independent `os.replace` calls; process death between them leaves a new index paired with an old canonical
  permanently and undetectably. Holds for in-process `OSError` and for the integrity-abort path. Unchanged.

- **[info] I7, I8 (carried) — closed-by-default asymmetry and the un-redactable device `name`.** Device
  optional fields are open-by-default while interface/IP optional fields are closed-by-default; `id` and
  `name` are exempt from policy in both views and required by `network.schema.json`. Both deliberate, both
  unchanged, both worth knowing before pointing the tool at a customer inventory.

- Re-confirmed clean this pass: the token appeared in **no** artifact, stdout or stderr across 23 invocations;
  the loopback stub genuinely required it (403 otherwise, 3 authenticated requests per network export); no
  traceback on any surface; the clean-venv binary still refuses `http://` before any request is sent, so every
  probe had to pass `--allow-insecure-http` explicitly.

### Test Coverage

The suite is unchanged at **48 passed** — the remediation was release hygiene and staging, and it added no
tests. All prior coverage warnings therefore stand, re-confirmed by grep this pass:

- **[warning] W12 (carried, still open) — the C1 regression guard does not leak-scan the index.**
  `tests/test_cli.py:204` asserts `"denied-network-serial" not in output.read_text()` against `network.yaml`
  only; `index_text` (`tests/test_cli.py:194-198`) is asserted positively for freshness and hierarchy but never
  scanned for the denied values. The index is safe in fact — V1 confirmed it — but the guard for the defect
  that shipped a critical finding still covers one of the two published artifacts. Two lines.
- **[warning] W13 (carried, still open) — no exporter-layer test asserts `device_policy` is honoured.**
  `grep -rn device_policy tests/` returns nothing. `tests/test_examples.py:62` still calls `export_network(...)`
  without it, so `examples/output/inventory/network.yaml:18` publishes `serial: SYNTHETIC-001` — the shipped
  example demonstrates the network view _without_ device redaction. Harmless with synthetic data; it means the
  repository's own example generator sits in the W8 trap.
- **[warning] W3, W5, W7 (carried, still open) — pagination, same-origin and assignment-filter regression tests
  are still absent on the two new endpoints.** V1 proved two-page retrieval on all three endpoints through the
  installed binary this pass, but `tests/test_client.py` still returns `"next": None` for all three and every
  hostile-pagination test still targets `api/dcim/devices/`. The behavior is correct because `_list_records` is
  shared; nothing pins that.
- **[warning] W6 (carried, still open) — the two rollback edge cases from the v0.1 audit remain untested.**
- **[info] I11 (new) — version-fixture brittleness is now measured.** The mutation test quantifies the TC-C
  concern carried since v0.1: a version bump reds **three** tests and requires regenerating **two** committed
  fixtures. Recording it as a measured cost rather than a defect, because it is the same mechanism that makes
  CC1's remediation load-bearing. If the cost ever justifies removing it, replace the byte-compare with a
  version-normalized compare — do not simply drop the assertion.

### Architecture Fit

- **[warning] W8 (carried, partially addressed) — the two-policy asymmetry is still in the public signature.**
  `export_network(client, output, *, agent_index, policy, device_policy)` takes two policy objects with
  opposite defaults: `policy=None` → fully closed for interfaces and IPs, `device_policy=None` → fully **open**
  for devices. A library caller who builds a closed `NetworkExportPolicy` and forgets `device_policy` gets the
  exact C1 behavior back; `tests/test_examples.py:62` is that caller today. Durable fix: fold devices into the
  policy object so there is one argument and one default. Unchanged this pass.
- **[info] I4 (carried, re-confirmed) — the shared publication boundary is still reused correctly.**
  `export_network` reuses `_publish_snapshot_pair` unchanged and the index renders from the **validated**
  document, which is why the C1 fix propagated to `NETWORK.md` for free and why the canary probe finds nothing
  in it. Decision 0003's unified-document choice is honoured.
- **[info] I2 (carried) — index injection remains handled.** `agent_index.py:98-101` collapses newlines and
  switches to a double-backtick delimiter.

### Operability

- **[resolved] CC2 / I6 — the public-readiness gate now covers the milestone.** `make public-check` reports
  _Public readiness checks passed (52 tracked files)_, up from 46. `git ls-files` confirms all six former
  untracked files are tracked: `src/netbox_scribe/schemas/v1/network.schema.json`,
  `tests/test_network_exporter.py`, `examples/netbox-interfaces-page.json`,
  `examples/netbox-ip-addresses-page.json`, `examples/output/inventory/network.yaml`,
  `examples/output/agent/NETWORK.md`. `git ls-files --others --exclude-standard` is empty and `git diff`
  against the index is empty, so **no** v0.2 artifact sits outside the gate. `.env`, `snapshot/` and `dist/`
  remain untracked and are re-asserted forbidden by the gate itself. See I10 for scan depth.
- **[warning] W9 (carried, still open) — the double-fault error discards both underlying causes.**
  `exporter.py:196-198` raises a new `OSError` `from None` with no errno, no path, and no statement of which
  file is stale.
- **[info] I5, I9 (carried, still open) — no structured logging; the `--output`/`--agent-index` collision is
  still rejected after the fetch rather than before.** Both are on `STATE.md` as deferred follow-ups.

### ASSERTED Items from TRACEABILITY.md

None. The fresh `TRACEABILITY.md` written this pass records **0 ASSERTED, 0 OPEN, 0 WAIVED** across all 19
requirements, and every v0.2 row was re-derived by executing the built artifact rather than carried from the
previous pass's verdict.

One accuracy note, unchanged: the `make ci with N tests` counts embedded in several `REQUIREMENTS.md`
`evidence:` notes are historical snapshots from when each slice landed (13, 19, 20, 32, 33, 39, 41, 42, 45, 46,
48). The suite is 48 today. Every named artifact resolves, so no classification changes.

### Verdict

**PASS** — both close conditions are discharged and independently re-verified. v0.2 closes clean.

- Critical findings: **0**
- Close conditions: **0** (CC1 and CC2 both discharged)
- Warnings: **10** (W1, W3, W5, W6, W7, W8, W9, W11, W12, W13 — all carried, none new, none blocking)
- Info: **9** (I2, I4, I5, I7, I8, I9 carried; I10 and I11 new)

v0.2 requirement counts: **6 PROVEN** (REQ-014..REQ-019), 0 ASSERTED, 0 OPEN, 0 WAIVED.
Whole-project counts: **19 PROVEN**, 0 ASSERTED, 0 OPEN, 0 WAIVED.

Rationale: both conditions were mechanical, and both were verified mechanically rather than by reading the
diff. CC1 is not just "the number changed" — the version agrees at ten independent sites including the built
wheel's own metadata, a fresh export from that wheel stamps it, three tests go red when it is reverted, and a
differential run against a wheel built from the pre-bump code proves the bump moved the provenance line and
nothing else. That last check is the one that matters: a release-hygiene edit is exactly the kind of change
that quietly perturbs deterministic output, and it did not. CC2 is discharged by the gate's own count moving
46 → 52 with an empty untracked set and an empty unstaged diff, so the enumeration is complete rather than
merely larger. C1 was re-tested from scratch rather than carried, including the nested-echo route by which a
denied device value could re-enter sideways, and it stays shut.

The residual risk is unchanged from the previous pass and has not worsened: it lives in the guards, not the
code. The single test that would catch a C1 regression scans one of the two published artifacts (W12), the
exporter layer has no such test at all (W13), and the library signature keeps the open-by-default trap that
made C1 possible (W8) — with the repository's own example generator sitting in it. None of that is a
correctness or security blocker today, so none of it is a condition on this close. If v0.2.x extends this
model to prefixes, VLANs and cables, those three are the guards to build first, with W3/W5/W7's endpoint
regression tests next.

**Optional follow-ups (candidates for v0.2.x — explicitly NOT conditions on this close):**

- W12 — two leak assertions against `index_text` in `tests/test_cli.py`.
- W13 — an exporter-layer `device_policy` test; consider passing one in `tests/test_examples.py` so the
  shipped example demonstrates device redaction under `--view network`.
- W11 — one README sentence stating device flags govern devices under `--view network`.
- W8 — fold devices into `NetworkExportPolicy` so there is one policy argument and one default.
- W3, W5, W7 — pagination, same-origin and assignment-filter regression tests on the two new endpoints.
- W6 — the two rollback edge-case tests carried from v0.1.
- W9 — chain the original exception and name both paths in the double-fault error.
- W1 — document that an out-of-scope address aborts rather than being skipped, or degrade to skip-with-count.
- I10 — extend the readiness gate's content scan beyond `examples/` if the tracked non-markdown set grows.
- W4, I5, I8, I9 — durability stamping, structured logging, the un-redactable device name, and pre-fetch path
  collision rejection.

**Release-readiness note, not a finding:** the v0.2 tree is fully staged but **not committed**. There is
nothing yet for a `v0.2.0` tag to point at, and the v0.1.1 audit's D3 finding is the standing reminder that a
mirror push before a commit publishes the wrong tree. Committing, tagging, pushing, and package publication
are operator actions explicitly reserved out of scope for this pass — this is release mechanics, not a
verification gap, and it is not a close condition.

Close-out path: `/saga-spec merge` to bake the verified v0.2 behavior into the living spec library. Not
performed by this audit.

Per instruction, this audit did not edit `ROADMAP.md` or `STATE.md`, did not commit, push, tag, or publish any
package, did not mutate any GitHub resource, and did not contact a live NetBox. All probes ran against
loopback stubs in `/tmp` scratch directories. It wrote `.planning/TRACEABILITY.md` and this section only.

---

## Audit: v0.2 finalization — view-specific default output paths (narrow recheck) — 2026-07-21

Scope deliberately narrow: only the finalization fix at `src/netbox_scribe/cli.py:127-130`
(`_default_export_paths`) and its two call sites at `cli.py:111-119`. Everything else in v0.2 is carried from
the close-out audit above and was not re-derived. Auditor: Claude Opus 4.8 (`claude-opus-4-8`) via Claude
Code. Tree: `HEAD = c70a628` plus the same 23 staged files; `git status --short` identical before and after.

**What the fix changed.** The `export` subparser previously carried two constant `argparse` defaults
(`snapshot/inventory/devices.yaml`, `snapshot/agent/INDEX.md`). Those constants are gone; both options now
default to `None` and `main()` resolves `args.output or default_output` against a view-dispatched pair. The
failure mode this prevents is `--view network` publishing network content into the device view's filenames.

### Correctness

- **[resolved] Defaults are view-correct and mutually non-interfering.** Probe V3 drove the installed
  0.2.0 wheel's `nbscribe` from a clean venv against a loopback stub: plain `export` produces exactly
  `snapshot/inventory/devices.yaml` + `snapshot/agent/INDEX.md`, and `--view network` produces exactly
  `snapshot/inventory/network.yaml` + `snapshot/agent/NETWORK.md`. In each case `find` over the scratch
  directory returns **two files total**, so the other view's artifacts are not created as a side effect.
  With the other view's artifacts pre-seeded with sentinels, both sentinels survive byte-intact across the
  opposing default export — neither default overwrites the other pair.
- **[resolved] Artifacts are distinguished by shape, not just by name.** `devices.yaml` carries top-level
  `devices` only; `network.yaml` adds `interfaces` and `ip_addresses` (43 vs. 65 lines). The indexes differ in
  title and freshness stamp. `nbscribe validate` returns `Valid snapshot` for both, resolving each against its
  own packaged schema. So no view is emitting the other's payload under the correct filename.
- **[resolved] Explicit overrides still win, structurally.** `--output` + `--agent-index` on either view
  create the custom paths and leave **both** default paths absent. A partial override (`--output` only) uses
  the custom canonical path and the view's default index, which is the intended composition. The `or` idiom is
  safe by construction rather than by luck: `pathlib.Path` defines no `__bool__`/`__len__`, so no `Path` is
  falsy — `Path("")` normalizes to `PosixPath('.')` and is truthy. No user-supplied path can be swallowed.
- **[resolved] The dispatch is load-bearing in both directions.** Deleting the `network` branch turns
  `tests/test_cli.py::test_network_view_fetches_relationships_and_writes_canonical_document` red; inverting
  the function to always return network paths turns
  `tests/test_cli.py::test_export_command_handles_unnamed_device_without_traceback` red. Both failures are
  `FileNotFoundError` on the missing default artifact, which is precisely the regression signature.

### Test Coverage

- **[warning] W14 — no repository test asserts the _negative_.** The two CLI tests pin that each view's
  default artifacts _are_ written, and the mutation results above prove that pin is real. Neither test asserts
  that the opposing view's files are _not_ created. Today that is safe by construction — each branch of
  `_run_export` writes exactly one pair through `_publish_snapshot_pair` and there is no code path that could
  touch the other pair — and Probe V3 covers it externally. It becomes worth pinning if a future view ever
  writes more than one pair, or if a shared "write all views" convenience flag is added. Non-blocking: two
  `assert not (tmp_path / ...).exists()` lines in the existing tests would close it.

### Operability

- **[warning] W15 — a degenerate `--output ""` surfaces a raw errno.** `nbscribe export --output ""`
  resolves to `PosixPath('.')` and fails with
  `error: [Errno 16] Device or resource busy: './..<rand>.tmp' -> '.'`. Behavior is otherwise correct: exit 1,
  no traceback, no partial artifacts, and — importantly for this audit — **no silent fallback to the default
  path**. This is pre-existing generic bad-path handling, not introduced by the fix, and it is not
  view-specific. Cosmetic only; a directory-target pre-check would give a better message, and it pairs
  naturally with I9 (pre-fetch path collision rejection) from the close-out audit.

### Methodology note (recorded because it nearly produced a false finding)

The first mutation attempt copied the tree with `cp -r` **including `.venv`**. Copied venv scripts embed
absolute paths, so `uv run` inside the copy resolved back to the source repository's environment and the
mutated tree reported a false **48 passed** — which would have been written up as "the fix is not
regression-guarded." The behavioral probe contradicted it (the mutated `nbscribe` visibly wrote network data
into `devices.yaml`), the contradiction was chased rather than averaged, and the root cause was found in the
venv resolution. Re-run against an `rsync --exclude='.venv'` copy with a fresh `uv venv`, the mutations go red
as documented. **Any future mutation testing in this project must exclude `.venv`.**

Incidental hygiene: the `rsync` copy initially included the gitignored `.env`. It was deleted from the `/tmp`
copy before any test ran, was never read, and never entered the repository.

### Gate

`make ci` run twice — before and after all mutation work — both green: `black --check` clean (17 files),
`ruff check` clean, `mypy` clean (16 source files), `pytest -n auto` → **48 passed**, `public-check` →
_Public readiness checks passed (52 tracked files)_. `git status --short` at the end is identical to the
start, so nothing in the source tree was perturbed by the probes.

### Verdict

**PASS** — the view-specific default-path fix is correct, non-interfering, override-respecting, and pinned by
tests that go red in both directions.

- Critical findings: **0**
- **Close conditions: 0 — there is no actual close condition on this recheck.**
- Warnings: **2 new** (W14 negative-assertion coverage; W15 degenerate `--output ""` errno). Both
  non-blocking. All prior warnings carried unchanged.
- Requirement impact: none. REQ-014 stays **PROVEN** with added evidence; no status in `TRACEABILITY.md`
  changed.

Rationale for PASS rather than CONDITIONAL: every claim in the brief was proven through the installed wheel's
public CLI rather than by reading the diff — correct defaults per view, non-creation and non-overwrite of the
opposing pair, and full override precedence including the partial-override case. The one result that could
have downgraded this to CONDITIONAL (the fix not being regression-guarded) turned out to be an artifact of my
own harness, and the corrected mutation test shows the dispatch pinned in both directions. W14 and W15 are
real but neither can produce a wrong artifact today: W14 is redundant with a structural guarantee, and W15 is
a message-quality issue on a path that already fails safely without falling back to a default.

**Optional follow-ups (NOT conditions on this close):**

- W14 — two `assert not ...exists()` lines pinning cross-view non-creation.
- W15 — reject directory targets before fetching, folding into I9.

Per instruction, this audit did not edit `ROADMAP.md` or `STATE.md`, did not commit, push, tag, or publish any
package, did not mutate any GitHub resource, and did not contact a live NetBox. All probes ran against a
loopback stdlib HTTP stub serving the repository's synthetic fixtures, in `/tmp` scratch directories. It wrote
`.planning/TRACEABILITY.md` and this section only.
