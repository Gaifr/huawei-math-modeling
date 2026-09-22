"""Validation tests for the result-evidence contract."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.common import sha256_file
from scripts.evidence_check import validate_evidence


def write_evidence(root: Path, evidence: dict, manifest: dict | None = None) -> None:
    (root / "results").mkdir(parents=True, exist_ok=True)
    (root / "code").mkdir(parents=True, exist_ok=True)
    (root / "results" / "result-evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False), encoding="utf-8"
    )
    (root / "code" / "code-manifest.json").write_text(
        json.dumps(manifest or {"schema_version": 1, "files": []}), encoding="utf-8"
    )


def codes_for(root: Path) -> set[str]:
    return {item["code"] for item in validate_evidence(root)}


def well_formed_result(**overrides) -> dict:
    result = {
        "id": "Q1.objective",
        "model_identity": "linear programming",
        "mechanism": "capacity constraints",
        "solver_algorithm": "HiGHS",
        "value": 12.5,
        "display_value": "12.50",
        "precision": "2 decimal places",
        "source_files": [{"path": "code/q1.py", "sha256": "0" * 64}],
        "run_command": "python code/q1.py",
        "environment": {"python": "3.13"},
    }
    result.update(overrides)
    return result


class EvidenceCheckTest(unittest.TestCase):
    def test_rejects_solver_used_as_model_identity(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "results").mkdir()
            (root / "code").mkdir()
            (root / "results" / "result-evidence.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "results": [
                            {
                                "id": "Q1.objective",
                                "model_identity": "Gurobi",
                                "mechanism": "capacity constraints",
                                "solver_algorithm": "Gurobi",
                                "value": 12.5,
                                "source_files": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / "code" / "code-manifest.json").write_text(
                json.dumps({"schema_version": 1, "files": []}), encoding="utf-8"
            )
            issues = validate_evidence(root)
            self.assertIn("solver_as_model", {item["code"] for item in issues})

    def test_detects_missing_or_mismatched_source_hash(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "results").mkdir()
            (root / "code").mkdir()
            source = root / "code" / "q1.py"
            source.write_text("print(1)\n", encoding="utf-8")
            (root / "results" / "result-evidence.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "results": [
                            {
                                "id": "Q1.value",
                                "model_identity": "linear programming",
                                "mechanism": "capacity constraints",
                                "solver_algorithm": "HiGHS",
                                "value": 1,
                                "source_files": [
                                    {"path": "code/q1.py", "sha256": "0" * 64}
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / "code" / "code-manifest.json").write_text(
                json.dumps({"schema_version": 1, "files": []}), encoding="utf-8"
            )
            codes = {item["code"] for item in validate_evidence(root)}
            self.assertIn("source_hash_mismatch", codes)

    def test_fully_bound_result_passes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "code" / "q1.py"
            (root / "code").mkdir(parents=True)
            source.write_text("print(1)\n", encoding="utf-8")
            result = well_formed_result(
                source_files=[{"path": "code/q1.py", "sha256": sha256_file(source)}]
            )
            write_evidence(root, {"schema_version": 1, "results": [result]})
            self.assertEqual(validate_evidence(root), [])

    def test_reports_every_finding_with_required_fields(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "code").mkdir(parents=True)
            (root / "code" / "q1.py").write_text("print(1)\n", encoding="utf-8")
            write_evidence(
                root,
                {
                    "schema_version": 1,
                    "results": [
                        well_formed_result(source_files=[{"path": "code/q1.py", "sha256": "0" * 64}]),
                        well_formed_result(source_files=[{"path": "code/q1.py", "sha256": "0" * 64}]),
                        well_formed_result(
                            id="Q2.value",
                            source_files=[{"path": "code/absent.py", "sha256": "0" * 64}],
                        ),
                    ],
                },
            )
            issues = validate_evidence(root)
            codes = {item["code"] for item in issues}
            self.assertIn("duplicate_result_id", codes)
            self.assertIn("source_file_missing", codes)
            self.assertIn("source_hash_mismatch", codes)
            for issue in issues:
                self.assertEqual(
                    {"issue_id", "severity", "code", "message", "paths"} - set(issue), set()
                )
                self.assertIn(issue["severity"], {"P0", "P1", "P2", "P3"})

    def test_rejects_missing_run_record_and_precision_conflict(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "code" / "q1.py"
            (root / "code").mkdir(parents=True)
            source.write_text("print(1)\n", encoding="utf-8")
            result = well_formed_result(
                source_files=[{"path": "code/q1.py", "sha256": sha256_file(source)}],
                run_command="",
                environment={},
                display_value="12.5",
            )
            write_evidence(root, {"schema_version": 1, "results": [result]})
            codes = codes_for(root)
            self.assertIn("missing_run_record", codes)
            self.assertIn("precision_mismatch", codes)

    def test_rejects_unstable_identifier(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "code" / "q1.py"
            (root / "code").mkdir(parents=True)
            source.write_text("print(1)\n", encoding="utf-8")
            result = well_formed_result(
                id="Q1 objective draft 2024-09-22",
                source_files=[{"path": "code/q1.py", "sha256": sha256_file(source)}],
            )
            write_evidence(root, {"schema_version": 1, "results": [result]})
            self.assertIn("unstable_result_id", codes_for(root))

    def test_rejects_citation_to_missing_figure_and_location(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "code" / "q1.py"
            (root / "code").mkdir(parents=True)
            source.write_text("print(1)\n", encoding="utf-8")
            result = well_formed_result(
                source_files=[{"path": "code/q1.py", "sha256": sha256_file(source)}],
                citations=[
                    {"figure": "figures/data/missing.png"},
                    {"paper_location": "manuscript/source/paper.md#q1"},
                ],
            )
            write_evidence(root, {"schema_version": 1, "results": [result]})
            self.assertIn("missing_citation_target", codes_for(root))

    def test_rejects_evidence_built_from_stale_artifacts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "code" / "q1.py"
            (root / "code").mkdir(parents=True)
            source.write_text("print(1)\n", encoding="utf-8")
            result = well_formed_result(
                source_files=[{"path": "code/q1.py", "sha256": sha256_file(source)}]
            )
            write_evidence(root, {"schema_version": 1, "results": [result]})
            (root / ".huawei-modeling").mkdir()
            (root / ".huawei-modeling" / "state.json").write_text(
                json.dumps({"stale_artifacts": ["code/q1.py"]}), encoding="utf-8"
            )
            self.assertIn("stale_evidence", codes_for(root))


if __name__ == "__main__":
    unittest.main()
