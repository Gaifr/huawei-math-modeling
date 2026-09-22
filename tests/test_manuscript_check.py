"""Consistency tests for the evidence-bound manuscript routes."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.common import atomic_write_json, sha256_file
from scripts.manuscript_check import check_manuscript


def codes_for(workspace: Path, route: str = "docx") -> set[str]:
    return {item["code"] for item in check_manuscript(workspace, route)}


def make_workspace(
    root: Path,
    body: str,
    *,
    results: list | None = None,
    route: str = "docx",
    ai_disclosure: str = "off",
    figures: list | None = None,
    template_sha256: str | None = None,
) -> None:
    (root / "manuscript" / "source").mkdir(parents=True, exist_ok=True)
    (root / "results").mkdir(parents=True, exist_ok=True)
    (root / "figures").mkdir(parents=True, exist_ok=True)
    (root / "inputs" / "official-template").mkdir(parents=True, exist_ok=True)
    (root / ".huawei-modeling").mkdir(parents=True, exist_ok=True)
    (root / "manuscript" / "source" / "paper.md").write_text(body, encoding="utf-8")
    atomic_write_json(
        root / "results" / "result-evidence.json",
        {"schema_version": 1, "results": results or []},
    )
    atomic_write_json(
        root / "figures" / "figure-manifest.json",
        {"schema_version": 1, "figures": figures or []},
    )
    template = root / "inputs" / "official-template" / "template.docx"
    template.write_bytes(b"official template")
    atomic_write_json(
        root / ".huawei-modeling" / "state.json",
        {
            "schema_version": 1,
            "active_stage": "MANUSCRIPT",
            "route": route,
            "ai_disclosure": ai_disclosure,
            "stages": {},
            "inputs": {
                "official_template": {
                    "filename": "template.docx",
                    "workspace_path": "inputs/official-template/template.docx",
                    "sha256": template_sha256 or sha256_file(template),
                    "size_bytes": template.stat().st_size,
                }
            },
            "artifacts": {},
            "stale_artifacts": [],
            "blocking_issues": [],
        },
    )


class ManuscriptCheckTest(unittest.TestCase):
    def test_flags_number_not_backed_by_evidence(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "results").mkdir()
            (root / "manuscript" / "source").mkdir(parents=True)
            (root / "results" / "result-evidence.json").write_text(
                json.dumps({"schema_version": 1, "results": []}), encoding="utf-8"
            )
            (root / "manuscript" / "source" / "paper.md").write_text(
                "最优目标值为 123.456。", encoding="utf-8"
            )
            codes = {i["code"] for i in check_manuscript(root, "docx")}
            self.assertIn("untraced_numeric_claim", codes)

    def test_accepts_number_that_matches_display_value(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workspace(
                root,
                "最优目标值为 123.46。",
                results=[
                    {
                        "id": "Q1.objective",
                        "model_identity": "linear programming",
                        "mechanism": "capacity constraints",
                        "solver_algorithm": "HiGHS",
                        "value": 123.456789,
                        "display_value": "123.46",
                    }
                ],
            )
            self.assertNotIn("untraced_numeric_claim", codes_for(root))

    def test_accepts_years_and_reference_numbers(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workspace(root, "2026 年第 3 章引用文献 [12] 与式 (7)，见图 2。")
            self.assertNotIn("untraced_numeric_claim", codes_for(root))

    def test_flags_workflow_leakage(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workspace(root, "按 workflow.py 的 P0 规则对 FORMULATION 执行 rework。")
            self.assertIn("workflow_leakage", codes_for(root))

    def test_flags_placeholder_text(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workspace(root, "本节结论：TODO")
            self.assertIn("placeholder_text", codes_for(root))

    def test_flags_missing_and_unreferenced_figures(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workspace(
                root,
                "见图 ![结果](figures/data/q1.png)",
                figures=[
                    {"id": "f1", "path": "figures/data/q1.png", "publish": True},
                    {"id": "f2", "path": "figures/data/q2.png", "publish": True},
                ],
            )
            codes = codes_for(root)
            self.assertIn("missing_figure", codes)
            self.assertIn("unreferenced_figure", codes)

    def test_flags_ai_disclosure_mismatch(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workspace(root, "本文全部工作由人工完成。", ai_disclosure="required")
            self.assertIn("ai_disclosure_mismatch", codes_for(root))

    def test_flags_model_name_mismatch(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workspace(
                root,
                "本文使用启发式方法求解。",
                results=[
                    {
                        "id": "Q1.objective",
                        "model_identity": "linear programming",
                        "mechanism": "capacity constraints",
                        "solver_algorithm": "HiGHS",
                        "value": 1,
                        "display_value": "1.0",
                    }
                ],
            )
            self.assertIn("model_name_mismatch", codes_for(root))

    def test_flags_template_hash_mismatch(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workspace(root, "正文内容。", template_sha256="0" * 64)
            self.assertIn("template_hash_mismatch", codes_for(root))

    def test_missing_source_is_a_hard_failure(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".huawei-modeling").mkdir(parents=True)
            issues = check_manuscript(root, "latex")
            self.assertIn("missing_manuscript_source", {i["code"] for i in issues})
            self.assertTrue(
                any(i["severity"] == "P0" for i in issues if i["code"] == "missing_manuscript_source")
            )


if __name__ == "__main__":
    unittest.main()
