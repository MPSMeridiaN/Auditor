import json
from pathlib import Path
import unittest

from coherence.models import ARTIFACT_TYPES, utc_now
from coherence.schema import validate_envelope
from coherence.store import ArtifactStore, Workspace, content_hash


def valid_envelope(artifact_type="system-model", content=None, **overrides):
    envelope = {
        "artifact_type": artifact_type,
        "schema_version": "1.0",
        "artifact_id": f"artifact/{artifact_type}",
        "run_id": "run-test",
        "status": "complete",
        "source_revision": "WORKTREE",
        "created_at": "2026-08-30T00:00:00Z",
        "producer": {"skill": "test", "agent": "test"},
        "inputs": [],
        "evidence_refs": [],
        "uncertainty": [],
        "freshness": {
            "state": "current",
            "checked_at": "2026-08-30T00:00:00Z",
            "dependency_fingerprint": "none",
        },
        "content": content or {"system_id": "sys-demo"},
    }
    envelope.update(overrides)
    return envelope


class ArtifactContractTests(unittest.TestCase):
    def test_rejects_missing_required_envelope_fields(self):
        errors = validate_envelope({"artifact_type": "system-model"})

        self.assertIn("missing required field: schema_version", errors)

    def test_rejects_an_invalid_status(self):
        errors = validate_envelope(valid_envelope(status="finished"))

        self.assertIn("status must be one of complete, partial, blocked, stale, invalid", errors)

    def test_rejects_a_self_referential_input(self):
        errors = validate_envelope(
            valid_envelope(inputs=["artifact/system-model"])
        )

        self.assertIn("artifact cannot list itself as an input", errors)

    def test_published_json_schema_enumerates_protocol_artifact_types(self):
        schema = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "skills"
                / "system-coherence"
                / "references"
                / "schemas"
                / "artifact-envelope.schema.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(schema["properties"]["artifact_type"]["enum"], list(ARTIFACT_TYPES))

    def test_published_payload_schema_has_a_root_selector(self):
        schema = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "skills"
                / "system-coherence"
                / "references"
                / "schemas"
                / "artifact-payloads.schema.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(len(schema["anyOf"]), len(ARTIFACT_TYPES))

    def test_published_schema_ids_are_local_resolvable(self):
        schema_root = (
            Path(__file__).resolve().parents[1]
            / "skills"
            / "system-coherence"
            / "references"
            / "schemas"
        )

        for filename in (
            "artifact-envelope.schema.json",
            "artifact-payloads.schema.json",
            "evaluation-scenarios.schema.json",
        ):
            schema = json.loads((schema_root / filename).read_text(encoding="utf-8"))
            self.assertEqual(schema["$id"], filename)

    def test_rejects_duplicate_state_transition_ids(self):
        errors = validate_envelope(
            valid_envelope(
                "state-model",
                {
                    "states": [{"state_id": "stt-demo"}],
                    "transitions": [
                        {"transition_id": "trn-demo"},
                        {"transition_id": "trn-demo"},
                    ],
                },
            )
        )

        self.assertIn("duplicate transition_id: trn-demo", errors)

    def test_rejects_scalar_relation_fields(self):
        errors = validate_envelope(
            valid_envelope(
                "audit-findings",
                {
                    "findings": [
                        {
                            "finding_id": "fnd-demo",
                            "capability_ids": "cap-demo",
                        }
                    ]
                },
            )
        )

        self.assertIn(
            "content.findings[0].capability_ids must be a list of non-empty strings",
            errors,
        )

    def test_revalidation_entries_require_target_result_revision_checks_and_evidence(self):
        errors = validate_envelope(
            valid_envelope(
                "revalidation-results",
                {
                    "validations": [
                        {
                            "validation_id": "val-demo",
                            "target_type": "capability",
                            "target_id": "cap-demo",
                            "result": "verified",
                        }
                    ]
                },
            )
        )

        self.assertIn("content.validations[0].checked_revision is required", errors)
        self.assertIn("content.validations[0].checks must be a non-empty list", errors)
        self.assertIn(
            "content.validations[0].evidence_refs must be a non-empty list",
            errors,
        )

    def test_ledger_entries_require_a_known_coherence_status(self):
        errors = validate_envelope(
            valid_envelope(
                "coherence-ledger",
                {"entries": [{"capability_id": "cap-demo", "status": "done"}]},
            )
        )

        self.assertTrue(
            any("content.entries[0].status must be one of" in error for error in errors)
        )


class ArtifactStoreTests(unittest.TestCase):
    def test_writes_reads_and_archives_current_artifact(self):
        with self.subTest("round trip"):
            root = Path(self._tmpdir())
            store = ArtifactStore(Workspace(root))
            store.write(valid_envelope())

            current = store.read("system-model")

            self.assertEqual(current["content"]["system_id"], "sys-demo")
            self.assertEqual(store.validate_all(), {})

        with self.subTest("previous version is retained"):
            store.write(
                valid_envelope(
                    content={"system_id": "sys-demo", "name": "renamed"},
                    run_id="run-test-2",
                )
            )
            history = list(
                (root / ".coherence" / "history" / "system-model").glob("*.json")
            )
            self.assertEqual(len(history), 1)
            self.assertEqual(
                json.loads(history[0].read_text(encoding="utf-8"))["run_id"],
                "run-test",
            )

    def test_replacing_evidence_keeps_stale_artifact_references_resolvable(self):
        root = Path(self._tmpdir())
        store = ArtifactStore(Workspace(root))
        store.write(
            valid_envelope(
                "repository-evidence",
                {"files": [{"evidence_id": "ev-old", "path": "app.py"}]},
                source_revision="TREE-old",
            )
        )
        store.write(
            valid_envelope(
                "system-model",
                {"system_id": "sys-demo"},
                inputs=["artifact/repository-evidence"],
                evidence_refs=["ev-old"],
            )
        )

        store.write(
            valid_envelope(
                "repository-evidence",
                {"files": [{"evidence_id": "ev-new", "path": "app.py"}]},
                source_revision="TREE-new",
            )
        )

        errors = store.validate_all()
        self.assertNotIn(
            "evidence reference not found: ev-old",
            errors.get("system-model", []),
        )
        self.assertIn(
            "dependency fingerprint does not match inputs",
            errors.get("system-model", []),
        )
        history = list((root / ".coherence" / "history" / "repository-evidence").glob("*.json"))
        self.assertEqual(len(history), 1)

    def test_rejects_unknown_artifact_type(self):
        root = Path(self._tmpdir())
        store = ArtifactStore(Workspace(root))

        with self.assertRaises(ValueError):
            store.write(valid_envelope("unknown", {}))

    def test_validate_all_reports_malformed_current_file(self):
        root = Path(self._tmpdir())
        workspace = Workspace(root)
        workspace.artifacts_dir.mkdir(parents=True)
        (workspace.artifacts_dir / "system-model.json").write_text(
            '{"artifact_type":"system-model"}', encoding="utf-8"
        )

        errors = ArtifactStore(workspace).validate_all()

        self.assertIn("system-model", errors)
        self.assertIn("missing required field: schema_version", errors["system-model"])

    def test_validate_all_reports_a_tampered_content_hash(self):
        root = Path(self._tmpdir())
        store = ArtifactStore(Workspace(root))
        store.write(valid_envelope())
        path = root / ".coherence" / "artifacts" / "system-model.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["content"]["name"] = "tampered"
        path.write_text(json.dumps(value), encoding="utf-8")

        errors = store.validate_all()

        self.assertIn("system-model", errors)
        self.assertIn("content_hash does not match artifact content", errors["system-model"])

    def test_validate_all_requires_a_content_hash_for_current_snapshots(self):
        root = Path(self._tmpdir())
        store = ArtifactStore(Workspace(root))
        store.write(valid_envelope())
        path = root / ".coherence" / "artifacts" / "system-model.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value.pop("content_hash")
        path.write_text(json.dumps(value), encoding="utf-8")

        errors = store.validate_all()

        self.assertIn("content_hash is required for current artifact", errors["system-model"])

    def test_validate_all_reports_unknown_current_artifact_files(self):
        root = Path(self._tmpdir())
        workspace = Workspace(root)
        workspace.artifacts_dir.mkdir(parents=True)
        (workspace.artifacts_dir / "unknown.json").write_text("{}", encoding="utf-8")

        errors = ArtifactStore(workspace).validate_all()

        self.assertIn("unknown", errors)
        self.assertTrue(any("unknown artifact type" in error for error in errors["unknown"]))

    def test_write_can_repair_a_malformed_current_artifact(self):
        root = Path(self._tmpdir())
        workspace = Workspace(root)
        workspace.artifacts_dir.mkdir(parents=True)
        (workspace.artifacts_dir / "system-model.json").write_text(
            "not-json", encoding="utf-8"
        )
        store = ArtifactStore(workspace)

        store.write(valid_envelope())

        self.assertEqual(store.read("system-model")["content"]["system_id"], "sys-demo")

    def test_validate_all_reports_dangling_transition_references(self):
        root = Path(self._tmpdir())
        store = ArtifactStore(Workspace(root))
        store.write(
            valid_envelope(
                "capability-map",
                {"capabilities": [{"capability_id": "cap-demo"}]},
            )
        )
        store.write(
            valid_envelope(
                "behavioral-contracts",
                {
                    "contracts": [
                        {
                            "contract_id": "con-demo",
                            "capability_id": "cap-demo",
                            "expected_transition": "trn-missing",
                        }
                    ]
                },
                inputs=["artifact/capability-map"],
            )
        )
        workspace = Workspace(root)
        workspace.ensure()
        state_model = valid_envelope(
            "state-model",
            {
                "states": [{"state_id": "stt-demo"}],
                "transitions": [{"transition_id": "trn-real"}],
            },
            inputs=["artifact/behavioral-contracts"],
        )
        state_model["content_hash"] = content_hash(state_model)
        (workspace.artifacts_dir / "state-model.json").write_text(
            json.dumps(state_model),
            encoding="utf-8",
        )

        errors = store.validate_all()

        self.assertTrue(
            any(
                "expected_transition references missing transition" in error
                for error in errors["behavioral-contracts"]
            )
        )

    def test_validate_all_reports_unknown_evidence_and_validation_references(self):
        root = Path(self._tmpdir())
        workspace = Workspace(root)
        store = ArtifactStore(workspace)
        store.write(
            valid_envelope(
                "repository-evidence",
                {"files": [{"evidence_id": "ev-known", "path": "app.py"}]},
            )
        )
        store.write(
            valid_envelope(
                "capability-map",
                {"capabilities": [{"capability_id": "cap-demo"}]},
                inputs=["artifact/repository-evidence"],
            )
        )
        workspace.ensure()
        system_model = valid_envelope(
            "system-model",
            {"system_id": "sys-demo"},
            evidence_refs=["ev-missing"],
            inputs=["artifact/repository-evidence"],
        )
        system_model["content_hash"] = content_hash(system_model)
        (workspace.artifacts_dir / "system-model.json").write_text(
            json.dumps(system_model),
            encoding="utf-8",
        )
        revalidation = valid_envelope(
            "revalidation-results",
            {
                "validations": [
                    {
                        "validation_id": "val-demo",
                        "target_type": "capability",
                        "target_id": "cap-missing",
                        "result": "verified",
                        "checked_revision": "rev-1",
                        "checks": ["test probe"],
                        "evidence_refs": ["ev-missing-nested"],
                    }
                ]
            },
            inputs=["artifact/capability-map"],
        )
        revalidation["content_hash"] = content_hash(revalidation)
        (workspace.artifacts_dir / "revalidation-results.json").write_text(
            json.dumps(revalidation),
            encoding="utf-8",
        )

        errors = store.validate_all()

        self.assertTrue(
            any("evidence reference not found" in error for error in errors["system-model"])
        )
        self.assertTrue(
            any(
                "validation references missing capability" in error
                for error in errors["revalidation-results"]
            )
        )
        self.assertTrue(
            any(
                "evidence reference not found: ev-missing-nested" in error
                for error in errors["revalidation-results"]
            )
        )

    def test_write_rejects_new_references_that_break_the_current_graph(self):
        root = Path(self._tmpdir())
        store = ArtifactStore(Workspace(root))
        store.write(
            valid_envelope(
                "capability-map",
                {"capabilities": [{"capability_id": "cap-demo"}]},
            )
        )
        store.write(
            valid_envelope(
                "behavioral-contracts",
                {
                    "contracts": [
                        {
                            "contract_id": "con-demo",
                            "capability_id": "cap-demo",
                            "expected_transition": "trn-missing",
                        }
                    ]
                },
                inputs=["artifact/capability-map"],
            )
        )

        with self.assertRaises(ValueError) as context:
            store.write(
                valid_envelope(
                    "state-model",
                    {
                        "states": [{"state_id": "stt-demo"}],
                        "transitions": [{"transition_id": "trn-real"}],
                    },
                    inputs=["artifact/behavioral-contracts"],
                )
            )

        self.assertIn("expected_transition references missing transition", str(context.exception))

    def test_write_rejects_a_dangling_capability_resource_reference(self):
        root = Path(self._tmpdir())
        store = ArtifactStore(Workspace(root))
        store.write(
            valid_envelope(
                "system-model",
                {
                    "system_id": "sys-demo",
                    "resources": [{"resource_id": "res-real"}],
                },
            )
        )

        with self.assertRaises(ValueError) as context:
            store.write(
                valid_envelope(
                    "capability-map",
                    {
                        "capabilities": [
                            {
                                "capability_id": "cap-demo",
                                "resource_ids": ["res-missing"],
                            }
                        ]
                    },
                    inputs=["artifact/system-model"],
                )
            )

        self.assertIn(
            "capability references missing resource: res-missing",
            str(context.exception),
        )

    def test_validate_all_reports_malformed_system_resources_without_crashing(self):
        root = Path(self._tmpdir())
        workspace = Workspace(root)
        malformed = valid_envelope(
            "system-model",
            {"system_id": "sys-demo", "resources": None},
        )
        malformed["content_hash"] = content_hash(malformed)
        workspace.ensure()
        (workspace.artifacts_dir / "system-model.json").write_text(
            json.dumps(malformed), encoding="utf-8"
        )

        errors = ArtifactStore(workspace).validate_all()

        self.assertIn("system-model", errors)
        self.assertIn("content.resources must be a list", errors["system-model"])

    def test_validate_all_reports_changed_input_dependencies(self):
        root = Path(self._tmpdir())
        store = ArtifactStore(Workspace(root))
        store.write(
            valid_envelope(
                "capability-map",
                {"capabilities": [{"capability_id": "cap-demo", "intent": "old"}]},
            )
        )
        store.write(
            valid_envelope(
                "system-model",
                {"system_id": "sys-demo"},
                inputs=["artifact/capability-map"],
            )
        )
        store.write(
            valid_envelope(
                "capability-map",
                {"capabilities": [{"capability_id": "cap-demo", "intent": "new"}]},
            )
        )

        errors = store.validate_all()

        self.assertTrue(
            any(
                "dependency fingerprint does not match inputs" in error
                for error in errors["system-model"]
            )
        )

    _temporary_roots = []

    @classmethod
    def _tmpdir(cls):
        import tempfile

        path = Path(tempfile.mkdtemp(prefix="coherence-artifacts-"))
        cls._temporary_roots.append(path)
        return path


if __name__ == "__main__":
    unittest.main()
