from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from coherence.cli import main
from coherence.evaluation import run_evaluations, validate_scenarios
from coherence.models import ARTIFACT_TYPES
from coherence.store import ArtifactStore, Workspace
from coherence.dogfood import build_dogfood
from coherence.workflow import route


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class EvaluationTests(unittest.TestCase):
    def test_fixture_evaluations_detect_two_defects_and_pass_the_negative_control(self):
        report = run_evaluations(PROJECT_ROOT)

        self.assertEqual(report["scenario_count"], 3)
        self.assertEqual(report["passed"], 3)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(
            {result["scenario_id"] for result in report["results"]},
            {"web-cache-staleness", "worker-partial-completion", "clean-cli-rename"},
        )
        self.assertEqual(
            report["findings_detected"],
            ["stale-derived-state", "partial-commit"],
        )
        for result in report["results"]:
            self.assertTrue(result["capability_ids"])
            self.assertEqual(
                result["negative_control"],
                result["expected_finding"] is False,
            )

    def test_dogfood_build_writes_every_current_artifact_and_validates_graph(self):
        with tempfile.TemporaryDirectory(prefix="coherence-dogfood-") as directory:
            root = Path(directory)
            (root / "src" / "coherence").mkdir(parents=True)
            (root / "src" / "coherence" / "cli.py").write_text(
                "def main():\n    return 0\n", encoding="utf-8"
            )
            (root / "skills").mkdir()
            (root / "skills" / "system-coherence.md").write_text(
                "system skill evidence\n", encoding="utf-8"
            )

            build_dogfood(root)
            store = ArtifactStore(Workspace(root))

            self.assertEqual(set(store.read_all()), set(ARTIFACT_TYPES))
            self.assertEqual(store.validate_all(), {})
            self.assertEqual(store.read("coherence-ledger")["status"], "complete")
            self.assertEqual(route(store)["stage"], "complete")

    def test_route_does_not_claim_completion_for_an_unverified_ledger(self):
        with tempfile.TemporaryDirectory(prefix="coherence-dogfood-") as directory:
            root = Path(directory)
            (root / "src" / "coherence").mkdir(parents=True)
            (root / "src" / "coherence" / "cli.py").write_text(
                "def main():\n    return 0\n", encoding="utf-8"
            )
            (root / "skills").mkdir()

            build_dogfood(root)
            store = ArtifactStore(Workspace(root))
            ledger = store.read("coherence-ledger")
            ledger["content"]["entries"][0]["status"] = "unverified"
            store.write(ledger)

            result = route(store)

            self.assertEqual(result["stage"], "revalidation")
            self.assertEqual(result["repair_artifact"], "revalidation-results")

    def test_route_does_not_claim_completion_for_a_ledger_missing_a_capability(self):
        with tempfile.TemporaryDirectory(prefix="coherence-dogfood-") as directory:
            root = Path(directory)
            (root / "src" / "coherence").mkdir(parents=True)
            (root / "src" / "coherence" / "cli.py").write_text(
                "def main():\n    return 0\n", encoding="utf-8"
            )
            (root / "skills").mkdir()

            build_dogfood(root)
            store = ArtifactStore(Workspace(root))
            ledger = store.read("coherence-ledger")
            ledger["content"]["entries"] = ledger["content"]["entries"][:-1]
            store.write(ledger)

            result = route(store)

            self.assertEqual(result["stage"], "ledger")
            self.assertEqual(result["repair_artifact"], "coherence-ledger")

    def test_dogfood_rebuilds_an_existing_snapshot_without_dangling_references(self):
        with tempfile.TemporaryDirectory(prefix="coherence-dogfood-") as directory:
            root = Path(directory)
            source = root / "src" / "coherence" / "cli.py"
            source.parent.mkdir(parents=True)
            source.write_text("def main():\n    return 0\n", encoding="utf-8")
            (root / "skills").mkdir()

            build_dogfood(root)
            source.write_text("def main():\n    return 1\n", encoding="utf-8")
            build_dogfood(root)

            store = ArtifactStore(Workspace(root))
            self.assertEqual(store.validate_all(), {})
            self.assertEqual(store.read("coherence-ledger")["status"], "complete")

    def test_capture_refresh_preserves_evidence_provenance_in_a_fresh_workspace(self):
        with tempfile.TemporaryDirectory(prefix="coherence-dogfood-") as directory:
            root = Path(directory)
            source = root / "src" / "coherence" / "cli.py"
            source.parent.mkdir(parents=True)
            source.write_text("def main():\n    return 0\n", encoding="utf-8")
            (root / "skills").mkdir()

            build_dogfood(root)
            source.write_text("def main():\n    return 1\n", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["capture", str(root), "--json"])

            self.assertEqual(exit_code, 0)
            errors = ArtifactStore(Workspace(root)).validate_all()
            self.assertFalse(
                any(
                    "evidence reference not found" in error
                    for messages in errors.values()
                    for error in messages
                )
            )

    def test_worktree_invalidation_routes_to_revalidation(self):
        with tempfile.TemporaryDirectory(prefix="coherence-dogfood-") as directory:
            root = Path(directory)
            source = root / "src" / "coherence" / "cli.py"
            source.parent.mkdir(parents=True)
            source.write_text("def main():\n    return 0\n", encoding="utf-8")
            (root / "skills").mkdir()

            build_dogfood(root)
            source.write_text("def main():\n    return 1\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    ["invalidate", str(root), "src/coherence/cli.py", "--json"]
                )

            self.assertEqual(exit_code, 0)
            report = json.loads(output.getvalue())
            self.assertEqual(
                report["scope"]["source_revision"],
                report["ledger"]["source_revision"],
            )
            result = route(ArtifactStore(Workspace(root)))
            self.assertEqual(result["stage"], "revalidation")

    def test_route_requires_fresh_repository_evidence_for_uninvalidated_changes(self):
        with tempfile.TemporaryDirectory(prefix="coherence-dogfood-") as directory:
            root = Path(directory)
            source = root / "src" / "coherence" / "cli.py"
            source.parent.mkdir(parents=True)
            source.write_text("def main():\n    return 0\n", encoding="utf-8")
            (root / "skills").mkdir()

            build_dogfood(root)
            source.write_text("def main():\n    return 1\n", encoding="utf-8")

            result = route(ArtifactStore(Workspace(root)))

            self.assertEqual(result["stage"], "evidence")
            self.assertEqual(result["repair_artifact"], "repository-evidence")

    def test_route_does_not_claim_completion_with_an_unknown_artifact_file(self):
        with tempfile.TemporaryDirectory(prefix="coherence-dogfood-") as directory:
            root = Path(directory)
            (root / "src" / "coherence").mkdir(parents=True)
            (root / "src" / "coherence" / "cli.py").write_text(
                "def main():\n    return 0\n", encoding="utf-8"
            )
            (root / "skills").mkdir()
            build_dogfood(root)
            (root / ".coherence" / "artifacts" / "unexpected.json").write_text(
                "{}", encoding="utf-8"
            )

            result = route(ArtifactStore(Workspace(root)))

            self.assertEqual(result["stage"], "validation")
            self.assertEqual(result["skill"], "system-coherence")

    def test_scenario_validation_rejects_missing_evidence_paths(self):
        scenario = {
            "scenario_id": "bad",
            "architecture": "CLI",
            "module": "examples/clean-cli/ledger.py",
            "class": "CleanLedger",
            "probe": "atomic_rename",
            "capability_ids": ["cap-cli-rename"],
            "expected_finding_category": None,
            "expected_finding": False,
            "negative_control": True,
            "evidence_paths": ["examples/does-not-exist.py"],
        }

        errors = validate_scenarios(PROJECT_ROOT, [scenario])

        self.assertTrue(any("evidence path does not exist" in error for error in errors))

    def test_missing_scenario_metadata_is_reported_without_a_traceback(self):
        with tempfile.TemporaryDirectory(prefix="coherence-eval-") as directory:
            report = run_evaluations(Path(directory))

            self.assertEqual(report["failed"], 1)
            self.assertEqual(report["passed"], 0)
            self.assertTrue(report["validation_errors"])


if __name__ == "__main__":
    unittest.main()
