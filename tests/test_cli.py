from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from coherence.cli import main


class CliTests(unittest.TestCase):
    def test_init_creates_workspace_and_repository_evidence(self):
        with tempfile.TemporaryDirectory(prefix="coherence-cli-") as directory:
            root = Path(directory)

            exit_code = main(["init", str(root)])

            self.assertEqual(exit_code, 0)
            self.assertTrue((root / ".coherence" / "config.json").exists())
            evidence = root / ".coherence" / "artifacts" / "repository-evidence.json"
            self.assertTrue(evidence.exists())
            self.assertEqual(
                json.loads(evidence.read_text(encoding="utf-8"))["artifact_type"],
                "repository-evidence",
            )

    def test_status_json_reports_the_next_route(self):
        with tempfile.TemporaryDirectory(prefix="coherence-cli-") as directory:
            root = Path(directory)
            main(["init", str(root)])
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["status", str(root), "--json"])

            self.assertEqual(exit_code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["workspace"], str(root.resolve()))
            self.assertEqual(payload["artifact_count"], 1)
            self.assertEqual(payload["next"]["skill"], "reconstruct-system")

    def test_write_rejects_invalid_json_without_traceback(self):
        with tempfile.TemporaryDirectory(prefix="coherence-cli-") as directory:
            root = Path(directory)
            main(["init", str(root)])
            source = root / "bad.json"
            source.write_text('{"artifact_type":"system-model"}', encoding="utf-8")
            errors = io.StringIO()

            with mock.patch("sys.stderr", errors):
                exit_code = main(["write", str(source), str(root)])

            self.assertNotEqual(exit_code, 0)
            self.assertIn("invalid artifact", errors.getvalue())

    def test_validate_skills_command_reports_a_clean_skill_tree(self):
        project_root = Path(__file__).resolve().parents[1]
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["validate-skills", str(project_root), "--json"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue())["errors"], [])

    def test_invalidate_without_changes_is_a_no_op(self):
        with tempfile.TemporaryDirectory(prefix="coherence-cli-") as directory:
            root = Path(directory)
            main(["init", str(root)])
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["invalidate", str(root), "--json"])

            self.assertEqual(exit_code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["changed_paths"], [])
            self.assertIsNone(payload["scope"])
            self.assertFalse(
                (root / ".coherence" / "artifacts" / "regression-scope.json").exists()
            )

    def test_status_reports_malformed_artifacts_as_a_repair_route(self):
        with tempfile.TemporaryDirectory(prefix="coherence-cli-") as directory:
            root = Path(directory)
            artifacts = root / ".coherence" / "artifacts"
            artifacts.mkdir(parents=True)
            (artifacts / "repository-evidence.json").write_text(
                "not-json", encoding="utf-8"
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["status", str(root), "--json"])

            self.assertEqual(exit_code, 0)
            payload = json.loads(output.getvalue())
            self.assertIn("repository-evidence", payload["validation_errors"])
            self.assertEqual(payload["next"]["repair_artifact"], "repository-evidence")

    def test_invalidate_reports_an_invalid_git_base(self):
        with tempfile.TemporaryDirectory(prefix="coherence-cli-") as directory:
            root = Path(directory)
            main(["init", str(root)])
            errors = io.StringIO()

            with mock.patch("sys.stderr", errors):
                exit_code = main(["invalidate", str(root), "--base", "missing-base"])

            self.assertEqual(exit_code, 2)
            self.assertIn("could not resolve git diff base", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
