"""Tests for stage gate aggregation and submission blocking."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.common import sha256_file
from scripts.gate_check import check_gate
from tests.helpers import make_workflow_fixture


class GateCheckTest(unittest.TestCase):
    def test_review_gate_rejects_p0_and_unaccepted_p1(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="REVIEW", severities=["P0", "P1"])
            result = check_gate(root, "REVIEW")
            self.assertFalse(result["passed"])
            self.assertEqual({i["severity"] for i in result["issues"]}, {"P0", "P1"})

    def test_delivery_rejects_stale_manuscript(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="DELIVERY", stale=["manuscript/paper.pdf"])
            result = check_gate(root, "DELIVERY")
            self.assertFalse(result["passed"])

    def test_clean_review_ledger_passes_the_review_gate(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="REVIEW")
            result = check_gate(root, "REVIEW")
            self.assertTrue(result["passed"])
            self.assertEqual(result["issues"], [])

    def test_accepted_p1_is_tolerated(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="REVIEW")
            ledger_path = root / "review" / "issue-ledger.json"
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            ledger["issues"] = [
                {
                    "root_stage": "COMPUTATION",
                    "root_key": "Q1.weak_validation",
                    "severity": "P1",
                    "locations": ["results"],
                    "message": "验证不足，用户已接受",
                    "status": "accepted",
                }
            ]
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
            state_path = root / ".huawei-modeling" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["artifacts"]["review/issue-ledger.json"]["sha256"] = sha256_file(ledger_path)
            state_path.write_text(json.dumps(state), encoding="utf-8")
            result = check_gate(root, "REVIEW")
            self.assertTrue(result["passed"])

    def test_missing_registered_artifact_blocks_the_gate(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="DELIVERY")
            (root / "delivery" / "submission-manifest.json").unlink()
            result = check_gate(root, "DELIVERY")
            self.assertFalse(result["passed"])
            self.assertIn("missing_artifact", {i["code"] for i in result["issues"]})

    def test_gate_report_is_written_and_machine_readable(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="REVIEW")
            check_gate(root, "REVIEW")
            report_path = root / ".huawei-modeling" / "gates" / "REVIEW.json"
            self.assertTrue(report_path.is_file())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            for key in ("passed", "issues", "checked_hashes", "timestamp"):
                self.assertIn(key, report)
            self.assertIsInstance(report["checked_hashes"], dict)

    def test_unknown_stage_is_rejected(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                check_gate(Path(tmp), "SUBMISSION")


if __name__ == "__main__":
    unittest.main()
