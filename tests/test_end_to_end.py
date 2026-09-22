import unittest

from scripts.quick_smoke import run_smoke


class EndToEndTest(unittest.TestCase):
    def test_synthetic_workflow_reaches_delivery_without_private_artifacts(self):
        summary = run_smoke()
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["final_stage"], "DELIVERY")
        self.assertEqual(summary["private_path_leaks"], [])


if __name__ == "__main__":
    unittest.main()
