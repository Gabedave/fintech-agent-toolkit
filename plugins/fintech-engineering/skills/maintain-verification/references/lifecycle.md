# Repository verifier lifecycle

Every repository verifier should provide or clearly document these phases:

1. **Doctor:** validate prerequisites, environment safety, feature-map shape, commands, selectors, and required local dependencies.
2. **Launch:** start only the local or isolated services, application, containers, simulator, or browser needed for proof.
3. **Drive:** exercise the mapped behaviour through its authoritative API, job, storage, browser, or device boundary.
4. **Evidence:** retain feature ID, exact command or scenario, environment, exit status, observable result, and limitations.
5. **Cleanup:** stop what the verifier started and remove privacy-sensitive or temporary artifacts.

For each feature, report:

`feature -> current entry points -> mapped proof -> executed evidence -> clean | changed | blocked | product_regression`

Automated tests may satisfy Drive and Evidence when they exercise the real risk. Mocked UI tests do not prove live backend contracts; unit tests do not prove migrations, runtime wiring, or native behaviour.
