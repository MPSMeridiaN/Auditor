"""Build a complete deterministic protocol fixture for local verification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import initialize_workspace
from .evidence import capture
from .ledger import derive
from .models import stable_id, utc_now
from .store import ArtifactStore, Workspace


def _envelope(
    artifact_type: str,
    content: dict[str, Any],
    revision: str,
    inputs: list[str],
    evidence_refs: list[str],
    status: str = "complete",
) -> dict[str, Any]:
    timestamp = utc_now()
    return {
        "artifact_type": artifact_type,
        "schema_version": "1.0",
        "artifact_id": f"artifact/{artifact_type}",
        "run_id": stable_id("run", f"dogfood:{artifact_type}:{revision}"),
        "status": status,
        "source_revision": revision,
        "created_at": timestamp,
        "producer": {"skill": "system-coherence", "agent": "dogfood"},
        "inputs": inputs,
        "evidence_refs": evidence_refs,
        "uncertainty": [],
        "freshness": {
            "state": "current",
            "checked_at": timestamp,
            "dependency_fingerprint": revision,
        },
        "content": content,
    }


def build_dogfood(root: Path) -> dict[str, Any]:
    """Create all current artifacts and return the derived ledger."""

    root = Path(root).resolve()
    workspace = initialize_workspace(root)
    store = ArtifactStore(workspace)
    evidence = capture(root)
    store.write(evidence)
    revision = evidence["source_revision"]
    files = evidence["content"]["files"]
    refs_by_path = {
        item["path"]: item["evidence_id"] for item in files if isinstance(item, dict)
    }
    evidence_refs = sorted(refs_by_path.values())[:6]
    source_ref = refs_by_path.get("src/coherence/cli.py") or (evidence_refs[:1] or ["ev-dogfood"])[0]

    system_id = stable_id("sys", "system-coherence-framework")
    cap_reconstruct = stable_id("cap", "system-coherence:reconstruct")
    cap_validate = stable_id("cap", "system-coherence:validate-handoff")
    cap_revalidate = stable_id("cap", "system-coherence:revalidate")
    con_reconstruct = stable_id("con", cap_reconstruct + ":durable-model")
    con_validate = stable_id("con", cap_validate + ":reject-dangling-reference")
    con_revalidate = stable_id("con", cap_revalidate + ":scoped-invalidation")
    trn_reconstruct = stable_id("trn", con_reconstruct + ":write-model")
    trn_validate = stable_id("trn", con_validate + ":validate")
    trn_revalidate = stable_id("trn", con_revalidate + ":invalidate")

    store.write(
        _envelope(
            "system-model",
            {
                "system_id": system_id,
                "name": "System Coherence",
                "purpose": "Preserve evidence-backed behavioral understanding across agent sessions.",
                "architecture": {
                    "style": "portable CLI plus Agent Skills",
                    "components": [
                        {
                            "component_id": stable_id("cmp", "artifact-runtime"),
                            "name": "artifact runtime",
                            "kind": "library",
                            "paths": ["src/coherence"],
                        },
                        {
                            "component_id": stable_id("cmp", "skill-suite"),
                            "name": "skill suite",
                            "kind": "agent-instructions",
                            "paths": ["skills"],
                        },
                    ],
                    "boundaries": ["repository", "agent runtime", "artifact workspace"],
                },
                "resources": [
                    {
                        "resource_id": stable_id("res", "artifact-snapshot"),
                        "name": "artifact snapshot",
                        "authority": "ArtifactStore",
                        "possible_states": ["missing", "current", "stale", "invalid"],
                    }
                ],
                "evidence_refs": evidence_refs,
                "open_questions": [
                    "Model-level pressure evaluation remains dependent on the host agent runtime."
                ],
            },
            revision,
            ["artifact/repository-evidence"],
            evidence_refs,
        )
    )
    store.write(
        _envelope(
            "capability-map",
            {
                "capabilities": [
                    {
                        "capability_id": cap_reconstruct,
                        "intent": "reconstruct a target system into durable artifacts",
                        "actors": ["agent"],
                        "triggers": ["coherence route"],
                        "surfaces": ["skills/reconstruct-system/SKILL.md"],
                        "resource_ids": [stable_id("res", "artifact-snapshot")],
                        "importance": "high",
                        "confidence": "high",
                        "evidence_refs": evidence_refs,
                    },
                    {
                        "capability_id": cap_validate,
                        "intent": "validate artifact handoffs and references",
                        "actors": ["agent", "CI"],
                        "triggers": ["coherence validate"],
                        "surfaces": ["src/coherence/schema.py"],
                        "resource_ids": [stable_id("res", "artifact-snapshot")],
                        "importance": "high",
                        "confidence": "high",
                        "evidence_refs": evidence_refs,
                    },
                    {
                        "capability_id": cap_revalidate,
                        "intent": "scope and revalidate behavior after implementation changes",
                        "actors": ["agent", "developer"],
                        "triggers": ["coherence invalidate"],
                        "surfaces": ["src/coherence/invalidation.py"],
                        "resource_ids": [stable_id("res", "artifact-snapshot")],
                        "importance": "high",
                        "confidence": "medium",
                        "evidence_refs": evidence_refs,
                    },
                ]
            },
            revision,
            ["artifact/system-model", "artifact/repository-evidence"],
            evidence_refs,
        )
    )
    store.write(
        _envelope(
            "behavioral-contracts",
            {
                "contracts": [
                    {
                        "contract_id": con_reconstruct,
                        "capability_id": cap_reconstruct,
                        "preconditions": ["repository evidence is current"],
                        "trigger": "agent invokes the orchestrator",
                        "expected_transition": trn_reconstruct,
                        "side_effects": ["write independently consumable model artifacts"],
                        "observables": ["system-model exists and validates"],
                        "persistence": "atomic JSON snapshot",
                        "failure_modes": ["missing evidence", "conflicting architecture evidence"],
                        "recovery": "route backward and preserve uncertainty",
                        "invariants": ["no hidden conversational prerequisite"],
                        "evidence_refs": evidence_refs,
                    },
                    {
                        "contract_id": con_validate,
                        "capability_id": cap_validate,
                        "preconditions": ["artifact envelope is readable"],
                        "trigger": "agent invokes the validator",
                        "expected_transition": trn_validate,
                        "side_effects": ["report exact protocol errors"],
                        "observables": ["zero errors for coherent graph"],
                        "persistence": "no mutation on invalid input",
                        "failure_modes": ["malformed envelope", "dangling reference"],
                        "recovery": "repair source artifact and re-run validation",
                        "invariants": ["invalid artifacts never become current"],
                        "evidence_refs": evidence_refs,
                    },
                    {
                        "contract_id": con_revalidate,
                        "capability_id": cap_revalidate,
                        "preconditions": ["implementation traces map changed paths"],
                        "trigger": "source path changes",
                        "expected_transition": trn_revalidate,
                        "side_effects": ["invalidate affected verification state"],
                        "observables": ["ledger shows needs-revalidation until verified"],
                        "persistence": "regression scope and ledger snapshots",
                        "failure_modes": ["unknown path mapping"],
                        "recovery": "widen scope and repair trace coverage",
                        "invariants": ["unmapped changes are never silently ignored"],
                        "evidence_refs": evidence_refs,
                    },
                ]
            },
            revision,
            [
                "artifact/repository-evidence",
                "artifact/system-model",
                "artifact/capability-map",
            ],
            evidence_refs,
        )
    )
    store.write(
        _envelope(
            "state-model",
            {
                "states": [
                    {"state_id": "stt-missing", "name": "artifact missing"},
                    {"state_id": "stt-current", "name": "artifact current"},
                    {"state_id": "stt-stale", "name": "artifact needs revalidation"},
                ],
                "transitions": [
                    {
                        "transition_id": trn_reconstruct,
                        "contract_ids": [con_reconstruct],
                        "from_state_ids": ["stt-missing"],
                        "to_state_ids": ["stt-current"],
                        "authoritative_changes": ["create current model snapshot"],
                        "derived_invalidations": [],
                        "notifications": ["route next skill"],
                        "persistence": ["atomic artifact file"],
                        "external_effects": [],
                        "atomicity": "replace-or-fail",
                        "retry_safety": "safe",
                        "rollback": "previous history snapshot",
                        "partial_failure": "temporary file is removed",
                        "startup_recovery": "read current snapshot and route",
                    },
                    {
                        "transition_id": trn_validate,
                        "contract_ids": [con_validate],
                        "from_state_ids": ["stt-current"],
                        "to_state_ids": ["stt-current"],
                        "authoritative_changes": ["none"],
                        "derived_invalidations": [],
                        "notifications": ["CLI result"],
                        "persistence": [],
                        "external_effects": [],
                        "atomicity": "read-only",
                        "retry_safety": "safe",
                        "rollback": "not applicable",
                        "partial_failure": "report all errors",
                        "startup_recovery": "re-run validation",
                    },
                    {
                        "transition_id": trn_revalidate,
                        "contract_ids": [con_revalidate],
                        "from_state_ids": ["stt-current"],
                        "to_state_ids": ["stt-stale"],
                        "authoritative_changes": ["regression scope"],
                        "derived_invalidations": ["ledger verification"],
                        "notifications": ["route revalidation skill"],
                        "persistence": ["scope and ledger"],
                        "external_effects": [],
                        "atomicity": "replace-or-fail",
                        "retry_safety": "safe",
                        "rollback": "history snapshot",
                        "partial_failure": "scope remains partial and conservative",
                        "startup_recovery": "inspect scope and route",
                    },
                ],
            },
            revision,
            ["artifact/system-model", "artifact/capability-map", "artifact/behavioral-contracts"],
            evidence_refs,
        )
    )
    store.write(
        _envelope(
            "implementation-traces",
            {
                "traces": [
                    {
                        "trace_id": "trc-dogfood-route",
                        "capability_ids": [cap_reconstruct, cap_validate],
                        "contract_ids": [con_reconstruct, con_validate],
                        "transition_ids": [trn_reconstruct, trn_validate],
                        "source_paths": ["src/coherence/cli.py", "src/coherence/workflow.py"],
                        "entrypoints": ["coherence route", "coherence status"],
                        "operations": ["read artifacts", "return route JSON"],
                        "coverage": {"mode": "static-and-test", "gaps": []},
                        "evidence_refs": [source_ref],
                    },
                    {
                        "trace_id": "trc-dogfood-invalidate",
                        "capability_ids": [cap_revalidate],
                        "contract_ids": [con_revalidate],
                        "transition_ids": [trn_revalidate],
                        "source_paths": ["src/coherence/invalidation.py"],
                        "entrypoints": ["coherence invalidate"],
                        "operations": ["match changed paths", "write scope", "derive ledger"],
                        "coverage": {"mode": "static-and-test", "gaps": []},
                        "evidence_refs": [source_ref],
                    },
                ]
            },
            revision,
            [
                "artifact/repository-evidence",
                "artifact/behavioral-contracts",
                "artifact/state-model",
            ],
            [source_ref],
        )
    )
    finding_id = stable_id("fnd", "dogfood:model-level-pressure-boundary")
    store.write(
        _envelope(
            "audit-findings",
            {
                "findings": [
                    {
                        "finding_id": finding_id,
                        "severity": "low",
                        "category": "evaluation-boundary",
                        "title": "Model-level agent pressure testing is host-dependent",
                        "statement": "The repository validates skill shape and executable protocol behavior, but agent compliance under pressure must be measured in the host runtime.",
                        "capability_ids": [cap_revalidate],
                        "contract_ids": [con_revalidate],
                        "transition_ids": [trn_revalidate],
                        "trace_ids": ["trc-dogfood-invalidate"],
                        "evidence_refs": evidence_refs,
                        "impact": "Evaluation coverage is bounded, not a framework defect.",
                        "reproduction": "Run the fixture evaluator and host-agent skill scenarios.",
                        "root_cause": "The CLI has no access to every host model or subagent API.",
                        "status": "accepted",
                        "recommended_actions": ["run host-specific pressure evaluations"],
                    }
                ]
            },
            revision,
            [
                "artifact/repository-evidence",
                "artifact/system-model",
                "artifact/capability-map",
                "artifact/behavioral-contracts",
                "artifact/state-model",
                "artifact/implementation-traces",
            ],
            evidence_refs,
        )
    )
    store.write(
        _envelope(
            "intervention-plan",
            {
                "actions": [
                    {
                        "action_id": stable_id("act", "dogfood-host-pressure-evaluations"),
                        "finding_ids": [finding_id],
                        "scope": "host agent runtimes",
                        "change": "Run pressure scenarios for skill compliance and add results as evidence.",
                        "acceptance_criteria": ["three scenario families report observed compliance"],
                        "regression_scope": ["skills", "host runtime"],
                        "status": "proposed",
                    }
                ]
            },
            revision,
            [
                "artifact/audit-findings",
                "artifact/implementation-traces",
                "artifact/behavioral-contracts",
            ],
            evidence_refs,
        )
    )
    store.write(
        _envelope(
            "regression-scope",
            {
                "change_set_id": stable_id("act", "dogfood-change-set"),
                "changed_paths": ["src/coherence/cli.py"],
                "target_revision": revision,
                "matched_trace_ids": ["trc-dogfood-route"],
                "invalidated_contract_ids": [con_validate],
                "impacted_capability_ids": [cap_validate],
                "scope_unknown_paths": [],
                "requires_broad_revalidation": False,
                "invalidated_artifact_types": ["revalidation-results", "coherence-ledger"],
            },
            revision,
            ["artifact/implementation-traces", "artifact/behavioral-contracts", "artifact/capability-map"],
            [source_ref],
        )
    )
    store.write(
        _envelope(
            "revalidation-results",
            {
                "validations": [
                    {
                        "validation_id": stable_id("val", cap_reconstruct + ":dogfood"),
                        "target_type": "capability",
                        "target_id": cap_reconstruct,
                        "result": "verified",
                        "checked_revision": revision,
                        "checks": ["artifact graph routes from evidence to model"],
                        "evidence_refs": evidence_refs,
                    },
                    {
                        "validation_id": stable_id("val", cap_validate + ":dogfood"),
                        "target_type": "capability",
                        "target_id": cap_validate,
                        "result": "verified",
                        "checked_revision": revision,
                        "checks": ["invalid and valid handoffs are reported"],
                        "evidence_refs": evidence_refs,
                    },
                    {
                        "validation_id": stable_id("val", cap_revalidate + ":dogfood"),
                        "target_type": "capability",
                        "target_id": cap_revalidate,
                        "result": "verified",
                        "checked_revision": revision,
                        "checks": ["mapped changes invalidate only linked capability"],
                        "evidence_refs": evidence_refs,
                    },
                ]
            },
            revision,
            ["artifact/regression-scope", "artifact/intervention-plan", "artifact/audit-findings"],
            evidence_refs,
        )
    )
    ledger = derive(store)
    store.write(ledger)
    errors = store.validate_all()
    if errors:
        raise ValueError("dogfood produced an invalid workspace: " + json.dumps(errors, sort_keys=True))
    return ledger
