from pathlib import Path
import tempfile
import unittest
import zipfile

from coherence import __version__
from coherence.release import (
    _inspect_skill_archive,
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
