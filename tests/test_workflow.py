from pathlib import Path
import tempfile
import unittest

from coherence.cli import main
from coherence.evidence import capture
from coherence.store import ArtifactStore, Workspace
from coherence.workflow import route

from tests.test_artifacts import valid_envelope


class WorkflowRoutingTests(unittest.TestCase):
    def test_route_after_init_selects_system_reconstruction(self):
        with tempfile.TemporaryDirectory(prefix="coherence-route-") as directory:
            root = Path(directory)
            self.assertEqual(main(["init", str(root)]), 0)

            result = route(ArtifactStore(Workspace(root)))

            self.assertEqual(result["skill"], "reconstruct-system")
            self.assertEqual(result["required_artifacts"], ["repository-evidence"])
            self.assertEqual(result["produces"], ["system-model"])

    def test_route_reports_a_blocked_prerequisite(self):
        with tempfile.TemporaryDirectory(prefix="coherence-route-") as directory:
            root = Path(directory)
            store = ArtifactStore(Workspace(root))
            store.write(
                valid_envelope(
                    "repository-evidence",
                    {"files": []},
                    status="blocked",
                )
            )

            result = route(store)

            self.assertEqual(result["reason"], "required artifact is blocked")
            self.assertEqual(result["repair_artifact"], "repository-evidence")

    def test_route_repairs_an_artifact_with_unknown_freshness(self):
        with tempfile.TemporaryDirectory(prefix="coherence-route-") as directory:
            root = Path(directory)
            store = ArtifactStore(Workspace(root))
            store.write(capture(root))
            store.write(
                valid_envelope(
                    "system-model",
                    {"system_id": "sys-demo"},
                    inputs=["artifact/repository-evidence"],
                    freshness={
                        "state": "unknown",
                        "checked_at": "2026-08-30T00:00:00Z",
                        "dependency_fingerprint": "unknown",
                    },
                )
            )

            result = route(store)

            self.assertEqual(result["repair_artifact"], "system-model")
            self.assertEqual(result["reason"], "artifact freshness is unknown")

    def test_route_repairs_an_artifact_missing_a_declared_stage_input(self):
        with tempfile.TemporaryDirectory(prefix="coherence-route-") as directory:
            root = Path(directory)
            store = ArtifactStore(Workspace(root))
            store.write(capture(root))
            store.write(
                valid_envelope(
                    "system-model",
                    {"system_id": "sys-demo"},
                    source_revision=store.read("repository-evidence")["source_revision"],
                )
            )

            result = route(store)

            self.assertEqual(result["repair_artifact"], "system-model")
            self.assertIn("required stage input", result["reason"])

    def test_route_on_empty_workspace_requests_evidence_capture(self):
        with tempfile.TemporaryDirectory(prefix="coherence-route-") as directory:
            result = route(ArtifactStore(Workspace(Path(directory))))

            self.assertEqual(result["skill"], "system-coherence")
            self.assertEqual(result["produces"], ["repository-evidence"])


if __name__ == "__main__":
    unittest.main()
