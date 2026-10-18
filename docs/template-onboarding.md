# Adopt the shared engineering foundation

A company can render a native plugin offline from a reviewed, pinned copy of this
repository. `profiles/example.json` is a fictitious Harbor Example adapter. It
requires no company repositories, credentials, services, or tools. Its discovery
paths are unverified hints; the example is not evidence that a company has adopted
the workflow.

## Render and check

Use Python 3 with its standard library. Obtain and review a specific foundation
checkout first. Record its canonical repository, full 40-character Git commit,
foundation version, and source digest in the release evidence. No runtime fetch
occurs. Keep exclusive ownership of the output directory during generation; the
renderer rejects symlink paths and parents. On systems where `/tmp` or `/var` is a
symlink, use its canonical path (`realpath`).

From the foundation checkout, replace `FOUNDATION_COMMIT` with that reviewed full
commit and `/absolute/canonical/output` with a clean, canonical directory:

```sh
python3 foundation/render.py --profile profiles/example.json \
  --output /absolute/canonical/output --source-commit FOUNDATION_COMMIT
python3 foundation/render.py --profile profiles/example.json \
  --output /absolute/canonical/output --source-commit FOUNDATION_COMMIT --check
```

The output contains a native plugin under `plugins/harbor-engineering`, a local
marketplace under `.agents/plugins/marketplace.json`, and `foundation-lock.json`.
The plugin carries `.codex-plugin/foundation-provenance.json`, so its identity and
content hashes remain available after isolated installation. Root lock validation
also checks those provenance bytes. Run the same render in two separate clean
directories and compare the complete outputs before adopting a new pin.

`--source-commit` identifies the **foundation source**, not the later generated
candidate's Git commit. The lock binds that declared pin to a digest of every
foundation source file, including the conformance harness and fixtures (Python
bytecode caches are excluded). The renderer cannot establish that an arbitrary
commit label is authentic: independently verify the checkout and its digest
against the reviewed source. Identify the final candidate revision externally in
release evidence, then compare actual installed bytes and inspect the identity
loaded by a fresh task. Rendering and `--check` alone do not prove installation or
loaded task identity, and do not authorize installation in user state.

The renderer validates all planned paths before writing. Files are replaced
atomically one at a time, with the root lock written last; an interrupted render
must pass `--check` before use. It preserves unrelated output files and rejects
unexpected files inside the managed plugin. Reconcile an older distribution
explicitly rather than deleting unknown files automatically. Each output has
exclusive ownership of a single-profile marketplace and root lock. An existing
marketplace must match the managed identity, sole plugin, and metadata (including
`interface.displayName`); additional entries or custom labels cause refusal before
any write. A lock for another profile or unsupported schema is also refused.
Reconcile those files explicitly, or use a clean output for a different profile.
The renderer does not merge unrelated marketplace metadata. A failed `--check`
performs no writes.

## Profile contract

Copy the example and change only declared fields. Schema version 1 requires every
field below and rejects unknown keys and unsupported schemas. Profile values
cannot add patches, replace safety rules, disable checks, or override acceptance
criteria. Changes to shared behavior belong in the reviewed foundation and need a
new reviewed pin.

| Field | Meaning and constraint |
| --- | --- |
| `schema_version` | Integer `1`. |
| `plugin_name`, `marketplace`, `router` | Lowercase hyphenated identifiers, at most 64 characters. Router names must not collide with another entrypoint. |
| `plugin_version` | Explicit semantic version; never `latest`. |
| `company`, `router_title`, `audience` | Short single-line plain labels, at most 120 characters. No markup, command text, or tokens. |
| `repository_url` | Canonical HTTPS URL of the company adapter's repository, without credentials. |
| `adapter_revision` | Explicit safe identifier for the reviewed adapter revision. |
| `discovery` | Repository role to a nonempty list of relative directory/path/glob hints. Absolute paths, traversal, URLs, commands, and backslashes are rejected. All hints remain unverified until inspected locally. |
| `delivery_default` | `pull-request` or `local-only`. This does not grant publication, merge, or deployment authority. Explicit user restrictions always apply. |

The shared source uses only `{{PLUGIN_NAME}}`, `{{PLUGIN_VERSION}}`,
`{{MARKETPLACE}}`, `{{COMPANY}}`, `{{ROUTER}}`, `{{ROUTER_TITLE}}`, `{{AUDIENCE}}`,
`{{REPOSITORY_URL}}`, `{{DISCOVERY}}`, and `{{DELIVERY_POLICY}}`. Unknown or
unresolved tokens fail generation. JSON is substituted structurally. Delivery
policy text is fixed by the renderer rather than supplied as free-form profile
instructions.

## Local adoption record: incomplete until verified

A company owner must supply the following facts in repository-owned instructions
and local verifier skills. Do not enter credentials or customer data into a
profile. Record each item as **incomplete** until direct local evidence exists.
Do not invent runnable commands, environments, policies, CI checks, or successful
results for this template.

| Required fact | Owner action and evidence |
| --- | --- |
| Adoption owner | Name the accountable engineering owner and who may approve workflow and pin changes. |
| Repository discovery | Confirm repository paths, role ownership, local `AGENTS.md` instructions, and verifier skill names. Inspect hints before using them. |
| Verifier and risk map | Supply actual repository-owned commands for relevant changes and their financial, storage, concurrency, authorization, and operational risks. Record command results before applicable production edits. |
| Safe environments | Identify permitted local/test resources, isolation/cleanup boundaries, prohibited systems, and credential handling. Missing access is incomplete evidence. |
| CI mapping | Map each required test to the actual selector/shard. Compare collected test IDs, demonstrate omission sensitivity, and identify real storage/runtime boundaries where required. |
| Aggregate readiness | Identify the actual required aggregate gate and exact-head inputs. If none exists, record the integration gap; green individual jobs do not establish readiness. |
| PR workflow | Name the repository's existing-PR discovery, upload/readback, draft/ready transition, and required review checks. Keep review-only captures outside tracked source unless explicitly authorized. |
| Operational permissions | Record who may authorize pushes, remote PR mutations, installation, merge, deployment, tickets, and team messages. A delivery default is not that authorization. |

## Evidence before adoption

Run the foundation's conformance checks against all intended profiles and retain
raw failures. Keep the independent acceptance contract and expected outcomes
outside the candidate's authority. Check that a candidate cannot weaken its own
profile, acceptance set, or required checks. The synthetic example covers shared
workflow behavior; it does not validate a company's financial system or CI.

Retain the existing repository-owned deterministic and installed-candidate suites
when migrating an existing plugin. Confirm all ten skill entrypoints, implicit
router metadata, helper environment-variable compatibility, and explicit user
restrictions. Verify exact generated and installed bytes in an isolated test
location, then check a fresh task's selected identity. Record candidate revision,
foundation pin and digest, adapter revision, harness/profile/environment/model
identities, observed operations, and unresolved integration limits. Do not score
an unavailable environment or a missing operational result as a pass.

Before release, an independent reviewer must assess the complete candidate diff,
provenance, transfer permission, and retained evidence. Publishing, pushing,
merging, deployment, and installation into user state require separate authority.
