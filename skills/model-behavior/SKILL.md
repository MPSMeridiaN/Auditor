---
name: model-behavior
description: Use when a capability map must become explicit behavioral contracts covering intent, preconditions, transitions, side effects, outcomes, failures, and recovery.
---

# Model Behavior

## Purpose

State what each capability promises independent of its current implementation. A behavioral contract is the reference against which traces, tests, and audit findings are compared.

## Inputs

- `artifact/capability-map`.
- `artifact/system-model` and `artifact/repository-evidence`.
- Targeted specifications, tests, runtime evidence, and external-system contracts.

## Required artifacts

- A current or partial capability map.
- Evidence references for every normative claim.

## Optional context

- Compatibility promises, error taxonomies, idempotency requirements, security boundaries, or product decisions not present in source.

## Outputs

- `artifact/behavioral-contracts` containing stable `contract_id` values linked to `capability_id`.

## Artifacts modified

- `.coherence/artifacts/behavioral-contracts.json`

## Completion criteria

- Each contract records capability, preconditions, trigger, expected transition, authoritative side effects, observables, persistence consequences, failure modes, recovery semantics, invariants, and evidence.
- Intended behavior is distinguished from observed behavior.
- Conflicts and unknowns are explicit; implementation quirks are not promoted to requirements without corroboration.

## Failure / uncertainty behavior

- If a capability is partial, produce a partial contract with a specific gap or route back when no safe assertion can be made.
- Preserve incompatible requirements as separate evidence-backed alternatives under `uncertainty`.
- Do not infer atomicity, retry safety, or rollback merely because a function returns successfully.

## Next likely transitions

- Contracts → `model-states`.
- Contract with unresolved state authority → targeted `reconstruct-system` or `model-states` work.
- Contract affected by a changed implementation path → `analyze-regression`.

## Procedure

1. For each capability, write the user/system intent before reading implementation details deeply.
2. Define preconditions, trigger, expected state transition, side effects, observable outcome, persistence effect, failure modes, and recovery semantics.
3. Capture invariants that must hold across retries, restarts, cancellation, duplicate actions, and external changes when relevant.
4. Link every contract to its capability and evidence. Use deterministic IDs from capability ID plus contract meaning.
5. Mark each statement as observed, specified, inferred, or unknown in the evidence/provenance fields.
6. Write and validate the envelope; downstream skills must be able to continue without this session's reasoning.

Example: a successful delete contract includes whether a cache, index, event subscriber, search projection, and restart reconciliation must observe deletion; “the database row disappeared” is not the whole contract.
