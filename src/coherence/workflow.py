"""The explicit stage registry and resumable orchestration decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence import capture
from .models import ARTIFACT_TYPES, METHODOLOGY_VERSION
from .store import ArtifactStore


@dataclass(frozen=True)
class Stage:
    key: str
    skill: str
    required_artifacts: tuple[str, ...]
    output_artifact: str
    context_paths: tuple[str, ...]


STAGES = (
    Stage("evidence", "system-coherence", (), "repository-evidence", ("repository",)),
    Stage(
        "reconstruction",
        "reconstruct-system",
        ("repository-evidence",),
        "system-model",
        (".coherence/artifacts/repository-evidence.json", "repository"),
    ),
    Stage(
        "capabilities",
        "discover-capabilities",
        ("repository-evidence", "system-model"),
        "capability-map",
        (".coherence/artifacts/system-model.json", "repository"),
    ),
    Stage(
        "contracts",
        "model-behavior",
        ("repository-evidence", "system-model", "capability-map"),
        "behavioral-contracts",
        (".coherence/artifacts/capability-map.json", "repository"),
    ),
    Stage(
        "states",
        "model-states",
        ("system-model", "capability-map", "behavioral-contracts"),
        "state-model",
        (".coherence/artifacts/behavioral-contracts.json", "repository"),
    ),
    Stage(
        "traces",
        "trace-implementation",
        ("repository-evidence", "behavioral-contracts", "state-model"),
        "implementation-traces",
        (".coherence/artifacts/state-model.json", "repository"),
    ),
    Stage(
        "audit",
        "audit-coherence",
        (
            "repository-evidence",
            "system-model",
            "capability-map",
            "behavioral-contracts",
            "state-model",
            "implementation-traces",
        ),
        "audit-findings",
        (".coherence/artifacts/implementation-traces.json", "repository"),
    ),
    Stage(
        "intervention",
        "plan-remediation",
        ("audit-findings", "implementation-traces", "behavioral-contracts"),
        "intervention-plan",
        (".coherence/artifacts/audit-findings.json", "repository"),
    ),
    Stage(
        "regression",
        "analyze-regression",
        ("implementation-traces", "behavioral-contracts", "capability-map"),
        "regression-scope",
        (".coherence/artifacts/implementation-traces.json", "git diff"),
    ),
    Stage(
        "revalidation",
        "revalidate-coherence",
        ("regression-scope", "intervention-plan", "audit-findings"),
        "revalidation-results",
        (".coherence/artifacts/regression-scope.json", "repository"),
    ),
    Stage(
        "ledger",
        "system-coherence",
        ("capability-map", "audit-findings", "revalidation-results"),
        "coherence-ledger",
        (".coherence/artifacts/revalidation-results.json", "repository"),
    ),
)


def stage_for_artifact(artifact_type: str) -> Stage:
    for stage in STAGES:
        if stage.output_artifact == artifact_type:
            return stage
    raise ValueError(f"unknown artifact type: {artifact_type}")


def validate_graph(store: ArtifactStore) -> list[str]:
    """Return artifact-format and reference errors in readable order."""

    errors: list[str] = []
    for artifact_type, messages in store.validate_all().items():
        errors.extend(f"{artifact_type}: {message}" for message in messages)
    return errors


def _revision(store: ArtifactStore) -> str | None:
    try:
        evidence = store.read("repository-evidence")
    except ValueError:
        return None
    if not evidence:
        return None
    return evidence.get("source_revision")


def _scope_target_revision(store: ArtifactStore) -> str | None:
    try:
        scope = store.read("regression-scope")
    except ValueError:
        return None
    if not scope:
        return None
    target_revision = scope.get("content", {}).get("target_revision")
    return target_revision if isinstance(target_revision, str) and target_revision else None


def _current_revision(store: ArtifactStore) -> str | None:
    try:
        return capture(store.workspace.root).get("source_revision")
    except OSError:
        return None


def _needs_repair(
    value: dict[str, Any],
    source_revision: str | None,
    artifact_type: str,
    store: ArtifactStore,
) -> str | None:
    status = value.get("status")
    methodology_version = value.get("methodology_version")
    if methodology_version != METHODOLOGY_VERSION:
        return "artifact methodology version is not current"
    if status == "blocked":
        return "required artifact is blocked"
    if status == "invalid":
        return "artifact is marked invalid"
    if status == "stale":
        return "artifact is stale"
    freshness = value.get("freshness", {})
    if isinstance(freshness, dict) and freshness.get("state") == "stale":
        return "artifact freshness is stale"
    if isinstance(freshness, dict) and freshness.get("state") == "unknown":
        return "artifact freshness is unknown"
    if (
        artifact_type != "repository-evidence"
        and source_revision
        and value.get("source_revision")
        and value.get("source_revision") != source_revision
    ):
        if (
            artifact_type in {"regression-scope", "revalidation-results", "coherence-ledger"}
            and value.get("source_revision") == _scope_target_revision(store)
        ):
            return None
        return "artifact was produced for a different source revision"
    return None


def _route_for_stage(stage: Stage, reason: str, repair_artifact: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "stage": stage.key,
        "skill": stage.skill,
        "reason": reason,
        "required_artifacts": list(stage.required_artifacts),
        "produces": [stage.output_artifact],
        "context_paths": list(stage.context_paths),
    }
    if repair_artifact is not None:
        result["repair_artifact"] = repair_artifact
    return result


def _prerequisite_issue(
    store: ArtifactStore, stage: Stage, source_revision: str | None
) -> tuple[Stage, str, str] | None:
    """Return the owning stage for the first unusable stage prerequisite."""

    for required_artifact in stage.required_artifacts:
        try:
            value = store.read(required_artifact)
        except ValueError:
            owner = stage_for_artifact(required_artifact)
            return owner, f"prerequisite {required_artifact} is invalid", required_artifact
        if value is None:
            owner = stage_for_artifact(required_artifact)
            return owner, f"prerequisite {required_artifact} is missing", required_artifact
        reason = _needs_repair(value, source_revision, required_artifact, store)
        if reason:
            owner = stage_for_artifact(required_artifact)
            return owner, f"prerequisite {required_artifact}: {reason}", required_artifact
    return None


def _ledger_route(store: ArtifactStore) -> dict[str, Any] | None:
    """Route unresolved capability statuses instead of treating a valid graph as success."""

    ledger = store.read("coherence-ledger")
    if ledger is None:
        return None
    content = ledger.get("content", {})
    entries = content.get("entries", []) if isinstance(content, dict) else []
    capability_content = store.read("capability-map")
    capability_payload = (
        capability_content.get("content", {})
        if isinstance(capability_content, dict)
        else {}
    )
    capabilities = (
        capability_payload.get("capabilities", [])
        if isinstance(capability_payload, dict)
        else []
    )
    capability_ids = {
        item.get("capability_id")
        for item in capabilities
        if isinstance(item, dict) and isinstance(item.get("capability_id"), str)
    }
    entry_ids = {
        entry.get("capability_id")
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("capability_id"), str)
    } if isinstance(entries, list) else set()
    statuses = {
        entry.get("status")
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("status"), str)
    }
    if (
        ledger.get("status") != "complete"
        or not isinstance(entries, list)
        or entry_ids != capability_ids
    ):
        return _route_for_stage(
            STAGES[-1],
            "coherence ledger is incomplete or does not cover every capability",
            repair_artifact="coherence-ledger",
        )
    unresolved = statuses.difference({"verified"})
    if not unresolved:
        return None
    if unresolved.intersection({"needs-revalidation", "unverified"}):
        return _route_for_stage(
            STAGES[-2],
            "ledger contains capabilities without current verification",
            repair_artifact="revalidation-results",
        )
    return _route_for_stage(
        STAGES[7],
        "ledger contains unresolved findings or failed validation",
        repair_artifact="intervention-plan",
    )


def route(store: ArtifactStore) -> dict[str, Any]:
    """Choose the next safe skill using only current repository artifacts."""

    graph_errors = store.validate_all()
    source_revision = _revision(store)
    try:
        evidence = store.read("repository-evidence")
    except ValueError:
        evidence = None
    if evidence is not None:
        evidence_reason = _needs_repair(
            evidence, source_revision, "repository-evidence", store
        )
        if evidence_reason:
            return _route_for_stage(
                STAGES[0], evidence_reason, repair_artifact="repository-evidence"
            )
    for stage in STAGES:
        if stage.output_artifact in graph_errors:
            return _route_for_stage(
                stage, "artifact is invalid", repair_artifact=stage.output_artifact
            )
    if graph_errors:
        return {
            "stage": "validation",
            "skill": "system-coherence",
            "reason": "artifact graph has validation errors",
            "required_artifacts": [],
            "produces": [],
            "context_paths": [".coherence/artifacts"],
            "validation_errors": graph_errors,
        }

    current_revision = _current_revision(store)
    if (
        source_revision
        and current_revision
        and current_revision != source_revision
        and _scope_target_revision(store) != current_revision
    ):
        return _route_for_stage(
            STAGES[0],
            "repository evidence does not match the current repository",
            repair_artifact="repository-evidence",
        )

    for stage in STAGES:
        prerequisite = _prerequisite_issue(store, stage, source_revision)
        if prerequisite:
            owner, reason, artifact_type = prerequisite
            return _route_for_stage(owner, reason, repair_artifact=artifact_type)
        value = store.read(stage.output_artifact)
        if value is None:
            return _route_for_stage(stage, "required artifact is missing")
        reason = _needs_repair(value, source_revision, stage.output_artifact, store)
        if reason:
            return _route_for_stage(
                stage, reason, repair_artifact=stage.output_artifact
            )
        declared_inputs = value.get("inputs", [])
        missing_inputs = [
            required
            for required in stage.required_artifacts
            if f"artifact/{required}" not in declared_inputs
        ]
        if missing_inputs:
            return _route_for_stage(
                stage,
                "required stage input is missing: " + ", ".join(missing_inputs),
                repair_artifact=stage.output_artifact,
            )

    ledger_route = _ledger_route(store)
    if ledger_route is not None:
        return ledger_route

    return {
        "stage": "complete",
        "skill": "system-coherence",
        "reason": "all workflow artifacts are current",
        "required_artifacts": list(ARTIFACT_TYPES),
        "produces": [],
        "context_paths": [".coherence/artifacts", "repository"],
    }
