"""Atomic storage and cross-artifact validation for a coherence workspace."""

from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from .models import ARTIFACT_TYPES, METHODOLOGY_VERSION, utc_now
from .schema import validate_envelope


MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
_HISTORY_NAME_PATTERN = re.compile(r"^[0-9a-f]{64}\.json$")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _reject_non_finite_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _strict_json_loads(payload: str) -> Any:
    """Parse JSON without silently accepting duplicate keys or NaN values."""

    return json.loads(
        payload,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_non_finite_constant,
    )


def _fsync_directory(directory: Path) -> None:
    """Best-effort directory durability after an atomic replacement."""

    if os.name == "nt":
        return
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        _fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _atomic_copy_file(source: Path, target: Path) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    os.close(descriptor)
    try:
        shutil.copyfile(source, temporary_name)
        with open(temporary_name, "rb+") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary_name, target)
        _fsync_directory(target.parent)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def content_hash(envelope: dict[str, Any]) -> str:
    value = copy.deepcopy(envelope)
    value.pop("content_hash", None)
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def dependency_fingerprint(
    artifacts: dict[str, dict[str, Any]], inputs: list[str]
) -> str | None:
    """Return a stable digest of the logical input artifact snapshots."""

    dependencies: list[dict[str, str]] = []
    for input_id in sorted(inputs):
        if not input_id.startswith("artifact/"):
            return None
        artifact = artifacts.get(input_id.removeprefix("artifact/"))
        if artifact is None:
            return None
        dependencies.append(
            {
                "artifact_id": input_id,
                "content_hash": artifact.get("content_hash") or content_hash(artifact),
            }
        )
    return "deps-" + hashlib.sha256(_canonical_json(dependencies)).hexdigest()


@dataclass(frozen=True)
class Workspace:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root).resolve())

    @property
    def coherence_dir(self) -> Path:
        return self.root / ".coherence"

    @property
    def artifacts_dir(self) -> Path:
        return self.coherence_dir / "artifacts"

    @property
    def evidence_dir(self) -> Path:
        return self.coherence_dir / "evidence"

    @property
    def history_dir(self) -> Path:
        return self.coherence_dir / "history"

    @property
    def tmp_dir(self) -> Path:
        return self.coherence_dir / "tmp"

    def ensure(self) -> None:
        if self.root.exists() and not self.root.is_dir():
            raise ValueError(f"workspace root is not a directory: {self.root}")
        self.root.mkdir(parents=True, exist_ok=True)
        for path in (
            self.coherence_dir,
            self.artifacts_dir,
            self.evidence_dir,
            self.history_dir,
            self.tmp_dir,
        ):
            if path.is_symlink():
                raise ValueError(f"workspace path must not be a symlink: {path}")
            path.mkdir(parents=True, exist_ok=True)


class ArtifactStore:
    """Read and atomically write the current artifact snapshots."""

    def __init__(self, workspace: Workspace | Path) -> None:
        self.workspace = workspace if isinstance(workspace, Workspace) else Workspace(workspace)

    def _safe_path(self, path: Path) -> Path:
        if path.is_symlink() or any(
            parent.is_symlink()
            for parent in path.parents
            if parent != self.workspace.root
        ):
            raise ValueError(f"refusing to follow symlink in workspace: {path}")
        try:
            path.resolve(strict=False).relative_to(self.workspace.root)
        except ValueError as exc:
            raise ValueError(f"workspace path escapes target root: {path}") from exc
        return path

    def read(self, artifact_type: str) -> dict[str, Any] | None:
        if artifact_type not in ARTIFACT_TYPES:
            raise ValueError(f"unknown artifact_type: {artifact_type}")
        path = self.workspace.artifacts_dir / f"{artifact_type}.json"
        self._safe_path(path)
        if not path.exists():
            return None
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise ValueError(f"artifact exceeds {MAX_ARTIFACT_BYTES} bytes: {path}")
        try:
            value = _strict_json_loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"could not read {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"artifact file is not an object: {path}")
        return value

    def read_all(self) -> dict[str, dict[str, Any]]:
        artifacts: dict[str, dict[str, Any]] = {}
        errors: dict[str, str] = {}
        for artifact_type in ARTIFACT_TYPES:
            try:
                value = self.read(artifact_type)
            except ValueError as exc:
                errors[artifact_type] = str(exc)
                continue
            if value is not None:
                artifacts[artifact_type] = value
        if errors:
            detail = "; ".join(
                f"{artifact_type}: {message}" for artifact_type, message in errors.items()
            )
            raise ValueError(f"could not read all artifacts: {detail}")
        return artifacts

    def write(self, envelope: dict[str, Any]) -> Path:
        normalized = copy.deepcopy(envelope)
        normalized.setdefault("methodology_version", METHODOLOGY_VERSION)
        errors = validate_envelope(normalized)
        if normalized.get("methodology_version") != METHODOLOGY_VERSION:
            errors.append(
                "methodology_version must match the installed verifier: "
                + METHODOLOGY_VERSION
            )
        if errors:
            raise ValueError("invalid artifact: " + "; ".join(errors))

        self.workspace.ensure()
        artifact_type = normalized["artifact_type"]
        target = self.workspace.artifacts_dir / f"{artifact_type}.json"
        self._safe_path(target)
        superseded_evidence_ids: set[str] = set()
        if artifact_type == "repository-evidence":
            try:
                previous_evidence = self.read("repository-evidence")
            except ValueError:
                previous_evidence = None
            if (
                isinstance(previous_evidence, dict)
                and not validate_envelope(previous_evidence, expected_type="repository-evidence")
                and (
                    previous_evidence.get("content_hash") is None
                    or previous_evidence.get("content_hash") == content_hash(previous_evidence)
                )
            ):
                superseded_evidence_ids = {
                    item.get("evidence_id")
                    for item in previous_evidence.get("content", {}).get("files", [])
                    if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
                }

        candidate_artifacts = {artifact_type: normalized}
        for candidate_type in ARTIFACT_TYPES:
            if candidate_type == artifact_type:
                continue
            candidate_target = self.workspace.artifacts_dir / f"{candidate_type}.json"
            if not candidate_target.exists():
                continue
            try:
                candidate = self.read(candidate_type)
            except ValueError:
                continue
            if validate_envelope(candidate, expected_type=candidate_type):
                continue
            declared_hash = candidate.get("content_hash")
            if declared_hash is not None and declared_hash != content_hash(candidate):
                continue
            candidate_artifacts[candidate_type] = candidate
        inputs = normalized.get("inputs", [])
        if inputs:
            fingerprint = dependency_fingerprint(candidate_artifacts, inputs)
            if fingerprint is not None:
                freshness = dict(normalized["freshness"])
                freshness["dependency_fingerprint"] = fingerprint
                normalized["freshness"] = freshness
        normalized["content_hash"] = content_hash(normalized)
        reference_errors = self._reference_errors(
            candidate_artifacts, extra_evidence_ids=superseded_evidence_ids
        )
        if reference_errors:
            messages = [
                f"{candidate_type}: {message}"
                for candidate_type, candidate_messages in reference_errors.items()
                for message in candidate_messages
            ]
            raise ValueError("artifact references are invalid: " + "; ".join(messages))

        if target.exists():
            try:
                previous = self.read(artifact_type)
            except ValueError:
                previous = None
            if previous is not None:
                previous_hash = previous.get("content_hash") or content_hash(previous)
                if previous_hash != normalized["content_hash"]:
                    history_dir = self.workspace.history_dir / artifact_type
                    self._safe_path(history_dir)
                    history_dir.mkdir(parents=True, exist_ok=True)
                    history_target = history_dir / f"{previous_hash}.json"
                    self._safe_path(history_target)
                    if history_target.is_symlink():
                        raise ValueError(f"refusing to replace symlink: {history_target}")
                    if not history_target.exists():
                        _atomic_copy_file(target, history_target)

        payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        _atomic_write_text(target, payload)
        return target

    def _artifact_directory_errors(self) -> dict[str, list[str]]:
        errors: dict[str, list[str]] = {}
        artifacts_dir = self.workspace.artifacts_dir
        if not artifacts_dir.exists():
            return errors
        if artifacts_dir.is_symlink() or not artifacts_dir.is_dir():
            return {"artifacts": ["artifact directory must be a real directory"]}
        expected = {f"{artifact_type}.json" for artifact_type in ARTIFACT_TYPES}
        for path in artifacts_dir.iterdir():
            if path.name in expected and path.is_file() and not path.is_symlink():
                continue
            if path.is_symlink():
                message = "symlink is not allowed"
            elif path.is_dir():
                message = "directory is not allowed"
            elif path.name not in expected:
                message = "unknown artifact type or temporary artifact file"
            else:
                message = "artifact snapshot must be a regular file"
            key = path.stem if path.suffix.lower() == ".json" else path.name
            errors.setdefault(key, []).append(message)
        return errors

    def _history_errors(self) -> dict[str, list[str]]:
        errors: dict[str, list[str]] = {}
        history_root = self.workspace.history_dir
        if not history_root.exists():
            return errors
        if history_root.is_symlink() or not history_root.is_dir():
            return {"history": ["history directory must be a real directory"]}
        for directory in history_root.iterdir():
            key = f"history/{directory.name}"
            if directory.is_symlink() or not directory.is_dir():
                errors[key] = ["history entry must be a real directory"]
                continue
            if directory.name not in ARTIFACT_TYPES:
                errors[key] = ["unknown artifact history type"]
                continue
            for path in directory.iterdir():
                path_key = f"{key}/{path.name}"
                if path.is_symlink() or not path.is_file():
                    errors[path_key] = ["history snapshot must be a regular file"]
                    continue
                if not _HISTORY_NAME_PATTERN.fullmatch(path.name):
                    errors[path_key] = ["history snapshot name must be a SHA-256 hash"]
                    continue
                try:
                    if path.stat().st_size > MAX_ARTIFACT_BYTES:
                        raise ValueError(f"artifact exceeds {MAX_ARTIFACT_BYTES} bytes")
                    value = _strict_json_loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    errors[path_key] = [f"could not parse history snapshot: {exc}"]
                    continue
                validation_errors = validate_envelope(
                    value, expected_type=directory.name
                )
                if validation_errors:
                    errors[path_key] = validation_errors
                    continue
                declared_hash = value.get("content_hash")
                expected_hash = content_hash(value)
                if declared_hash != expected_hash:
                    errors[path_key] = ["history snapshot content_hash does not match"]
                elif path.stem != expected_hash:
                    errors[path_key] = ["history filename does not match content_hash"]
        return errors

    def _temporary_workspace_errors(self) -> dict[str, list[str]]:
        errors: dict[str, list[str]] = {}
        temporary_root = self.workspace.tmp_dir
        if not temporary_root.exists():
            return errors
        if temporary_root.is_symlink() or not temporary_root.is_dir():
            return {"tmp": ["temporary workspace must be a real directory"]}
        for path in temporary_root.rglob("*"):
            relative = path.relative_to(self.workspace.coherence_dir).as_posix()
            errors[relative] = [
                "orphaned temporary workspace entry; inspect interrupted write"
            ]
        return errors

    def validate_all(self) -> dict[str, list[str]]:
        errors_by_type: dict[str, list[str]] = {}
        artifacts: dict[str, dict[str, Any]] = {}
        errors_by_type.update(self._artifact_directory_errors())
        errors_by_type.update(self._history_errors())
        errors_by_type.update(self._temporary_workspace_errors())
        for artifact_type in ARTIFACT_TYPES:
            path = self.workspace.artifacts_dir / f"{artifact_type}.json"
            if not path.exists():
                continue
            try:
                self._safe_path(path)
                if path.stat().st_size > MAX_ARTIFACT_BYTES:
                    raise ValueError(
                        f"artifact exceeds {MAX_ARTIFACT_BYTES} bytes"
                    )
                value = _strict_json_loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                errors_by_type[artifact_type] = [f"could not parse artifact: {exc}"]
                continue
            errors = validate_envelope(value, expected_type=artifact_type)
            if errors:
                errors_by_type[artifact_type] = errors
            elif isinstance(value, dict):
                if value.get("methodology_version") != METHODOLOGY_VERSION:
                    errors_by_type[artifact_type] = [
                        "methodology_version does not match installed verifier"
                    ]
                else:
                    declared_hash = value.get("content_hash")
                    if declared_hash is None:
                        errors_by_type[artifact_type] = [
                            "content_hash is required for current artifact"
                        ]
                    elif declared_hash != content_hash(value):
                        errors_by_type[artifact_type] = [
                            "content_hash does not match artifact content"
                        ]
                    else:
                        artifacts[artifact_type] = value

        for artifact_type, messages in self._reference_errors(artifacts).items():
            errors_by_type.setdefault(artifact_type, []).extend(messages)
        for artifact_type, value in artifacts.items():
            inputs = value.get("inputs", [])
            if not inputs:
                continue
            expected = dependency_fingerprint(artifacts, inputs)
            declared = value.get("freshness", {}).get("dependency_fingerprint")
            if expected is not None and declared != expected:
                errors_by_type.setdefault(artifact_type, []).append(
                    "dependency fingerprint does not match inputs"
                )
        return errors_by_type

    def _historical_evidence_ids(self) -> set[str]:
        history_dir = self.workspace.history_dir / "repository-evidence"
        if not history_dir.exists():
            return set()
        evidence_ids: set[str] = set()
        for path in history_dir.glob("*.json"):
            if path.is_symlink():
                continue
            try:
                if path.stat().st_size > MAX_ARTIFACT_BYTES:
                    continue
                value = _strict_json_loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if validate_envelope(value, expected_type="repository-evidence"):
                continue
            declared_hash = value.get("content_hash")
            if declared_hash is not None and declared_hash != content_hash(value):
                continue
            evidence_ids.update(
                item.get("evidence_id")
                for item in value.get("content", {}).get("files", [])
                if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
            )
        return evidence_ids

    def _reference_errors(
        self,
        artifacts: dict[str, dict[str, Any]],
        *,
        extra_evidence_ids: set[str] | None = None,
    ) -> dict[str, list[str]]:
        errors: dict[str, list[str]] = {}
        available_artifact_ids = {
            value.get("artifact_id") for value in artifacts.values() if isinstance(value, dict)
        }

        def add(artifact_type: str, message: str) -> None:
            errors.setdefault(artifact_type, []).append(message)

        def ref_values(item: dict[str, Any], field: str) -> list[Any]:
            value = item.get(field, [])
            return value if isinstance(value, list) else []

        for artifact_type, value in artifacts.items():
            for input_id in value.get("inputs", []):
                if input_id not in available_artifact_ids:
                    add(artifact_type, f"input references missing artifact: {input_id}")

        # Artifact inputs form a directed acyclic derivation graph.  A cycle
        # would make freshness impossible to establish and can otherwise look
        # valid when every individual reference exists.
        input_graph = {
            value.get("artifact_id"): list(value.get("inputs", []))
            for value in artifacts.values()
            if isinstance(value, dict) and isinstance(value.get("artifact_id"), str)
        }
        artifact_types_by_id = {
            value.get("artifact_id"): artifact_type
            for artifact_type, value in artifacts.items()
            if isinstance(value, dict) and isinstance(value.get("artifact_id"), str)
        }
        visiting: set[str] = set()
        visited: set[str] = set()
        reported_cycles: set[tuple[str, ...]] = set()

        def visit(node: str, stack: list[str]) -> None:
            if node in visiting:
                cycle = tuple(stack[stack.index(node) :] + [node])
                if cycle in reported_cycles:
                    return
                reported_cycles.add(cycle)
                labels = " -> ".join(cycle)
                for cycle_node in set(cycle):
                    artifact_type = artifact_types_by_id.get(cycle_node)
                    if artifact_type:
                        add(artifact_type, f"artifact input cycle detected: {labels}")
                return
            if node in visited:
                return
            visiting.add(node)
            stack.append(node)
            for dependency in input_graph.get(node, []):
                if dependency in input_graph:
                    visit(dependency, stack)
            stack.pop()
            visiting.remove(node)
            visited.add(node)

        for node in input_graph:
            visit(node, [])

        evidence_content = artifacts.get("repository-evidence", {}).get("content", {})
        evidence_ids = {
            item.get("evidence_id")
            for item in evidence_content.get("files", [])
            if isinstance(item, dict)
        }
        evidence_ids.update(self._historical_evidence_ids())
        evidence_ids.update(extra_evidence_ids or set())
        if artifacts.get("repository-evidence") is not None:
            for artifact_type, value in artifacts.items():
                if artifact_type == "repository-evidence":
                    continue
                for evidence_ref in value.get("evidence_refs", []):
                    if evidence_ref not in evidence_ids:
                        add(
                            artifact_type,
                            f"evidence reference not found: {evidence_ref}",
                        )

        def check_nested_evidence(
            artifact_type: str, items: list[Any], field_name: str = "evidence_refs"
        ) -> None:
            for item in items:
                if not isinstance(item, dict):
                    continue
                for evidence_ref in ref_values(item, field_name):
                    if evidence_ref not in evidence_ids:
                        add(
                            artifact_type,
                            f"evidence reference not found: {evidence_ref}",
                        )

        system_content = artifacts.get("system-model", {}).get("content", {})
        check_nested_evidence("system-model", [system_content])
        for artifact_type, collection_name in (
            ("capability-map", "capabilities"),
            ("behavioral-contracts", "contracts"),
            ("state-model", "transitions"),
            ("implementation-traces", "traces"),
            ("audit-findings", "findings"),
            ("revalidation-results", "validations"),
            ("coherence-ledger", "entries"),
        ):
            collection = artifacts.get(artifact_type, {}).get("content", {}).get(
                collection_name, []
            )
            if isinstance(collection, list):
                check_nested_evidence(artifact_type, collection)

        content = artifacts.get("capability-map", {}).get("content", {})
        capability_ids = {
            item.get("capability_id")
            for item in content.get("capabilities", [])
            if isinstance(item, dict)
        }
        system_resources = system_content.get("resources", [])
        if not isinstance(system_resources, list):
            system_resources = []
        resource_ids = {
            item.get("resource_id")
            for item in system_resources
            if isinstance(item, dict)
        }
        if artifacts.get("system-model") is not None:
            for item in content.get("capabilities", []):
                if not isinstance(item, dict):
                    continue
                for resource_id in ref_values(item, "resource_ids"):
                    if resource_id not in resource_ids:
                        add(
                            "capability-map",
                            f"capability references missing resource: {resource_id}",
                        )

        def collection_ids(
            artifact_type: str, collection_name: str, id_field: str
        ) -> set[str] | None:
            artifact = artifacts.get(artifact_type)
            if artifact is None:
                return None
            entries = artifact.get("content", {}).get(collection_name, [])
            return {
                item[id_field]
                for item in entries
                if isinstance(item, dict) and isinstance(item.get(id_field), str)
            }

        contracts = artifacts.get("behavioral-contracts", {}).get("content", {}).get(
            "contracts", []
        )
        contract_ids = {
            item.get("contract_id") for item in contracts if isinstance(item, dict)
        }
        state_ids = collection_ids("state-model", "states", "state_id")
        transition_ids = collection_ids(
            "state-model", "transitions", "transition_id"
        )
        for item in contracts:
            if isinstance(item, dict) and item.get("capability_id") not in capability_ids:
                add(
                    "behavioral-contracts",
                    f"contract references missing capability: {item.get('capability_id')}",
                )
            expected_transition = item.get("expected_transition") if isinstance(item, dict) else None
            if (
                transition_ids is not None
                and isinstance(expected_transition, str)
                and expected_transition not in transition_ids
            ):
                add(
                    "behavioral-contracts",
                    "expected_transition references missing transition: "
                    + expected_transition,
                )

        state_content = artifacts.get("state-model", {}).get("content", {})
        if state_ids is not None and transition_ids is not None:
            for transition in state_content.get("transitions", []):
                if not isinstance(transition, dict):
                    continue
                for contract_id in ref_values(transition, "contract_ids"):
                    if (
                        artifacts.get("behavioral-contracts") is not None
                        and contract_id not in contract_ids
                    ):
                        add(
                            "state-model",
                            f"transition references missing contract: {contract_id}",
                        )
                endpoints = ref_values(transition, "from_state_ids") + ref_values(
                    transition, "to_state_ids"
                )
                for endpoint in endpoints:
                    if endpoint not in state_ids:
                        add(
                            "state-model",
                            f"transition references missing state: {endpoint}",
                        )
        trace_content = artifacts.get("implementation-traces", {}).get("content", {})
        trace_ids = {
            item.get("trace_id")
            for item in trace_content.get("traces", [])
            if isinstance(item, dict)
        }
        for item in trace_content.get("traces", []):
            if not isinstance(item, dict):
                continue
            for contract_id in ref_values(item, "contract_ids"):
                if contract_id not in contract_ids:
                    add("implementation-traces", f"trace references missing contract: {contract_id}")
            for capability_id in ref_values(item, "capability_ids"):
                if capability_id not in capability_ids:
                    add(
                        "implementation-traces",
                        f"trace references missing capability: {capability_id}",
                    )
            for transition_id in ref_values(item, "transition_ids"):
                if transition_ids is not None and transition_id not in transition_ids:
                    add(
                        "implementation-traces",
                        f"trace references missing transition: {transition_id}",
                    )

        finding_content = artifacts.get("audit-findings", {}).get("content", {})
        for item in finding_content.get("findings", []):
            if not isinstance(item, dict):
                continue
            for capability_id in ref_values(item, "capability_ids"):
                if capability_id not in capability_ids:
                    add("audit-findings", f"finding references missing capability: {capability_id}")
            for contract_id in ref_values(item, "contract_ids"):
                if (
                    artifacts.get("behavioral-contracts") is not None
                    and contract_id not in contract_ids
                ):
                    add("audit-findings", f"finding references missing contract: {contract_id}")
            for transition_id in ref_values(item, "transition_ids"):
                if (
                    transition_ids is not None
                    and transition_id not in transition_ids
                ):
                    add("audit-findings", f"finding references missing transition: {transition_id}")
            for trace_id in ref_values(item, "trace_ids"):
                if (
                    artifacts.get("implementation-traces") is not None
                    and trace_id not in trace_ids
                ):
                    add("audit-findings", f"finding references missing trace: {trace_id}")

        intervention_content = artifacts.get("intervention-plan", {}).get("content", {})
        for item in intervention_content.get("actions", []):
            if not isinstance(item, dict):
                continue
            for finding_id in ref_values(item, "finding_ids"):
                if (
                    artifacts.get("audit-findings") is not None
                    and finding_id not in {
                        finding.get("finding_id")
                        for finding in finding_content.get("findings", [])
                        if isinstance(finding, dict)
                    }
                ):
                    add("intervention-plan", f"action references missing finding: {finding_id}")

        regression_content = artifacts.get("regression-scope", {}).get("content", {})
        for trace_id in regression_content.get("matched_trace_ids", []):
            if (
                artifacts.get("implementation-traces") is not None
                and trace_id
                not in {
                    trace.get("trace_id")
                    for trace in trace_content.get("traces", [])
                    if isinstance(trace, dict)
                }
            ):
                add("regression-scope", f"scope references missing trace: {trace_id}")
        for contract_id in regression_content.get("invalidated_contract_ids", []):
            if (
                artifacts.get("behavioral-contracts") is not None
                and contract_id not in contract_ids
            ):
                add("regression-scope", f"scope references missing contract: {contract_id}")
        for capability_id in regression_content.get("impacted_capability_ids", []):
            if (
                artifacts.get("capability-map") is not None
                and capability_id not in capability_ids
            ):
                add("regression-scope", f"scope references missing capability: {capability_id}")

        finding_ids = {
            finding.get("finding_id")
            for finding in finding_content.get("findings", [])
            if isinstance(finding, dict)
        }
        revalidation_content = artifacts.get("revalidation-results", {}).get("content", {})
        for item in revalidation_content.get("validations", []):
            if not isinstance(item, dict):
                continue
            target_type = item.get("target_type")
            target_id = item.get("target_id")
            target_sets = {
                "capability": capability_ids,
                "contract": contract_ids,
                "transition": transition_ids or set(),
                "trace": trace_ids,
                "finding": finding_ids,
            }
            target_artifacts = {
                "capability": "capability-map",
                "contract": "behavioral-contracts",
                "transition": "state-model",
                "trace": "implementation-traces",
                "finding": "audit-findings",
            }
            if (
                isinstance(target_type, str)
                and isinstance(target_id, str)
                and target_type in target_sets
                and target_artifacts[target_type] in artifacts
                and target_id not in target_sets[target_type]
            ):
                add(
                    "revalidation-results",
                    f"validation references missing {target_type}: {target_id}",
                )
            for capability_id in ref_values(item, "capability_ids"):
                if (
                    artifacts.get("capability-map") is not None
                    and capability_id not in capability_ids
                ):
                    add(
                        "revalidation-results",
                        f"validation references missing capability: {capability_id}",
                    )

        ledger_content = artifacts.get("coherence-ledger", {}).get("content", {})
        for item in ledger_content.get("entries", []):
            if not isinstance(item, dict):
                continue
            capability_id = item.get("capability_id")
            if (
                artifacts.get("capability-map") is not None
                and capability_id not in capability_ids
            ):
                add("coherence-ledger", f"ledger references missing capability: {capability_id}")
            for contract_id in ref_values(item, "contract_ids"):
                if (
                    artifacts.get("behavioral-contracts") is not None
                    and contract_id not in contract_ids
                ):
                    add("coherence-ledger", f"ledger references missing contract: {contract_id}")
            for finding_id in ref_values(item, "finding_ids"):
                if (
                    artifacts.get("audit-findings") is not None
                    and finding_id not in finding_ids
                ):
                    add("coherence-ledger", f"ledger references missing finding: {finding_id}")

        return errors
