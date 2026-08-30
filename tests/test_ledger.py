import json
from pathlib import Path
import tempfile
import unittest

from coherence.invalidation import apply_scope
from coherence.ledger import derive
from coherence.store import ArtifactStore, Workspace, content_hash

from tests.test_artifacts import valid_envelope


def seed_capability(store: ArtifactStore) -> None:
    store.write(
        valid_envelope(
            "repository-evidence",
            {"files": [{"evidence_id": "ev-test", "path": "test.py"}]},
        )
    )
    store.write(
        valid_envelope(
            "capability-map",
            {
                "capabilities": [
                    {"capability_id": "cap-cache", "intent": "remove a resource"},
                    {"capability_id": "cap-read", "intent": "read a resource"},
                ]
            },
        )
    )


class LedgerTests(unittest.TestCase):
    def test_high_open_finding_makes_capability_broken(self):
        with tempfile.TemporaryDirectory(prefix="coherence-ledger-") as directory:
            store = ArtifactStore(Workspace(Path(directory)))
            seed_capability(store)
            store.write(
                valid_envelope(
                    "audit-findings",
                    {
                        "findings": [
                            {
                                "finding_id": "fnd-cache",
                                "capability_ids": ["cap-cache"],
                                "severity": "high",
                                "status": "open",
                                "title": "stale cache",
                            }
                        ]
                    },
                    inputs=["artifact/capability-map"],
                )
            )

            ledger = derive(store)

            self.assertEqual(ledger["content"]["entries"][0]["status"], "broken")
            self.assertEqual(ledger["content"]["entries"][0]["finding_ids"], ["fnd-cache"])

    def test_verified_validation_with_no_open_findings_makes_capability_verified(self):
        with tempfile.TemporaryDirectory(prefix="coherence-ledger-") as directory:
            store = ArtifactStore(Workspace(Path(directory)))
            seed_capability(store)
            store.write(
                valid_envelope(
                    "revalidation-results",
                    {
                        "validations": [
                            {
                                "validation_id": "val-cache",
                                "target_type": "capability",
                                "target_id": "cap-cache",
                                "result": "verified",
                                "checked_revision": "rev-2",
                                "checks": ["test probe"],
                                "evidence_refs": ["ev-test"],
                            }
                        ]
                    },
                    inputs=["artifact/capability-map"],
                )
            )

            ledger = derive(store)

            self.assertEqual(ledger["content"]["entries"][0]["status"], "verified")
            self.assertEqual(
                ledger["content"]["entries"][0]["last_verified_revision"], "rev-2"
            )

    def test_old_verified_revision_cannot_verify_a_new_repository_snapshot(self):
        with tempfile.TemporaryDirectory(prefix="coherence-ledger-") as directory:
            store = ArtifactStore(Workspace(Path(directory)))
            store.write(
                valid_envelope(
                    "repository-evidence",
                    {"files": [{"evidence_id": "ev-test", "path": "test.py"}]},
                    source_revision="rev-2",
                )
            )
            store.write(
                valid_envelope(
                    "capability-map",
                    {"capabilities": [{"capability_id": "cap-cache"}]},
                    inputs=["artifact/repository-evidence"],
                    source_revision="rev-2",
                )
            )
            store.write(
                valid_envelope(
                    "revalidation-results",
                    {
                        "validations": [
                            {
                                "validation_id": "val-cache",
                                "target_type": "capability",
                                "target_id": "cap-cache",
                                "result": "verified",
                                "checked_revision": "rev-1",
                                "checks": ["test probe"],
                                "evidence_refs": ["ev-test"],
                            }
                        ]
                    },
                    inputs=["artifact/capability-map"],
                    source_revision="rev-1",
                )
            )

            ledger = derive(store)

            self.assertEqual(
                ledger["content"]["entries"][0]["status"], "needs-revalidation"
            )
            self.assertIsNone(
                ledger["content"]["entries"][0]["last_verified_revision"]
            )

    def test_capability_snapshot_from_an_old_revision_cannot_be_verified(self):
        with tempfile.TemporaryDirectory(prefix="coherence-ledger-") as directory:
            store = ArtifactStore(Workspace(Path(directory)))
            store.write(
                valid_envelope(
                    "repository-evidence",
                    {"files": [{"evidence_id": "ev-test", "path": "test.py"}]},
                    source_revision="rev-2",
                )
            )
            store.write(
                valid_envelope(
                    "capability-map",
                    {"capabilities": [{"capability_id": "cap-cache"}]},
                    inputs=["artifact/repository-evidence"],
                    source_revision="rev-1",
                )
            )
            store.write(
                valid_envelope(
                    "revalidation-results",
                    {
                        "validations": [
                            {
                                "validation_id": "val-cache",
                                "target_type": "capability",
                                "target_id": "cap-cache",
                                "result": "verified",
                                "checked_revision": "rev-2",
                                "checks": ["test probe"],
                                "evidence_refs": ["ev-test"],
                            }
                        ]
                    },
                    inputs=["artifact/capability-map"],
                    source_revision="rev-2",
                )
            )

            ledger = derive(store)

            self.assertEqual(
                ledger["content"]["entries"][0]["status"], "needs-revalidation"
            )

    def test_validation_of_a_transition_is_attributed_to_its_capability(self):
        with tempfile.TemporaryDirectory(prefix="coherence-ledger-") as directory:
            store = ArtifactStore(Workspace(Path(directory)))
            seed_capability(store)
            store.write(
                valid_envelope(
                    "behavioral-contracts",
                    {
                        "contracts": [
                            {
                                "contract_id": "con-cache",
                                "capability_id": "cap-cache",
                            }
                        ]
                    },
                    inputs=["artifact/capability-map"],
                )
            )
            store.write(
                valid_envelope(
                    "state-model",
                    {
                        "states": [{"state_id": "state-cache"}],
                        "transitions": [
                            {
                                "transition_id": "trn-cache",
                                "contract_ids": ["con-cache"],
                            }
                        ],
                    },
                    inputs=["artifact/behavioral-contracts"],
                )
            )
            store.write(
                valid_envelope(
                    "revalidation-results",
                    {
                        "validations": [
                            {
                                "validation_id": "val-transition",
                                "target_type": "transition",
                                "target_id": "trn-cache",
                                "result": "verified",
                                "checked_revision": "WORKTREE",
                                "checks": ["transition probe"],
                                "evidence_refs": ["ev-test"],
                            }
                        ]
                    },
                    inputs=["artifact/state-model"],
                )
            )

            ledger = derive(store)

            statuses = {
                entry["capability_id"]: entry["status"]
                for entry in ledger["content"]["entries"]
            }
            self.assertEqual(statuses["cap-cache"], "verified")

    def test_unknown_revalidation_freshness_cannot_verify_a_capability(self):
        with tempfile.TemporaryDirectory(prefix="coherence-ledger-") as directory:
            store = ArtifactStore(Workspace(Path(directory)))
            seed_capability(store)
            store.write(
                valid_envelope(
                    "revalidation-results",
                    {
                        "validations": [
                            {
                                "validation_id": "val-cache",
                                "target_type": "capability",
                                "target_id": "cap-cache",
                                "result": "verified",
                                "checked_revision": "rev-2",
                                "checks": ["test probe"],
                                "evidence_refs": ["ev-test"],
                            }
                        ]
                    },
                    inputs=["artifact/capability-map"],
                    freshness={
                        "state": "unknown",
                        "checked_at": "2026-08-30T00:00:00Z",
                        "dependency_fingerprint": "unknown",
                    },
                )
            )

            ledger = derive(store)

            self.assertEqual(
                ledger["content"]["entries"][0]["status"], "needs-revalidation"
            )

    def test_stale_revalidation_artifact_cannot_verify_a_capability(self):
        with tempfile.TemporaryDirectory(prefix="coherence-ledger-") as directory:
            store = ArtifactStore(Workspace(Path(directory)))
            seed_capability(store)
            store.write(
                valid_envelope(
                    "revalidation-results",
                    {
                        "validations": [
                            {
                                "validation_id": "val-cache",
                                "target_type": "capability",
                                "target_id": "cap-cache",
                                "result": "verified",
                                "checked_revision": "rev-2",
                                "checks": ["test probe"],
                                "evidence_refs": ["ev-test"],
                            }
                        ]
                    },
                    inputs=["artifact/capability-map"],
                    status="stale",
                )
            )

            ledger = derive(store)

            self.assertEqual(
                ledger["content"]["entries"][0]["status"], "needs-revalidation"
            )

    def test_malformed_revalidation_record_cannot_verify_a_capability(self):
        with tempfile.TemporaryDirectory(prefix="coherence-ledger-") as directory:
            root = Path(directory)
            store = ArtifactStore(Workspace(root))
            seed_capability(store)
            malformed = valid_envelope(
                "revalidation-results",
                {
                    "validations": [
                        {
                            "validation_id": "val-cache",
                            "target_type": "capability",
                            "target_id": "cap-cache",
                            "result": "verified",
                        }
                    ]
                },
                inputs=["artifact/capability-map"],
            )
            malformed["content_hash"] = content_hash(malformed)
            store.workspace.ensure()
            (store.workspace.artifacts_dir / "revalidation-results.json").write_text(
                json.dumps(malformed), encoding="utf-8"
            )

            ledger = derive(store)

            self.assertEqual(
                ledger["content"]["entries"][0]["status"], "needs-revalidation"
            )

    def test_changed_input_dependency_cannot_leave_capability_verified(self):
        with tempfile.TemporaryDirectory(prefix="coherence-ledger-") as directory:
            store = ArtifactStore(Workspace(Path(directory)))
            store.write(
                valid_envelope(
                    "repository-evidence",
                    {"files": [{"evidence_id": "ev-test", "path": "test.py"}]},
                )
            )
            store.write(valid_envelope("system-model", {"system_id": "sys-old"}))
            store.write(
                valid_envelope(
                    "capability-map",
                    {"capabilities": [{"capability_id": "cap-cache"}]},
                    inputs=["artifact/system-model"],
                )
            )
            store.write(
                valid_envelope(
                    "revalidation-results",
                    {
                        "validations": [
                            {
                                "validation_id": "val-cache",
                                "target_type": "capability",
                                "target_id": "cap-cache",
                                "result": "verified",
                                "checked_revision": "rev-1",
                                "checks": ["test probe"],
                                "evidence_refs": ["ev-test"],
                            }
                        ]
                    },
                    inputs=["artifact/capability-map"],
                )
            )
            store.write(valid_envelope("system-model", {"system_id": "sys-new"}))

            ledger = derive(store)

            self.assertEqual(
                ledger["content"]["entries"][0]["status"], "needs-revalidation"
            )

    def test_scoped_invalidation_preserves_unaffected_verified_capabilities(self):
        with tempfile.TemporaryDirectory(prefix="coherence-ledger-") as directory:
            store = ArtifactStore(Workspace(Path(directory)))
            seed_capability(store)
            store.write(
                valid_envelope(
                    "revalidation-results",
                    {
                        "validations": [
                            {
                                "validation_id": "val-cache",
                                "target_type": "capability",
                                "target_id": "cap-cache",
                                "result": "verified",
                                "checked_revision": "rev-1",
                                "checks": ["test probe"],
                                "evidence_refs": ["ev-test"],
                            },
                            {
                                "validation_id": "val-read",
                                "target_type": "capability",
                                "target_id": "cap-read",
                                "result": "verified",
                                "checked_revision": "rev-1",
                                "checks": ["test probe"],
                                "evidence_refs": ["ev-test"],
                            },
                        ]
                    },
                    inputs=["artifact/capability-map"],
                )
            )
            scope = valid_envelope(
                "regression-scope",
                {
                    "changed_paths": ["src/cache.py"],
                    "impacted_capability_ids": ["cap-cache"],
                    "invalidated_contract_ids": [],
                    "target_revision": "rev-2",
                },
                inputs=["artifact/capability-map"],
            )

            ledger = apply_scope(store, scope)
            statuses = {
                entry["capability_id"]: entry["status"]
                for entry in ledger["content"]["entries"]
            }

            self.assertEqual(statuses["cap-cache"], "needs-revalidation")
            self.assertEqual(statuses["cap-read"], "verified")

    def test_broad_scope_invalidates_every_capability(self):
        with tempfile.TemporaryDirectory(prefix="coherence-ledger-") as directory:
            store = ArtifactStore(Workspace(Path(directory)))
            seed_capability(store)
            store.write(
                valid_envelope(
                    "revalidation-results",
                    {
                        "validations": [
                            {
                                "validation_id": "val-cache",
                                "target_type": "capability",
                                "target_id": "cap-cache",
                                "result": "verified",
                                "checked_revision": "rev-1",
                                "checks": ["test probe"],
                                "evidence_refs": ["ev-test"],
                            },
                            {
                                "validation_id": "val-read",
                                "target_type": "capability",
                                "target_id": "cap-read",
                                "result": "verified",
                                "checked_revision": "rev-1",
                                "checks": ["test probe"],
                                "evidence_refs": ["ev-test"],
                            },
                        ]
                    },
                    inputs=["artifact/capability-map"],
                )
            )
            scope = valid_envelope(
                "regression-scope",
                {
                    "changed_paths": ["unknown.py"],
                    "impacted_capability_ids": [],
                    "scope_unknown_paths": ["unknown.py"],
                    "requires_broad_revalidation": True,
                    "target_revision": "rev-2",
                },
                inputs=["artifact/capability-map"],
            )

            ledger = apply_scope(store, scope)
            statuses = {
                entry["capability_id"]: entry["status"]
                for entry in ledger["content"]["entries"]
            }

            self.assertEqual(statuses["cap-cache"], "needs-revalidation")
            self.assertEqual(statuses["cap-read"], "needs-revalidation")

    def test_existing_regression_scope_marks_impacted_capability_for_revalidation(self):
        with tempfile.TemporaryDirectory(prefix="coherence-ledger-") as directory:
            store = ArtifactStore(Workspace(Path(directory)))
            seed_capability(store)
            store.write(
                valid_envelope(
                    "regression-scope",
                    {
                        "changed_paths": ["src/cache.py"],
                        "impacted_capability_ids": ["cap-cache"],
                        "invalidated_contract_ids": ["con-cache"],
                        "target_revision": "rev-3",
                    },
                    inputs=["artifact/capability-map"],
                )
            )

            ledger = derive(store)

            self.assertEqual(
                ledger["content"]["entries"][0]["status"], "needs-revalidation"
            )

    def test_current_verified_result_closes_an_impacted_regression_scope(self):
        with tempfile.TemporaryDirectory(prefix="coherence-ledger-") as directory:
            store = ArtifactStore(Workspace(Path(directory)))
            seed_capability(store)
            store.write(
                valid_envelope(
                    "regression-scope",
                    {
                        "changed_paths": ["src/cache.py"],
                        "impacted_capability_ids": ["cap-cache"],
                        "invalidated_contract_ids": ["con-cache"],
                        "target_revision": "rev-3",
                    },
                )
            )
            store.write(
                valid_envelope(
                    "revalidation-results",
                    {
                        "validations": [
                            {
                                "validation_id": "val-cache",
                                "target_type": "capability",
                                "target_id": "cap-cache",
                                "result": "verified",
                                "checked_revision": "rev-3",
                                "checks": ["test probe"],
                                "evidence_refs": ["ev-test"],
                            }
                        ]
                    },
                )
            )

            ledger = derive(store)

            self.assertEqual(ledger["content"]["entries"][0]["status"], "verified")


if __name__ == "__main__":
    unittest.main()
