# System Coherence Design

**Date:** 2026-08-30  
**Status:** Accepted for implementation  
**Scope:** A release-quality, artifact-backed Agent Skill framework for behavioral reconstruction, auditing, incremental invalidation, and revalidation.

## Problem and success criteria

Conventional review often examines files, tests, or individual functions without preserving a durable model of what the system is supposed to do across its layers. System Coherence gives an agent a repeatable way to reconstruct the system before judging it, connect behavioral contracts to implementation evidence, identify states and transitions that are not represented, and preserve the result across sessions.

The repository is successful when a fresh agent can inspect repository artifacts alone and answer: what has been learned, how certain it is, what evidence supports it, what changed, which verification is stale, and which skill should run next. The framework must work for systems with or without UI, persistence, a database, a single process, or external services.

## Design principles

- The repository is shared memory; chat history is never a prerequisite.
- Every meaningful stage consumes and produces a named artifact with a documented contract.
- Interpretation is separate from evidence. Evidence points to source/runtime facts; derived artifacts explain behavior.
- Stable IDs preserve traceability across artifact revisions.
- Unknown, conflicting, and not-applicable states are first-class outcomes.
- A transition is an audit unit: authoritative changes, invalidations, notifications, persistence, side effects, atomicity, retry, rollback, partial failure, and recovery must be accounted for.
- The orchestrator routes and validates; specialist skills do the domain reasoning.
- Incremental verification is the default. Unmapped changes conservatively widen scope.
- A small deterministic core is preferable to a database, network service, or mandatory third-party dependency.

## Considered approaches

### A. Markdown prompts only

This would be easy to install but would leave handoff meaning implicit and make resumption dependent on an agent interpreting prose consistently. It fails the central artifact-contract requirement.

### B. Central graph/database service

This would support rich queries, but it adds setup, migrations, authentication, and a failure mode that is unrelated to the target repository. It also makes artifacts less portable between agents.

### C. Markdown skills plus a portable artifact workspace (chosen)

Skills follow the Agent Skills directory format. A standard-library Python CLI validates and routes JSON artifact envelopes stored under `.coherence/`. Human-readable Markdown documents explain the protocol and method; JSON is used where stable identity, cross-reference, freshness, and validation materially improve reliability. This keeps the system inspectable, offline-capable, and extensible without pretending the CLI can infer intent without an agent.

## Architecture

```text
repository evidence
        ↓
system model
        ↓
capability map
        ↓
behavioral contracts
        ↓
state / transition model
        ↓
implementation traces
        ↓
audit findings
        ↓
intervention plan
        ↓
regression scope
        ↓
revalidation results
        ↓
coherence ledger
```

The first seven stages reconstruct and audit behavior. The intervention and regression stages turn findings into scoped work. Revalidation closes the loop. A ledger summarizes capability-level verification and is regenerated from the other artifacts plus explicit validation results.

### Runtime components

- `coherence.models`: typed constants and stable identifier helpers.
- `coherence.schema`: envelope and payload semantic validation, including reference integrity.
- `coherence.store`: atomic current snapshots, content hashes, history metadata, and workspace discovery.
- `coherence.evidence`: deterministic file inventory with SHA-256 hashes, git revision when available, and source classification.
- `coherence.workflow`: stage registry, prerequisite checks, routing decisions, and skill metadata.
- `coherence.invalidation`: changed-path mapping through traces/contracts/capabilities and scoped stale-state updates.
- `coherence.ledger`: capability status derivation and human/JSON rendering.
- `coherence.cli`: `init`, `capture`, `status`, `route`, `write`, `validate`, `invalidate`, `ledger`, `validate-skills`, and `eval` commands.

### Workspace layout

```text
.coherence/
  config.json
  session.json
  artifacts/
    repository-evidence.json
    system-model.json
    capability-map.json
    behavioral-contracts.json
    state-model.json
    implementation-traces.json
    audit-findings.json
    intervention-plan.json
    regression-scope.json
    revalidation-results.json
    coherence-ledger.json
  evidence/
  history/                 # local snapshots; ignored by default
```

The current file at `artifacts/<artifact-type>.json` is the authoritative snapshot for that logical artifact. Each envelope has a stable `artifact_id` (`artifact/<artifact-type>`), a producing `run_id`, source revision, content hash, input artifact IDs, evidence references, freshness metadata, and uncertainty entries. Domain objects inside the content use deterministic IDs such as `cap-<hash>` and remain stable when descriptions are extended.

## Artifact contract

Every envelope contains:

```json
{
  "artifact_type": "capability-map",
  "schema_version": "1.0",
  "artifact_id": "artifact/capability-map",
  "run_id": "run-uuid",
  "status": "complete",
  "source_revision": "git-sha-or-WORKTREE",
  "created_at": "2026-08-30T00:00:00Z",
  "producer": {"skill": "discover-capabilities", "agent": "agent-runtime"},
  "inputs": ["artifact/system-model", "artifact/repository-evidence"],
  "evidence_refs": ["ev-..."],
  "uncertainty": [],
  "freshness": {"state": "current", "checked_at": "...", "dependency_fingerprint": "..."},
  "content": {}
}
```

`status` is one of `complete`, `partial`, `blocked`, `stale`, or `invalid`. `complete` means the producer satisfied its scope, not that the target system is correct. `partial` permits downstream work with explicit gaps. `blocked` means prerequisites or evidence are insufficient to proceed safely. `stale` means a previously valid artifact no longer describes the current source/dependency revision. `invalid` means the envelope or its references violate the protocol.

Authoritative fields are artifact identity, status, source revision, inputs, evidence references, dependency fingerprint, and the structured domain objects. Inferred fields are interpretations such as intent, confidence, likely failure mode, and proposed recovery. Uncertainty is never erased when a downstream skill refines an artifact; it may be resolved by adding new evidence and a provenance note.

Conflicts are preserved as explicit `uncertainty` entries with `kind: conflicting-evidence` and references to both sources. A skill may extend an artifact only by reading the current snapshot, retaining stable IDs, and writing a new envelope with the prior artifact in `inputs`. The CLI rejects unknown artifact types, malformed references, missing required IDs, and cross-artifact references to objects that do not exist.

## Stage and skill boundaries

| Stage | Skill | Reads | Produces |
| --- | --- | --- | --- |
| Evidence | `system-coherence` routing / CLI | repository | `repository-evidence` |
| Reconstruction | `reconstruct-system` | evidence, repository | `system-model` |
| Capability discovery | `discover-capabilities` | system model, evidence | `capability-map` |
| Behavior modeling | `model-behavior` | capability map, evidence | `behavioral-contracts` |
| State modeling | `model-states` | contracts, system model, evidence | `state-model` |
| Implementation tracing | `trace-implementation` | contracts, states, evidence | `implementation-traces` |
| Audit | `audit-coherence` | all reconstruction artifacts, evidence | `audit-findings` |
| Intervention | `plan-remediation` | findings, traces, contracts | `intervention-plan` |
| Regression scope | `analyze-regression` | git diff/change set, traces, contracts, capabilities | `regression-scope` |
| Revalidation | `revalidate-coherence` | scope, plan, evidence, changed implementation | `revalidation-results` and updated ledger |

Each `SKILL.md` repeats this contract in agent-facing form and provides a procedure that is independently resumable. The primary `system-coherence` skill inspects the workspace and invokes the CLI to select the next stage; it does not duplicate specialist reasoning.

## Behavioral method

The core unit is a capability, described by intent, preconditions, trigger, transition, side effects, observable outcome, persistence consequences, failure modes, and recovery semantics. The state model derives relevant states from discovered resources, dependencies, and environments. An unrepresented state is one that evidence or a transition can produce but no model/implementation path can represent or recover from; examples are hypotheses, not a universal checklist.

For each meaningful transition, the no-orphan check records:

1. authoritative state change;
2. derived state that becomes stale and invalidation mechanism;
3. notification/event behavior;
4. persistence requirements;
5. external effects;
6. atomicity and retry safety;
7. rollback and partial-failure behavior;
8. startup/recovery reconstruction.

The audit skill derives adversarial scenarios from actual capabilities and transitions. It records only relevant duplicate, concurrent, cancellation, retry, interruption, restart, crash, stale-view, multi-writer, dependency-disappearance, and reconciliation scenarios.

## Resumption and routing

`coherence status` validates every present artifact and reports missing, blocked, stale, or invalid prerequisites. `coherence route` emits a machine-readable route with the skill, required artifacts, reason, and expected output. A new session can continue from the repository alone. A partial artifact may be consumed when its declared gaps do not block the next stage; a blocked or invalid prerequisite routes backward for repair.

Every write is atomic. The store writes a temporary file, replaces the current snapshot, and records content hash metadata. A source revision mismatch or changed dependency fingerprint marks dependent artifacts stale. The CLI never silently upgrades a stale artifact to current.

## Incremental invalidation

`coherence invalidate --base <revision>` obtains changed paths with `git diff --name-only`, or accepts explicit paths when git is unavailable. It matches paths against implementation traces. Matching traces invalidate their linked contracts and capabilities. A missing mapping creates a conservative `scope-unknown` entry that requests broader revalidation. The command writes a `regression-scope` artifact and updates affected ledger entries to `needs-revalidation`; existing revalidation results become stale.

Revalidation may close a finding, introduce a new finding, or mark the result inconclusive. It must reference the checked revision and evidence. The ledger status is derived as follows: any open high/critical finding makes a capability `broken`; any other open finding makes it `partial`; explicit verified results with no open findings make it `verified`; stale or invalid dependencies make it `needs-revalidation`; blocked prerequisites make it `blocked`; absent coverage remains `unverified`.

## Architecture challenge

| Target architecture | Adaptation |
| --- | --- |
| Desktop application | Components may include UI, local state, filesystem, IPC, and workers; traces link UI-triggered transitions to durable state and restart recovery. |
| Web application | Interfaces, browser state, services, database, queues, and external APIs are modeled only when discovered; optimistic UI and cache invalidation are explicit derived-state edges. |
| CLI | The interface is a command/parser boundary; process exit, files, environment variables, and repeated invocation become observable outcomes. |
| Backend API | Request/response, authorization, idempotency, transactions, persistence, and asynchronous side effects are modeled without inventing a UI. |
| Filesystem-heavy application | File identity, missing/moved/inaccessible/corrupt states, multiple writers, and reconciliation are first-class resources. |
| Library/package | Public APIs and caller-visible invariants replace UI; version compatibility and tests are evidence sources. |
| Worker/service | Queue delivery, retries, leases, partial side effects, crash recovery, and idempotency are modeled as transitions. |
| Distributed/event-driven system | Producers, consumers, out-of-order/duplicate delivery, eventual consistency, and reconciliation are represented as explicit boundaries. |

No row is a required checklist. The system model records only the layers and resources supported by evidence.

## Evaluation and dogfood

The repository includes three small fixtures: a web/cache system with a stale derived cache after deletion, a worker with a partial side effect after a premature completion mark, and a clean CLI negative control. Tests execute the fixtures, then validate representative evidence-to-finding handoffs, no-orphan coverage, scoped invalidation, and the negative control. A root `.coherence/` workspace is generated by a dogfood script that treats the framework's own skills, CLI, and artifact protocol as capabilities. Its findings and ledger are checked into the repository as an inspectable release artifact.

## Limitations

System Coherence cannot infer intent from source code with certainty, replace runtime access to external systems, or guarantee that an agent has found every behavior. It exposes those limits as partial/blocked status, uncertainty, evidence provenance, and conservative invalidation. The CLI validates protocol correctness; it does not claim that a structurally valid model is behaviorally correct.

