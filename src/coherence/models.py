"""Shared protocol constants and deterministic identity helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
import unicodedata

from ._version import __version__ as METHODOLOGY_VERSION

ARTIFACT_STATUSES = frozenset(
    {"complete", "partial", "blocked", "stale", "invalid"}
)

ARTIFACT_TYPES = (
    "repository-evidence",
    "system-model",
    "capability-map",
    "behavioral-contracts",
    "state-model",
    "implementation-traces",
    "audit-findings",
    "intervention-plan",
    "regression-scope",
    "revalidation-results",
    "coherence-ledger",
)

DOMAIN_ID_PREFIXES = frozenset(
    {"ev", "sys", "cap", "con", "trn", "trc", "fnd", "act", "val", "run"}
)

_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


def stable_id(prefix: str, seed: str) -> str:
    """Return a short deterministic identifier for a domain object.

    The seed is normalized for stable IDs across equivalent Unicode spellings,
    while the caller-provided prefix remains visible to humans.
    """

    if not isinstance(prefix, str) or not _PREFIX_PATTERN.fullmatch(prefix):
        raise ValueError("prefix must contain lowercase letters, digits, or hyphens")
    if not isinstance(seed, str):
        raise TypeError("seed must be a string")
    normalized = unicodedata.normalize("NFKC", seed).strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def utc_now() -> str:
    """Return a compact, UTC ISO-8601 timestamp suitable for artifacts."""

    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
