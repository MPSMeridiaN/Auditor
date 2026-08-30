from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_readme_contains_operational_quickstart_and_limits(self):
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

        for phrase in (
            "coherence init",
            "coherence route",
            ".coherence",
            "coherence invalidate",
            "limitations",
            "coherence eval",
        ):
            self.assertIn(phrase, readme.lower())

    def test_readme_has_the_public_story_and_local_visual_assets(self):
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        lowered = readme.lower()

        for phrase in (
            "most coding agents inspect files",
            "install in 30 seconds",
            "first invocation",
            "what happens when you run it",
            "why not just tests",
            "artifacts are the shared memory",
            "coherence gap",
            "resume",
            "revalidate",
        ):
            self.assertIn(phrase, lowered)

        self.assertIn(
            'npx skills add "<repository-url>" --skill \'*\' --copy --yes',
            readme,
        )
        self.assertIn("public github url", lowered)
        self.assertIn("install with your ai agent", lowered)

        for relative_path in (
            "docs/assets/system-coherence-hero.webp",
            "docs/assets/skill-handoffs.svg",
        ):
            self.assertIn(relative_path, readme)
            self.assertTrue((PROJECT_ROOT / relative_path).is_file())

        self.assertLess(
            (PROJECT_ROOT / "docs/assets/system-coherence-hero.webp").stat().st_size,
            500_000,
        )
        ET.parse(PROJECT_ROOT / "docs/assets/skill-handoffs.svg")
        self.assertNotIn("<owner>/<repo>", readme)

    def test_public_docs_and_ci_are_present(self):
        required = (
            "docs/architecture.md",
            "docs/methodology.md",
            "docs/getting-started.md",
            "skills/system-coherence/references/artifact-protocol.md",
            "docs/extension-guide.md",
            "docs/evaluation.md",
            "AGENTS.md",
            "CONTRIBUTING.md",
            "LICENSE",
            ".github/workflows/test.yml",
        )
        missing = [path for path in required if not (PROJECT_ROOT / path).exists()]

        self.assertEqual(missing, [])

    def test_development_audits_and_research_are_not_public_documentation(self):
        removed = (
            "docs/distribution-audit.md",
            "docs/runtime-packaging-audit.md",
            "docs/research.md",
            "docs/superpowers",
        )

        self.assertTrue(all(not (PROJECT_ROOT / path).exists() for path in removed))

        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").lower()
        for path in removed[:3]:
            self.assertNotIn(path, readme)

    def test_ci_fails_when_the_release_route_is_not_complete(self):
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "test.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn('payload.get("stage") != "complete"', workflow)


if __name__ == "__main__":
    unittest.main()
