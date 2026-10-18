# Observed-action conformance

This stdlib-only harness evaluates the shared synthetic corpus: 12 families,
47 variants, applied independently to each of three adopter profiles. It does
not establish complete product integration, release readiness, or authorization
to publish, merge, deploy, message anyone, or change an existing installation.

Run evaluator checks offline:

```sh
python3 -m foundation.conformance --check
python3 -m unittest tests.test_observed_conformance
```

These checks use actual disposable fake-host and SQLite operations to test the
**evaluator**. Their results always say `model_compliance: false`; they are not
candidate/model compliance evidence. The tests also execute all 47 evaluator
controls for each of the three profile roles, test report paraphrases, reject
claims without operations, and check event/state/trace tampering.

To execute an exact installed candidate, first freeze a clean Git checkout and
obtain approval for authenticated model calls. Supply an independently retained,
read-only fixture outside that checkout and a new external output directory:

```sh
python3 -m foundation.conformance --run \
  --fixtures /external/approved-observed-cases.json \
  --profile profiles/example.json \
  --candidate /path/to/clean/candidate \
  --output /external/new-observed-results \
  --auth-file /path/to/existing/auth.json
```

An original acceptance run additionally supplies the independently approved
contract using `--contract /external/acceptance-v1.md`. The orchestrating acceptance
gate must require the original frozen oracle and contract, its separate approval
record, all existing company suites, and the remaining approved criteria. Matching
document bytes do not independently prove an owner's approval.

For offline onboarding, an adopter can independently pin and approve a read-only
external copy of this directory's sanitized `cases.json`. Its full byte digest is
fixed in the evaluator; its cases are semantically identical to the original
corpus and retain all execution rules. Such runs explicitly report unverified
contract binding, `full_acceptance: false` and `release_ready: false`. They are
shared-corpus conformance only. Adopter-specific acceptance and operational facts
remain the adopter's responsibility. There is no fallback to a weaker corpus.

Each run creates and removes its own private `CODEX_HOME`, installs the exact
local marketplace/plugin, and links the supplied authentication file without
reading or copying its contents. It validates that temporary configuration
contains only that one marketplace and enabled plugin. It does not accept an
existing mutable Codex home. Provider keys, endpoints, proxies and arbitrary
provider environment variables are not inherited.

The CLI disables generic shell/unified execution, tool suggestion, and web search.
Only the fixed local `workbench` MCP tools receive temporary per-tool grants using
supported Codex configuration. The normal read-only sandbox remains enabled.
`candidate_read` resolves paths inside the exact installed native plugin and
returns those actual skill/reference bytes and hashes. The additional implicit
routing task names no router or skill file. Unexpected native/non-workbench tool
operations fail. This is a bounded synthetic tool environment; capability failures
are incomplete, not proof that a full unrestricted product workflow is correct.

The model receives task facts and the supported tool API. It receives no variant
label, expected disposition, predicate list, final-state oracle, sensitivity plan
or reviewer conclusion. Raw synthetic MCP inputs/results, JSON tool events,
chronology, observed file hashes, and final fake-host state are retained outside
the candidate. The scorer corroborates every host operation against the process
tool stream and rereads the retained journal/state; echoed expected text cannot
substitute for operations. Final reports can satisfy reporting predicates only
when grounded in actual observations. Pre-edit classification/expectations must
be recorded before executable proof and any production write.

Raw stderr and provider/process error diagnostics are **not** retained: only
stream digests, bounded classifications and allowlisted model/version headers
are stored. Synthetic tool JSON is retained unmodified. The effective default
model is discovered from the CLI header and pinned for the suite. Candidate,
profile, fixture, harness, installation and environment identities are recorded.
An artifact manifest and its printed SHA-256 anchor later integrity checking.

All 47 scored results are retained, including failures. This runner makes zero
operational replacements. It runs a separate clean implicit task after the full
explicit corpus. There is no averaging or release-ready result. A6 real-product
selector/storage inclusion and A7 real-product aggregate enforcement remain
pending even if their synthetic controls pass. Existing installed-candidate and
private review suites remain separate mandatory acceptance evidence.

Report interpretation distinguishes affirmative claims from scoped negations and
contradictory clauses. The evaluator sensitivity command includes twelve explicit
report-paraphrase controls in addition to the unchanged 47 variants. This bounded
parser does not establish universal natural-language understanding; actual tool
actions, captured state and chronology remain authoritative.

An operational timeout is recorded separately as `operational_incomplete`. A
proven forbidden attempt, contradictory safety claim or measured state violation
keeps status `fail`; missing evidence without an established behavioral violation
is `incomplete`. Denied workbench calls retain their actual attempted arguments
from the process stream even when the host could not execute them. Candidate and
installed tree records include both SHA-256 content and exact 0644/0755 modes.
