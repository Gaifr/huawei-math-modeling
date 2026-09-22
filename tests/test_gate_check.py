"""Tests for stage gate aggregation and submission blocking."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.common import atomic_write_json, sha256_file
from scripts.gate_check import check_gate
from tests.helpers import make_workflow_fixture


def write_rule_snapshot(root: Path, **overrides) -> Path:
    state = json.loads(
        (root / ".huawei-modeling" / "state.json").read_text(encoding="utf-8")
    )
    rules = state["inputs"]["official_rules"]
    snapshot = {
        "schema_version": 1,
        "competition": "NPGMCM",
        "year": 2026,
        "source_filename": rules["filename"],
        "source_sha256": rules["sha256"],
        "max_pages": 25,
        "toc_max_depth": 3,
        "anonymity_required": True,
        "filename_pattern": None,
    }
    snapshot.update(overrides)
    path = root / ".huawei-modeling" / "rule-snapshot.json"
    atomic_write_json(path, snapshot)
    return path


def write_layout_report(root: Path, page_count: int = 5, **overrides) -> None:
    paper = root / "manuscript" / "paper.pdf"
    report = {
        "schema_version": 1,
        "check": "render_audit",
        "status": "pass",
        "passed": True,
        "strict": False,
        "paper_sha256": sha256_file(paper),
        "page_count": page_count,
        "checked_pages": list(range(1, page_count + 1)),
        "uninspected_pages": [],
        "findings": [],
        "unavailable": [],
    }
    report.update(overrides)
    atomic_write_json(root / "manuscript" / "pdf-layout-report.json", report)


def write_manuscript_check(root: Path, **summary) -> None:
    counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    counts.update(summary)
    atomic_write_json(
        root / "manuscript" / "manuscript-check.json",
        {"schema_version": 1, "check": "manuscript", "summary": counts, "issues": []},
    )


def refresh_artifact_hash(root: Path, relative: str) -> None:
    state_path = root / ".huawei-modeling" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["artifacts"][relative]["sha256"] = sha256_file(root / relative)
    atomic_write_json(state_path, state)


def write_submission_manifest(root: Path, paper: Path) -> None:
    atomic_write_json(
        root / "delivery" / "submission-manifest.json",
        {
            "schema_version": 1,
            "files": [
                {
                    "path": "manuscript/paper.pdf",
                    "sha256": sha256_file(paper),
                    "size_bytes": paper.stat().st_size,
                }
            ],
        },
    )
    refresh_artifact_hash(root, "delivery/submission-manifest.json")


def write_manuscript_source(root: Path, body: str) -> Path:
    source = root / "manuscript" / "source" / "paper.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(body, encoding="utf-8")
    return source


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

    def test_delivery_requires_the_current_rule_snapshot(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="DELIVERY")
            result = check_gate(root, "DELIVERY")
            self.assertFalse(result["passed"])
            self.assertIn("missing_rule_snapshot", {i["code"] for i in result["issues"]})

    def test_manuscript_gate_requires_the_current_rule_snapshot(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="MANUSCRIPT")
            result = check_gate(root, "MANUSCRIPT")
            self.assertIn("missing_rule_snapshot", {i["code"] for i in result["issues"]})

    def test_delivery_rejects_page_limit_exceeded(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="DELIVERY")
            write_rule_snapshot(root, max_pages=25)
            write_layout_report(root, page_count=30)
            result = check_gate(root, "DELIVERY")
            self.assertIn("page_limit_exceeded", {i["code"] for i in result["issues"]})

    def test_delivery_rejects_stale_rule_snapshot(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="DELIVERY")
            write_rule_snapshot(root, source_sha256="0" * 64)
            result = check_gate(root, "DELIVERY")
            self.assertIn("rule_snapshot_stale", {i["code"] for i in result["issues"]})

    def test_delivery_rejects_anonymity_leak(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="DELIVERY")
            write_rule_snapshot(root, anonymity_required=True)
            write_manuscript_source(root, "作者：张三，联系邮箱 zhangsan@example.com\n")
            result = check_gate(root, "DELIVERY")
            self.assertIn("anonymity_leak", {i["code"] for i in result["issues"]})

    def test_delivery_tolerates_allowlisted_anonymity_text(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="DELIVERY")
            write_rule_snapshot(
                root,
                anonymity_required=True,
                anonymity_allowlist=[r"zhangsan@example\.com"],
            )
            write_manuscript_source(root, "示例邮箱 zhangsan@example.com\n")
            result = check_gate(root, "DELIVERY")
            self.assertNotIn("anonymity_leak", {i["code"] for i in result["issues"]})

    def test_delivery_rejects_filename_outside_pattern(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="DELIVERY")
            write_rule_snapshot(root, filename_pattern=r"^[0-9]{11}\.pdf$")
            write_submission_manifest(root, root / "manuscript" / "paper.pdf")
            result = check_gate(root, "DELIVERY")
            self.assertIn("filename_violation", {i["code"] for i in result["issues"]})

    def test_delivery_marks_unknown_page_limit_unverified(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="DELIVERY")
            write_rule_snapshot(root, max_pages=None, toc_max_depth=None)
            write_layout_report(root)
            result = check_gate(root, "DELIVERY")
            self.assertNotIn("page_limit_exceeded", {i["code"] for i in result["issues"]})
            self.assertTrue(any("page_limit" in item for item in result["unverified"]))

    def test_complete_delivery_package_passes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="DELIVERY")
            write_rule_snapshot(root, max_pages=25, toc_max_depth=3)
            write_layout_report(root, page_count=5)
            write_manuscript_check(root)
            write_manuscript_source(root, "# 合成论文\n\n正文内容。\n")
            write_submission_manifest(root, root / "manuscript" / "paper.pdf")
            result = check_gate(root, "DELIVERY")
            self.assertTrue(result["passed"], result["issues"])


if __name__ == "__main__":
    unittest.main()
