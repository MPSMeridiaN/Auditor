# System Coherence Artifact Protocol

This is the authoritative handoff contract for the System Coherence skill
collection. All skills read current snapshots under the target repository's
`.coherence/artifacts/` directory and write their output there. The optional
Python verifier can validate and atomically store an envelope with
`coherence write`; a skill must remain usable when that verifier is not
installed.

## Envelope

Every artifact is a JSON object with these required fields:

| Field | Meaning |
| --- | --- |
| `artifact_type` | One of the eleven protocol types. |
| `schema_version` | Currently `1.0`. |
| `artifact_id` | Stable logical address `artifact/<artifact-type>`. |
| `run_id` | Identifier for the producing activity. |
| `methodology_version` | Version of the producing System Coherence methodology. Persisted snapshots include it so upgrades invalidate stale assumptions. |
| `status` | `complete`, `partial`, `blocked`, `stale`, or `invalid`. |
| `source_revision` | Revision or `WORKTREE` snapshot used. |
| `created_at` | UTC ISO-8601 timestamp. |
| `producer` | At least `skill` and `agent`. |
| `inputs` | Artifact IDs consumed by the producer. |
| `evidence_refs` | Evidence IDs supporting the artifact. |
| `uncertainty` | Objects with at least `kind` and `message` when unresolved. |
| `freshness` | `state`, `checked_at`, and `dependency_fingerprint`; the store derives `deps-<sha256>` fingerprints from input snapshot hashes. |
| `content` | Structured payload for the artifact type. |
| `content_hash` | SHA-256 digest of the envelope without this field; required on persisted snapshots. |

The store adds `content_hash`, a SHA-256 digest of the envelope without its own hash field.

Minimal example:

```json
{
  "artifact_type": "capability-map",
  "schema_version": "1.0",
  "artifact_id": "artifact/capability-map",
  "run_id": "run-example",
  "methodology_version": "1.2.0",
  "status": "partial",
  "source_revision": "WORKTREE",
  "created_at": "2026-08-30T00:00:00Z",
  "producer": {"skill": "discover-capabilities", "agent": "agent-runtime"},
  "inputs": ["artifact/system-model", "artifact/repository-evidence"],
  "evidence_refs": ["ev-example"],
  "uncertainty": [{"kind": "missing-runtime", "message": "The queue consumer was not available."}],
  "freshness": {"state": "current", "checked_at": "2026-08-30T00:00:00Z", "dependency_fingerprint": "WORKTREE"},
  "content": {"capabilities": []},
  "content_hash": "<store-generated-sha256>"
}
```

## Payloads

The runtime requires these primary collections/fields; richer fields are added by the producing skill and preserved by consumers.

| Type | Required payload | Stable object IDs |
| --- | --- | --- |
| `repository-evidence` | `files` | `evidence_id` (`ev-`) |
| `system-model` | `system_id` | `sys-`, component/resource IDs |
| `capability-map` | `capabilities` | `capability_id` (`cap-`) |
| `behavioral-contracts` | `contracts` | `contract_id` (`con-`) |
| `state-model` | `states`, `transitions` | `state_id`, `transition_id` (`trn-`) |
| `implementation-traces` | `traces` | `trace_id` (`trc-`) |
| `audit-findings` | `findings` | `finding_id` (`fnd-`) |
| `intervention-plan` | `actions` | `action_id` (`act-`) |
| `regression-scope` | `changed_paths`, `impacted_capability_ids` | `change_set_id` (`act-`) |
| `revalidation-results` | `validations` | `validation_id` (`val-`) |
| `coherence-ledger` | `entries` (`capability_id`, `status`) | `capability_id` |

JSON Schema documents are in `schemas/` beside this file. The optional
standard-library verifier adds semantic checks for collection uniqueness,
strict timestamps, duplicate-key/non-finite JSON rejection, input cycles, and
cross-artifact references. A persisted snapshot without a matching
`content_hash` is invalid.

## Authority and uncertainty

Authoritative protocol fields are identity, status, source revision, inputs, evidence references, freshness, and structured object IDs. Intent, confidence, likely root cause, and proposed recovery are derived interpretations. A downstream skill may extend a current artifact only after reading it, retaining IDs and uncertainty, and writing a new envelope whose `inputs` include the prior logical artifact. Ledger entries must carry a known status; only `verified` is a completion status.

Conflicting sources remain visible as `uncertainty` entries with `kind: conflicting-evidence`. A valid envelope does not mean its interpretation is correct.

## Freshness and invalidation

`current` means the artifact was produced against the declared dependency fingerprint. `stale` means a change invalidated the prior verification. `unknown` means freshness cannot be established. Repository evidence uses a source-tree fingerprint so artifact-only commits do not change the source identity. The optional `coherence invalidate` command creates a regression scope at the current source snapshot and marks affected ledger entries `needs-revalidation`; without that command, record the same scope and stale state directly in the target workspace. Input references must remain acyclic; a missing or untracked change is conservatively routed for repair.

## Provenance

Use `inputs` for artifact derivation and `evidence_refs` for source/runtime support. Evidence is kept separate from interpretation. When a refreshed evidence snapshot supersedes one in use, the old snapshot remains locally resolvable through hash-addressed history while dependency fingerprints mark stale consumers for repair. A finding should link capability, contract, transition, trace, and evidence IDs when those objects exist. A revalidation result must identify the checked revision, target, checks, result, and evidence.

## Writing and validating

```text
target-repository/
└── .coherence/
    └── artifacts/
        └── <artifact-type>.json
```

Write the complete envelope to the target path above, preserving stable IDs
and existing uncertainty. When the optional verifier is available, use:

```bash
coherence write path/to/envelope.json /path/to/target
coherence validate --json /path/to/target
```

Do not edit a current snapshot with a text replacement that bypasses the
protocol. Use an atomic file replacement when native file tools support it;
otherwise write the complete JSON document and validate it before handing off.
The verifier rejects orphaned temporary files, malformed history snapshots,
duplicate JSON keys, non-finite numbers, and symlink escapes. Fixture
evaluation is metadata-only by default; executing repository fixtures requires
an explicit trusted-checkout opt-in.
