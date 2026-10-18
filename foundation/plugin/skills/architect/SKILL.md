---
name: architect
description: Design caller-first {{AUDIENCE}} interfaces and domain boundaries before high-impact implementation. Use automatically for public contracts, schemas, shared state, authentication, money movement, cross-repository seams, and substantial refactors; do not edit production code during the design pass.
---

# Architect

Turn a grounded current-system model into a reviewable design decision. Preserve product intent and authorization; architecture work does not authorize implementation.

## Establish the design problem

1. Use the output of `$how`, or run it when no fresh current-system model exists.
2. State the caller-visible outcome, constraints, invariants, compatibility window, failure and recovery behaviour, and the data model that must remain valid.
3. Identify the public seams, owners, mutable state, deployment order, and verification surface.
4. Read [the decision-record policy](references/decision-records.md) and related repository ADRs. Decide whether this work introduces a durable choice, not merely whether it touches an architectural boundary.

## Compare real alternatives

Read [references/design-record.md](references/design-record.md). Produce at least two materially different designs unless only one is technically viable and explain the disqualifying evidence. Show the caller-facing types, requests, events, or module interface before internal implementation details.

Compare alternatives against correctness, invalid-state prevention, boundary clarity, compatibility, failure recovery, operability, verification cost, migration burden, and reader load. Prefer subtraction or a clearer domain shape over an extra compatibility layer when policy permits it.

## Commit to a falsifiable design

Select one design and record rejected alternatives and trade-offs. Define evidence that would invalidate the decision. If implementation later produces repeated workarounds, duplicated state, unclear ownership, or an inability to test the seam, stop and redesign rather than normalizing the friction.

When the policy requires an ADR, reuse this rationale in the owning repository's record as part of authorized implementation; a design-only pass returns the proposed record without writing it. Otherwise keep the rationale in the task handoff or authorized PR. Reassess if implementation reveals a new durable trade-off.

For contested or high-risk designs, include the decision and rejected alternatives in `$pre-push-review`; do not invoke a separate adversarial-review workflow.
