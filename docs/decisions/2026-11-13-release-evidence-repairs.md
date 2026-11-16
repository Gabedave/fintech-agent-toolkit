# Release evidence and operation prerequisites

Status: implemented design decisions; release qualification is a separate gate.

## Authority and workflow

State-changing operations require the existing authorization ledger and current domain prerequisites. Read/validate operations assess those prerequisites. Inspection and assessment remain read-only except for separately requested changes. Attachment-method defaults apply within existing publication authority; a storage exception authorizes only its named operation. Merge, release and active installation require their own authority.

One inspectable authorization ledger retains all action classes, required structured fields and separately named actions, including unavailable delivery stages. Delta reporting avoids repeated permission recaps. Lazy playbook loading, focused verifier maintenance, direct status reads, one combined-tree verification owner and strict evidence invalidation remain the workflow boundaries. Status-only requests and verifier repairs reach their existing workflows directly; explicit browser publication skips irrelevant CLI discovery. Investigation handles one status pass; long-running handles monitoring to a persistent finish condition, with the existing CI check/monitor modes and authorization limits. The single-pass path does not require continuity.

Initial review findings use `pending` until a remediation response has been reconsidered. Readiness of the requested subject, lifecycle state and permission to change that state are separate conclusions.

## Authoritative state and financial identity

The observer distinguishes diagnostic events from tool requests. It compares complete authoritative ownership and ledger rows and schemas, retaining database copies and hashes. SQLite byte changes alone do not establish financial mutation. Ownership readbacks identify their SQLite store and committed ledger rows; an empty JSON resource ledger does not establish absence of every durable posting. Readbacks identify field producers and resource-store mirrors so supplied history/status observations remain distinct from host defaults. Missing or unsettled evidence remains unknown.

Ownership-probe inputs are validated before SQLite writes; healthy and seeded databases retain distinct identities. The synthetic financial host rejects missing or malformed authoritative identity before validation or posting. Existing subject, owner and fence fields must be present and correctly typed, preventing absent fields from matching each other to produce a null-subject posting. The same predicate bounds possible effects without introducing extra identity fields, amount ranges or identifier formats.

Authored PR evidence fields enter reporting through projection version 2; historical version 1 manifests retain their interpretation. Native operation journals without host sequence IDs retain their native format; only host records enter the host lookup. Native capture recognizes documented Git global options before classifying push/merge attempts and retains item-updated report and request phases. These negative-evidence controls do not expand the separately pinned positive-read parser or admit unsupported reads.

## Versioned attachment acceptance

Acceptance amendments require external acceptance-owner approval; that approval does not grant release authority. Versioned tasks, fixed oracle identities and fixed review identities select matching evidence. Historical receipts cannot qualify a different version, and affected baselines and candidates require reevaluation.

The original v1 control requires a new upload despite valid hosted evidence. The approved v2 corpus separates missing-hosted-evidence upload from verified reuse; reuse rejects another upload. Both preserve image, URL, revision, label, rendering/access, chronology and preservation requirements. The approved v3 overlay explicitly requests publication in those positive cases. Hosted readback precedes rendering/access verification, and an earlier correct PR write need not be repeated. Verified attachment evidence and correct terminal linkage to the fixture's draft PR are both required before completion. Independent review rejects unsupported or premature completion claims. Unaffected cases and all earlier versioned artifacts and outcomes remain unchanged.

Development lifecycle controls remain development evidence. Model collection uses the shared versioned `foundation.conformance --run --fixtures ...` entrypoint; the unused experimental attachment collector is retired to avoid a separate unqualified collection path.

## Source-bound probes

The generic semantic probe names its isolated in-memory duplicate-row fixture and states that it executes neither production code nor the provider timeout/retry path. The observed runner requires the workbench MCP server at startup so an optional pending server cannot silently disappear. This changes neither permissions nor acceptance criteria.

The named pre-edit `test_unknown_outcome_replay` executes the exact trusted synthetic settlement baseline against a local provider that commits before losing its first response. Retry commits a second debit; an independent reopened file-backed SQLite connection reads both effects. Evidence identifies the test, source hash and synthetic scope. Captured source bytes must match the trusted baseline before execution; edited or unrecognized source cannot execute through this probe or be reported as verified. The frozen case requires the named pre-edit test, makes a production write optional and does not require a verified repaired implementation.

Positive refactor controls similarly bind to the editable synthetic settlement baseline. The host captures and verifies source bytes before fixed assertions exercise its invariant boundaries and controlled unsafe variants. Changed or missing source is unavailable: pre-edit evidence cannot certify a later authored repair. Generic probes retain their separate scope, and absent product profiles remain absent.

Unavailable-evidence verification accepts the original semantic probe or a corroborated same-run facts read containing the exact trusted unavailable evidence. Strict content, initial/final state and capture checks, plus independent blocker-report review, remain mandatory. Probe descriptions and reports identify local database/file effects. These controls add no production dependency, permission grant or ordinary plugin workflow gate.

## Native result custody and review inputs

Native evaluators retain the original attempt's prompt, schema, stream, final result and process disposition outside the candidate. Raw provider diagnostics are excluded. Scoring parses bytes retained at capture, verifies their sealed digest and binds the usable-result marker to that snapshot. Later output replacement, missing-at-capture late output, symlinks and retained-file tampering cannot silently substitute a scored result.

A complete usable result is scored once, including after a later nonzero exit or timeout; unsuccessful process evidence remains retained. A usable unfavorable result cannot be rerun for replacement. No-capture behavior and operational replacement limits remain unchanged.

Read-only native transport uses the approved variant-task selector for prompt text, task digest and scoring comparison. Unapproved task edits are rejected before fixture preparation. Native behavior and source-review runners supply the unchanged schema as final-response format data, keeping operational commentary separate from final decisions. A dependency-free validator enforces the original schema vocabulary before semantic scoring. Invalid parsed objects are known failures without operational replacement; existing handling of non-object or undecodable results remains. Intermediate messages, final raw results, actual effective prompts and the transport helper remain bound evidence. Transport retains one model call per native case.

Optional review-input capture retains hashed context for the selected installed plugin, catalogue readback, verifier inputs and safe invocation environment, and passes that context explicitly to child evaluators. Each attempt captures actual fixture bytes and inventories before execution and before temporary-workspace cleanup; changes and gaps remain separate from the scored result. Shared installation inputs are captured once per suite. Ordinary plugin use and calls without review-input capture retain their existing behavior.

## Model, environment and policy identity

Opt-in release collection reuses the conformance collector for one shared non-JSON model probe, retains its safe observed header and provenance, and pins both evaluator commands to that observed model. Missing task headers remain null; shared-probe evidence is labelled separately. Exact installation, suite and attempt environment digests and transitions remain visible. Task runtime drift, wrong model pins, conflicting headers, tampered probes and unsuccessful probes remain gaps. The additional probe is shared by the suite; ordinary plugin use and the no-capture path remain unchanged.

Verification callers may select reasoning effort. Observed runs and native runs with claim-review inputs establish the requested setting through the existing capability probe and retain explicit task settings with resolved model identity. Other native runs retain explicit invocation settings without shared-probe proof. Omission preserves defaults, model-alias behavior and probe counts; user configuration and permanent installation remain unchanged.

Disposable installations preserve ordinary security policy and rules without forced tool grants. Preparation and verification inspect the complete rules directory structure, reject unsupported symbolic links or unreadable traversal, and copy and verify regular nested rules. These checks govern disposable verification admission without adding model calls or ordinary plugin approvals.

## Reporting and qualification

Reports derive summaries from performed work and collected evidence, keeping each subject/environment, operation and observed result together through recaps. Claims retain actor, revision, store and evidence layer; required identifiers are copied in full. Safety guarantees identify their enforcing function/condition, and causal explanations require evidence. Authorization, current state and execution history remain distinct.

Reports distinguish test discovery from executed assertions, reads from mutations and local probe effects from unrelated host counters. Test-ledger postings and provider-stub calls are financial and provider operations in their test environments; those definitions do not change owned-test authorization, live-action authority or domain prerequisites. Relevant absence findings retain actor, store and evidence limits. Handoffs report the requested outcome, actual effects, verification and blockers, including requested delivery stages left undone and why, without unrelated no-action inventories.

Whole-report sealing and independent claim review remain external to the plugin. Missing or altered evidence cannot establish qualification. Source checks and deterministic regressions do not establish behavioral remediation: fresh source review, regression controls, current-candidate live evidence and exact-head CI remain required. Frozen tasks, acceptance criteria, schemas, scorers and replacement rules remain unchanged except for the explicitly owner-approved versioned attachment amendments.

Historical raw records and outcomes, including failures and interrupted attempts, remain retained. Harness repairs cannot erase attempted invalid actions, unsupported claims or unfavorable results, and cannot retroactively establish capture equality or qualification. Every new candidate must earn fresh evidence; release and installation authority remain separate.
