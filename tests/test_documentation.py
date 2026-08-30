from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_readme_is_a_visual_first_product_landing_page(self):
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        lowered = readme.lower()

        for phrase in (
            "audit the system, not the files",
            "why ordinary review misses the bug",
            "how the suite works",
            "install",
            "durable memory",
            "one coherence gap",
            "proof / verification",
            "explore",
        ):
            self.assertIn(phrase, lowered)

        self.assertIn(
            'npx skills add "https://github.com/MPSMeridiaN/Auditor" --skill \'*\' --copy --yes',
            readme,
        )
        self.assertIn("https://github.com/MPSMeridiaN/Auditor", readme)
        self.assertIn("advanced installation", lowered)
        self.assertIn("optional python", lowered)
        self.assertNotIn("coherence invalidate", lowered)
        self.assertNotIn("coherence release-check", lowered)

        asset_paths = (
            "docs/assets/system-coherence-hero.webp",
            "docs/assets/review-vs-coherence.webp",
            "docs/assets/workflow-10-skills.webp",
            "docs/assets/install-flow.webp",
            "docs/assets/skill-handoffs.webp",
            "docs/assets/coherence-gap.webp",
            "docs/assets/verification-board.webp",
        )
        for relative_path in asset_paths:
            self.assertIn(relative_path, readme)
            self.assertTrue((PROJECT_ROOT / relative_path).is_file())
            self.assertGreater((PROJECT_ROOT / relative_path).stat().st_size, 10_000)
            self.assertLess((PROJECT_ROOT / relative_path).stat().st_size, 500_000)

        actual_image_paths = {
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in (PROJECT_ROOT / "docs/assets").iterdir()
            if path.is_file() and path.suffix.lower() in {".svg", ".png", ".webp"}
        }
        self.assertEqual(actual_image_paths, set(asset_paths))

        self.assertLess(len(readme), 10_000)
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
            "SECURITY.md",
            "CHANGELOG.md",
            "CODE_OF_CONDUCT.md",
            "docs/compatibility.md",
            "docs/case-studies.md",
            "LICENSE",
            ".github/workflows/test.yml",
            ".github/workflows/release.yml",
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
