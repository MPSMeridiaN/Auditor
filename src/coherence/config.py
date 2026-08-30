"""Creation and loading of the small workspace metadata files."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any
import uuid

from .models import stable_id, utc_now
from .store import Workspace


PROTOCOL_VERSION = "1.0"


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def initialize_workspace(root: Path) -> Workspace:
    workspace = Workspace(root)
    workspace.ensure()
    config_path = workspace.coherence_dir / "config.json"
    if not config_path.exists():
        write_json(
            config_path,
            {
                "protocol_version": PROTOCOL_VERSION,
                "root": ".",
                "artifact_directory": ".coherence/artifacts",
                "created_at": utc_now(),
            },
        )
    write_json(
        workspace.coherence_dir / "session.json",
        {
            "protocol_version": PROTOCOL_VERSION,
            "run_id": stable_id("run", str(uuid.uuid4())),
            "started_at": utc_now(),
            "status": "active",
        },
    )
    return workspace
