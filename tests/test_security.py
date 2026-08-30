from pathlib import Path
import tempfile
import unittest

from coherence.evaluation import _load_module
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


if __name__ == "__main__":
    unittest.main()
