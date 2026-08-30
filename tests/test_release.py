from pathlib import Path
import io
import subprocess
import tarfile
import tempfile
import unittest
import zipfile

from coherence import __version__
from coherence.release import (
    _inspect_skill_archive,
    _inspect_sdist,
    _history_privacy,
    _safe_archive_name,
    _write_skill_archive,
    release_check,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ReleaseCheckTests(unittest.TestCase):
    def test_skill_archive_is_deterministic_and_self_contained(self):
        with tempfile.TemporaryDirectory(prefix="coherence-release-") as directory:
            output = Path(directory)
            archive = _write_skill_archive(PROJECT_ROOT, __version__, output)
            first_bytes = archive.read_bytes()
            second = _write_skill_archive(PROJECT_ROOT, __version__, output)

            self.assertEqual(archive, second)
            self.assertEqual(first_bytes, second.read_bytes())
            self.assertEqual(_inspect_skill_archive(archive, __version__), [])
            with zipfile.ZipFile(archive) as handle:
                self.assertTrue(
                    all(not name.startswith("src/") for name in handle.namelist())
                )

    def test_archive_path_policy_rejects_traversal_and_absolute_names(self):
        self.assertTrue(_safe_archive_name("skills/system-coherence/SKILL.md"))
        self.assertFalse(_safe_archive_name("../outside.txt"))
        self.assertFalse(_safe_archive_name("C:\\outside.txt"))
        self.assertFalse(_safe_archive_name("/outside.txt"))

    def test_sdist_boundary_rejects_development_surfaces(self):
        with tempfile.TemporaryDirectory(prefix="coherence-sdist-") as directory:
            archive_path = Path(directory) / "system_coherence-1.2.0.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                for name, data in (
                    ("system_coherence-1.2.0/", b""),
                    ("system_coherence-1.2.0/src/", b""),
                    ("system_coherence-1.2.0/src/coherence/", b""),
                    ("system_coherence-1.2.0/PKG-INFO", b"Version: 1.2.0\n"),
                    ("system_coherence-1.2.0/tests/test_secret.py", b"test"),
                ):
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data) if data else None)

            errors = _inspect_sdist(archive_path, "1.2.0")

        self.assertTrue(any("development file" in error for error in errors))

    def test_history_privacy_finding_redacts_the_address(self):
        with tempfile.TemporaryDirectory(prefix="coherence-history-") as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test.person@gmail.com"], cwd=root, check=True)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)

            findings, message = _history_privacy(root)

        self.assertIn("scanned", message)
        self.assertTrue(any(item["kind"] == "private-commit-email" for item in findings))
        self.assertFalse(any("@gmail.com" in str(item) for item in findings))

    def test_no_build_mode_reports_missing_python_artifacts_explicitly(self):
        with tempfile.TemporaryDirectory(prefix="coherence-release-") as directory:
            report = release_check(
                PROJECT_ROOT,
                dist_dir=Path(directory) / "dist",
                build_artifacts=False,
                clean_install=False,
            )

        self.assertFalse(report["passed"])
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("wheel-count", failed)
        self.assertIn("sdist-count", failed)


if __name__ == "__main__":
    unittest.main()
