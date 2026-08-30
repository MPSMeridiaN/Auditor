from pathlib import Path
import tempfile
import unittest

from coherence.skills import REQUIRED_SECTIONS, validate_skill_tree


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SkillValidationTests(unittest.TestCase):
    def test_published_skills_have_spec_frontmatter_and_contracts(self):
        errors = validate_skill_tree(PROJECT_ROOT / "skills")

        self.assertEqual(errors, [])

    def test_validator_catches_directory_name_mismatch_and_missing_contract_section(self):
        with tempfile.TemporaryDirectory(prefix="coherence-skills-") as directory:
            root = Path(directory)
            skill = root / "bad-name"
            skill.mkdir()
            skill.joinpath("SKILL.md").write_text(
                "---\nname: different\ndescription: Use when testing a skill.\n---\n\n# Bad\n",
                encoding="utf-8",
            )
            errors = validate_skill_tree(root)

            self.assertTrue(any("name must match directory" in error for error in errors))
            self.assertTrue(
                any(
                    f"missing required section: {section}" in error
                    for error in errors
                    for section in REQUIRED_SECTIONS
                )
            )

    def test_validator_rejects_non_discoverable_description(self):
        with tempfile.TemporaryDirectory(prefix="coherence-skills-") as directory:
            root = Path(directory)
            skill = root / "valid-name"
            skill.mkdir()
            skill.joinpath("SKILL.md").write_text(
                "---\nname: valid-name\ndescription: Helps with audits.\n---\n\n"
                + "\n".join(f"## {section}" for section in REQUIRED_SECTIONS),
                encoding="utf-8",
            )

            errors = validate_skill_tree(root)

            self.assertTrue(
                any("description must start with 'Use when'" in error for error in errors)
            )

    def test_validator_does_not_require_a_custom_registry(self):
        with tempfile.TemporaryDirectory(prefix="coherence-skills-") as directory:
            root = Path(directory)
            root.joinpath("README.md").write_text("skill collection", encoding="utf-8")

            errors = validate_skill_tree(root)

            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
