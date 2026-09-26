# Release process

1. Run the deterministic validation commands in the README and the official Codex skill and plugin validators.
2. Review the complete diff for company identifiers, private URLs, secrets, customer data, and product-specific commands.
3. Update the semantic version in `plugins/fintech-engineering/.codex-plugin/plugin.json` and summarize material changes.
4. After committing the candidate, create a synthetic example workspace with `python3 scripts/prepare_example_workspace.py /absolute/path/to/new-fixture`. Run `python3 scripts/release_smoke.py --repo /absolute/path/to/new-fixture/backend` against that clean checkout. Add `--review-quality` when review guidance changes. The example tests routing only; it does not prove product behavior.
5. Publish a reviewed tag. Consumers should install a reviewed release and start a new Codex task.

Model-backed results are evidence for the tested version and example only. They do not prove an adopting product's runtime behavior; each product repository must provide its own verification.
