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
