from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SKILLS = {
    "analyze-regression",
    "audit-coherence",
    "discover-capabilities",
    "model-behavior",
    "model-states",
    "plan-remediation",
    "reconstruct-system",
    "revalidate-coherence",
    "system-coherence",
    "trace-implementation",
}


def _npx_command() -> str:
    command = shutil.which("npx") or shutil.which("npx.cmd")
    if command is None:
        raise unittest.SkipTest("npx is not available in PATH")
    return command


class DistributionTests(unittest.TestCase):
    def test_public_skill_collection_is_flat_and_has_no_custom_registry(self):
        skills_root = PROJECT_ROOT / "skills"
        directories = {
            path.name
            for path in skills_root.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        }

        self.assertEqual(directories, PUBLIC_SKILLS)
        self.assertTrue(
            all((skills_root / name / "SKILL.md").is_file() for name in PUBLIC_SKILLS)
        )
        self.assertFalse((skills_root / "manifest.json").exists())

    def test_protocol_resources_live_with_the_orchestrator_skill(self):
        skill_root = PROJECT_ROOT / "skills" / "system-coherence"
        self.assertTrue((skill_root / "references" / "artifact-protocol.md").is_file())
        for name in (
            "artifact-envelope.schema.json",
            "artifact-payloads.schema.json",
            "evaluation-scenarios.schema.json",
        ):
            self.assertTrue((skill_root / "references" / "schemas" / name).is_file())
        self.assertFalse((PROJECT_ROOT / "schemas").exists())
        self.assertFalse((PROJECT_ROOT / "docs" / "artifact-protocol.md").exists())

    def test_public_skills_do_not_require_development_checkout_files(self):
        forbidden_phrases = (
            "python -m coherence",
            "from this checkout",
            "pyproject.toml",
            "skills/manifest.json",
            "docs/artifact-protocol.md",
            "`src/",
            "pip install",
        )

        for path in sorted((PROJECT_ROOT / "skills").glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8").lower()
            for phrase in forbidden_phrases:
                self.assertNotIn(phrase, text, f"{path} depends on {phrase!r}")

    def test_public_skills_use_only_existing_skill_local_references(self):
        expected = {
            "skills/system-coherence/references/artifact-protocol.md",
            "skills/system-coherence/references/schemas/artifact-envelope.schema.json",
            "skills/system-coherence/references/schemas/artifact-payloads.schema.json",
            "skills/system-coherence/references/schemas/evaluation-scenarios.schema.json",
        }
        actual = {
            path.as_posix()
            for path in (PROJECT_ROOT / "skills" / "system-coherence" / "references").rglob("*")
            if path.is_file()
        }
        self.assertEqual(actual, {str(PROJECT_ROOT / item).replace("\\", "/") for item in expected})

    def test_npx_discovery_finds_exactly_the_public_collection(self):
        result = subprocess.run(
            [_npx_command(), "skills", "add", ".", "--list"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env={**os.environ, "NO_COLOR": "1"},
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Found 10 skills", result.stdout + result.stderr)

    def test_clean_npx_install_preserves_all_first_class_skills_and_support(self):
        with tempfile.TemporaryDirectory(prefix="coherence-skills-install-") as directory:
            result = subprocess.run(
                [
                    _npx_command(),
                    "skills",
                    "add",
                    str(PROJECT_ROOT),
                    "--skill",
                    "*",
                    "--agent",
                    "codex",
                    "--copy",
                    "--yes",
                ],
                cwd=directory,
                capture_output=True,
                text=True,
                env={**os.environ, "NO_COLOR": "1"},
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            installed = Path(directory) / ".agents" / "skills"
            names = {
                path.name
                for path in installed.iterdir()
                if path.is_dir() and not path.name.startswith(".")
            }
            self.assertEqual(names, PUBLIC_SKILLS)
            self.assertTrue(
                (installed / "system-coherence" / "references" / "artifact-protocol.md").is_file()
            )

            source_only = (
                "src",
                "scripts",
                "docs",
                "examples",
                "tests",
                "pyproject.toml",
                "README.md",
            )
            for path in source_only:
                self.assertFalse(Path(directory, path).exists(), path)

            local_link_pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")
            for skill_doc in installed.glob("*/SKILL.md"):
                for target in local_link_pattern.findall(
                    skill_doc.read_text(encoding="utf-8")
                ):
                    target = target.split("#", 1)[0]
                    if not target or target.startswith(("http:", "https:", "mailto:")):
                        continue
                    self.assertTrue(
                        (skill_doc.parent / target).is_file(),
                        f"{skill_doc} references missing installed resource {target}",
                    )

            primary = (installed / "system-coherence" / "SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(".coherence/artifacts/", primary)
            for sibling in PUBLIC_SKILLS - {"system-coherence"}:
                self.assertIn(f"`{sibling}`", primary)

    def test_generated_audit_state_is_not_tracked_as_distribution_content(self):
        tracked = subprocess.check_output(
            ["git", "ls-files"], cwd=PROJECT_ROOT, text=True
        ).splitlines()
        generated_prefixes = (
            ".coherence/",
            "build/",
            "dist/",
            "src/system_coherence.egg-info/",
        )
        self.assertFalse(
            any(
                path == prefix.rstrip("/") or path.startswith(prefix)
                for path in tracked
                for prefix in generated_prefixes
            )
        )
        self.assertNotIn("skills-lock.json", tracked)

    def test_optional_python_package_has_no_skill_data_installer(self):
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertNotIn("[tool.setuptools.data-files]", pyproject)
        self.assertFalse((PROJECT_ROOT / "MANIFEST.in").exists())

    def test_readme_describes_standard_skill_installation(self):
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").lower()
        self.assertIn("npx skills add", readme)
        self.assertIn("optional", readme)
        self.assertIn(".coherence", readme)


if __name__ == "__main__":
    unittest.main()
