# UI verification evidence

Use this record for changed web or native mobile behaviour. The repository verifier owns the exact launch, test, browser, simulator, and cleanup commands. Select the affected feature and the surface a user touches before running a check.

| Field | Record |
| --- | --- |
| Identity | Exact candidate commit or dirty-diff identity, feature-map ID, and design reference when visual fidelity is claimed. |
| Surface | Local build or development scheme, platform and device or browser and viewport, test identity, and whether external responses are real or repository-owned doubles. |
| Journey | The entry point, user action, expected visible result, observed visible result, and any relevant backend or stored side effect. Include the changed success, failure, retry, cancellation, and back-navigation states that matter to the change. |
| Checks | Exact commands and exit results, plus the runtime drive result. A passing unit test does not stand in for a browser or device step. |
| Artifact | A privacy-safe screenshot, video, trace, or deterministic test result that lets a reviewer inspect the action and outcome. State its location and retain it through cleanup. |
| Verdict | `confirmed`, `partial`, `unverified`, or `failed`, with the untested platform, state, or real contract named explicitly. |

Check one affected platform for a platform-specific change. For shared UI, cover each platform whose rendering or navigation can differ, or label the untested platform `unverified`. On web, exercise the relevant desktop and narrow viewport when layout can change. On mobile, inspect safe areas, small screens, and large text when layout can change. Check keyboard or assistive focus when controls, dialogs, or navigation change.

For exact visual-parity claims, capture a fixed baseline before the change and compare equivalent states, data, fonts, viewport, and scale with an image diff. Keep baseline changes separately reviewable. Ordinary UI work needs a design-reference comparison and inspectable visual evidence, not a zero-pixel-diff gate.

Use isolated non-production identities and safe data. Keep customer records, credentials, biometric material, payment references, and sensitive traces out of evidence and pull requests. If the app or required device cannot run, record the blocker; do not label a source test or another platform as runtime confirmation.

## Publish review captures

Keep generated review captures in ignored or temporary storage. By default, publish them as labeled GitHub PR attachments; commit images only when they are intentional maintained assets or the user explicitly requests repository storage. Carry the evidence record above into the PR description and final handoff, including the captured revision, synthetic-data context, and limitations.

1. Select the user's explicit upload method first. An explicit browser method goes directly to authenticated browser upload; CLI source is `none` and capability is `not-applicable`. When the method is unspecified or CLI is selected, inspect `gh pr create --help` or `gh pr edit --help` for `--attach`. When that native capability is established and fits the selected method, invoke it directly with `--body-file` and repeated `--attach` flags; creating a redundant upload helper adds no capability. Markdown references to those local paths are rewritten to uploaded URLs; preserve descriptive labels. Unknown support requires discovery first. See [GitHub's attachment documentation](https://docs.github.com/en/github-cli/github-cli/attaching-files-with-github-cli).
2. If the installed CLI lacks attachment support, check the official current CLI. Use a checksum-verified official binary in temporary storage when installation is authorized; otherwise use an available authenticated browser upload or report the concrete limitation. Honor the user's selected upload method. After a stalled upload, inspect what saved before retrying; reuse confirmed uploads and upload only missing files. Switch to a supported alternative after a repeat failure rather than repeating an unchanged transfer.
3. Read back the hosted PR description and confirm every expected label has a persistent attachment URL, with no local paths or upload placeholders remaining. Verify each image renders in the authenticated PR view. For private repositories, verify access in each destination repository's scope before reusing an attachment across PRs.
4. Retain the originals and existing evidence until the replacement attachments and context are verified. If verification is blocked, report the missing check and keep the evidence. Remove obsolete committed captures only as a scoped normal commit after verification, preserving history and any intentional maintained assets.
