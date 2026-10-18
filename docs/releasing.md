# Release process

1. Run the deterministic validation commands in the README and the official Codex skill and plugin validators.
2. Review the complete diff for company identifiers, private URLs, secrets, customer data, and product-specific commands.
3. Update the semantic version in `plugins/fintech-engineering/.codex-plugin/plugin.json` and summarize material changes.
4. After committing the candidate, create a synthetic example workspace with `python3 scripts/prepare_example_workspace.py /absolute/path/to/new-fixture`. Run `python3 scripts/release_smoke.py --repo /absolute/path/to/new-fixture/backend` against that clean checkout. Add `--review-quality` when review guidance changes. The example tests routing only; it does not prove product behavior.
5. Publish a reviewed tag. Consumers should install a reviewed release and start a new Codex task.

Model-backed results are evidence for the tested version and example only. They do not prove an adopting product's runtime behavior; each product repository must provide its own verification.

## Foundation and action evidence

Run `python3 scripts/check_foundation.py` before repository checks. The adapter lock binds the reviewed foundation source; it is not the final candidate Git identity. Review both shared source and company profile changes, preserve user restrictions, and record installed content plus fresh-task identity in disposable state. Never update an active user installation as a side effect of verification.

Run the shared observed-action harness against the independently fixed external expectations and contract before release. Its `--check` mode establishes evaluator sensitivity only. Retain actual raw synthetic tool/state evidence and all scored failures, with exact model, harness, profile, environment and candidate identities. A public baseline run has unverified contract binding and is not full acceptance. Product selector/shard and aggregate enforcement remain explicit integration gaps until demonstrated in the owning product repositories.

Keep review-only reports and captures in the PR description/attachments and temporary or ignored local storage. Maintained design decisions, runbooks and intentional assets remain normal source files. Report what is active, what still requires installation/configuration, and the next integration step.
