# Release process

1. Run the deterministic validation commands in the README and the official Codex skill and plugin validators.
2. Review the complete diff for company identifiers, private URLs, secrets, customer data, and product-specific commands.
3. Update `plugin_version` and the adapter revision in `profiles/gabedave.json`, then regenerate from the reviewed foundation pin. Do not hand-edit the generated manifest. Summarize material changes in the pull request.
4. After committing the candidate, create a synthetic example workspace with `python3 scripts/prepare_example_workspace.py /absolute/path/to/new-fixture`. Run `python3 scripts/release_smoke.py --repo /absolute/path/to/new-fixture/backend` against that clean checkout. Add `--review-quality` when review guidance changes. The example tests routing only; it does not prove product behavior.
5. When separately authorized, publish a reviewed tag. Consumers install a reviewed release only with installation authority and start a new Codex task. Passing checks alone grants no merge or deployment authority.

Model-backed results are evidence for the tested version and example only. They do not prove an adopting product's runtime behavior; each product repository must provide its own verification.

## Foundation and action evidence

Run `python3 scripts/check_foundation.py` before repository checks. The adapter lock binds the reviewed foundation source; it is not the final candidate Git identity. Review both shared source and company profile changes, preserve user restrictions, and record installed content plus fresh-task identity in disposable state. Never update an active user installation as a side effect of verification.

Run the shared observed-action harness against the independently fixed external expectations and contract before release. Its `--check` mode establishes evaluator sensitivity only. Retain actual raw synthetic tool/state evidence and all scored failures, with exact model, harness, profile, environment and candidate identities. A public baseline run has unverified contract binding and is not full acceptance. Product selector/shard and aggregate enforcement remain explicit integration gaps until demonstrated in the owning product repositories.

Keep review-only reports and captures in the PR description/attachments and temporary or ignored local storage. Maintained design decisions, runbooks and intentional assets remain normal source files. Report what is active, what still requires installation/configuration, and the next integration step.

Before publishing an adapter, make its exact foundation source commit retrievable from the authorized canonical foundation repository. Preserve that commit in reviewed history or a reviewed immutable source reference; source and generated-plugin release identities are distinct. Squash or rebase can change commit IDs. If a pin changes, regenerate and reverify the distributions rather than relabeling a lock. Local candidate commits are not published source references, and none of these steps grants publication authority.


## Independent prose-claim review

Action/state evidence and prose claims are separate required checks. Seal the
complete raw notes, intermediate messages, final report, tool stream and state
before a context-isolated, non-implementing reviewer applies the pinned
[claim-review rubric](../foundation/conformance/claim-review-rubric-v1.json) and
[receipt protocol](../foundation/conformance/claim-review-protocol-v1.json).
A combined per-case pass requires both complete action/state evidence and a
complete confirmed receipt bound to that exact run and candidate. Follow the
[collection and reconciliation commands](../foundation/conformance/README.md);
collection alone does not complete independent claim review. Keep receipts,
raw evidence and the trusted index outside candidate trees and hidden from the
scored model. Retain prior usable failures and separate reconciliation records.

The trusted caller must verify the reviewer's actual platform assignment,
independence, sender and returned receipt/input identities, then pin the external
index digest. The program validates those bindings; arbitrary JSON, a file path,
a hash, or self-reported approval cannot authenticate a reviewer. Missing,
untrusted, stale, partial or uncertain review remains incomplete; any established
violation remains failed regardless of a favorable or missing receipt.

Adopters appoint their own independent acceptance owner and trusted index issuer.
The public protocol-instance compatibility key is not adoption approval or a
verified private-freeze preimage. Public rubric/protocol/control hashes are
reproducible without private approval metadata. Public baseline runs retain
`contract_binding: unverified`, `full_acceptance: false` and
`release_ready: false`. A task with separately approved private acceptance inputs
must also verify its original frozen criteria and approval in its final gate;
the public derivative cannot substitute for those inputs.

## Official validator recovery

Match official validator source to the Codex runtime. For Codex CLI 0.151.0, the
historical official sources are
[validate_plugin.py](https://github.com/openai/codex/blob/78c290807ce710180111df227df3b7a4fe845452/codex-rs/skills/src/assets/samples/plugin-creator/scripts/validate_plugin.py)
and its required
[identifier_validation.py](https://github.com/openai/codex/blob/78c290807ce710180111df227df3b7a4fe845452/codex-rs/skills/src/assets/samples/plugin-creator/scripts/identifier_validation.py)
at `openai/codex` commit `78c290807ce710180111df227df3b7a4fe845452`
(`rust-v0.151.0`). If they are absent from the installed skill bundle, recover the
unchanged pair into external review storage, verify source hashes, and record the
validator, Python and required PyYAML dependency identities with exact-candidate
results. Do not vendor review tooling or evidence into the candidate.

This historical validator covers compatibility manifests, not every newer format.
Retain specification checks, official skill validation, native installation and
readback, and behavioral gates. For a changed runtime or format, establish a
matching applicable validator. A missing or unsuitable official check remains
incomplete and blocks release; an older validator is neither a replacement for
new-format coverage nor a waiver.

## Targeted development checks

For a bounded change with known impact, select affected cases and named regression controls:

```sh
python3 scripts/release_smoke.py --development --scenario <affected-id> --scenario <control-id> --repo /path/to/clean/fixture
```

Record why the selection covers the changed behavior. The command retains candidate/fixture identity, disposable-state setup and per-call limits, and prints selected and omitted IDs. It does not authorize installation or external model use. Use only a supported, authorized disposable route; stop if isolation cannot be established. A targeted pass is development evidence, not team-ready or release qualification. Full release checks, broad/uncertain routing-change coverage, required review-quality pilots, adverse history and unresolved qualification gaps remain mandatory.
