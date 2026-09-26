## Summary

<!-- What changed and why? -->

<!-- For non-trivial implementations: ADR required: <path>, or ADR skipped: <concrete reason>. Link an existing ADR when it already covers the change. -->

## Verification

- [ ] Deterministic validation and evaluation passed.
- [ ] Official Codex skill and plugin validation passed when plugin files changed.
- [ ] For plugin-behavior changes, `scripts/release_smoke.py` passed every scenario against the exact clean candidate commit; version, commit, and pass count are included below.
- [ ] For review-gate/evaluator changes, the local `--review-quality` pilot passed all configured broken/fixed pairs; actual model-call, detection, fixed-control, false-blocker, and elapsed-time counts are included below (otherwise N/A).
- [ ] Product-specific commands and proof remain in their owning repositories.

<!-- Paste concise command/result evidence. -->
