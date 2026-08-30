from pathlib import Path
import tempfile
import unittest

from coherence.invalidation import changed_paths, compute_scope
from coherence.store import ArtifactStore, Workspace

from tests.test_artifacts import valid_envelope


def seed_trace_workspace(root: Path) -> ArtifactStore:
    store = ArtifactStore(Workspace(root))
    store.write(valid_envelope("repository-evidence", {"files": []}))
    store.write(
        valid_envelope(
            "capability-map",
            {"capabilities": [{"capability_id": "cap-cache", "intent": "delete"}]},
            inputs=["artifact/repository-evidence"],
        )
    )
    store.write(
        valid_envelope(
            "behavioral-contracts",
            {
                "contracts": [
                    {"contract_id": "con-cache", "capability_id": "cap-cache"}
                ]
            },
            inputs=["artifact/capability-map"],
        )
    )
    store.write(
        valid_envelope(
            "state-model",
            {
                "states": [{"state_id": "state-cache", "name": "present"}],
                "transitions": [{"transition_id": "trn-cache", "contract_ids": ["con-cache"]}],
            },
            inputs=["artifact/behavioral-contracts"],
        )
    )
    store.write(
        valid_envelope(
            "implementation-traces",
            {
                "traces": [
                    {
                        "trace_id": "trc-cache",
                        "source_paths": ["src/cache.py"],
                        "capability_ids": ["cap-cache"],
                        "contract_ids": ["con-cache"],
                        "transition_ids": ["trn-cache"],
                    }
                ]
            },
            inputs=["artifact/state-model", "artifact/behavioral-contracts"],
        )
    )
    return store


class InvalidationTests(unittest.TestCase):
    def test_explicit_absolute_paths_are_normalized_to_repository_relative_paths(self):
        with tempfile.TemporaryDirectory(prefix="coherence-invalidation-") as directory:
            root = Path(directory)
            source = root / "src" / "cache.py"
            source.parent.mkdir(parents=True)
            source.write_text("pass\n", encoding="utf-8")

            self.assertEqual(
                changed_paths(root, explicit=[str(source), ".\\src\\cache.py"]),
                ["src/cache.py"],
            )

    def test_explicit_paths_outside_repository_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="coherence-invalidation-") as directory:
            root = Path(directory)
            outside = Path(directory).parent / "outside.py"

            with self.assertRaises(ValueError):
                changed_paths(root, explicit=[str(outside)])

    def test_changed_trace_path_invalidates_only_linked_capability(self):
        with tempfile.TemporaryDirectory(prefix="coherence-invalidation-") as directory:
            store = seed_trace_workspace(Path(directory))

            scope = compute_scope(store, ["src/cache.py"], "rev-2")

            self.assertEqual(scope["content"]["impacted_capability_ids"], ["cap-cache"])
            self.assertEqual(scope["content"]["invalidated_contract_ids"], ["con-cache"])
            self.assertEqual(scope["content"]["matched_trace_ids"], ["trc-cache"])
            self.assertFalse(scope["content"]["requires_broad_revalidation"])

    def test_unmapped_path_requests_conservative_broad_revalidation(self):
        with tempfile.TemporaryDirectory(prefix="coherence-invalidation-") as directory:
            store = seed_trace_workspace(Path(directory))

            scope = compute_scope(store, ["src/unmapped.py"], "rev-2")

            self.assertEqual(scope["content"]["scope_unknown_paths"], ["src/unmapped.py"])
            self.assertTrue(scope["content"]["requires_broad_revalidation"])


if __name__ == "__main__":
    unittest.main()
