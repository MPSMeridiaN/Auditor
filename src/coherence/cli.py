"""Command-line entry point for the System Coherence protocol runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .config import initialize_workspace
from .evidence import capture
from .skills import validate_skill_tree
from .store import ArtifactStore, Workspace


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coherence",
        description="Validate, route, and preserve a System Coherence workspace.",
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

    ledger = commands.add_parser("ledger", help="derive and render the coherence ledger")
    ledger.add_argument("root", nargs="?", default=".")
    ledger.add_argument("--json", action="store_true", dest="as_json")

    skills = commands.add_parser("validate-skills", help="validate Agent Skills directories")
    skills.add_argument("root", nargs="?", default=".")
    skills.add_argument("--json", action="store_true", dest="as_json")

    evaluation = commands.add_parser("eval", help="run executable example evaluations")
    evaluation.add_argument("root", nargs="?", default=".")
    evaluation.add_argument("--json", action="store_true", dest="as_json")

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
    artifacts = store.read_all()
    return {
        "workspace": str(Workspace(root).root),
        "artifact_count": len(artifacts),
        "artifacts": {
            artifact_type: {
                "status": value.get("status"),
                "source_revision": value.get("source_revision"),
                "content_hash": value.get("content_hash"),
            }
            for artifact_type, value in artifacts.items()
        },
        "validation_errors": store.validate_all(),
        "next": _route(store),
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
        if args.command == "eval":
            from .evaluation import run_evaluations

            report = run_evaluations(root)
            _emit(report, args.as_json)
            return 1 if report["failed"] else 0
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
        if args.command == "invalidate":
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
