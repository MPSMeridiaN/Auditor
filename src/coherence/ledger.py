"""Derive the capability-level Coherence Ledger from current artifacts."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from .models import stable_id, utc_now
from .store import ArtifactStore


_REVALIDATION_RESULTS = frozenset(
    {"verified", "failed", "inconclusive", "unverified"}
)
_REVALIDATION_TARGET_TYPES = frozenset(
    {"capability", "contract", "transition", "trace", "finding"}
)


def _fingerprint(values: list[dict[str, Any]]) -> str:
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def _artifact(store: ArtifactStore, artifact_type: str) -> dict[str, Any] | None:
    return store.read(artifact_type)


def _artifact_content(store: ArtifactStore, artifact_type: str) -> dict[str, Any]:
    value = _artifact(store, artifact_type)
    content = value.get("content", {}) if value else {}
    return content if isinstance(content, dict) else {}


def _revision_matches(value: Any, expected: str | None) -> bool:
    """Treat the un-hashed WORKTREE marker as an intentionally loose revision."""

    if not isinstance(value, str) or not value.strip() or not expected:
        return False
    return value == expected or value == "WORKTREE" or expected == "WORKTREE"


def _scope_info(
    store: ArtifactStore, capability_ids: set[str]
) -> dict[str, Any]:
    evidence = _artifact(store, "repository-evidence")
    evidence_revision = (
        evidence.get("source_revision")
        if isinstance(evidence, dict)
        else None
    )
    scope_artifact = _artifact(store, "regression-scope")
    scope_content = (
        scope_artifact.get("content", {})
        if isinstance(scope_artifact, dict)
        else {}
    )
    if not isinstance(scope_content, dict):
        scope_content = {}
    target_revision = scope_content.get("target_revision")
    freshness = (
        scope_artifact.get("freshness", {})
        if isinstance(scope_artifact, dict)
        else {}
    )
    scope_usable = bool(
        isinstance(scope_artifact, dict)
        and scope_artifact.get("status") not in {"blocked", "invalid", "stale"}
        and isinstance(freshness, dict)
        and freshness.get("state") == "current"
        and isinstance(target_revision, str)
        and bool(target_revision.strip())
        and _revision_matches(
            scope_artifact.get("source_revision"), target_revision
        )
    )
    scope_problem = None
    if scope_artifact is not None and not scope_usable:
        scope_problem = "regression scope is not current"
        if isinstance(scope_artifact, dict) and scope_artifact.get("status") == "blocked":
            scope_problem = "regression scope is blocked"

    impacted = {
        item
        for item in _list_value(scope_content.get("impacted_capability_ids"))
        if isinstance(item, str) and item
    }
    broad = bool(scope_content.get("requires_broad_revalidation"))
    if broad:
        impacted.update(capability_ids)

    current_revision = (
        target_revision
        if scope_usable and isinstance(target_revision, str)
        else evidence_revision
    )
    if not isinstance(current_revision, str) or not current_revision:
        current_revision = "WORKTREE"
    return {
        "active": scope_usable,
        "broad": broad,
        "current_revision": current_revision,
        "evidence_revision": evidence_revision or "WORKTREE",
        "impacted": impacted,
        "problem": scope_problem,
        "target_revision": target_revision,
    }


def _source_revision(store: ArtifactStore) -> str:
    capabilities = _artifact_content(store, "capability-map").get("capabilities", [])
    if not isinstance(capabilities, list):
        capabilities = []
    capability_ids = {
        item.get("capability_id")
        for item in capabilities
        if isinstance(item, dict) and isinstance(item.get("capability_id"), str)
    }
    return str(_scope_info(store, capability_ids)["current_revision"])


def _open_findings(store: ArtifactStore) -> dict[str, list[dict[str, Any]]]:
    findings = _artifact_content(store, "audit-findings").get("findings", [])
    by_capability: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(findings, list):
        return by_capability
    for finding in findings:
        if not isinstance(finding, dict) or finding.get("status", "open") != "open":
            continue
        capability_ids = finding.get("capability_ids", [])
        if not isinstance(capability_ids, list):
            continue
        for capability_id in capability_ids:
            if isinstance(capability_id, str):
                by_capability.setdefault(capability_id, []).append(finding)
    return by_capability


def _collection_by_id(
    store: ArtifactStore, artifact_type: str, collection_name: str, id_field: str
) -> dict[str, dict[str, Any]]:
    collection = _artifact_content(store, artifact_type).get(collection_name, [])
    if not isinstance(collection, list):
        return {}
    return {
        item[id_field]: item
        for item in collection
        if isinstance(item, dict) and isinstance(item.get(id_field), str)
    }


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _capabilities_for_validation(
    validation: dict[str, Any],
    capabilities: dict[str, dict[str, Any]],
    contracts: dict[str, dict[str, Any]],
    transitions: dict[str, dict[str, Any]],
    traces: dict[str, dict[str, Any]],
    findings: dict[str, dict[str, Any]],
) -> set[str]:
    """Resolve a validation target to capabilities without trusting chat context."""

    declared_capability_ids = validation.get("capability_ids", [])
    if not isinstance(declared_capability_ids, list):
        declared_capability_ids = []
    capability_ids: set[str] = {
        item
        for item in declared_capability_ids
        if isinstance(item, str)
        and item in capabilities
    }
    target_type = validation.get("target_type")
    target_id = validation.get("target_id")

    def add_contract(contract_id: Any) -> None:
        if not isinstance(contract_id, str):
            return
        capability_id = contracts.get(contract_id, {}).get("capability_id")
        if isinstance(capability_id, str) and capability_id in capabilities:
            capability_ids.add(capability_id)

    if target_type == "capability" and isinstance(target_id, str):
        if target_id in capabilities:
            capability_ids.add(target_id)
    elif target_type == "contract":
        add_contract(target_id)
    elif target_type == "transition":
        transition = transitions.get(target_id) if isinstance(target_id, str) else None
        if transition:
            for contract_id in _list_value(transition.get("contract_ids")):
                add_contract(contract_id)
    elif target_type == "trace":
        trace = traces.get(target_id) if isinstance(target_id, str) else None
        if trace:
            capability_ids.update(
                item
                for item in _list_value(trace.get("capability_ids"))
                if isinstance(item, str) and item in capabilities
            )
            for contract_id in _list_value(trace.get("contract_ids")):
                add_contract(contract_id)
            for transition_id in _list_value(trace.get("transition_ids")):
                transition = transitions.get(transition_id)
                if transition:
                    for contract_id in _list_value(transition.get("contract_ids")):
                        add_contract(contract_id)
    elif target_type == "finding":
        finding = findings.get(target_id) if isinstance(target_id, str) else None
        if finding:
            capability_ids.update(
                item
                for item in _list_value(finding.get("capability_ids"))
                if isinstance(item, str) and item in capabilities
            )
    return capability_ids


def _validation_by_capability(store: ArtifactStore) -> dict[str, list[dict[str, Any]]]:
    validations = _artifact_content(store, "revalidation-results").get("validations", [])
    by_capability: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(validations, list):
        return by_capability
    capabilities = _collection_by_id(
        store, "capability-map", "capabilities", "capability_id"
    )
    contracts = _collection_by_id(
        store, "behavioral-contracts", "contracts", "contract_id"
    )
    transitions = _collection_by_id(store, "state-model", "transitions", "transition_id")
    traces = _collection_by_id(
        store, "implementation-traces", "traces", "trace_id"
    )
    findings = _collection_by_id(store, "audit-findings", "findings", "finding_id")
    for validation in validations:
        if not _usable_validation(validation):
            continue
        for capability_id in _capabilities_for_validation(
            validation, capabilities, contracts, transitions, traces, findings
        ):
            by_capability.setdefault(capability_id, []).append(validation)
    return by_capability


def _usable_validation(validation: Any) -> bool:
    if not isinstance(validation, dict):
        return False
    if validation.get("target_type") not in _REVALIDATION_TARGET_TYPES:
        return False
    if not isinstance(validation.get("target_id"), str) or not validation["target_id"].strip():
        return False
    if validation.get("result") not in _REVALIDATION_RESULTS:
        return False
    if not isinstance(validation.get("checked_revision"), str) or not validation[
        "checked_revision"
    ].strip():
        return False
    checks = validation.get("checks")
    evidence_refs = validation.get("evidence_refs")
    return (
        isinstance(checks, list)
        and bool(checks)
        and all(isinstance(item, str) and item.strip() for item in checks)
        and isinstance(evidence_refs, list)
        and bool(evidence_refs)
        and all(isinstance(item, str) and item.strip() for item in evidence_refs)
    )


def _artifact_has_unusable_state(artifact: dict[str, Any] | None) -> str | None:
    if not artifact:
        # The router owns stage completeness. The ledger can still derive
        # useful capability status while an upstream snapshot is absent.
        return None
    if artifact.get("status") == "blocked":
        return "required artifact is blocked"
    if artifact.get("status") in {"invalid", "stale"}:
        return "required artifact is not current"
    freshness = artifact.get("freshness", {})
    if isinstance(freshness, dict) and freshness.get("state") in {"stale", "unknown"}:
        return "required artifact freshness is not current"
    return None


def _artifact_revision_is_allowed(
    artifact: dict[str, Any] | None, scope: dict[str, Any]
) -> bool:
    if not artifact:
        return True
    expected = {scope["evidence_revision"]}
    if scope["active"]:
        expected.add(scope["current_revision"])
    return any(
        _revision_matches(artifact.get("source_revision"), revision)
        for revision in expected
    )


def _eligible_validations(
    capability_id: str,
    validations: list[dict[str, Any]],
    scope: dict[str, Any],
) -> list[dict[str, Any]]:
    """Keep only results whose checked revision is valid for this capability."""

    revalidation = scope.get("revalidation")
    revalidation_status = (
        revalidation.get("status") if isinstance(revalidation, dict) else None
    )
    revalidation_freshness = None
    if isinstance(revalidation, dict):
        freshness = revalidation.get("freshness")
        if isinstance(freshness, dict):
            revalidation_freshness = freshness.get("state")
    if revalidation_status in {"blocked", "invalid"}:
        return []
    if revalidation_status == "stale" or revalidation_freshness in {"stale", "unknown"}:
        if capability_id in scope["impacted"] or not scope["active"]:
            return []

    expected_revisions = {scope["current_revision"]}
    if scope["active"] and capability_id not in scope["impacted"]:
        expected_revisions.add(scope["evidence_revision"])
    if isinstance(revalidation, dict) and not any(
        _revision_matches(revalidation.get("source_revision"), expected)
        for expected in expected_revisions
    ):
        return []
    return [
        validation
        for validation in validations
        if any(
            _revision_matches(validation.get("checked_revision"), expected)
            for expected in expected_revisions
        )
    ]


def _status_for(
    capability_id: str,
    capability_map: dict[str, Any],
    store: ArtifactStore,
    findings: list[dict[str, Any]],
    validations: list[dict[str, Any]],
    scope: dict[str, Any],
    dependency_errors: set[str],
) -> tuple[str, str]:
    if dependency_errors.intersection(
        {
            "system-model",
            "capability-map",
            "behavioral-contracts",
            "state-model",
            "implementation-traces",
            "audit-findings",
            "revalidation-results",
            "regression-scope",
        }
    ):
        return "needs-revalidation", "an upstream artifact has validation errors"

    for artifact_type in (
        "system-model",
        "capability-map",
        "behavioral-contracts",
        "state-model",
        "implementation-traces",
    ):
        issue = _artifact_has_unusable_state(_artifact(store, artifact_type))
        if issue:
            artifact = _artifact(store, artifact_type)
            if artifact and artifact.get("status") == "blocked":
                return "blocked", f"{artifact_type} is blocked"
            return "needs-revalidation", f"{artifact_type}: {issue}"
        if not _artifact_revision_is_allowed(_artifact(store, artifact_type), scope):
            return "needs-revalidation", f"{artifact_type} was produced for a different revision"

    if capability_map.get("status") == "blocked":
        return "blocked", "capability map is blocked"

    if scope.get("problem"):
        if scope.get("problem") == "regression scope is blocked":
            return "blocked", str(scope["problem"])
        return "needs-revalidation", str(scope["problem"])

    revalidation = scope.get("revalidation")
    if isinstance(revalidation, dict) and revalidation.get("status") == "blocked":
        return "blocked", "revalidation results are blocked"

    revalidation_freshness = None
    if isinstance(revalidation, dict):
        freshness = revalidation.get("freshness")
        if isinstance(freshness, dict):
            revalidation_freshness = freshness.get("state")
    revalidation_unusable = isinstance(revalidation, dict) and (
        revalidation.get("status") in {"invalid", "stale"}
        or revalidation_freshness in {"stale", "unknown"}
    )
    if revalidation_unusable and (
        not scope["active"] or capability_id in scope["impacted"]
    ):
        return "needs-revalidation", "revalidation results are not current"

    if isinstance(revalidation, dict) and not _artifact_revision_is_allowed(
        revalidation, scope
    ):
        return "needs-revalidation", "revalidation results are for a different revision"

    current_validations = _eligible_validations(capability_id, validations, scope)
    results = {str(validation.get("result")) for validation in current_validations}

    high_open = any(
        str(finding.get("severity", "")).lower() in {"critical", "high"}
        for finding in findings
    )
    if high_open:
        return "broken", "open high or critical finding"
    if findings:
        return "partial", "open finding requires remediation"
    if "failed" in results:
        return "broken", "revalidation failed"
    if "inconclusive" in results:
        return "partial", "revalidation was inconclusive"

    if capability_id in scope["impacted"] and "verified" not in results:
        return "needs-revalidation", "implementation change invalidated this capability"
    if "verified" in results:
        return "verified", "current validation has no open findings"
    return "unverified", "no current verification result"


def derive(store: ArtifactStore) -> dict[str, Any]:
    """Return a ledger envelope derived from current workspace artifacts."""

    dependency_errors = set(store.validate_all())
    dependency_errors.discard("coherence-ledger")
    capability_artifact = _artifact(store, "capability-map")
    capabilities = _artifact_content(store, "capability-map").get("capabilities", [])
    if not isinstance(capabilities, list):
        capabilities = []
    contracts = _artifact_content(store, "behavioral-contracts").get("contracts", [])
    if not isinstance(contracts, list):
        contracts = []
    capability_ids = {
        item.get("capability_id")
        for item in capabilities
        if isinstance(item, dict) and isinstance(item.get("capability_id"), str)
    }
    scope = _scope_info(store, capability_ids)
    scope["revalidation"] = _artifact(store, "revalidation-results")
    open_findings = _open_findings(store)
    validations_by_capability = _validation_by_capability(store)
    entries: list[dict[str, Any]] = []
    contract_by_capability: dict[str, list[str]] = {}
    for contract in contracts:
        if isinstance(contract, dict) and isinstance(contract.get("capability_id"), str):
            contract_by_capability.setdefault(contract["capability_id"], []).append(
                contract.get("contract_id", "")
            )

    for capability in capabilities:
        if not isinstance(capability, dict) or not isinstance(
            capability.get("capability_id"), str
        ):
            continue
        capability_id = capability["capability_id"]
        capability_findings = open_findings.get(capability_id, [])
        all_validations = validations_by_capability.get(capability_id, [])
        current_validations = _eligible_validations(
            capability_id, all_validations, scope
        )
        status, reason = _status_for(
            capability_id,
            capability_artifact or {},
            store,
            capability_findings,
            all_validations,
            scope,
            dependency_errors,
        )
        verified_revisions = [
            validation.get("checked_revision")
            for validation in current_validations
            if validation.get("result") == "verified"
            and validation.get("checked_revision")
        ]
        entries.append(
            {
                "capability_id": capability_id,
                "intent": capability.get("intent", capability.get("name", "")),
                "status": status,
                "reason": reason,
                "contract_ids": sorted(contract_by_capability.get(capability_id, [])),
                "finding_ids": sorted(
                    finding.get("finding_id", "") for finding in capability_findings
                ),
                "last_verified_revision": max(verified_revisions)
                if verified_revisions
                else None,
                "evidence_refs": sorted(
                    {
                        ref
                        for validation in current_validations
                        for ref in validation.get("evidence_refs", [])
                        if isinstance(ref, str)
                    }
                ),
                "next_action": (
                    "revalidate"
                    if status == "needs-revalidation"
                    else "investigate"
                    if status in {"broken", "partial"}
                    else "continue coverage"
                ),
            }
        )
    entries.sort(key=lambda entry: entry["capability_id"])
    inputs = [
        f"artifact/{artifact_type}"
        for artifact_type in (
            "capability-map",
            "behavioral-contracts",
            "audit-findings",
            "regression-scope",
            "revalidation-results",
        )
        if _artifact(store, artifact_type) is not None
    ]
    captured_at = utc_now()
    return {
        "artifact_type": "coherence-ledger",
        "schema_version": "1.0",
        "artifact_id": "artifact/coherence-ledger",
        "run_id": stable_id(
            "run", f"ledger:{scope['current_revision']}:{json.dumps(entries, sort_keys=True)}"
        ),
        "status": "complete" if capability_artifact else "partial",
        "source_revision": scope["current_revision"],
        "created_at": captured_at,
        "producer": {"skill": "system-coherence", "agent": "coherence-cli"},
        "inputs": inputs,
        "evidence_refs": [],
        "uncertainty": [],
        "freshness": {
            "state": "current",
            "checked_at": captured_at,
            "dependency_fingerprint": _fingerprint(entries),
        },
        "content": {
            "generated_at": captured_at,
            "source_revision": scope["current_revision"],
            "entries": entries,
            "summary": {
                status: sum(1 for entry in entries if entry["status"] == status)
                for status in sorted({entry["status"] for entry in entries})
            },
        },
    }
