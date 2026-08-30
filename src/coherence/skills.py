"""Validation and discovery helpers for Agent Skills-compatible directories."""

from __future__ import annotations

from pathlib import Path
import re

REQUIRED_SECTIONS = (
    "Purpose",
    "Inputs",
    "Required artifacts",
    "Optional context",
    "Outputs",
    "Artifacts modified",
    "Completion criteria",
    "Failure / uncertainty behavior",
    "Next likely transitions",
)

_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

PUBLIC_SKILLS = frozenset(
    {
        "analyze-regression",
        "audit-coherence",
        "discover-capabilities",
        "model-behavior",
        "model-states",
        "plan-remediation",
        "reconstruct-system",
        "revalidate-coherence",
        "system-coherence",
        "trace-implementation",
    }
)


def _strip_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str, list[str]]:
    """Parse the deliberately small scalar frontmatter subset used by skills."""

    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {}, "", [f"could not read {path}: {exc}"]
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, ["frontmatter must start with ---"]
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}, text, ["frontmatter must end with ---"]
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        if ":" not in line:
            errors.append(f"frontmatter line is not key/value: {line}")
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = _strip_scalar(value)
    return metadata, "\n".join(lines[end + 1 :]), errors


def validate_skill_tree(skills_dir: Path) -> list[str]:
    """Return all format and contract errors in a skill collection."""

    skills_dir = Path(skills_dir)
    if skills_dir.is_symlink():
        return [f"skills directory must not be a symlink: {skills_dir}"]
    if not skills_dir.is_dir():
        return [f"skills directory does not exist: {skills_dir}"]
    directories = sorted(
        path for path in skills_dir.iterdir() if path.is_dir() and not path.name.startswith(".")
    )
    errors: list[str] = []
    for directory in directories:
        if directory.is_symlink():
            errors.append(f"symlinked skill directory is not allowed: {directory.name}")
            continue
        path = directory / "SKILL.md"
        if not path.exists():
            errors.append(f"missing SKILL.md: {directory.name}")
            continue
        if path.is_symlink():
            errors.append(f"symlinked SKILL.md is not allowed: {directory.name}")
            continue
        metadata, body, frontmatter_errors = parse_frontmatter(path)
        errors.extend(f"{directory.name}: {error}" for error in frontmatter_errors)
        name = metadata.get("name")
        description = metadata.get("description")
        if name is None:
            errors.append(f"{directory.name}: missing frontmatter field: name")
        else:
            if name != directory.name:
                errors.append(f"{directory.name}: name must match directory")
            if len(name) > 64 or not _NAME_PATTERN.fullmatch(name):
                errors.append(f"{directory.name}: name is not Agent Skills-compatible")
        if description is None:
            errors.append(f"{directory.name}: missing frontmatter field: description")
        else:
            if not description.startswith("Use when"):
                errors.append(f"{directory.name}: description must start with 'Use when'")
            if not 1 <= len(description) <= 1024:
                errors.append(f"{directory.name}: description length is invalid")
        headings = {
            line[3:].strip() for line in body.splitlines() if line.startswith("## ")
        }
        for section in REQUIRED_SECTIONS:
            if section not in headings:
                errors.append(f"{directory.name}: missing required section: {section}")
        if len(body.splitlines()) > 500:
            errors.append(f"{directory.name}: SKILL.md body exceeds 500 lines")
    return errors
