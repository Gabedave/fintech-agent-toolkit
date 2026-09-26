# Fintech engineering agent toolkit

Codex skills for investigating, designing, changing, verifying, and reviewing fintech software. The plugin provides shared engineering workflows; each adopting repository supplies its own instructions, verification commands, risk map, and environment boundaries.

This is a company-neutral adaptation of a private fintech engineering toolkit. It contains no product code, credentials, provider configuration, or repository-specific verification maps.

## Install

1. Clone this repository.
2. Add its marketplace to Codex:

   ```sh
   codex plugin marketplace add /absolute/path/to/fintech-agent-toolkit
   codex plugin add fintech-engineering@gabedave
   ```

3. Start a new Codex task to load the installed skills.

## Skills

- `fintech-mode` routes a task to a proportionate playbook and records its authorization boundary.
- `how` traces current runtime behavior before a substantial change.
- `why` reconstructs historical intent when it can affect a decision.
- `blast-radius` maps affected repositories, contracts, data, tests, and operations.
- `architect` designs high-impact contracts and domain boundaries.
- `maintain-verification` checks that repository verifiers still prove their claims.
- `work-continuity` keeps long-running work resumable with privacy-safe records.
- `pre-push-review` performs an independent, evidence-backed review of candidate changes.
- `ci-babysit` follows the latest pull-request revision through checks and review.
- `reflect` proposes improvements after demonstrated workflow friction.

The router keeps small mechanical edits small. High-risk work adds explicit ownership, state, retry, recovery, and observability proofs. Non-trivial implementation defaults to reviewed pull-request delivery and CI follow-through; local-only instructions narrow that path. Merge, deployment, production mutation, and team communication remain separate authorization boundaries.

## Adopt in a repository

Add a short root `AGENTS.md` identifying the product, its repositories and release branches, local verification entrypoints, critical flows, and safe test environments. Put executable product proof in repository-owned `verify-*` skills or scripts. See [the example adoption guide](docs/adoption.md) and [operating model](docs/operating-model.md).

## Validate

```sh
python3 scripts/validate.py
python3 scripts/evaluate.py
python3 scripts/evaluate_behavior.py --check
python3 scripts/evaluate_review_quality.py --check
python3 -m unittest discover -s tests -p 'test_*.py'
```

The deterministic checks run in CI. See [release guidance](docs/releasing.md) for model-backed checks against an installed candidate and the included synthetic routing workspace.
