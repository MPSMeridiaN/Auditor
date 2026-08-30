"""Map changed implementation paths to scoped behavioral revalidation."""

from __future__ import annotations

import fnmatch
from pathlib import Path
import subprocess
from typing import Any

from .models import METHODOLOGY_VERSION, stable_id, utc_now
from .store import ArtifactStore


INVALIDATED_ARTIFACT_TYPES = [
    "implementation-traces",
    "audit-findings",
    "intervention-plan",
    "revalidation-results",
    "coherence-ledger",
]


def _normalize_path(path: str, root: Path | None = None) -> str:
    normalized = str(path).replace("\\", "/").strip()
    if not normalized:
        return ""
    if root is None:
        while normalized.startswith("./"):
            normalized = normalized[2:]
        return normalized

    root = Path(root).resolve()
    candidate = Path(normalized)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"changed path is outside target repository: {path}") from exc
    return relative.as_posix()


def changed_paths(
    root: Path, base: str | None = None, explicit: list[str] | None = None
) -> list[str]:
    """Resolve explicit paths or a git diff into normalized POSIX paths."""

    if explicit:
        root = Path(root).resolve()
        return sorted(
            {
                _normalize_path(path, root)
                for path in explicit
                if isinstance(path, str) and path.strip()
            }
        )
    if not base:
        return []
    try:
        result = subprocess.run(
            ["git", "-C", str(Path(root).resolve()), "diff", "--name-only", base, "--"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"could not resolve git diff base {base}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or "git diff failed"
        raise ValueError(f"could not resolve git diff base {base}: {detail}")
    paths = {
        _normalize_path(line)
        for line in result.stdout.splitlines()
        if line.strip()
    }
    # ``git diff`` omits untracked files.  They are still implementation or
    # documentation evidence and must not silently escape the regression scope.
    try:
        status = subprocess.run(
            [
                "git",
                "-C",
                str(Path(root).resolve()),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"could not inspect git status: {exc}") from exc
    if status.returncode != 0:
        detail = status.stderr.strip() or "git status failed"
        raise ValueError(f"could not inspect git status: {detail}")
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        raw_path = line[3:].strip()
        for candidate in raw_path.split(" -> "):
            if candidate:
                paths.add(_normalize_path(candidate))
    return sorted(paths)


def _matches(path: str, pattern: str) -> bool:
    pattern = _normalize_path(pattern)
    return path == pattern or fnmatch.fnmatchcase(path, pattern)


def compute_scope(
    store: ArtifactStore, paths: list[str], source_revision: str
) -> dict[str, Any]:
    """Build a regression-scope envelope without mutating prior artifacts."""

    changed = sorted(
        {
            _normalize_path(path)
            for path in paths
            if isinstance(path, str) and path.strip()
        }
    )
    traces_artifact = store.read("implementation-traces")
    traces = []
    if traces_artifact:
        trace_content = traces_artifact.get("content", {})
        if isinstance(trace_content, dict):
            traces = trace_content.get("traces", [])
    if not isinstance(traces, list):
        traces = []

    matched_trace_ids: set[str] = set()
    invalidated_contract_ids: set[str] = set()
    impacted_capability_ids: set[str] = set()
    matched_paths: set[str] = set()
    for trace in traces:
        if not isinstance(trace, dict):
            continue
        source_paths = trace.get("source_paths", [])
        entrypoints = trace.get("entrypoints", [])
        if not isinstance(source_paths, list):
            source_paths = []
        if not isinstance(entrypoints, list):
            entrypoints = []
        patterns = source_paths + entrypoints
        trace_matches = {path for path in changed if any(_matches(path, pattern) for pattern in patterns)}
        if not trace_matches:
            continue
        trace_id = trace.get("trace_id")
        if isinstance(trace_id, str):
            matched_trace_ids.add(trace_id)
        matched_paths.update(trace_matches)
        contract_ids = trace.get("contract_ids", [])
        capability_ids = trace.get("capability_ids", [])
        if isinstance(contract_ids, list):
            invalidated_contract_ids.update(
                item for item in contract_ids if isinstance(item, str)
            )
        if isinstance(capability_ids, list):
            impacted_capability_ids.update(
                item for item in capability_ids if isinstance(item, str)
            )

    contracts_artifact = store.read("behavioral-contracts")
    contract_content = (
        contracts_artifact.get("content", {}) if contracts_artifact else {}
    )
    contracts = (
        contract_content.get("contracts", [])
        if isinstance(contract_content, dict)
        else []
    )
    if not isinstance(contracts, list):
        contracts = []
    for contract in contracts:
        if not isinstance(contract, dict) or contract.get("contract_id") not in invalidated_contract_ids:
            continue
        capability_id = contract.get("capability_id")
        if isinstance(capability_id, str):
            impacted_capability_ids.add(capability_id)

    unknown_paths = sorted(set(changed) - matched_paths)
    evidence = store.read("repository-evidence")
    evidence_content = (evidence or {}).get("content", {})
    evidence_files = evidence_content.get("files", []) if isinstance(evidence_content, dict) else []
    evidence_by_path = {
        item.get("path"): item.get("evidence_id")
        for item in evidence_files
        if isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and isinstance(item.get("evidence_id"), str)
    }
    evidence_refs = sorted(
        evidence_by_path[path] for path in changed if path in evidence_by_path
    )
    captured_at = utc_now()
    all_inputs = [
        f"artifact/{artifact_type}"
        for artifact_type in (
            "repository-evidence",
            "capability-map",
            "behavioral-contracts",
            "implementation-traces",
        )
        if store.read(artifact_type) is not None
    ]
    uncertainty = [
        {
            "kind": "scope-unknown",
            "message": f"No implementation trace covers changed path: {path}",
            "path": path,
        }
        for path in unknown_paths
    ]
    return {
        "artifact_type": "regression-scope",
        "schema_version": "1.0",
        "methodology_version": METHODOLOGY_VERSION,
        "artifact_id": "artifact/regression-scope",
        "run_id": stable_id("run", f"regression:{source_revision}:{'|'.join(changed)}"),
        "status": "partial" if unknown_paths else "complete",
        "source_revision": source_revision,
        "created_at": captured_at,
        "producer": {"skill": "analyze-regression", "agent": "coherence-cli"},
        "inputs": all_inputs,
        "evidence_refs": evidence_refs,
        "uncertainty": uncertainty,
        "freshness": {
            "state": "current",
            "checked_at": captured_at,
            "dependency_fingerprint": source_revision,
        },
        "content": {
            "change_set_id": stable_id("act", f"change:{source_revision}:{'|'.join(changed)}"),
            "changed_paths": changed,
            "target_revision": source_revision,
            "matched_trace_ids": sorted(matched_trace_ids),
            "invalidated_contract_ids": sorted(invalidated_contract_ids),
            "impacted_capability_ids": sorted(impacted_capability_ids),
            "scope_unknown_paths": unknown_paths,
            "requires_broad_revalidation": bool(unknown_paths),
            "invalidated_artifact_types": INVALIDATED_ARTIFACT_TYPES,
        },
    }


def apply_scope(store: ArtifactStore, scope: dict[str, Any]) -> dict[str, Any]:
    """Persist a scope and derive a fresh ledger from its impact."""

    store.write(scope)
    existing_revalidation = store.read("revalidation-results")
    if existing_revalidation is not None and existing_revalidation.get("status") not in {
        "blocked",
        "invalid",
    }:
        stale = dict(existing_revalidation)
        stale["status"] = "stale"
        stale["freshness"] = dict(stale.get("freshness", {}))
        stale["freshness"]["state"] = "stale"
        store.write(stale)
    from .ledger import derive

    ledger = derive(store)
    store.write(ledger)
    return ledger
