---
name: trace-implementation
description: Use when behavioral contracts and state transitions need evidence-backed links to source paths, entry points, runtime observations, and test coverage.
---

# Trace Implementation

## Purpose

Connect the behavioral model to the implementation without declaring the implementation correct. Traces make coverage, state ownership, change impact, and evidence provenance queryable.

## Inputs

- `artifact/repository-evidence`.
- `artifact/behavioral-contracts`.
- `artifact/state-model`.
- Targeted source, tests, runtime traces, dependency manifests, and process boundaries.

## Required artifacts

- Current contracts and state model.
- Evidence inventory for every source path cited.

## Optional context

- Test commands, logs, traces, profiler output, deployment topology, or external API recordings.

## Outputs

- `artifact/implementation-traces` with `trace_id`, linked capability/contract/transition IDs, source paths, entry points, operations, coverage mode, gaps, and evidence references.

## Artifacts modified

- `.coherence/artifacts/implementation-traces.json`

## Completion criteria

- Every trace names the code/runtime boundary it covers and the contract/transition it is evidence for.
- `source_paths` are normalized repository-relative paths or explicit globs usable by regression analysis.
- Static, runtime, and inferred evidence are distinguished.
- Missing coverage, hidden state owners, external dependencies, and unobserved failure paths are recorded as gaps.

## Failure / uncertainty behavior

- Do not upgrade a static reference to runtime verification.
- If an entry point cannot be followed, produce a partial trace with a gap and evidence of the boundary.
- If a path changed but no trace covers it, leave the mapping absent; `analyze-regression` must escalate conservatively.
- Never copy large source blocks into the artifact; link path and line/span metadata instead.

## Next likely transitions

- Complete or partial traces → `audit-coherence`.
- A changed path → `analyze-regression`.
- A trace gap that changes intended behavior → `model-behavior` or `model-states`.

## Procedure

1. For each contract and transition, locate interface entry points, state mutation, persistence, derived state, notifications, external effects, and recovery code.
2. Record one trace per coherent path, linking stable IDs and normalized `source_paths`.
3. Add tests and runtime observations as evidence rather than treating test presence as proof of correctness.
4. Identify missing edges and label coverage `static`, `runtime`, `test`, `inferred`, or `unobserved`.
5. Write and validate the envelope. Re-read it independently and confirm every path can be mapped by the regression tool.

Example: a delete trace includes the handler, domain operation, database mutation, cache invalidation, event publication, subscriber refresh, and restart reconciliation—or records each missing edge as a trace gap.
