# Methodology

System Coherence audits behavior from the outside in. The current implementation is evidence, not the definition of correctness.

## 1. Reconstruct the system

Start with the repository evidence inventory. Identify boundaries, components, processes, resources, state authorities, derived representations, external owners, and observable interfaces. Record only architecture supported by evidence. If documentation conflicts with code or runtime behavior, preserve the conflict.

## 2. Discover capabilities

Group entry points by intent rather than by function or screen. Include user, API, library, scheduler, queue, startup, reconciliation, and external-writer capabilities when they exist. A capability describes an end-to-end slice and records actors, trigger, surfaces, resources, importance, confidence, and evidence.

## 3. Write behavioral contracts

For every capability, define:

1. intent;
2. preconditions;
3. trigger;
4. expected transition;
5. authoritative side effects;
6. observable outcome;
7. persistence consequences;
8. failure modes;
9. recovery semantics;
10. invariants across retries, duplicate actions, restarts, and external changes when relevant.

Separate specified, observed, inferred, and unknown statements. Do not promote an implementation quirk to intended behavior without corroboration.

## 4. Model states and transitions

Derive states from actual resources, dependencies, and environment. A file may be missing or moved; a request may be pending or cancelled; a worker may be partially applied; an external resource may disappear. Include a state only when the target system can reach it or the evidence makes it a credible boundary condition.

### No Orphan Transition

Every meaningful transition must account for:

- authoritative state change;
- derived state that becomes stale;
- invalidation or notification;
- persistence;
- external effects;
- atomicity;
- retry safety and idempotency;
- rollback;
- partial failure;
- startup/recovery reconstruction.

If one field cannot be answered, the transition is an audit target or carries explicit uncertainty.

## 5. Trace the implementation

Follow each contract through interface, local state, application/domain logic, services, persistence, external effects, events, invalidations, reconciliation, and final observables. Record source paths, entry points, operations, runtime observations, tests, and coverage gaps. A test reference is not runtime proof.

## 6. Audit coherence

Compare intended contracts to implementation traces. Derive adversarial scenarios from the real transitions: duplicate and rapid actions, concurrency, cancellation, retry, interruption, restart, crash, partial persistence, external deletion or movement, delayed/out-of-order completion, dependency disappearance, stale views, multiple writers, partial rollback, lost notifications, and reconciliation failure. Keep only scenarios relevant to the discovered system.

An unrepresented state is a reachable or credible state with no product representation, contract, trace, observable outcome, invariant, or recovery path. A finding must state the violated capability/contract/transition and link the evidence that demonstrates it.

## 7. Plan and revalidate

Turn findings into acceptance-driven actions. After code changes, map the changed paths to traces and invalidate only what those edges affect. Verify the smallest safe scope first, then expand if the evidence or unknown mapping requires it. Results must carry the exact checked revision and evidence references.

## Evidence discipline

Evidence and interpretation stay separate. Evidence entries point to repository-relative paths, hashes, line spans, commands, logs, or runtime observations. Derived artifacts link those evidence IDs instead of embedding large source excerpts. Uncertainty is a durable field, not a conversational disclaimer.
