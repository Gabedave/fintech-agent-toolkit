# Build company plugins from one pinned fintech foundation

- Status: Proposed for repository review
- Owner: Toolkit maintainers and adopting company owners
- Date: 2026-10-18

## Context

Independently copied workflow bodies drift, while installed plugins can lag their canonical source. Passing policy-selection fixtures does not show that an agent ran evidence before editing, included a storage test in CI, verified an aggregate gate, published inspectable evidence or completed PR delivery.

## Decision

Keep shared native Codex skill sources, portable helpers, a small standard-library renderer and the shared conformance corpus in `foundation/`. Company profiles declare identity, discovery hints and a bounded delivery default. Render self-contained plugins at build time; no runtime network dependency or automatic upgrades. Product repositories retain commands, feature/risk maps, provider semantics, accounting rules and operational authority.

Each adapter pins the foundation repository, exact source commit, version and content digest. Generated plugin content carries installation-safe provenance. The root lock covers the complete generated file set; regenerate into temporary output and compare bytes in CI. Generated files are distribution artifacts, not another manually edited source. A declared commit label needs independent source attestation; the renderer does not authenticate it. Final candidate Git identity is recorded outside the generated tree to avoid self-reference.

Preserve fintech invariants: known/unknown outcomes, idempotency, authoritative ownership, transaction integrity, identity/state fencing, recovery and reconciliation. Bound transient resources and per-operation work without deleting durable financial or recovery truth. Use independently fixed expectations, truthful pre-edit chronology and exact-revision evidence. Company guidance may strengthen requirements and narrow authority; a profile cannot supply arbitrary safety patches.

## Alternatives

- Continue copying: simplest initially, but no deterministic shared-source or drift boundary.
- Runtime dependency/plugin inheritance: avoids generated copies, but adds availability, compatibility and host-resolution assumptions.
- General policy service or cross-agent framework: unjustified operational and conceptual cost for this bounded distribution problem.

## Verification and adoption

Keep cheap deterministic and regeneration checks in toolkit CI. Preserve repository-owned installed-candidate and paired source-review gates. The shared action harness uses disposable native installations, restricted tool access, synthetic storage/hosting and an independently pinned oracle. Evaluator sensitivity controls alone do not prove candidate compliance. Synthetic CI cases do not activate or prove product-repository enforcement.

Upgrade through a reviewed pin/profile change with a compatibility note, complete conformance evidence and a fresh task after an authorized installation. Installation, publication, merge and deployment remain distinct actions. A public baseline cannot claim an adopter's full acceptance approval or product integration. Roll back the pin/profile/generated output together to the previous reviewed snapshot; no product-data migration is involved.

Revisit only if multiple real consumers require runtime composition, shared-source drift repeatedly escapes required regeneration checks, or measured evaluation cost exceeds the value of the current release corpus.
