---
name: system-coherence
description: Use when starting, resuming, or coordinating a behavioral coherence audit across an unfamiliar software repository and its durable artifact workspace.
---

# System Coherence

## Purpose

Route a coherence audit from repository evidence through reconstruction, behavioral verification, scoped revalidation, and the Coherence Ledger. The orchestrator validates prerequisites and selects specialist work; it does not replace specialist reasoning.

## Inputs

- The target repository.
- `.coherence/` when it already exists.
- The installed sibling skills in this collection.
- An optional `coherence` verifier command supplied by the host environment.
- [The artifact protocol](references/artifact-protocol.md) when envelope details
  or schema examples are needed.

## Required artifacts

- `repository-evidence` is required before any reconstruction stage.
- Read the current snapshot at `.coherence/artifacts/<artifact-type>.json`; do not rely on prior conversation.

## Optional context

- A requested capability, changed path, base revision, runtime observation, or external-system constraint.
- Targeted source files named by evidence or implementation traces.

## Outputs

- A route decision naming exactly one next skill, its prerequisites, and its output.
- `repository-evidence` after initialization.
- `coherence-ledger` after specialist artifacts and validation results exist.

## Artifacts modified

- `.coherence/config.json`
- `.coherence/session.json`
- `.coherence/artifacts/repository-evidence.json`
- `.coherence/artifacts/coherence-ledger.json`

## Completion criteria

- The target `.coherence/` workspace contains complete, readable handoffs.
- The next skill is selected from current files, statuses, freshness, and
  references rather than conversational history.
- If the optional verifier is available, `coherence validate --json` reports no
  protocol errors and `coherence route --json` agrees with the manual route.

## Failure / uncertainty behavior

- If the workspace is absent, initialize it and capture evidence.
- If an artifact is invalid, blocked, or stale, route to repair that artifact before downstream work.
- Preserve conflicting evidence and uncertainty entries; never replace them with an unsupported conclusion.
- If a change cannot be mapped to a trace, retain conservative broad-revalidation scope.

## Next likely transitions

Use the first matching row. A stale, blocked, or invalid snapshot goes to the
skill that owns that snapshot before any later stage runs.

| Durable condition | Invoke |
| --- | --- |
| No current repository evidence | `system-coherence` to capture evidence |
| Evidence is current; system model is missing or stale | `reconstruct-system` |
| System model is current; capability map is missing or stale | `discover-capabilities` |
| Capability map is current; contracts are missing or stale | `model-behavior` |
| Contracts are current; states are missing or stale | `model-states` |
| States are current; implementation traces are missing or stale | `trace-implementation` |
| Traces are current; findings are missing or stale | `audit-coherence` |
| Findings require an intervention plan | `plan-remediation` |
| Implementation changed or scope is unknown | `analyze-regression` |
| A current regression scope needs checks | `revalidate-coherence` |
| All checks are current and the ledger is missing or stale | `system-coherence` to refresh the ledger |
| All eleven artifacts are current, referentially valid, and every ledger entry is `verified` | No specialist; report `complete` |

## Procedure

1. Resolve the target repository and inspect `.coherence/`; never use the
   installed skill directory as the artifact workspace.
2. If the workspace is absent, create the target `.coherence/` directories and
   capture `repository-evidence` with repository-relative paths, hashes, and a
   source revision. If the optional verifier is available, `coherence init`
   performs this step.
3. Read only the current snapshots needed for the first incomplete row above.
   Check each envelope's `status`, `source_revision`, `freshness`, `inputs`, and
   evidence references before trusting it.
4. For a specialist stage, invoke exactly one sibling skill by its installed
   name. Pass the target repository and the required artifact paths; do not
   pass conclusions through chat instead of the files. For the ledger stage,
   the orchestrator derives the ledger from the current snapshots itself.
5. Require the specialist to write its complete envelope to
   `.coherence/artifacts/<artifact-type>.json`, preserving stable IDs and
   uncertainty. For the ledger stage, write a complete
   `.coherence/artifacts/coherence-ledger.json` envelope whose entries reflect
   current findings, regression scope, and revalidation results. If the
   optional verifier exists, run `coherence write`/`coherence ledger` and
   `coherence validate --json` after the handoff; otherwise perform the same
   derivation with native file tools and validate the resulting graph before
   routing again.
6. Re-read the changed snapshot and route again. When implementation or
   dependencies changed, route through `analyze-regression` and
   `revalidate-coherence` before calling a capability verified.
7. Stop only when every required artifact is current, referentially valid, and
   every capability ledger entry is `verified`. If any entry is
   `needs-revalidation`, `unverified`, `partial`, `broken`, or `blocked`, route
   to the owning remediation or revalidation stage instead of reporting
   completion. A new agent can repeat this procedure from `.coherence/` alone.

Example: after evidence capture, a missing system model routes to
`reconstruct-system`, which reads `artifact/repository-evidence` and writes
`artifact/system-model` in the target workspace; it does not infer a system
model from the orchestrator's chat text.
