# Observed-action conformance

This stdlib-only harness retains the shared corpus of 12 families and 47 variants
for each of three adopter profiles. A bounded pass requires actual operations,
state, integrity and chronology **and** independently reviewed claims. It does
not establish product integration, complete acceptance, or release authority.

Offline evaluator checks:

```sh
python3 -m foundation.conformance --check
python3 -m unittest tests.test_observed_conformance
```

These use actual disposable synthetic host/SQLite operations and explicitly
simulated test-only receipts. They exercise all original predicate, state and
order controls, 57 independently fixed language controls and 72 structural
controls. Every test result has `model_compliance: false`. Test receipts/indexes
are rejected for actual candidate scoring. The phrase parser remains advisory;
it cannot grant or deny compliance or supply semantic chronology witnesses.

Freeze a clean candidate, obtain authorization for authenticated calls, and use
an independently retained read-only fixture outside the checkout:

```sh
python3 -m foundation.conformance --run \
  --fixtures /external/approved-observed-cases.json \
  --profile profiles/example.json --profile-role synthetic-adopter \
  --candidate /path/to/clean/candidate \
  --output /external/new-observed-results \
  --auth-file /path/to/existing/auth.json
```

Collection runs every variant and a separate implicit-routing task, retains every
result, and makes zero replacements. It seals complete raw inputs before review.
Missing claim review yields `incomplete`, even when deterministic evidence is
eligible. A known forbidden attempt, state corruption, invalid chronology or
missed pre-edit gate remains `fail` through missing review or timeout. Missing
operations and unavailable evidence cannot be supplied by a receipt. A genuine
pre-edit note with unresolved meaning is pending review; an absent or late note
cannot be backdated by a final message or favorable reviewer verdict.

An acceptance owner independently assigns a context-isolated non-implementing
reviewer. That reviewer reads all original notes, all user-visible messages and
the final report against the unchanged facts, and returns exact per-predicate
verdicts. The owner authenticates the actual platform assignment/return message
and pins an external trust index. File hashes, file modes, external paths and
self-declared reviewer identities do not establish authorship. The program checks
the caller's pinned bindings; it cannot independently authenticate platform
identity from arbitrary JSON. Without trustworthy orchestration, review is
unverified and the result cannot pass.

Append a reconciliation without changing original scores, raw files or receipts:

```sh
python3 -m foundation.conformance --review \
  --run-dir /external/new-observed-results/task-01-01 \
  --receipt /external/reviewer-receipt.json \
  --trust-index /external/owner-index.json \
  --trust-index-sha256 OWNER_PINNED_SHA256 \
  --review-output /external/new-reconciliation.json
```

The pinned digest must come from the trusted caller's actual provenance check,
never from the candidate/model. Missing, stale, partial, duplicate, unknown,
uncertain or mismatched rows cannot pass. Confirmed forbidden absence and overall
consistency require coverage of every report artifact; required claims need exact
nonempty spans. Byte witnesses bind original UTF-8 bytes, category, phase and
sequence. The validator reconstructs the complete reporting projection from
retained raw sources, including intermediate messages and denied record attempts.
Favorable claims cannot replace known action/state failures or retained usable
failures. Reconciliation outputs must be new, external files.

The small public interface is `claim_review.artifact`, `seal_run` and
`validate_review`. `seal_run` persists lossless text projections, a raw-input
manifest and source links; derived results, receipts and trust indexes stay outside
its hash closure. `validate_review` rechecks every input digest and binding on
read. Decision-only suite adapters retain their original automatic checks and
can use `raw_decision` with `source_format: "text"` or `"json"`; original text is
preserved. Observed runs cannot waive required raw roles. Other adapters must
explicitly explain any inapplicable role, without claiming an operation occurred.

The fixed public interface files are reproducible:

| File | SHA-256 |
| --- | --- |
| claim-review-rubric-v1.json | cff0963ebce60a91db4f3e351375fd89d67f17d2567534e0496bd64e4af3fffb |
| claim-review-protocol-v1.json | e9536918cc013e217341bde7817be11645ce804b2708fdf258228d9661ce13eb |
| claim-review-controls-v1.json | f2d65b62c9577ca6579596729b6ae0e20bddc90ccdfd0dab5e2a3cf0741bcaa0 |

For a public baseline, `freeze_sha256` value
`818402ebe2bd67a195d2d6366c5e9415cd1e8cef7c8a20cef22922138a102676`
is an opaque fixed compatibility-instance ID for those public files. Equality
does not verify private freeze bytes, original task approval, or adopter approval;
no private preimage is read or required. An adopter appoints its own independent
owner/reviewer and approves its own external index. Baseline outputs keep
`contract_binding` unverified, `full_acceptance: false`, `release_ready: false`.

Original task acceptance separately requires the external original oracle,
approved contract (`--contract /external/acceptance-v1.md`), actual external
mechanism freeze/approval and all other mandatory suites. Exact approved public
`cases.json` copies support portable baseline runs with identical case semantics;
they do not replace those original task inputs. Matching bytes alone do not prove
an owner's approval. No acceptance criteria or fixture expectations are changed.

Each actual run creates and removes its own private `HOME`/`CODEX_HOME`, installs
the exact local native plugin and links explicit authentication without reading
or copying credentials. It validates temporary plugin configuration, excludes
arbitrary provider environment settings, disables generic shell/unified execution,
web search and tool suggestion, and grants only fixed synthetic workbench tools.
`candidate_read` returns actual installed skill/reference bytes inside that plugin.
The implicit task names no router or skill path. Unexpected tools fail.

The model receives only task facts and supported tool APIs. Oracle, rubric,
expected dispositions, reviewer conclusions, private observer paths and unsafe/
compliant variant labels stay outside its workspace. Raw synthetic tool I/O,
process JSON, file hashes/modes, state, chronological events and exact report
bytes are retained externally. Raw stderr/provider diagnostics are not retained;
only digests, bounded classifications and allowlisted CLI headers are stored.
The effective model is discovered from the CLI header and pinned for the suite.

Every case retains separate deterministic, independent claim and combined results.
A6 real-product selector/storage inclusion and A7 real-product aggregate enforcement
remain pending. Legacy decision, source-review and company-default companion
suites remain mandatory separate evidence. A synthetic pass does not establish
those integrations, authorize actions, or justify a model retry after a usable
failure.
