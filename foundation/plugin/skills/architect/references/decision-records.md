# Engineering decision records

Preserve the rationale a future engineer needs, not a transcript of the task. The shared toolkit owns this policy and its template; the repository that owns the decision owns the record.

## Choose the smallest useful record

| Record | Trigger | Home |
| --- | --- | --- |
| PR rationale | Bounded implementation choices within an established design | The authorized PR description, or the task handoff if no PR is requested |
| Decision trail | Long-running, multi-session, cross-repository, or handed-off work with consequential checkpoints | One working record through `$work-continuity`; local by default |
| Architecture Decision Record (ADR) | A new or changed durable decision meeting a condition below | The owning repository, reviewed alongside the change |

A trail explains how work progressed; an ADR explains why the system should retain a choice. One can link to the other but does not replace it. Neither is required for trivial mechanical work.

## When an ADR is required

Record a decision when it does any of the following:

- Establishes a lasting architecture, dependency, operational convention, or ownership constraint that future changes must respect.
- Establishes or changes a contract across components or repositories.
- Chooses among meaningful alternatives with material security, authorization, financial-correctness, data-integrity, or recovery consequences.
- Accepts a trade-off that is costly to reverse or that a future maintainer could mistake for an oversight. Include departures from a preferred design forced by measured constraints or failed approaches.
- Replaces or invalidates an accepted architectural decision.

Touching a sensitive file, adding a schema field, crossing a function boundary, or spending a long time on a task is not sufficient by itself. Skip a new ADR for routine maintenance, straightforward bug fixes, mechanical migrations, or implementation already dictated by an accepted ADR; link the existing decision where relevant. Work of any size can still need an ADR if it makes a new durable choice.

## Classification precedence

Classify the requested outcome, not the amount of uncertainty in the task. Apply the first matching rule:

1. **No durable decision is being created:** use `not-required:none`. This includes a read-only investigation, diagnosis, explanation, or review that does not itself establish or change a lasting choice. Uncertain rationale or incomplete historical evidence affects the findings, not this ADR disposition. It also includes routine work covered by an existing design.
2. **The request already establishes a trigger above:** use `required:owning-repository`. For example, a requested cross-component contract change or replacement of an accepted decision is already durable; discovery determines the record's evidence and content, not whether the record is required.
3. **A requested change may establish a trigger, but that depends on discovery:** use `assess-after-discovery:undetermined`. Reserve this for unresolved change scope or consequences. Do not use it for a read-only task merely because historical evidence is incomplete, or for a trigger the request already establishes.

Assess this during design and revisit it when evidence changes the approach and before final review. Candidate-final implementation must resolve it as `ADR required: <path>` or `ADR skipped: <concrete reason>`. An unresolved required record is a review blocker, not a reason to claim it was skipped.

## Ownership and lifecycle

1. Read related ADRs and the repository's existing decision convention before designing. Check status and superseding links; do not silently override an accepted constraint or assume it is still correct despite contradictory evidence.
2. Follow an existing repository convention. Otherwise use `docs/decisions/YYYY-MM-DD-short-title.md` and the [ADR template](../assets/adr-template.md). Use a distinct descriptive slug when dates collide; never overwrite another record. Do not scaffold empty directories or duplicate the shared policy into every repository.
3. Keep one canonical ADR in the repository owning the affected contract or system. Cross-link it from affected repository documentation and authorized PRs rather than copying its text. Shared engineering-policy decisions belong in the toolkit, not the local workspace-control folder. If ownership cannot be resolved from evidence, raise that specific question before publishing the record.
4. Draft the record as `Proposed`, alongside the implementation when file edits are authorized. A read-only investigation or design pass may recommend or present a draft in the response but must not write files. Record the evidence and trade-offs while deciding; update the proposal to match what is actually implemented before review.
5. Obtain the owning repository's normal review and any affected contract-owner review. Mark `Accepted` only after the required approval is evidenced. Approval of a design does not authorize commits, pushes, PR creation, merging, or deployment.
6. To change an accepted decision, create a new proposal linking `Supersedes` to the old ADR. Only once the replacement is accepted, mark the old one `Superseded` and add a reciprocal link. Preserve the old rationale; do not rewrite it to imply the new choice was always intended. A rejected proposal is `Rejected`, with the rejection reason and evidence. Record a real review reference; never invent approval.

## Content and evidence

Aim for one page: context and constraints, selected decision, meaningful alternatives and why they lost, accepted consequences, evidence, and conditions for reconsideration. Include compatibility, rollout, and rollback when they matter. Reuse the design rationale; do not maintain a second competing design document. Link caller-facing sketches or existing specifications instead of copying large sections.

Evidence should be resolvable code, tests, measurements, issues, or PR references. Preserve failed approaches when they explain a consequential constraint. If reconstructing an older decision, distinguish contemporaneous evidence from inference and leave unknowns explicit. Never manufacture a history or mine private transcripts.

Keep credentials, customer and provider identifiers, unrestricted logs, and private messages out of records. Use privacy-safe summaries and references; a link must not expose a secret in its URL. A local trail must be sanitized and explicitly authorized for publication before it enters a team system or committed tree. A normal push request does not by itself select private working notes for publication.

## Final review

`$pre-push-review` checks the ADR assessment against the actual diff, not just the author's claim. For a required ADR, verify its owner and location, decision/evidence alignment, alternatives, consequences, reconsideration conditions, truthful status, and superseding links. For an existing ADR, verify that it still covers the change. For a trail, spot-check consequential entries and evidence links without reading transcripts. Missing proof remains unresolved.
