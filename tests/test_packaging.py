from pathlib import Path
import subprocess
import shutil
import tempfile
import tomllib
import unittest
import zipfile

from coherence import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_runtime_version_matches_project_version(self):
        with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
            project = tomllib.load(handle)

        self.assertEqual(__version__, project["project"]["version"])

    def test_python_package_does_not_repackage_the_skill_collection(self):
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertNotIn("[tool.setuptools.data-files]", pyproject)
        self.assertFalse((PROJECT_ROOT / "MANIFEST.in").exists())

    def test_wheel_contains_only_the_optional_python_verifier(self):
        try:
            with tempfile.TemporaryDirectory(prefix="coherence-wheel-") as directory:
                subprocess.run(
                    [
                        "python",
                        "-m",
                        "pip",
                        "wheel",
                        "--no-deps",
                        ".",
                        "--wheel-dir",
                        directory,
                    ],
                    cwd=PROJECT_ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                wheel = next(Path(directory).glob("*.whl"))
                with zipfile.ZipFile(wheel) as archive:
                    names = set(archive.namelist())
        finally:
            for path in (
                PROJECT_ROOT / "build",
                PROJECT_ROOT / "src" / "system_coherence.egg-info",
            ):
                if path.exists():
                    shutil.rmtree(path)

        self.assertIn("coherence/cli.py", names)
        self.assertFalse(any("share/system-coherence" in name for name in names))
        self.assertFalse(any("/skills/" in name for name in names))


if __name__ == "__main__":
    unittest.main()
