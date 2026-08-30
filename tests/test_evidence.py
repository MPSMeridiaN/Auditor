from pathlib import Path
import tempfile
import unittest
from unittest import mock

from coherence.evidence import _working_tree_state, capture, classify_path


class EvidenceCaptureTests(unittest.TestCase):
    def test_capture_hashes_files_and_excludes_internal_directories(self):
        with tempfile.TemporaryDirectory(prefix="coherence-evidence-") as directory:
            root = Path(directory)
            (root / "src").mkdir()
            source = root / "src" / "app.py"
            source.write_text("print('ok')\n", encoding="utf-8")
            (root / ".coherence").mkdir()
            (root / ".coherence" / "secret.txt").write_text("ignore", encoding="utf-8")
            (root / ".agents").mkdir()
            (root / ".agents" / "local.md").write_text("ignore", encoding="utf-8")

            envelope = capture(root)

            files = {item["path"]: item for item in envelope["content"]["files"]}
            self.assertIn("src/app.py", files)
            self.assertNotIn(".coherence/secret.txt", files)
            self.assertNotIn(".agents/local.md", files)
            self.assertEqual(files["src/app.py"]["kind"], "source")
            self.assertEqual(files["src/app.py"]["size"], 13)
            self.assertEqual(len(files["src/app.py"]["sha256"]), 64)

    def test_capture_excludes_ignored_install_and_secret_files(self):
        with tempfile.TemporaryDirectory(prefix="coherence-evidence-") as directory:
            root = Path(directory)
            (root / "skills-lock.json").write_text("{}", encoding="utf-8")
            (root / ".env.local").write_text("TOKEN=secret\n", encoding="utf-8")
            (root / "coverage").mkdir()
            (root / "coverage" / "report.json").write_text("{}", encoding="utf-8")
            (root / "README.md").write_text("public\n", encoding="utf-8")

            paths = {
                item["path"]
                for item in capture(root)["content"]["files"]
            }

            self.assertEqual(paths, {"README.md"})

    def test_classify_path_distinguishes_tests_docs_and_config(self):
        self.assertEqual(classify_path(Path("tests/test_cli.py")), "test")
        self.assertEqual(classify_path(Path("docs/methodology.md")), "docs")
        self.assertEqual(classify_path(Path("pyproject.toml")), "config")

    def test_worktree_revision_changes_when_source_content_changes(self):
        with tempfile.TemporaryDirectory(prefix="coherence-evidence-") as directory:
            root = Path(directory)
            first = capture(root)
            (root / "app.py").write_text("return 1\n", encoding="utf-8")
            second = capture(root)

            self.assertNotEqual(first["source_revision"], second["source_revision"])
            self.assertTrue(second["source_revision"].startswith("WORKTREE-"))

    def test_ignored_first_git_status_entry_is_not_reported_as_dirty(self):
        with mock.patch(
            "coherence.evidence.subprocess.run",
            return_value=mock.Mock(
                returncode=0,
                stdout=" M .coherence/session.json\n",
            ),
        ):
            self.assertEqual(_working_tree_state(Path(".")), "clean")


if __name__ == "__main__":
    unittest.main()
