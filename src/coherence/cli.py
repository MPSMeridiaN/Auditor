"""Command-line entry point for the System Coherence protocol runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from . import __version__
from .config import initialize_workspace
from .doctor import run_doctor
from .evidence import capture
from .models import ARTIFACT_TYPES
from .release import release_check
from .skills import validate_skill_tree
from .store import ArtifactStore, Workspace


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coherence",
        description="Validate, route, and preserve a System Coherence workspace.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    for name in ("init", "capture"):
        command = commands.add_parser(name, help=f"{name} repository evidence")
        command.add_argument("root", nargs="?", default=".")
        command.add_argument("--json", action="store_true", dest="as_json")

    status = commands.add_parser("status", help="summarize artifacts and next work")
    status.add_argument("root", nargs="?", default=".")
    status.add_argument("--json", action="store_true", dest="as_json")

    route = commands.add_parser("route", help="emit the next skill route")
    route.add_argument("root", nargs="?", default=".")
    route.add_argument("--json", action="store_true", dest="as_json")

    validate = commands.add_parser("validate", help="validate current artifacts")
    validate.add_argument("root", nargs="?", default=".")
    validate.add_argument("--json", action="store_true", dest="as_json")

    invalidate = commands.add_parser(
        "invalidate", help="map changed paths to scoped revalidation"
    )
    invalidate.add_argument("root", nargs="?", default=".")
    invalidate.add_argument("paths", nargs="*")
    invalidate.add_argument("--base", default=None)
    invalidate.add_argument("--json", action="store_true", dest="as_json")

    regression = commands.add_parser(
        "regression", help="calculate and persist scoped revalidation"
    )
    regression.add_argument("root", nargs="?", default=".")
    regression.add_argument("paths", nargs="*")
    regression.add_argument("--base", default=None)
    regression.add_argument("--json", action="store_true", dest="as_json")

    revalidation = commands.add_parser(
        "revalidation", help="show the current revalidation result"
    )
    revalidation.add_argument("root", nargs="?", default=".")
    revalidation.add_argument("--json", action="store_true", dest="as_json")

    ledger = commands.add_parser("ledger", help="derive and render the coherence ledger")
    ledger.add_argument("root", nargs="?", default=".")
    ledger.add_argument("--json", action="store_true", dest="as_json")

    skills = commands.add_parser("validate-skills", help="validate Agent Skills directories")
    skills.add_argument("root", nargs="?", default=".")
    skills.add_argument("--json", action="store_true", dest="as_json")

    doctor = commands.add_parser("doctor", help="run read-only environment diagnostics")
    doctor.add_argument("root", nargs="?", default=".")
    doctor.add_argument("--strict", action="store_true")
    doctor.add_argument("--json", action="store_true", dest="as_json")

    explain = commands.add_parser("explain", help="explain the current route and next safe step")
    explain.add_argument("root", nargs="?", default=".")
    explain.add_argument("--json", action="store_true", dest="as_json")

    findings = commands.add_parser("findings", help="list audit findings")
    findings.add_argument("root", nargs="?", default=".")
    findings.add_argument("--all", action="store_true", dest="include_closed")
    findings.add_argument("--json", action="store_true", dest="as_json")

    evaluation = commands.add_parser("eval", help="run executable example evaluations")
    evaluation.add_argument("root", nargs="?", default=".")
    evaluation.add_argument(
        "--trusted-fixtures",
        action="store_true",
        help="explicitly allow execution of Python fixtures in the target checkout",
    )
    evaluation.add_argument("--json", action="store_true", dest="as_json")

    release_check = commands.add_parser(
        "release-check",
        help="verify source, packages, skill archive, and clean installs",
    )
    release_check.add_argument("root", nargs="?", default=".")
    release_check.add_argument("--dist-dir", default=None)
    release_check.add_argument("--output-dir", default=None)
    release_check.add_argument("--no-build", action="store_true")
    release_check.add_argument("--no-clean-install", action="store_true")
    release_check.add_argument("--json", action="store_true", dest="as_json")

    write = commands.add_parser("write", help="validate and store an artifact envelope")
    write.add_argument("artifact_file")
    write.add_argument("root", nargs="?", default=".")

    return parser


def _emit(value: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))
        return
    if isinstance(value, dict) and "next" in value:
        next_route = value["next"]
        print(f"Workspace: {value.get('workspace', '')}")
        print(f"Artifacts: {value.get('artifact_count', 0)}")
        print(f"Next: {next_route.get('skill', next_route.get('stage', 'none'))}")
        print(f"Reason: {next_route.get('reason', '')}")
    elif isinstance(value, dict) and "skill" in value:
        print(f"Next skill: {value['skill']}")
        print(f"Reason: {value.get('reason', '')}")
    else:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def _basic_route(store: ArtifactStore) -> dict[str, Any]:
    if store.read("repository-evidence") is None:
        return {
            "stage": "evidence",
            "skill": "system-coherence",
            "reason": "repository evidence is missing",
            "required_artifacts": [],
            "produces": ["repository-evidence"],
            "context_paths": ["repository"],
        }
    return {
        "stage": "reconstruction",
        "skill": "reconstruct-system",
        "reason": "system model is missing",
        "required_artifacts": ["repository-evidence"],
        "produces": ["system-model"],
        "context_paths": [".coherence/artifacts/repository-evidence.json"],
    }


def _route(store: ArtifactStore) -> dict[str, Any]:
    try:
        from .workflow import route
    except ImportError:
        return _basic_route(store)
    return route(store)


def _status(root: Path) -> dict[str, Any]:
    store = ArtifactStore(Workspace(root))
    workspace = Workspace(root)
    validation_errors = store.validate_all()
    artifacts: dict[str, dict[str, Any]] = {}
    for artifact_type in ARTIFACT_TYPES:
        path = workspace.artifacts_dir / f"{artifact_type}.json"
        if not path.exists() and not path.is_symlink():
            continue
        try:
            value = store.read(artifact_type)
        except ValueError as exc:
            artifacts[artifact_type] = {
                "status": "invalid",
                "read_error": str(exc),
            }
            continue
        if value is not None:
            artifacts[artifact_type] = value
    return {
        "workspace": str(workspace.root),
        "artifact_count": len(artifacts),
        "artifacts": {
            artifact_type: {
                "status": "invalid"
                if artifact_type in validation_errors
                else value.get("status"),
                "source_revision": value.get("source_revision"),
                "content_hash": value.get("content_hash"),
                **(
                    {"read_error": value["read_error"]}
                    if "read_error" in value
                    else {}
                ),
            }
            for artifact_type, value in artifacts.items()
        },
        "validation_errors": validation_errors,
        "next": _route(store),
    }


def _explain(store: ArtifactStore) -> dict[str, Any]:
    route = _route(store)
    validation_errors = store.validate_all()
    try:
        artifacts = store.read_all()
    except ValueError:
        artifacts = {}
    statuses = {
        artifact_type: value.get("status")
        for artifact_type, value in artifacts.items()
    }
    statuses.update({artifact_type: "invalid" for artifact_type in validation_errors})
    skill = route.get("skill", "system-coherence")
    if route.get("stage") == "complete":
        next_step = "No specialist stage is required; the current ledger is complete."
    else:
        next_step = f"Invoke {skill} and write {', '.join(route.get('produces', [])) or 'the routed repair'}."
    return {
        "route": route,
        "artifact_statuses": statuses,
        "validation_errors": validation_errors,
        "next_step": next_step,
    }


def _findings(store: ArtifactStore, include_closed: bool = False) -> dict[str, Any]:
    artifact = store.read("audit-findings")
    if artifact is None:
        return {
            "available": False,
            "artifact": "audit-findings",
            "findings": [],
            "message": "audit findings are not available; run the routed audit stage first",
        }
    content = artifact.get("content", {})
    findings = content.get("findings", []) if isinstance(content, dict) else []
    if not isinstance(findings, list):
        findings = []
    if not include_closed:
        findings = [
            finding
            for finding in findings
            if isinstance(finding, dict)
            and finding.get("status") not in {"accepted", "closed", "resolved", "verified"}
        ]
    return {
        "available": True,
        "artifact": "audit-findings",
        "source_revision": artifact.get("source_revision"),
        "finding_count": len(findings),
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command in {"init", "capture"}:
            workspace = initialize_workspace(Path(args.root))
            evidence_path = ArtifactStore(workspace).write(capture(workspace.root))
            result = {
                "workspace": str(workspace.root),
                "artifact": str(evidence_path),
                "artifact_type": "repository-evidence",
            }
            _emit(result, args.as_json)
            return 0

        root = Path(args.root).resolve()
        store = ArtifactStore(Workspace(root))
        if args.command == "validate-skills":
            errors = validate_skill_tree(root / "skills")
            _emit({"errors": errors}, args.as_json)
            return 1 if errors else 0
        if args.command == "doctor":
            report = run_doctor(root, strict=args.strict)
            _emit(report, args.as_json)
            return 0 if report["ok"] else 1
        if args.command == "explain":
            _emit(_explain(store), args.as_json)
            return 0
        if args.command == "findings":
            _emit(_findings(store, args.include_closed), args.as_json)
            return 0
        if args.command == "eval":
            from .evaluation import run_evaluations

            report = run_evaluations(root, execute_fixtures=args.trusted_fixtures)
            _emit(report, args.as_json)
            if report.get("execution") == "skipped":
                return 2
            return 1 if report["failed"] else 0
        if args.command == "release-check":
            report = release_check(
                root,
                dist_dir=Path(args.dist_dir) if args.dist_dir else None,
                output_dir=Path(args.output_dir) if args.output_dir else None,
                build_artifacts=not args.no_build,
                clean_install=not args.no_clean_install,
            )
            _emit(report, args.as_json)
            return 0 if report["passed"] else 1
        if args.command == "status":
            _emit(_status(root), args.as_json)
            return 0
        if args.command == "route":
            _emit(_route(store), args.as_json)
            return 0
        if args.command == "validate":
            errors = store.validate_all()
            _emit({"errors": errors}, args.as_json)
            return 1 if errors else 0
        if args.command in {"invalidate", "regression"}:
            from .invalidation import apply_scope, changed_paths, compute_scope

            paths = changed_paths(root, args.base, args.paths)
            if not paths:
                _emit(
                    {
                        "changed_paths": [],
                        "scope": None,
                        "ledger": store.read("coherence-ledger"),
                        "message": "no changed paths; workspace unchanged",
                    },
                    args.as_json,
                )
                return 0
            current_revision = capture(root)["source_revision"]
            scope = compute_scope(store, paths, current_revision)
            ledger = apply_scope(store, scope)
            result = {"scope": scope, "ledger": ledger}
            _emit(result, args.as_json)
            return 0
        if args.command == "revalidation":
            artifact = store.read("revalidation-results")
            errors = store.validate_all().get("revalidation-results", [])
            result = {
                "available": artifact is not None,
                "artifact": artifact,
                "validation_errors": errors,
            }
            _emit(result, args.as_json)
            return 1 if errors else 0
        if args.command == "ledger":
            from .ledger import derive

            value = derive(store)
            store.write(value)
            _emit(value, args.as_json)
            return 0
        if args.command == "write":
            value = json.loads(Path(args.artifact_file).read_text(encoding="utf-8"))
            path = store.write(value)
            print(path)
            return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2
