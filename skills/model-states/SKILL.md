---
name: model-states
description: Use when behavioral contracts must be expanded into resource states, transitions, invariants, recovery paths, and unrepresented-state hypotheses.
---

# Model States

## Purpose

Construct a state and transition model from the resources and contracts that reality can affect. Make state ownership and recovery explicit across process, persistence, filesystem, cache, queue, and external boundaries.

## Inputs

- `artifact/system-model`.
- `artifact/capability-map`.
- `artifact/behavioral-contracts`.
- Targeted source and runtime evidence.

## Required artifacts

- Current system model and behavioral contracts, even when partial.

## Optional context

- Crash/restart transcripts, queue delivery guarantees, persistence semantics, external API behavior, or concurrency notes.

## Outputs

- `artifact/state-model` with stable states and `transition_id` records.

## Artifacts modified

- `.coherence/artifacts/state-model.json`

## Completion criteria

- States describe observable conditions, owners, representations, and evidence.
- Each meaningful transition links contracts and records authoritative changes, derived invalidations, notifications, persistence, external effects, atomicity, retry safety, rollback, partial failure, and startup/recovery behavior.
- Unrepresented states are derived from resources, transitions, dependencies, and environment, not copied from a universal checklist.
- Transition and state IDs are stable and referenced by later traces and findings.

## Failure / uncertainty behavior

- Mark an unknown transition field as uncertain instead of assuming atomicity or eventual reconciliation.
- If a resource can be missing, stale, moved, inaccessible, corrupt, pending, conflicting, or externally modified, include only the states supported by the system's evidence.
- A transition without a complete consequence inventory is an audit target, not a verified transition.

## Next likely transitions

- State model → `trace-implementation`.
- Orphan transition or unrepresented state → `audit-coherence` once traces exist.
- Changed state authority → `analyze-regression` for affected traces.

## Procedure

1. Enumerate each discovered resource and its authoritative owner.
2. Derive reachable and failure states from contracts, dependencies, environment, and observed behavior.
3. For every transition, fill the no-orphan fields in order: authority, stale derived state, notifications, persistence, external effects, atomicity, retry, rollback, partial failure, and recovery.
4. Identify reachable conditions with no representation, invariant, recovery path, or observable outcome. Record them as `unrepresented-state` hypotheses with evidence.
5. Link transitions to contracts and use stable IDs derived from their source contract and trigger.
6. Write and validate the state-model envelope before handing off to implementation tracing.

Example: a file-backed record can be `present`, `moved`, `inaccessible`, or `externally-modified` only if the application can encounter and distinguish those conditions; the model must then state how startup or refresh reconciles them.
