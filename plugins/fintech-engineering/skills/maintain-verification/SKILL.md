---
name: maintain-verification
description: Audit and repair fintech repository verifiers against current source and safe live behaviour. Use automatically when verifier assets or proof boundaries change, a critical feature is unmapped, or verification appears stale; never weaken proof to hide a product regression.
---

# Maintain Verification

Treat repository verification as maintained product infrastructure. During a verifier-only task, change only verifier-owned skills, maps, scripts, fixtures, selectors, and documentation unless the user separately authorizes product changes.

## Audit every feature

1. Read repository `AGENTS.md`, the local `verify-*` skill, its feature map, planner, test configuration, and relevant CI.
2. For each mapped feature, trace the entry points and proof claim against current source, contracts, jobs, routes, native surfaces, and tests.
3. Confirm mapped commands and selectors still exist, run the planner or doctor surface, and execute one safe automated or live pass per feature where the environment permits it.
4. Check for important current behaviour with no feature mapping and for mapped proof claims that no longer exercise their stated boundary.
5. Capture privacy-safe evidence and clean up processes, containers, simulator state, traces, and temporary identities started by the audit.

Read [references/lifecycle.md](references/lifecycle.md) for the required verifier contract and result classification.

## Repair honestly

- `clean`: source, command, proof claim, and safe execution agree.
- `changed`: repair a stale map, command, fixture, selector, or lifecycle instruction, then rerun the affected proof.
- `blocked`: name the missing environment, permission, dependency, or unsafe operation without treating it as passing.
- `product_regression`: report the product failure; do not edit the verifier to accommodate it.

Keep audits local and on demand by default. Add scheduled or cloud execution only when explicitly approved with its Actions cost, privacy boundary, and maintenance owner.
