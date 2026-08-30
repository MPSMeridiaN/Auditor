---
name: plan-remediation
description: Use when audit findings need an evidence-linked, regression-aware intervention plan with acceptance criteria and safe sequencing.
---

# Plan Remediation

## Purpose

Turn verified or well-supported findings into bounded interventions that restore a behavioral contract and state the evidence needed to prove the repair.

## Inputs

- `artifact/audit-findings`.
- `artifact/implementation-traces`.
- `artifact/behavioral-contracts`.
- `artifact/state-model` when transition changes are involved.

## Required artifacts

- Findings with stable traceability links and status/severity.
- Current traces and contracts for scope and regression impact.

## Optional context

- Product priorities, release constraints, ownership, incident timelines, and proposed implementation options.

## Outputs

- `artifact/intervention-plan` with stable `action_id`, linked findings, change scope, acceptance criteria, regression scope, dependencies, and action status.

## Artifacts modified

- `.coherence/artifacts/intervention-plan.json`

## Completion criteria

- Each action names the finding(s) and exact behavioral contract it repairs.
- Acceptance criteria are observable and include relevant success, failure, retry, concurrency, restart, or reconciliation cases.
- Change scope identifies implementation paths and affected capabilities/contracts.
- Actions are ordered by dependency and do not claim a fix without a validation step.

## Failure / uncertainty behavior

- Do not merge unrelated findings into one vague action.
- If a finding is uncertain, plan evidence collection or a focused reproduction before a code change.
- If the affected scope is unknown, preserve that uncertainty and require conservative regression analysis.
- If an action would alter intended behavior, record the decision as a contract update rather than silently changing the test target.

## Next likely transitions

- Plan ready → implementation by the developer/agent, then `analyze-regression`.
- Missing reproduction → `audit-coherence` or targeted evidence capture.
- Code changed → `analyze-regression` before marking an action fixed.

## Procedure

1. Group findings only when they share a root cause and acceptance boundary.
2. For each action, specify the smallest implementation scope, linked IDs, migration/rollback concerns, and exact observable acceptance criteria.
3. Include regression paths for directly and transitively dependent capabilities.
4. Mark status `proposed`, `in-progress`, `blocked`, or `complete`; completion requires revalidation evidence.
5. Write the envelope, validate references, and leave the next agent a concrete command/context path.

Example: a stale-cache finding becomes an action to invalidate or rebuild the cache on delete, with acceptance checks for delete/read, restart, duplicate delete, and a cache-miss response—not merely “update cache code.”
