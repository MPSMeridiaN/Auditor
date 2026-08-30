"""Read-only environment and repository diagnostics for the doctor command."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
from typing import Any

from .skills import PUBLIC_SKILLS, validate_skill_tree
from .store import ArtifactStore, Workspace


def _check(
    checks: list[dict[str, Any]],
    name: str,
    status: str,
    message: str,
    details: Any = None,
) -> None:
    value: dict[str, Any] = {"name": name, "status": status, "message": message}
    if details is not None:
        value["details"] = details
    checks.append(value)


def _git_status(root: Path) -> tuple[str, str]:
    if shutil.which("git") is None:
        return "warn", "git executable is not available"
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "warn", f"could not inspect git worktree: {exc}"
    if result.returncode:
        return "warn", result.stderr.strip() or "target is not a git worktree"
    if result.stdout.strip():
        return "warn", "worktree has uncommitted or untracked files"
    return "pass", "git worktree is clean"


def run_doctor(root: Path, *, strict: bool = False) -> dict[str, Any]:
    """Return read-only diagnostics without initializing or mutating artifacts."""

    root = Path(root).resolve()
    checks: list[dict[str, Any]] = []
    python_ok = sys.version_info >= (3, 11)
    _check(
        checks,
        "python",
        "pass" if python_ok else "fail",
        f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )

    pyproject = root / "pyproject.toml"
    project_version: str | None = None
    try:
        with pyproject.open("rb") as handle:
            project_version = tomllib.load(handle)["project"]["version"]
        _check(checks, "project-metadata", "pass", f"version {project_version}")
    except (KeyError, OSError, tomllib.TOMLDecodeError, TypeError) as exc:
        _check(checks, "project-metadata", "fail", f"invalid pyproject metadata: {exc}")

    try:
        from . import __version__

        version_ok = project_version is not None and __version__ == project_version
        _check(
            checks,
            "runtime-version",
            "pass" if version_ok else "fail",
            f"runtime={__version__}, project={project_version}",
        )
    except (ImportError, AttributeError) as exc:
        _check(checks, "runtime-version", "fail", str(exc))

    skills_root = root / "skills"
    skill_errors = validate_skill_tree(skills_root)
    skill_names = {
        path.name
        for path in skills_root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    } if skills_root.is_dir() and not skills_root.is_symlink() else set()
    if skill_names != set(PUBLIC_SKILLS):
        skill_errors.append(
            "skill set mismatch: expected "
            + ", ".join(sorted(PUBLIC_SKILLS))
            + "; found "
            + ", ".join(sorted(skill_names))
        )
    _check(
        checks,
        "skill-tree",
        "pass" if not skill_errors else "fail",
        "10 direct skills are valid" if not skill_errors else "skill validation failed",
        skill_errors,
    )

    protocol_files = [
        root / "skills" / "system-coherence" / "references" / "artifact-protocol.md",
        root / "skills" / "system-coherence" / "references" / "schemas" / "artifact-envelope.schema.json",
        root / "skills" / "system-coherence" / "references" / "schemas" / "artifact-payloads.schema.json",
        root / "skills" / "system-coherence" / "references" / "schemas" / "evaluation-scenarios.schema.json",
    ]
    missing_protocol = [
        str(path.relative_to(root)).replace("\\", "/")
        for path in protocol_files
        if not path.is_file() or path.is_symlink()
    ]
    _check(
        checks,
        "protocol-boundary",
        "pass" if not missing_protocol else "fail",
        "orchestrator protocol and schemas are local"
        if not missing_protocol
        else "protocol resources are missing or symlinked",
        missing_protocol,
    )

    git_status, git_message = _git_status(root)
    _check(checks, "git", git_status, git_message)

    workspace = Workspace(root)
    if not workspace.coherence_dir.exists():
        _check(
            checks,
            "coherence-workspace",
            "warn" if not strict else "fail",
            "not initialized; run coherence init when starting an audit",
        )
    else:
        errors = ArtifactStore(workspace).validate_all()
        _check(
            checks,
            "coherence-workspace",
            "pass" if not errors else "fail",
            "current artifacts are valid" if not errors else "artifact validation failed",
            errors,
        )

    failures = sum(check["status"] == "fail" for check in checks)
    warnings = sum(check["status"] == "warn" for check in checks)
    return {
        "tool": "coherence doctor",
        "root": str(root),
        "ok": failures == 0 and (not strict or warnings == 0),
        "summary": {"pass": len(checks) - failures - warnings, "warn": warnings, "fail": failures},
        "checks": checks,
    }


def doctor_json(root: Path, *, strict: bool = False) -> str:
    return json.dumps(run_doctor(root, strict=strict), ensure_ascii=False, sort_keys=True, indent=2)
