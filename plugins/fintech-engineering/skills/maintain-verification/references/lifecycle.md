# Repository verifier lifecycle

Every repository verifier should provide or clearly document these phases:

1. **Doctor:** validate prerequisites, environment safety, feature-map shape, commands, selectors, and required local dependencies.
2. **Launch:** start only the local or isolated services, application, containers, simulator, or browser needed for proof.
3. **Drive:** exercise the mapped behaviour through its authoritative API, job, storage, browser, or device boundary.
4. **Evidence:** retain feature ID, exact command or scenario, environment, exit status, observable result, and limitations.
5. **Cleanup:** stop what the verifier started and remove privacy-sensitive or temporary artifacts.

For each feature, report:

`feature -> current entry points -> mapped proof -> executed evidence -> clean | changed | blocked | product_regression`

For a UI feature, compare the verifier's plan and observed browser or device result with [the shared UI evidence contract](../../fintech-mode/references/ui-verification.md). A doctor that validates paths and commands does not establish the visible outcome.

Automated tests may satisfy Drive and Evidence when they exercise the real risk. Mocked UI tests do not prove live backend contracts; unit tests do not prove migrations, runtime wiring, or native behaviour.

When required tests change, compare the actual CI-collected test identities and shard selectors with the required proof. A path map is insufficient if CI omits the case. Demonstrate the repository aggregate gate with all expected results at the same candidate head. Missing product integration remains a gap even when synthetic toolkit fixtures pass.

## Storage proof plans

A storage plan is complete only when it names the setup, actual adapter calls and observable durable state for each required invariant. Planning-only work proposes these steps; it does not execute them.

1. **Setup:** name the repository-owned backend and adapter and test command when discoverable. If the backend is not implemented, state the missing integration work. Propose a fresh per-test temporary database/file or isolated service database/schema in an authorized test environment, a fresh namespace, deterministic synthetic rows, transaction boundaries and cleanup of only owned resources. Use no production data or credentials. A substitute SQLite fixture proves only that fixture unless SQLite is the actual storage boundary.
2. **Replay:** through the real adapter, commit an operation and its ledger/effect row; close/reopen the store or use a separate connection/process, replay the same identity, and query durable rows for exactly one committed effect and a stable operation outcome. Set arithmetic and mocked success cannot establish this proof.
3. **Fencing:** persist authoritative identity, owner, attempt and fence; advance ownership/attempt, then submit the stale actor through a separate connection/transaction. Query before/after operation, owner/fence and ledger rows to prove rejection, no stale mutation, no partial commit and no extra effect. Include a current-owner success control so rejecting every write cannot pass.
4. **Sensitivity and evidence:** use deterministic coordination for competing transactions when claiming concurrency; record winners/losers and committed state. Show a seeded replay/fencing defect fails. Bind each action and observation to retained adapter/backend identity, schema/seed identity, exact invocation and connection/transaction context, collected test IDs, exit status, raw before/after durable observations, exact candidate revision and limitations. In planning-only work, specify this future retention contract; the proposed evidence does not yet exist.
5. **Collection and limits:** name the intended complete selector and collection invocation using the repository's discoverable framework/configuration; distinguish a known supported command from a proposed one. If the invocation, framework or shard binding is missing, name what must be established. A generic complete-selector label is insufficient. Compare the collected identities to the unchanged required manifest, with zero missing IDs, using omitted-selector and complete-selector controls. In a plan, describe these future collections without claiming they ran. Separately prove actual product CI inclusion and the aggregate gate at the same candidate head; local/synthetic proof does not establish either.

Unavailable adapter execution or durable queries remain planned/INCOMPLETE. A plan, toy check or successful doctor does not become executed storage proof.
