"""Deterministic source evidence capture for a repository."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import subprocess
from typing import Any

from .models import stable_id, utc_now


EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".coherence",
        ".agents",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "dist",
        "build",
        "coverage",
        "htmlcov",
        "audit-output",
        "release-evidence",
        "reports",
        ".hypothesis",
        ".idea",
        ".vscode",
        "env",
    }
)

EXCLUDED_FILE_NAMES = frozenset(
    {
        "skills-lock.json",
        ".coverage",
        ".ds_store",
        "thumbs.db",
        "desktop.ini",
    }
)

_LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".sql": "sql",
    ".sh": "shell",
    ".ps1": "powershell",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
}


def classify_path(path: Path) -> str:
    """Classify a relative repository path without inspecting its contents."""

    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    suffix = path.suffix.lower()
    if "tests" in parts or name.startswith("test_") or name.endswith("_test.py"):
        return "test"
    if "docs" in parts or suffix in {".md", ".rst", ".adoc"}:
        return "docs"
    if name in {"dockerfile", "makefile", "pyproject.toml", "package.json"} or suffix in {
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
    }:
        return "config"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp"}:
        return "asset"
    if any(part in parts for part in {"dist", "build", "generated", "coverage"}):
        return "generated"
    return "source"


def _language(path: Path) -> str | None:
    return _LANGUAGES.get(path.suffix.lower())


def _git(root: Path, *arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.rstrip()


def _source_revision(root: Path, files: list[dict[str, Any]]) -> str:
    fingerprint = sha256(
        "\n".join(
            f"{item['path']}\0{item['sha256']}"
            for item in files
        ).encode("utf-8")
    ).hexdigest()[:16]
    if _git(root, "rev-parse", "HEAD"):
        return f"TREE-{fingerprint}"
    return f"WORKTREE-{fingerprint}"


def _working_tree_state(root: Path) -> str:
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    if status is None:
        return "unknown"
    relevant_lines = []
    for line in status.splitlines():
        changed_path = line[3:].strip() if len(line) >= 4 else ""
        candidates = changed_path.split(" -> ")
        if any(not _is_excluded_path(Path(candidate)) for candidate in candidates):
            relevant_lines.append(line)
    return "dirty" if relevant_lines else "clean"


def _iter_files(root: Path):
    for current, directories, filenames in os.walk(root, topdown=True, followlinks=False):
        directories[:] = [
            name
            for name in directories
            if not _is_excluded_directory(name)
            and not (Path(current) / name).is_symlink()
        ]
        current_path = Path(current)
        for filename in sorted(filenames):
            path = current_path / filename
            if _is_excluded_file(filename) or path.is_symlink() or not path.is_file():
                continue
            yield path


def _is_excluded_directory(name: str) -> bool:
    lowered = name.lower()
    return lowered in EXCLUDED_DIRECTORIES or lowered.endswith(".egg-info")


def _is_excluded_file(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered in EXCLUDED_FILE_NAMES
        or lowered.startswith(".env")
        or lowered.endswith((".pyc", ".pyo", ".log", ".tmp", ".temp", ".bak", ".swp"))
    )


def _is_excluded_path(path: Path) -> bool:
    return any(
        _is_excluded_directory(part) or _is_excluded_file(part)
        for part in path.parts
    )


def capture(root: Path) -> dict[str, Any]:
    """Capture file-level evidence and return a valid artifact envelope."""

    root = Path(root).resolve()
    captured_at = utc_now()
    files: list[dict[str, Any]] = []
    for path in sorted(_iter_files(root), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        digest = sha256(data).hexdigest()
        files.append(
            {
                "evidence_id": stable_id("ev", f"file:{relative}:{digest}"),
                "path": relative,
                "kind": classify_path(Path(relative)),
                "size": len(data),
                "sha256": digest,
                "language": _language(path),
            }
        )
    working_tree = _working_tree_state(root)
    revision = _source_revision(root, files)

    return {
        "artifact_type": "repository-evidence",
        "schema_version": "1.0",
        "artifact_id": "artifact/repository-evidence",
        "run_id": stable_id("run", f"evidence:{root}:{captured_at}"),
        "status": "complete",
        "source_revision": revision,
        "created_at": captured_at,
        "producer": {"skill": "system-coherence", "agent": "coherence-cli"},
        "inputs": [],
        "evidence_refs": [],
        "uncertainty": [],
        "freshness": {
            "state": "current",
            "checked_at": captured_at,
            "dependency_fingerprint": revision,
        },
        "content": {
            "root": ".",
            "source_revision": revision,
            "working_tree": working_tree,
            "captured_at": captured_at,
            "files": files,
        },
    }
