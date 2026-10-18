# Review-quality pilot

This complements routing/authorization smoke tests with actual source review. It is not a second reviewer on product PRs and is not an estimate of general model accuracy.

## Run

Cheap checks (no Codex invocation, network, or third-party Python dependencies):

```sh
python3 -B scripts/evaluate_review_quality.py --check
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

For a review-gate or evaluator change, commit a clean candidate and use the existing release runner:

```sh
python3 scripts/prepare_example_workspace.py /absolute/path/to/new-fixture
python3 -B scripts/release_smoke.py --repo /absolute/path/to/new-fixture/backend --review-quality
```

This requires clean toolkit and example backend checkouts, freezes and reports both commits, installs the exact candidate into disposable Codex state, runs every routing scenario, then all five broken/fixed review pairs, and verifies both checkouts stayed unchanged. It does not update the user's installed plugin. Authentication uses the existing release runner's linked file. The inner `evaluate_review_quality.py --run` is for an already installed matching candidate; by itself it does not attest either checkout. Use the release wrapper for PR evidence.

## Proof boundary

- The pairs model bounded transient retention, state refreshed between recovery and finalization, actual producer record formats, retention while delivery is paused, and competing ownership claims. They are synthetic Python programs, not copies of backend code or production-shaped savings tests.
- Existing smoke tests pass both candidates. Independent deterministic counterexamples must distinguish broken from fixed; neutral inputs must agree. These checks prevent broken fixtures from impersonating a reviewer failure.
- Each fresh review sees `README.md`, `before.py`, one variant as `flow.py`, `support.py`, `smoke.py`, and the public JSON replay interface `observe.py`. It receives no variant label, other candidate, expected observations, scoring code, or prior review.
- The harness states execution facts it owns: each fresh model is context-isolated and no repair cycle has occurred. The normal invocation is reviewer attempt one. Across the entire pilot, one operational replacement is allowed only when an invocation produces no usable report; it receives no prior findings, reports attempt two, and cannot delegate again. A scored report is never retried to seek another verdict.
- At least one blocking finding must name the changed faulty location. Every blocker must give JSON input plus complete observed/expected state that reproduces against the pair, including supporting findings such as missing regression coverage. The scorer executes only trusted `observe.py` code with that data. No model-supplied code, wording rubric, or second model judge is used. Humans should still inspect explanations: a valid counterexample does not validate every sentence in a report.
- Every result must include the structured criterion, high-risk invariant, external-evidence, decision-record, verification, independence, consensus, and snapshot record required by the review protocol. The fixture manifest identifies the invariant areas that each pair must prove; an all-not-applicable audit cannot pass.
- Verdicts are monotonic: a reproduced blocker or failed criterion/invariant is `not_ready` even when a separate residual risk is still partial or unverified. `incomplete` applies when unresolved material evidence is the only reason the candidate cannot be accepted.
- Fixed controls must be accepted without Critical/Major blockers. Minor findings do not block. Unsupported extra blockers, incomplete verdicts, invalid JSON, execution errors, or fixture mutations fail the run.
- The ownership pair uses a barrier to produce a deterministic simultaneous start. Its broken implementation permits two successful claims while the fixed implementation permits exactly one; sequential smoke checks intentionally pass both candidates, so a reviewer must inspect or execute the concurrency seam.

## Cost, isolation, and interpretation

All routing and review model calls have 120-second deadlines by default; the release option allows 30–180 seconds and forwards the selected value to both evaluators. Timeout, interrupt, and SIGTERM unwind the evaluator and stop the call's process group. The POSIX release wrapper also bounds installation and evaluator subprocesses, including the one permitted replacement in its aggregate deadline, and forwards termination with a five-second grace period so a nested evaluator can stop its separate model group before disposable state is removed. Uncatchable SIGKILL or host loss cannot guarantee cleanup. Replay and smoke commands have five-second deadlines. No result-seeking retry or partial-pass label exists. At most one failed invocation across the whole pilot receives an operational replacement, avoiding a full ten-review restart while keeping cost bounded. The model subprocess receives runtime/auth-discovery environment keys, not arbitrary provider credentials. Temporary fixture/output directories are removed on normal/error/graceful-cancellation exits; raw Codex diagnostic output is not retained or printed.

The direct evaluator prints each final structured synthetic review for inspection. Each review is instructed to keep local investigation to one smoke run plus the minimum targeted observations, capped at six commands, and to avoid repeated or non-writing-incompatible checks. This preserves the required source, regression, counterexample, and invariant evidence without paying for exhaustive exploration of the bounded fixture. On success the release wrapper prints only the aggregate counts and pass line by default, preventing those complete JSON records from being duplicated into its caller's context. Use `--verbose-review-output` with `--review-quality` when the complete successful records are needed. A failed or timed-out pilot always preserves every completed structured review and count available at failure; compact success reporting never hides diagnostics for an unsuccessful run.

The model uses the existing Codex default unless an explicit `--model` override is supplied. Report the version, exact toolkit and example backend commits, reproduced defects out of five, accepted controls out of five, false-blocked controls, operational replacements used, completed cases, and elapsed seconds. Keep failed runs visible when interpreting results. Passing this small public corpus cannot prove absence of other defects, benchmark secrecy, production behavior, or improvement over an unmeasured baseline. The prompt's read scope is a rule, not a filesystem-security guarantee.

When extending fixtures, keep data synthetic and cases bounded, preserve positive/negative controls, and rerun the live pilot. Product-specific regression tests and verifier mappings remain in their owning repositories.
