"""Tests for root-cause review deduplication and the review ledger."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.review_ledger import (
    load_ledger,
    merge_issues,
    record_review,
    summarize_issues,
)


def issue(root_key: str, severity: str, location: str, **overrides) -> dict:
    payload = {
        "root_stage": "COMPUTATION",
        "root_key": root_key,
        "severity": severity,
        "locations": [location],
        "message": f"message for {root_key}",
    }
    payload.update(overrides)
    return payload


class ReviewLedgerTest(unittest.TestCase):
    def test_same_root_cause_is_not_double_counted(self):
        issues = merge_issues(
            [],
            [
                {
                    "root_stage": "COMPUTATION",
                    "root_key": "Q2.metric_missing",
                    "severity": "P1",
                    "locations": ["abstract"],
                    "message": "摘要指标无证据",
                },
                {
                    "root_stage": "COMPUTATION",
                    "root_key": "Q2.metric_missing",
                    "severity": "P1",
                    "locations": ["results"],
                    "message": "结果指标无法复现",
                },
            ],
        )
        self.assertEqual(len(issues), 1)
        self.assertEqual(set(issues[0]["locations"]), {"abstract", "results"})
        self.assertEqual(summarize_issues(issues)["P1"], 1)

    def test_merge_keeps_highest_severity_and_unions_details(self):
        issues = merge_issues(
            [issue("Q1.weak_validation", "P2", "validation")],
            [
                issue(
                    "Q1.weak_validation",
                    "P0",
                    "abstract",
                    evidence=["results/run-logs/run-1.log"],
                    affected_questions=["Q1"],
                )
            ],
        )
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["severity"], "P0")
        self.assertEqual(set(issues[0]["locations"]), {"abstract", "validation"})
        self.assertIn("results/run-logs/run-1.log", issues[0]["evidence"])
        self.assertEqual(summarize_issues(issues)["P0"], 1)
        self.assertEqual(summarize_issues(issues)["P2"], 0)

    def test_merging_existing_ledger_does_not_inflate_counts(self):
        first = merge_issues([], [issue("Q2.metric_missing", "P1", "abstract")])
        second = merge_issues(first, [issue("Q2.metric_missing", "P1", "results")])
        self.assertEqual(len(second), 1)
        summary = summarize_issues(second)
        self.assertEqual(summary["P1"], 1)
        self.assertEqual(summary["total"], 1)

    def test_record_review_requires_a_consistent_paper_hash(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_review(root, [issue("Q1.weak_validation", "P1", "abstract")], "a" * 64)
            ledger = load_ledger(root)
            self.assertEqual(ledger["paper_sha256"], "a" * 64)
            with self.assertRaises(ValueError):
                record_review(root, [issue("Q1.other", "P1", "abstract")], "b" * 64)

    def test_record_review_rejects_invalid_paper_hash(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                record_review(root, [], "not-a-hash")

    def test_second_review_round_accumulates_on_the_same_paper(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_review(root, [issue("Q1.a", "P1", "abstract")], "c" * 64)
            ledger = record_review(root, [issue("Q1.b", "P2", "results")], "c" * 64)
            self.assertEqual(len(ledger["issues"]), 2)
            self.assertEqual(ledger["revision_round"], 2)

    def test_summary_reports_unresolved_blocking_issues(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = record_review(
                root,
                [
                    issue("Q1.a", "P0", "abstract"),
                    issue("Q1.b", "P1", "results", status="accepted"),
                ],
                "d" * 64,
            )
            summary = summarize_issues(ledger["issues"])
            self.assertEqual(summary["P0"], 1)
            self.assertEqual(summary["P1"], 1)
            self.assertEqual(summary["open_P1"], 0)
            self.assertTrue(summary["blocking"])


if __name__ == "__main__":
    unittest.main()
