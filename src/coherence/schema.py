"""Semantic validation for the portable artifact protocol.

The repository also publishes JSON Schema documents for tooling that speaks
JSON Schema. This module intentionally has no third-party dependency so the
CLI remains usable in a clean checkout.
"""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any

from .models import ARTIFACT_STATUSES, ARTIFACT_TYPES


SCHEMA_VERSION = "1.0"
FRESHNESS_STATES = frozenset({"current", "stale", "unknown"})
_ARTIFACT_ID_PATTERN = re.compile(r"^artifact/[a-z0-9-]+$")

REQUIRED_ENVELOPE_FIELDS = (
    "artifact_type",
    "schema_version",
    "artifact_id",
    "run_id",
    "status",
    "source_revision",
    "created_at",
    "producer",
    "inputs",
    "evidence_refs",
    "uncertainty",
    "freshness",
    "content",
)

REQUIRED_CONTENT_FIELDS = {
    "repository-evidence": ("files",),
    "system-model": ("system_id",),
    "capability-map": ("capabilities",),
    "behavioral-contracts": ("contracts",),
    "state-model": ("states", "transitions"),
    "implementation-traces": ("traces",),
    "audit-findings": ("findings",),
    "intervention-plan": ("actions",),
    "regression-scope": ("changed_paths", "impacted_capability_ids"),
    "revalidation-results": ("validations",),
    "coherence-ledger": ("entries",),
}

DOMAIN_COLLECTIONS = {
    "repository-evidence": ("files", "evidence_id"),
    "capability-map": ("capabilities", "capability_id"),
    "behavioral-contracts": ("contracts", "contract_id"),
    "state-model": ("states", "state_id"),
    "implementation-traces": ("traces", "trace_id"),
    "audit-findings": ("findings", "finding_id"),
    "intervention-plan": ("actions", "action_id"),
    "revalidation-results": ("validations", "validation_id"),
    "coherence-ledger": ("entries", "capability_id"),
}

_RELATION_LIST_FIELDS = {
    "capability-map": {
        "capabilities": ("actors", "triggers", "surfaces", "resource_ids", "evidence_refs"),
    },
    "behavioral-contracts": {
        "contracts": ("preconditions", "side_effects", "observables", "failure_modes", "invariants", "evidence_refs"),
    },
    "state-model": {
        "transitions": (
            "contract_ids",
            "from_state_ids",
            "to_state_ids",
            "authoritative_changes",
            "derived_invalidations",
            "notifications",
            "persistence",
            "external_effects",
        ),
    },
    "implementation-traces": {
        "traces": (
            "capability_ids",
            "contract_ids",
            "transition_ids",
            "source_paths",
            "entrypoints",
            "operations",
            "evidence_refs",
        ),
    },
    "audit-findings": {
        "findings": (
            "capability_ids",
            "contract_ids",
            "transition_ids",
            "trace_ids",
            "evidence_refs",
            "recommended_actions",
        ),
    },
    "intervention-plan": {
        "actions": ("finding_ids", "regression_scope", "acceptance_criteria"),
    },
    "regression-scope": {
        "content": (
            "changed_paths",
            "matched_trace_ids",
            "invalidated_contract_ids",
            "impacted_capability_ids",
            "invalidated_artifact_types",
        ),
    },
    "revalidation-results": {
        "validations": ("capability_ids", "evidence_refs", "checks"),
    },
    "coherence-ledger": {
        "entries": ("contract_ids", "finding_ids", "evidence_refs"),
    },
}

_REVALIDATION_TARGET_TYPES = frozenset(
    {"capability", "contract", "transition", "trace", "finding"}
)
_REVALIDATION_RESULTS = frozenset(
    {"verified", "failed", "inconclusive", "unverified"}
)
_LEDGER_STATUSES = frozenset(
    {"verified", "broken", "partial", "needs-revalidation", "blocked", "unverified"}
)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _append_required(errors: list[str], value: dict[str, Any], field: str) -> None:
    if field not in value:
        errors.append(f"missing required field: {field}")


def _validate_string_list(errors: list[str], value: Any, field: str) -> None:
    if not isinstance(value, list) or any(not _is_non_empty_string(item) for item in value):
        errors.append(f"{field} must be a list of non-empty strings")


def _validate_domain_collection(
    errors: list[str], content: dict[str, Any], artifact_type: str
) -> None:
    collection_name, id_field = DOMAIN_COLLECTIONS.get(artifact_type, (None, None))
    if collection_name is None or collection_name not in content:
        return
    collection = content[collection_name]
    if not isinstance(collection, list):
        errors.append(f"content.{collection_name} must be a list")
        return
    seen: set[str] = set()
    for index, item in enumerate(collection):
        if not isinstance(item, dict):
            errors.append(f"content.{collection_name}[{index}] must be an object")
            continue
        identifier = item.get(id_field)
        if not _is_non_empty_string(identifier):
            errors.append(
                f"content.{collection_name}[{index}] missing non-empty {id_field}"
            )
        elif identifier in seen:
            errors.append(f"duplicate {id_field}: {identifier}")
        else:
            seen.add(identifier)

    if artifact_type == "state-model":
        _validate_identifier_collection(errors, content, "transitions", "transition_id")


def _validate_identifier_collection(
    errors: list[str], content: dict[str, Any], collection_name: str, id_field: str
) -> None:
    collection = content.get(collection_name)
    if not isinstance(collection, list):
        return
    seen: set[str] = set()
    for index, item in enumerate(collection):
        if not isinstance(item, dict):
            continue
        identifier = item.get(id_field)
        if _is_non_empty_string(identifier):
            if identifier in seen:
                errors.append(f"duplicate {id_field}: {identifier}")
            else:
                seen.add(identifier)


def _validate_relation_lists(
    errors: list[str], content: dict[str, Any], artifact_type: str
) -> None:
    fields_by_collection = _RELATION_LIST_FIELDS.get(artifact_type, {})
    for collection_name, field_names in fields_by_collection.items():
        if collection_name == "content":
            items = [content]
            prefix = "content"
        else:
            items = content.get(collection_name, [])
            prefix = f"content.{collection_name}"
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            for field_name in field_names:
                if field_name not in item:
                    continue
                field = item[field_name]
                if not isinstance(field, list) or any(
                    not _is_non_empty_string(value) for value in field
                ):
                    item_prefix = prefix if collection_name == "content" else f"{prefix}[{index}]"
                    errors.append(
                        f"{item_prefix}.{field_name} must be a list of non-empty strings"
                    )


def _validate_revalidation_entries(errors: list[str], content: dict[str, Any]) -> None:
    validations = content.get("validations")
    if not isinstance(validations, list):
        return
    for index, item in enumerate(validations):
        if not isinstance(item, dict):
            continue
        prefix = f"content.validations[{index}]"
        target_type = item.get("target_type")
        if target_type not in _REVALIDATION_TARGET_TYPES:
            errors.append(
                f"{prefix}.target_type must be one of "
                + ", ".join(sorted(_REVALIDATION_TARGET_TYPES))
            )
        for field_name in ("target_id", "checked_revision"):
            if not _is_non_empty_string(item.get(field_name)):
                errors.append(f"{prefix}.{field_name} is required")
        if item.get("result") not in _REVALIDATION_RESULTS:
            errors.append(
                f"{prefix}.result must be one of "
                + ", ".join(sorted(_REVALIDATION_RESULTS))
            )
        for field_name in ("checks", "evidence_refs"):
            field = item.get(field_name)
            if not isinstance(field, list) or not field or any(
                not _is_non_empty_string(value) for value in field
            ):
                errors.append(f"{prefix}.{field_name} must be a non-empty list")


def _validate_system_resources(errors: list[str], content: dict[str, Any]) -> None:
    if "resources" not in content:
        return
    resources = content["resources"]
    if not isinstance(resources, list):
        errors.append("content.resources must be a list")
        return
    seen: set[str] = set()
    for index, resource in enumerate(resources):
        if not isinstance(resource, dict):
            errors.append(f"content.resources[{index}] must be an object")
            continue
        resource_id = resource.get("resource_id")
        if not _is_non_empty_string(resource_id):
            errors.append(
                f"content.resources[{index}] missing non-empty resource_id"
            )
        elif resource_id in seen:
            errors.append(f"duplicate resource_id: {resource_id}")
        else:
            seen.add(resource_id)


def _validate_ledger_entries(errors: list[str], content: dict[str, Any]) -> None:
    entries = content.get("entries")
    if not isinstance(entries, list):
        return
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        status = entry.get("status")
        if status not in _LEDGER_STATUSES:
            errors.append(
                f"content.entries[{index}].status must be one of "
                + ", ".join(sorted(_LEDGER_STATUSES))
            )


def validate_envelope(
    value: Any, expected_type: str | None = None
) -> list[str]:
    """Return protocol errors for one artifact envelope.

    Validation is intentionally reported as a list so a skill or CLI can fix
    several malformed fields in one pass instead of discovering them serially.
    """

    errors: list[str] = []
    if not isinstance(value, dict):
        return ["artifact envelope must be an object"]

    for field in REQUIRED_ENVELOPE_FIELDS:
        _append_required(errors, value, field)

    artifact_type = value.get("artifact_type")
    if artifact_type not in ARTIFACT_TYPES:
        errors.append(f"unknown artifact_type: {artifact_type}")
    elif expected_type is not None and artifact_type != expected_type:
        errors.append(f"artifact_type must be {expected_type}")

    if value.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")

    artifact_id = value.get("artifact_id")
    if artifact_type in ARTIFACT_TYPES and artifact_id != f"artifact/{artifact_type}":
        errors.append(f"artifact_id must be artifact/{artifact_type}")
    elif artifact_id is not None and not _ARTIFACT_ID_PATTERN.fullmatch(str(artifact_id)):
        errors.append("artifact_id must match artifact/<artifact-type>")

    if not _is_non_empty_string(value.get("run_id")):
        errors.append("run_id must be a non-empty string")
    if value.get("status") not in ARTIFACT_STATUSES:
        errors.append(
            "status must be one of complete, partial, blocked, stale, invalid"
        )
    if not _is_non_empty_string(value.get("source_revision")):
        errors.append("source_revision must be a non-empty string")
    if not _is_non_empty_string(value.get("created_at")):
        errors.append("created_at must be a non-empty string")

    producer = value.get("producer")
    if not isinstance(producer, dict):
        errors.append("producer must be an object")
    else:
        for field in ("skill", "agent"):
            if not _is_non_empty_string(producer.get(field)):
                errors.append(f"producer.{field} must be a non-empty string")

    _validate_string_list(errors, value.get("inputs"), "inputs")
    for artifact in value.get("inputs", []) if isinstance(value.get("inputs"), list) else []:
        if not _ARTIFACT_ID_PATTERN.fullmatch(artifact):
            errors.append(f"input is not an artifact ID: {artifact}")
        if artifact == value.get("artifact_id"):
            errors.append("artifact cannot list itself as an input")

    _validate_string_list(errors, value.get("evidence_refs"), "evidence_refs")

    uncertainty = value.get("uncertainty")
    if not isinstance(uncertainty, list):
        errors.append("uncertainty must be a list")
    else:
        for index, item in enumerate(uncertainty):
            if not isinstance(item, dict):
                errors.append(f"uncertainty[{index}] must be an object")
                continue
            if not _is_non_empty_string(item.get("kind")):
                errors.append(f"uncertainty[{index}].kind must be a non-empty string")
            if not _is_non_empty_string(item.get("message")):
                errors.append(
                    f"uncertainty[{index}].message must be a non-empty string"
                )

    freshness = value.get("freshness")
    if not isinstance(freshness, dict):
        errors.append("freshness must be an object")
    else:
        if freshness.get("state") not in FRESHNESS_STATES:
            errors.append("freshness.state must be current, stale, or unknown")
        if not _is_non_empty_string(freshness.get("checked_at")):
            errors.append("freshness.checked_at must be a non-empty string")
        if not _is_non_empty_string(freshness.get("dependency_fingerprint")):
            errors.append("freshness.dependency_fingerprint must be a non-empty string")

    content = value.get("content")
    if not isinstance(content, dict):
        errors.append("content must be an object")
    elif artifact_type in REQUIRED_CONTENT_FIELDS:
        for field in REQUIRED_CONTENT_FIELDS[artifact_type]:
            _append_required(errors, content, field)
        _validate_domain_collection(errors, content, artifact_type)
        _validate_relation_lists(errors, content, artifact_type)
        if artifact_type == "system-model":
            _validate_system_resources(errors, content)
        if artifact_type == "revalidation-results":
            _validate_revalidation_entries(errors, content)
        if artifact_type == "coherence-ledger":
            _validate_ledger_entries(errors, content)

    content_hash = value.get("content_hash")
    if content_hash is not None and not re.fullmatch(r"[0-9a-f]{64}", str(content_hash)):
        errors.append("content_hash must be a 64-character lowercase SHA-256 digest")

    return errors


def all_artifact_types() -> Iterable[str]:
    return ARTIFACT_TYPES
