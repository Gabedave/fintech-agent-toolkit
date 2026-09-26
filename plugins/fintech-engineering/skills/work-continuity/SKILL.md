---
name: work-continuity
description: Preserve compact, privacy-safe decision and resume state for long-running, multi-session, cross-repository, or handed-off fintech work. Use automatically when continuity risk is material; do not mine transcripts or commit local notes by default.
---

# Work Continuity

Make consequential work resumable without requiring another engineer or agent to reconstruct the entire conversation.

## Start or resume

Read [references/resume-record.md](references/resume-record.md). Define a checkable finish predicate, current repository and worktree identities, authorization boundary, highest-risk unknown, and next safe action. When resuming, verify the recorded branch, commit, diff, checks, and external state instead of trusting stale notes.

## Record only consequential state

For a long iteration, record the hypothesis or decision, why it was selected, evidence, result, and keep/revise/discard outcome as it happens, not as a reconstructed success story at the end. Keep one canonical trail. Log consequential choices, completed verification checkpoints, pivots, reverts, and blockers; skip trivial actions. Refresh the resume capsule after a material design decision, failed direction, repository handoff, external wait, or before pausing.

Keep the trail local by default, outside the committed product tree unless the repository defines a safe ignored location. For team-owned continuity, prefer an authorized issue-tracker item, PR, or task handoff. Publish a sanitized trail only when reviewers need it to assess the result of ambitious work and publication of that artifact is authorized; a commit or push request alone does not authorize publishing private notes. Never copy raw transcripts, credentials, customer or provider data, unrestricted logs, or private messages into the record.

When a checkpoint makes a lasting architectural choice, apply [the decision-record policy](../architect/references/decision-records.md) and link the repository ADR from the trail instead of treating the trail as the permanent design record. Before handoff, resolve evidence links and spot-check consequential entries against actual artifacts. Send needed trail evidence through the existing `$pre-push-review` gate after implementation; do not introduce a second review workflow or mine transcripts.

Creating or updating an external team record still requires authorization. This skill does not authorize commits, pushes, ticket edits, messages, merges, deployments, or production changes.
