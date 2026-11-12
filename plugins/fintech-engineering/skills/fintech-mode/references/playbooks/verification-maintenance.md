# Verification maintenance

Read [delivery and authorization](../playbooks.md#delivery-and-authorization) before executing these steps, including direct entry.

1. Run `$maintain-verification` for the affected features and dependent proof boundaries; expand to every feature only for an explicit full audit, shared verifier changes affecting all features, or evidence of systemic drift.
2. Compare mapped entry points and proof claims with current source and tests.
3. Run the verifier doctor/plan surface and one safe live or automated pass per selected feature where available.
4. Classify each feature as clean, changed, or blocked; distinguish product regressions from verifier defects and environment failures.
5. Change only verifier-owned assets during a verifier-maintenance task unless product changes were separately authorized.
