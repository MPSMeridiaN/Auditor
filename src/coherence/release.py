"""Release-boundary checks for the optional verifier and skill distribution.

The release checker deliberately treats the source checkout and its generated
outputs as different things.  It validates the public skill tree, builds and
inspects Python artifacts, creates a deterministic skill-only archive, and
optionally installs both Python artifact formats in disposable virtual
environments.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
import tomllib
from typing import Any

from .skills import PUBLIC_SKILLS, validate_skill_tree


SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

_RUNTIME_VERSION_PATTERN = re.compile(
    r"__version__\s*=\s*[\"']([^\"']+)[\"']"
)
_LOCAL_LINK_PATTERN = re.compile(r"\[[^]]+\]\(([^)]+)\)")
_ABSOLUTE_DEV_PATH_PATTERNS = (
    re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+\\(?:Desktop|Documents|AppData)\\"),
    re.compile(r"(?i)\b[A-Z]:[\\/]Users[\\/][^\\/\s]+[\\/](?:Desktop|Documents|AppData)[\\/]"),
    re.compile(r"(?i)(?:^|[\s\"'(])/(?:home|Users)/[A-Za-z0-9_.-]+/"),
)
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\b(?:ghp|github_pat|gho|ghs|ghr)_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:xox[baprs]-|npm_|pypi-)[A-Za-z0-9_-]{20,}\b"),
)
_SENSITIVE_FILENAME_SUFFIXES = frozenset(
    {".key", ".pem", ".p12", ".pfx", ".crt", ".cer"}
)

_GENERATED_PARTS = frozenset(
    {
        ".agents",
        ".coherence",
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "build",
        "coverage",
        "dist",
        "htmlcov",
        "release",
        "release-evidence",
        "reports",
        "node_modules",
    }
)
_GENERATED_SUFFIXES = (".pyc", ".pyo", ".log", ".tmp", ".bak")
_SDIST_ALLOWED_ROOT_FILES = frozenset(
    {
        "CHANGELOG.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "MANIFEST.in",
        "PKG-INFO",
        "README.md",
        "SECURITY.md",
        "pyproject.toml",
        "setup.cfg",
        "setup.py",
    }
)
_PUBLIC_NO_REPLY_EMAIL = re.compile(
    r"^(?:[0-9]+\+[^@\s]+|[^@\s]+)@(?:users\.noreply\.github\.com|noreply\.github\.com)$",
    re.IGNORECASE,
)


def _check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    message: str,
    details: Any = None,
) -> None:
    value: dict[str, Any] = {
        "name": name,
        "passed": bool(passed),
        "message": message,
    }
    if details is not None:
        value["details"] = details
    checks.append(value)


def _project_version(root: Path) -> tuple[str | None, str | None]:
    try:
        with (root / "pyproject.toml").open("rb") as handle:
            metadata = tomllib.load(handle)
        project = metadata["project"]
        version = project.get("version")
        if version is None and "version" in project.get("dynamic", []):
            attr = metadata.get("tool", {}).get("setuptools", {}).get("dynamic", {}).get(
                "version", {}
            ).get("attr")
            if not isinstance(attr, str) or "." not in attr:
                return None, "dynamic project version attribute is missing"
            module_name, attribute_name = attr.rsplit(".", 1)
            module_path = root / "src" / Path(*module_name.split("."))
            source_path = module_path / "__init__.py"
            if not source_path.is_file():
                source_path = module_path.with_suffix(".py")
            tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
            version = None
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if not any(
                    isinstance(target, ast.Name) and target.id == attribute_name
                    for target in targets
                ):
                    continue
                value = node.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    version = value.value
                    break
            if version is None:
                return None, f"could not resolve dynamic version attribute: {attr}"
    except (KeyError, OSError, SyntaxError, tomllib.TOMLDecodeError, TypeError) as exc:
        return None, f"could not read project version: {exc}"
    if not isinstance(version, str) or not SEMVER_PATTERN.fullmatch(version):
        return None, f"project version is not semantic versioning: {version!r}"
    return version, None


def _runtime_version(root: Path) -> tuple[str | None, str | None]:
    path = root / "src" / "coherence" / "_version.py"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"could not read runtime version: {exc}"
    match = _RUNTIME_VERSION_PATTERN.search(text)
    if match is None:
        return None, "runtime __version__ is missing"
    return match.group(1), None


def _walk_files(root: Path) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    symlinks: list[str] = []
    if not root.is_dir():
        return files, [str(root)]
    for current, directories, filenames in os.walk(
        root, topdown=True, followlinks=False
    ):
        current_path = Path(current)
        kept_directories: list[str] = []
        for name in directories:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                symlinks.append(relative)
                continue
            kept_directories.append(name)
        directories[:] = kept_directories
        for name in filenames:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                symlinks.append(relative)
                continue
            if path.is_file():
                files.append(path)
    return files, symlinks


def _is_generated(relative: str) -> bool:
    path = PurePosixPath(relative)
    return (
        any(
            part in _GENERATED_PARTS or part.endswith(".egg-info")
            for part in path.parts
        )
        or path.name.endswith(_GENERATED_SUFFIXES)
    )


def _is_sensitive_filename(relative: str) -> bool:
    path = PurePosixPath(relative)
    return (
        path.name.lower().startswith(".env")
        or path.suffix.lower() in _SENSITIVE_FILENAME_SUFFIXES
    )


def _scan_public_source(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    files, _ = _walk_files(root)
    for path in files:
        relative = path.relative_to(root).as_posix()
        if _is_generated(relative):
            continue
        if _is_sensitive_filename(relative):
            findings.append({"path": relative, "match": "sensitive filename"})
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            findings.append({"path": relative, "match": f"could not read: {exc}"})
            continue
        if len(data) > 5 * 1024 * 1024:
            continue
        text = data.decode("utf-8", errors="ignore")
        for pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                findings.append({"path": relative, "match": pattern.pattern})
        for pattern in _ABSOLUTE_DEV_PATH_PATTERNS:
            if pattern.search(text):
                findings.append({"path": relative, "match": pattern.pattern})
    return findings


def _git_lines(root: Path, command: list[str], input_text: str | None = None) -> list[str]:
    """Run a bounded Git query and return non-empty text lines."""

    result = subprocess.run(
        ["git", "-C", str(root), *command],
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if result.returncode:
        detail = result.stderr.strip() or "git query failed"
        raise RuntimeError(detail)
    return [line for line in result.stdout.splitlines() if line.strip()]


def _public_refs(root: Path) -> list[str]:
    refs = _git_lines(
        root,
        [
            "for-each-ref",
            "--format=%(refname)",
            "refs/heads",
            "refs/tags",
        ],
    )
    return sorted(set(refs))


def _historical_blob_findings(root: Path, refs: list[str]) -> list[dict[str, str]]:
    object_lines = _git_lines(root, ["rev-list", "--objects", *refs])
    object_ids = sorted({line.split(" ", 1)[0] for line in object_lines})
    if not object_ids:
        return []
    result = subprocess.run(
        ["git", "-C", str(root), "cat-file", "--batch"],
        input=("\n".join(object_ids) + "\n").encode("ascii"),
        capture_output=True,
        check=False,
        timeout=120,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "git cat-file failed")
    path_by_object = {
        line.split(" ", 1)[0]: line.split(" ", 1)[1]
        for line in object_lines
        if " " in line
    }
    findings: list[dict[str, str]] = []
    payload = result.stdout
    offset = 0
    while offset < len(payload):
        header_end = payload.find(b"\n", offset)
        if header_end < 0:
            break
        header = payload[offset:header_end].decode("ascii", errors="replace")
        parts = header.split(" ")
        offset = header_end + 1
        if len(parts) != 3:
            continue
        try:
            size = int(parts[2])
        except ValueError:
            break
        blob = payload[offset : offset + size]
        offset += size
        if offset < len(payload) and payload[offset : offset + 1] == b"\n":
            offset += 1
        if parts[1] != "blob":
            continue
        text = blob.decode("utf-8", errors="ignore")
        for pattern in (*_SECRET_PATTERNS, *_ABSOLUTE_DEV_PATH_PATTERNS):
            if pattern.search(text):
                findings.append(
                    {
                        "object": parts[0][:12],
                        "path": path_by_object.get(parts[0], "(unnamed blob)"),
                        "match": pattern.pattern,
                    }
                )
    return findings


def _history_privacy(root: Path) -> tuple[list[dict[str, str]], str]:
    """Check public Git refs for private identity and high-confidence leaks."""

    git_dir = root / ".git"
    if not git_dir.exists():
        return [], "no Git metadata; public history scan is not applicable"
    if shutil.which("git") is None:
        return [{"kind": "tooling", "message": "git executable is unavailable"}], "history scan could not run"
    try:
        refs = _public_refs(root)
        if not refs:
            return [], "no public refs found; history scan is not applicable"
        findings: list[dict[str, str]] = []
        log_lines = _git_lines(
            root,
            ["log", "--format=%H%x00%ae%x00%ce", *refs],
        )
        for line in log_lines:
            fields = line.split("\x00")
            if len(fields) != 3:
                continue
            commit, author_email, committer_email = fields
            for role, email in (("author", author_email), ("committer", committer_email)):
                normalized = email.strip().lower()
                domain = normalized.rsplit("@", 1)[-1] if "@" in normalized else "(invalid)"
                if not _PUBLIC_NO_REPLY_EMAIL.fullmatch(normalized):
                    findings.append(
                        {
                            "kind": "private-commit-email",
                            "commit": commit[:12],
                            "role": role,
                            "domain": domain,
                        }
                    )
        for line in _git_lines(
            root,
            ["for-each-ref", "--format=%(refname)%00%(taggeremail)", "refs/tags"],
        ):
            fields = line.split("\x00")
            if len(fields) != 2:
                continue
            tag_ref, tagger_email = fields
            normalized = tagger_email.strip().strip("<>").lower()
            domain = normalized.rsplit("@", 1)[-1] if "@" in normalized else "(invalid)"
            if not _PUBLIC_NO_REPLY_EMAIL.fullmatch(normalized):
                findings.append(
                    {
                        "kind": "private-tag-email",
                        "tag": tag_ref.removeprefix("refs/tags/"),
                        "domain": domain,
                    }
                )
        findings.extend(
            {"kind": "historical-content", **item}
            for item in _historical_blob_findings(root, refs)
        )
        return findings, f"scanned {len(refs)} public refs"
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        return [{"kind": "tooling", "message": str(exc)}], "history scan could not run"


def _validate_skill_distribution(root: Path) -> tuple[list[str], list[str]]:
    skills_root = root / "skills"
    if skills_root.is_symlink():
        return ["skills directory must not be a symlink"], ["skills"]
    errors = validate_skill_tree(skills_root)
    if not skills_root.is_dir():
        return errors, []
    directories = {
        path.name
        for path in skills_root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    } if skills_root.is_dir() and not skills_root.is_symlink() else set()
    if directories != set(PUBLIC_SKILLS):
        errors.append(
            "public skill set mismatch: expected "
            + ", ".join(sorted(PUBLIC_SKILLS))
            + "; found "
            + ", ".join(sorted(directories))
        )

    files, symlinks = _walk_files(skills_root)
    if symlinks:
        errors.extend(f"skill distribution contains symlink: {path}" for path in symlinks)
    for path in files:
        if path.name != "SKILL.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{path.relative_to(root).as_posix()}: {exc}")
            continue
        for raw_target in _LOCAL_LINK_PATTERN.findall(text):
            target = raw_target.split("#", 1)[0].strip()
            if not target or target.startswith(("http:", "https:", "mailto:")):
                continue
            target_path = Path(target)
            if target_path.is_absolute() or ".." in target_path.parts:
                errors.append(
                    f"{path.relative_to(root).as_posix()}: unsafe local reference {target}"
                )
                continue
            if not (path.parent / target_path).is_file():
                errors.append(
                    f"{path.relative_to(root).as_posix()}: missing local reference {target}"
                )
    return errors, symlinks


def _validate_documentation_links(root: Path) -> list[str]:
    """Validate local Markdown links used by the public documentation."""

    errors: list[str] = []
    candidates = [root / "README.md", *sorted((root / "docs").glob("*.md"))]
    for path in candidates:
        if not path.is_file() or path.is_symlink():
            if path == root / "README.md":
                errors.append("README.md is missing or symlinked")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{path.relative_to(root).as_posix()}: {exc}")
            continue
        for raw_target in _LOCAL_LINK_PATTERN.findall(text):
            target = raw_target.split("#", 1)[0].strip()
            if not target or target.startswith(("http:", "https:", "mailto:")):
                continue
            target_path = Path(target)
            if target_path.is_absolute():
                errors.append(
                    f"{path.relative_to(root).as_posix()}: unsafe local link {target}"
                )
                continue
            candidate = (path.parent / target_path).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                errors.append(
                    f"{path.relative_to(root).as_posix()}: link escapes repository {target}"
                )
                continue
            if not candidate.is_file() or candidate.is_symlink():
                errors.append(
                    f"{path.relative_to(root).as_posix()}: missing local link {target}"
                )
    return errors


def _run(command: list[str], cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    # Reproducibility is a release invariant; a caller's ambient value must
    # not silently change the bytes emitted by this check.
    environment["SOURCE_DATE_EPOCH"] = "0"
    environment.pop("PYTHONPATH", None)
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        env=environment,
    )


def _build_python_artifacts(root: Path, dist_dir: Path) -> tuple[bool, str]:
    dist_dir = dist_dir.resolve()

    try:
        with tempfile.TemporaryDirectory(prefix="coherence-release-source-") as directory:
            staging_root = Path(directory) / root.name

            def ignore_generated(directory: str, names: list[str]) -> set[str]:
                ignored: set[str] = set()
                directory_path = Path(directory)
                for name in names:
                    path = directory_path / name
                    relative = path.relative_to(root).as_posix()
                    if path.is_symlink() or _is_generated(relative):
                        ignored.add(name)
                        continue
                    if path.is_dir() and (
                        name == ".git"
                        or name in _GENERATED_PARTS
                        or name.endswith(".egg-info")
                    ):
                        ignored.add(name)
                        continue
                    try:
                        resolved = path.resolve()
                        if resolved == dist_dir or dist_dir in resolved.parents:
                            ignored.add(name)
                    except OSError:
                        ignored.add(name)
                return ignored

            shutil.copytree(root, staging_root, ignore=ignore_generated)
            (staging_root / "build").mkdir(parents=True, exist_ok=True)
            result = _run(
                [
                    sys.executable,
                    "-m",
                    "build",
                    "--sdist",
                    "--wheel",
                    "--outdir",
                    str(dist_dir),
                ],
                staging_root,
            )
    except (OSError, subprocess.TimeoutExpired, shutil.Error) as exc:
        return False, f"could not run python -m build: {exc}"
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        return False, "python -m build failed: " + detail[-2000:]
    return True, "wheel and sdist built from a clean source staging tree"


def _safe_archive_name(name: str) -> bool:
    normalized = name.replace(chr(92), "/")
    path = PurePosixPath(normalized)
    return (
        not path.is_absolute()
        and not re.match(r"^[A-Za-z]:", normalized)
        and ".." not in path.parts
    )


def _inspect_wheel(path: Path, version: str) -> list[str]:
    errors: list[str] = []
    expected_dist_info = f"system_coherence-{version}.dist-info/"
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                errors.append("wheel contains duplicate member names")
            for info in archive.infolist():
                name = info.filename.replace(chr(92), "/")
                if not _safe_archive_name(name):
                    errors.append(f"wheel contains unsafe path: {name}")
                if _is_sensitive_filename(name):
                    errors.append(f"wheel contains sensitive filename: {name}")
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    errors.append(f"wheel contains symlink: {name}")
                if name.endswith("/"):
                    continue
                if not (
                    name.startswith("coherence/")
                    or name.startswith(expected_dist_info)
                ):
                    errors.append(f"wheel contains non-runtime file: {name}")
            metadata_name = expected_dist_info + "METADATA"
            if metadata_name not in names:
                errors.append(f"wheel is missing {metadata_name}")
            else:
                metadata = archive.read(metadata_name).decode("utf-8", errors="replace")
                if f"Version: {version}" not in metadata:
                    errors.append("wheel metadata version does not match project version")
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        errors.append(f"could not inspect wheel: {exc}")
    return errors


def _inspect_sdist(path: Path, version: str) -> list[str]:
    errors: list[str] = []
    expected_root = f"system_coherence-{version}"
    try:
        with tarfile.open(path, "r:*") as archive:
            members = archive.getmembers()
            names = [member.name.replace(chr(92), "/") for member in members]
            if len(names) != len(set(names)):
                errors.append("sdist contains duplicate member names")
            for member in members:
                name = member.name.replace(chr(92), "/")
                if not _safe_archive_name(name):
                    errors.append(f"sdist contains unsafe path: {name}")
                    continue
                if member.issym() or member.islnk():
                    errors.append(f"sdist contains link: {name}")
                relative = name.removeprefix(expected_root + "/")
                if name != expected_root and not name.startswith(expected_root + "/"):
                    errors.append(f"sdist contains unexpected root path: {name}")
                    continue
                if name == expected_root or member.isdir():
                    if name not in {
                        expected_root,
                        expected_root + "/src",
                        expected_root + "/src/coherence",
                    }:
                        errors.append(f"sdist contains unexpected directory: {name}")
                    continue
                if not member.isfile():
                    errors.append(f"sdist contains unsupported member type: {name}")
                    continue
                allowed = (
                    relative in _SDIST_ALLOWED_ROOT_FILES
                    or relative.startswith("src/coherence/")
                )
                if not allowed:
                    errors.append(f"sdist contains development file: {name}")
                if _is_generated(name):
                    errors.append(f"sdist contains generated file: {name}")
                if _is_sensitive_filename(name):
                    errors.append(f"sdist contains sensitive filename: {name}")
                extracted = archive.extractfile(member)
                if extracted is not None:
                    data = extracted.read(5 * 1024 * 1024 + 1)
                    if len(data) <= 5 * 1024 * 1024:
                        text = data.decode("utf-8", errors="ignore")
                        for pattern in (*_SECRET_PATTERNS, *_ABSOLUTE_DEV_PATH_PATTERNS):
                            if pattern.search(text):
                                errors.append(
                                    f"sdist contains possible leak in {name}: {pattern.pattern}"
                                )
                        if relative == "PKG-INFO" and f"Version: {version}" not in text:
                            errors.append("sdist metadata version does not match project version")
    except (OSError, tarfile.TarError) as exc:
        errors.append(f"could not inspect sdist: {exc}")
    return errors


def _write_skill_archive(root: Path, version: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"system-coherence-skills-{version}.zip"
    if target.is_symlink():
        raise ValueError(f"refusing to replace symlink: {target}")
    relative_paths = [Path("LICENSE"), Path("README.md")]
    relative_paths.extend(
        sorted(
            path.relative_to(root)
            for path in (root / "skills").rglob("*")
            if path.is_file() and not path.is_symlink()
        )
    )
    for relative in relative_paths:
        source = root / relative
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"missing or unsafe archive input: {relative.as_posix()}")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=output_dir
    )
    os.close(descriptor)
    try:
        with zipfile.ZipFile(
            temporary_name, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for relative in relative_paths:
                info = zipfile.ZipInfo(relative.as_posix(), (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, (root / relative).read_bytes())
        os.replace(temporary_name, target)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return target


def _inspect_skill_archive(path: Path, version: str) -> list[str]:
    errors: list[str] = []
    expected = {"LICENSE", "README.md"}
    expected.update(
        f"skills/{skill}/SKILL.md" for skill in PUBLIC_SKILLS
    )
    expected.update(
        {
            "skills/system-coherence/references/artifact-protocol.md",
            "skills/system-coherence/references/schemas/artifact-envelope.schema.json",
            "skills/system-coherence/references/schemas/artifact-payloads.schema.json",
            "skills/system-coherence/references/schemas/evaluation-scenarios.schema.json",
        }
    )
    try:
        with zipfile.ZipFile(path) as archive:
            listed_names = archive.namelist()
            names = set(listed_names)
            if len(listed_names) != len(names):
                errors.append("skill archive contains duplicate member names")
            if names != expected:
                errors.append(
                    "skill archive contents differ from the intended runtime set: "
                    f"missing={sorted(expected - names)}, extra={sorted(names - expected)}"
                )
            for info in archive.infolist():
                if not _safe_archive_name(info.filename):
                    errors.append(f"skill archive contains unsafe path: {info.filename}")
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    errors.append(f"skill archive contains symlink: {info.filename}")
                data = archive.read(info.filename)
                text = data.decode("utf-8", errors="ignore")
                for pattern in (*_SECRET_PATTERNS, *_ABSOLUTE_DEV_PATH_PATTERNS):
                    if pattern.search(text):
                        errors.append(
                            f"skill archive contains possible leak in {info.filename}: {pattern.pattern}"
                        )
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"could not inspect skill archive: {exc}")
    if not path.name.endswith(f"-{version}.zip"):
        errors.append("skill archive filename does not contain the project version")
    return errors


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _clean_install(artifact: Path, version: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="coherence-release-venv-") as directory:
        venv_dir = Path(directory) / "venv"
        try:
            venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
            python = _venv_python(venv_dir)
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            install = subprocess.run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-deps",
                    str(artifact),
                ],
                cwd=venv_dir.parent,
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
                env=environment,
            )
            if install.returncode:
                detail = (install.stderr or install.stdout).strip()
                return False, f"pip install failed: {detail[-2000:]}"
            probe = subprocess.run(
                [
                    str(python),
                    "-c",
                    (
                        "import coherence, sys; "
                        "assert coherence.__version__ == sys.argv[1]; "
                        "print(coherence.__version__)"
                    ),
                    version,
                ],
                cwd=venv_dir.parent,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
                env=environment,
            )
            if probe.returncode:
                detail = (probe.stderr or probe.stdout).strip()
                return False, f"installed package probe failed: {detail[-2000:]}"
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"clean install failed: {exc}"
    return True, "installed and imported in a disposable virtual environment"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_text_write(path: Path, payload: str) -> None:
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
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _write_release_outputs(
    report: dict[str, Any],
    artifact_paths: list[Path],
    output_dir: Path,
) -> None:
    if output_dir.is_symlink():
        raise ValueError(f"refusing to write release outputs through symlink: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    checksum_lines = [
        f"{_sha256(path)}  {path.name}" for path in sorted(artifact_paths, key=lambda p: p.name)
    ]
    checksums = output_dir / "SHA256SUMS"
    if checksums.is_symlink():
        raise ValueError(f"refusing to replace symlink: {checksums}")
    _atomic_text_write(checksums, "\n".join(checksum_lines) + "\n")
    report_path = output_dir / "release-check-report.json"
    if report_path.is_symlink():
        raise ValueError(f"refusing to replace symlink: {report_path}")
    _atomic_text_write(
        report_path,
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def release_check(
    root: Path,
    *,
    dist_dir: Path | None = None,
    output_dir: Path | None = None,
    build_artifacts: bool = True,
    clean_install: bool = True,
) -> dict[str, Any]:
    """Run source, archive, packaging, and clean-install release checks."""

    root = Path(root).resolve()
    checks: list[dict[str, Any]] = []
    version, version_error = _project_version(root)
    runtime_version, runtime_error = _runtime_version(root)
    _check(
        checks,
        "project-version",
        version_error is None,
        version_error or f"project version is {version}",
    )
    _check(
        checks,
        "runtime-version",
        runtime_error is None,
        runtime_error or f"runtime version is {runtime_version}",
    )
    if version is not None and runtime_version is not None:
        _check(
            checks,
            "version-consistency",
            version == runtime_version,
            f"project={version}, runtime={runtime_version}",
        )

    skill_errors, skill_symlinks = _validate_skill_distribution(root)
    _check(
        checks,
        "skill-distribution",
        not skill_errors,
        "public skill tree is valid" if not skill_errors else "skill tree has errors",
        skill_errors,
    )
    _check(
        checks,
        "skill-symlink-safety",
        not skill_symlinks,
        "no skill symlinks found" if not skill_symlinks else "skill symlinks are forbidden",
        skill_symlinks,
    )
    documentation_errors = _validate_documentation_links(root)
    _check(
        checks,
        "documentation-links",
        not documentation_errors,
        "local documentation links resolve"
        if not documentation_errors
        else "documentation link validation failed",
        documentation_errors,
    )
    source_findings = _scan_public_source(root)
    _check(
        checks,
        "source-hygiene",
        not source_findings,
        "no high-confidence secret or absolute developer path leaks found"
        if not source_findings
        else "possible secret or developer path leak found",
        source_findings,
    )
    _, source_symlinks = _walk_files(root)
    _check(
        checks,
        "source-symlink-safety",
        not source_symlinks,
        "no source symlinks found"
        if not source_symlinks
        else "source symlinks are excluded from release staging",
        source_symlinks,
    )
    history_findings, history_message = _history_privacy(root)
    _check(
        checks,
        "history-privacy",
        not history_findings,
        "public Git history contains only GitHub no-reply identities and no high-confidence leak"
        if not history_findings
        else history_message,
        history_findings,
    )

    temporary_dist: tempfile.TemporaryDirectory[str] | None = None
    if dist_dir is None:
        if output_dir is None:
            temporary_dist = tempfile.TemporaryDirectory(prefix="coherence-release-dist-")
            artifact_dir = Path(temporary_dist.name)
        else:
            artifact_dir = Path(output_dir).resolve()
            artifact_dir.mkdir(parents=True, exist_ok=True)
    else:
        artifact_dir = Path(dist_dir).resolve()
        artifact_dir.mkdir(parents=True, exist_ok=True)

    try:
        if version is not None:
            if build_artifacts:
                built, message = _build_python_artifacts(root, artifact_dir)
                _check(checks, "python-build", built, message)
            else:
                built = True
                _check(checks, "python-build", True, "using existing artifacts")

            wheels = sorted(artifact_dir.glob("*.whl")) if built else []
            sdists = sorted(artifact_dir.glob("*.tar.gz")) if built else []
            _check(
                checks,
                "wheel-count",
                len(wheels) == 1,
                f"expected one wheel, found {len(wheels)}",
                [path.name for path in wheels],
            )
            _check(
                checks,
                "sdist-count",
                len(sdists) == 1,
                f"expected one sdist, found {len(sdists)}",
                [path.name for path in sdists],
            )

            wheel_errors = _inspect_wheel(wheels[0], version) if len(wheels) == 1 else ["wheel unavailable"]
            sdist_errors = _inspect_sdist(sdists[0], version) if len(sdists) == 1 else ["sdist unavailable"]
            _check(
                checks,
                "wheel-boundary",
                not wheel_errors,
                "wheel contains only intended runtime files" if not wheel_errors else "wheel boundary failed",
                wheel_errors,
            )
            _check(
                checks,
                "sdist-boundary",
                not sdist_errors,
                "sdist contains no generated or unsafe files" if not sdist_errors else "sdist boundary failed",
                sdist_errors,
            )

            if clean_install:
                if len(wheels) == 1:
                    installed, message = _clean_install(wheels[0], version)
                    _check(checks, "wheel-clean-install", installed, message)
                else:
                    _check(checks, "wheel-clean-install", False, "wheel unavailable")
                if len(sdists) == 1:
                    installed, message = _clean_install(sdists[0], version)
                    _check(checks, "sdist-clean-install", installed, message)
                else:
                    _check(checks, "sdist-clean-install", False, "sdist unavailable")
            else:
                _check(checks, "clean-install", True, "clean-install checks disabled")

            destination = (
                Path(output_dir).resolve()
                if output_dir is not None
                else artifact_dir
            )
            try:
                skill_archive = _write_skill_archive(root, version, destination)
                skill_archive_errors = _inspect_skill_archive(skill_archive, version)
                _check(
                    checks,
                    "skill-archive",
                    not skill_archive_errors,
                    "skill-only archive contains the exact intended runtime set"
                    if not skill_archive_errors
                    else "skill archive boundary failed",
                    skill_archive_errors,
                )
            except (OSError, ValueError) as exc:
                skill_archive = None
                _check(checks, "skill-archive", False, str(exc))

            artifact_paths = [*wheels, *sdists]
            if skill_archive is not None and skill_archive.exists():
                artifact_paths.append(skill_archive)
            report: dict[str, Any] = {
                "tool": "coherence release-check",
                "schema_version": "1.0",
                "version": version,
                "passed": all(item["passed"] for item in checks),
                "checks": checks,
                "artifacts": [path.name for path in artifact_paths],
            }
            if output_dir is not None:
                try:
                    _write_release_outputs(report, artifact_paths, destination)
                    _check(checks, "release-output", True, "checksums and report written")
                    report["passed"] = all(item["passed"] for item in checks)
                    _write_release_outputs(report, artifact_paths, destination)
                except (OSError, ValueError) as exc:
                    _check(checks, "release-output", False, str(exc))
            report["passed"] = all(item["passed"] for item in checks)
            report["checks"] = checks
            return report
        return {
            "tool": "coherence release-check",
            "schema_version": "1.0",
            "version": None,
            "passed": False,
            "checks": checks,
            "artifacts": [],
        }
    finally:
        if temporary_dist is not None:
            temporary_dist.cleanup()
