---
name: blast-radius
description: Map the repositories, contracts, consumers, data, tests, CI, and operational boundaries affected by a proposed {{AUDIENCE}} change. Use before cross-repository, schema, API, event, authentication, payments, or release-sensitive work; keep this pass read-only.
---

# Blast Radius

Produce a bounded impact map before implementation. Do not edit code, create branches, or update tickets during this skill unless the user separately asks for those actions.

## Establish the source of truth

1. Read workspace and repository `AGENTS.md` instructions.
2. Inspect the ticket, comments, linked pull requests, and named user flow.
3. Locate the current producer or entry point, not only files with matching words.
4. Follow runtime calls, imports, API routes, events, queues, persisted fields, feature flags, and deployment configuration outward.

## Check every boundary

For each possible repository, record evidence for inclusion or exclusion:

- contract producers and consumers;
- shared types, payloads, error codes, and state machines;
- schema, migration, backfill, and rollback implications;
- authentication, authorization, privacy, and money-movement boundaries;
- background jobs, retries, idempotency, and external-provider outcomes;
- tests, fixtures, build jobs, release flows, monitoring, and runbooks.

Use [references/repository-discovery.md](references/repository-discovery.md) as a discovery aid, not as proof that every repository is affected.

## Report

Return a compact table with: repository or system, affected seam, evidence, required change, verification, and risk. Separate direct facts from inference and list searches that produced no evidence. Identify an owner and independent PR boundary for every affected repository.

Stop and request direction when product intent or compatibility policy materially changes the correct set of repositories.
