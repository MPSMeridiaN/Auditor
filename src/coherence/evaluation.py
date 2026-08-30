"""Executable fixture evaluations for the framework's documented examples."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from typing import Any


REQUIRED_SCENARIO_FIELDS = (
    "scenario_id",
    "architecture",
    "module",
    "class",
    "probe",
    "capability_ids",
    "expected_finding_category",
    "expected_finding",
    "negative_control",
    "evidence_paths",
)


def _safe_path(root: Path, relative_path: str) -> Path | None:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        return None
    candidate = root / path
    if candidate.is_symlink():
        return None
    if any(parent.is_symlink() for parent in candidate.parents if parent != root):
        return None
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def validate_scenarios(root: Path, scenarios: Any) -> list[str]:
    """Validate scenario metadata and repository evidence paths."""

    root = Path(root).resolve()
    if not isinstance(scenarios, list):
        return ["scenario metadata must be an array"]
    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, scenario in enumerate(scenarios):
        prefix = f"scenario[{index}]"
        if not isinstance(scenario, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in REQUIRED_SCENARIO_FIELDS:
            if field not in scenario:
                errors.append(f"{prefix} missing required field: {field}")
        scenario_id = scenario.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            errors.append(f"{prefix}.scenario_id must be a non-empty string")
        elif scenario_id in seen_ids:
            errors.append(f"duplicate scenario_id: {scenario_id}")
        else:
            seen_ids.add(scenario_id)
        for field in ("architecture", "module", "class", "probe"):
            if not isinstance(scenario.get(field), str) or not scenario[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        capability_ids = scenario.get("capability_ids")
        if (
            not isinstance(capability_ids, list)
            or not capability_ids
            or any(not isinstance(item, str) or not item.strip() for item in capability_ids)
        ):
            errors.append(f"{prefix}.capability_ids must be a non-empty string list")
        evidence_paths = scenario.get("evidence_paths")
        if not isinstance(evidence_paths, list) or any(
            not isinstance(item, str) or not item.strip() for item in evidence_paths
        ):
            errors.append(f"{prefix}.evidence_paths must be a string list")
        else:
            for relative_path in evidence_paths:
                resolved = _safe_path(root, relative_path)
                if resolved is None or not resolved.is_file():
                    errors.append(f"{prefix} evidence path does not exist: {relative_path}")
        module_path = scenario.get("module")
        if isinstance(module_path, str):
            resolved = _safe_path(root, module_path)
            if resolved is None or not resolved.is_file():
                errors.append(f"{prefix} module path does not exist: {module_path}")
        if not isinstance(scenario.get("expected_finding"), bool):
            errors.append(f"{prefix}.expected_finding must be a boolean")
        if not isinstance(scenario.get("negative_control"), bool):
            errors.append(f"{prefix}.negative_control must be a boolean")
        elif scenario.get("negative_control") and scenario.get("expected_finding"):
            errors.append(f"{prefix} negative controls cannot expect a finding")
        category = scenario.get("expected_finding_category")
        if scenario.get("expected_finding") and (
            not isinstance(category, str) or not category.strip()
        ):
            errors.append(f"{prefix}.expected_finding_category is required for findings")
        if not scenario.get("expected_finding") and category is not None:
            errors.append(f"{prefix}.expected_finding_category must be null for clean scenarios")
    return errors


def _load_module(root: Path, relative_path: str, module_name: str):
    path = _safe_path(root, relative_path)
    if path is None:
        raise ValueError(f"unsafe fixture module path: {relative_path}")
    spec = spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load fixture module: {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _probe(module: Any, probe_name: str) -> tuple[bool, dict[str, Any]]:
    if probe_name == "delete_cache":
        system = module.WebCache()
        system.create("document", "payload")
        system.delete("document")
        observed = system.get("document")
        detected = observed == "payload"
        return detected, {
            "database_contains_document": "document" in system.database,
            "cache_contains_document": "document" in system.cache,
            "read_after_delete": observed,
        }
    if probe_name == "failed_side_effect":
        worker = module.Worker()
        completed = worker.process("job-1", fail_side_effect=True)
        detected = worker.status("job-1") == "completed" and "job-1" not in worker.outputs
        return detected, {
            "process_returned": completed,
            "status_after_failure": worker.status("job-1"),
            "output_exists": "job-1" in worker.outputs,
        }
    if probe_name == "atomic_rename":
        ledger = module.CleanLedger()
        ledger.rename("old", "new")
        stale_alias = ledger.lookup("old") is not None
        detected = stale_alias or ledger.lookup("new") != "present"
        return detected, {
            "old_lookup": ledger.lookup("old"),
            "new_lookup": ledger.lookup("new"),
        }
    raise ValueError(f"unknown evaluation probe: {probe_name}")


def run_evaluations(root: Path) -> dict[str, Any]:
    """Execute all scenarios and return a stable, machine-readable report."""

    root = Path(root).resolve()
    try:
        scenarios = json.loads(
            (root / "examples" / "scenarios.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "scenario_count": 0,
            "passed": 0,
            "failed": 1,
            "findings_detected": [],
            "results": [],
            "validation_errors": [f"could not read scenario metadata: {exc}"],
        }
    metadata_errors = validate_scenarios(root, scenarios)
    if metadata_errors:
        scenario_count = len(scenarios) if isinstance(scenarios, list) else 0
        return {
            "scenario_count": scenario_count,
            "passed": 0,
            "failed": len(metadata_errors),
            "findings_detected": [],
            "results": [],
            "validation_errors": metadata_errors,
        }
    results: list[dict[str, Any]] = []
    findings_detected: list[str] = []
    for index, scenario in enumerate(scenarios):
        scenario_id = scenario["scenario_id"]
        try:
            module = _load_module(root, scenario["module"], f"coherence_fixture_{index}")
            detected, observed = _probe(module, scenario["probe"])
            passed = detected == scenario["expected_finding"]
            error = None
        except Exception as exc:
            detected = False
            observed = {}
            passed = False
            error = str(exc)
        if detected and scenario.get("expected_finding_category"):
            findings_detected.append(scenario["expected_finding_category"])
        result = {
            "scenario_id": scenario_id,
            "architecture": scenario["architecture"],
            "probe": scenario["probe"],
            "passed": passed,
            "finding_detected": detected,
            "expected_finding": scenario["expected_finding"],
            "expected_finding_category": scenario.get("expected_finding_category"),
            "capability_ids": scenario["capability_ids"],
            "negative_control": scenario["negative_control"],
            "observed": observed,
            "evidence_paths": scenario.get("evidence_paths", []),
        }
        if error:
            result["error"] = error
        results.append(result)
    return {
        "scenario_count": len(results),
        "passed": sum(1 for result in results if result["passed"]),
        "failed": sum(1 for result in results if not result["passed"]),
        "findings_detected": findings_detected,
        "results": results,
    }
