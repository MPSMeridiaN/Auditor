import unittest

from coherence.models import ARTIFACT_STATUSES, stable_id, utc_now


class ModelTests(unittest.TestCase):
    def test_stable_id_is_deterministic_and_prefixed(self):
        first = stable_id("cap", "delete a file")
        second = stable_id("cap", "delete a file")

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("cap-"))
        self.assertNotEqual(first, stable_id("cap", "rename a file"))

    def test_utc_now_is_machine_sortable_and_statuses_are_explicit(self):
        timestamp = utc_now()

        self.assertTrue(timestamp.endswith("Z"))
        self.assertIn("T", timestamp)
        self.assertEqual(
            set(ARTIFACT_STATUSES),
            {"complete", "partial", "blocked", "stale", "invalid"},
        )


if __name__ == "__main__":
    unittest.main()
