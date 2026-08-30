"""Generate a disposable protocol fixture workspace for System Coherence."""

from __future__ import annotations

import json
from pathlib import Path
import sys


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = _project_root()
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from coherence.dogfood import build_dogfood

    ledger = build_dogfood(root)
    entries = ledger["content"]["entries"]
    print(json.dumps({"workspace": str(root / ".coherence"), "entries": entries}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
