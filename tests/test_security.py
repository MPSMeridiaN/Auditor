from pathlib import Path
import json
import tempfile
import unittest

from coherence.evaluation import _load_module, run_evaluations, validate_scenarios
from coherence.store import ArtifactStore, Workspace


class SecurityBoundaryTests(unittest.TestCase):
    def test_artifact_store_rejects_symlinked_artifacts(self):
        with tempfile.TemporaryDirectory(prefix="coherence-security-") as directory:
            root = Path(directory)
            store = ArtifactStore(Workspace(root))
            store.workspace.ensure()
            outside = root.parent / (root.name + "-outside.json")
            outside.write_text("{}", encoding="utf-8")
            link = store.workspace.artifacts_dir / "repository-evidence.json"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                outside.unlink(missing_ok=True)
                self.skipTest("symlinks are unavailable on this platform")

            try:
                with self.assertRaises(ValueError):
                    store.read("repository-evidence")
            finally:
                link.unlink(missing_ok=True)
                outside.unlink(missing_ok=True)

    def test_evaluation_loader_rejects_symlinked_fixture(self):
        with tempfile.TemporaryDirectory(prefix="coherence-security-") as directory:
            root = Path(directory)
            outside = root.parent / (root.name + "-fixture.py")
            outside.write_text("VALUE = 1\n", encoding="utf-8")
            link = root / "fixture.py"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                outside.unlink(missing_ok=True)
                self.skipTest("symlinks are unavailable on this platform")

            try:
                with self.assertRaises(ValueError):
                    _load_module(root, Path("fixture.py"), "fixture")
            finally:
                link.unlink(missing_ok=True)
                outside.unlink(missing_ok=True)

    def test_evaluation_metadata_rejects_modules_outside_examples(self):
        root = Path.cwd()
        scenario = {
            "scenario_id": "unsafe",
            "architecture": "test",
            "module": "fixture.py",
            "class": "Fixture",
            "probe": "noop",
            "capability_ids": ["cap-test"],
            "expected_finding_category": None,
            "expected_finding": False,
            "negative_control": True,
            "evidence_paths": [],
        }

        errors = validate_scenarios(root, [scenario])

        self.assertTrue(any("safe examples fixture" in error for error in errors))

    def test_default_evaluation_does_not_import_declared_fixture_code(self):
        with tempfile.TemporaryDirectory(prefix="coherence-eval-security-") as directory:
            root = Path(directory)
            examples = root / "examples"
            examples.mkdir()
            (examples / "fixture.py").write_text(
                "from pathlib import Path\n"
                "Path(__file__).with_name('executed').write_text('yes')\n"
                "class CleanLedger:\n"
                "    def rename(self, old, new): self.items = {new: 'present'}\n"
                "    def lookup(self, key): return self.items.get(key)\n",
                encoding="utf-8",
            )
            scenario = {
                "scenario_id": "safe-default",
                "architecture": "CLI",
                "module": "examples/fixture.py",
                "class": "CleanLedger",
                "probe": "atomic_rename",
                "capability_ids": ["cap-test"],
                "expected_finding_category": None,
                "expected_finding": False,
                "negative_control": True,
                "evidence_paths": ["examples/fixture.py"],
            }
            (examples / "scenarios.json").write_text(
                json.dumps([scenario]), encoding="utf-8"
            )

            report = run_evaluations(root)

            self.assertEqual(report["execution"], "skipped")
            self.assertFalse((examples / "executed").exists())


if __name__ == "__main__":
    unittest.main()
