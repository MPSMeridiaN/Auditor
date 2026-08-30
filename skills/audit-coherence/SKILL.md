---
name: audit-coherence
description: Use when a reconstructed system, behavioral contract, state model, and implementation trace must be compared for cross-layer inconsistency, orphan transitions, races, or unrepresented states.
---

# Audit Coherence

## Purpose

Challenge whether each capability's intended behavior, states, implementation, persistence, notifications, external effects, and final observables describe the same reality.

## Inputs

- `artifact/system-model`.
- `artifact/capability-map`.
- `artifact/behavioral-contracts`.
- `artifact/state-model`.
- `artifact/implementation-traces`.
- `artifact/repository-evidence`.

## Required artifacts

- All reconstruction artifacts through implementation traces, with valid cross-references.

## Optional context

- Runtime experiments, concurrent executions, crash/restart tests, external-resource controls, and recent regression scope.

## Outputs

- `artifact/audit-findings` with stable `finding_id`, severity, category, statement, traceability links, evidence, impact, reproduction, root cause, and status.

## Artifacts modified

- `.coherence/artifacts/audit-findings.json`

## Completion criteria

- Every finding identifies the violated capability/contract/transition and evidence that demonstrates the mismatch.
- The audit checks the no-orphan transition fields and reports missing coverage as findings or explicit uncertainty.
- Unrepresented-state scenarios are derived from real resources and transitions.
- Adversarial lifecycle scenarios are relevant to the discovered architecture and distinguish observed failures from hypotheses.

## Failure / uncertainty behavior

- If a trace is incomplete, report a coverage gap rather than infer a pass.
- If a conflict cannot be resolved, create a finding with `status: uncertain` or an uncertainty entry instead of choosing the convenient source.
- Do not label a behavior broken without an evidence reference or a reproducible scenario.
- Severity reflects impact and reachability, not how surprising the code looks.

## Next likely transitions

- Open findings → `plan-remediation`.
- No findings but uncovered transitions → `trace-implementation` or targeted state modeling.
- Changed implementation → `analyze-regression`, then scoped revalidation.

## Procedure

1. Walk each capability end to end: trigger → interface → local/application/domain logic → service → persistence/external effect → notification/invalidation → reconciliation → observable result.
2. For every transition, ask whether authoritative state, stale derived state, notification, persistence, external side effect, atomicity, retry, rollback, partial failure, and startup recovery are accounted for.
3. Derive relevant adversarial sequences: duplicate/rapid action, concurrent mutation, cancellation, retry, interruption, restart, crash, partial persistence, external deletion/movement, delayed or out-of-order completion, dependency disappearance, stale view, multiple writers, rollback, lost notification, and reconciliation failure.
4. Search for reachable states that have no representation, contract, trace, observable outcome, or recovery path. Name the resource and transition that can produce each state.
5. Compare expected and observed behavior; create precise findings with stable links and evidence spans.
6. Write the envelope, run validation, and ensure each finding can be handed to remediation without this session's context.

Example: “delete is broken” is insufficient. A finding states which delete contract is violated, which transition leaves a cache or projection stale, which trace and evidence show it, and what a user or caller observes.
