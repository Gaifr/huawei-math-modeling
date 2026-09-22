"""Contract tests for the stage protocol reference files."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STAGE_NAMES = ("intake", "discovery", "formulation", "computation", "evidence")


def stage_text(name: str) -> str:
    return (ROOT / "references" / "stages" / f"{name}.md").read_text(encoding="utf-8")


class StageProtocolTest(unittest.TestCase):
    def test_protocols_define_inputs_outputs_and_stop_conditions(self):
        for name in STAGE_NAMES:
            text = stage_text(name)
            self.assertIn("## Required inputs", text)
            self.assertIn("## Required outputs", text)
            self.assertIn("## Stop conditions", text)

    def test_formulation_separates_model_mechanism_and_solver(self):
        text = stage_text("formulation")
        for term in ("Model identity", "Problem-specific mechanism", "Solver algorithm"):
            self.assertIn(term, text)

    def test_formulation_requires_candidate_decision_table_and_baseline(self):
        text = stage_text("formulation")
        for column in (
            "candidate",
            "model identity",
            "mechanism",
            "solver",
            "inputs",
            "outputs",
            "assumptions",
            "validation",
            "failure conditions",
            "implementation cost",
            "downstream compatibility",
        ):
            self.assertIn(column, text)
        self.assertIn("modeling/model-decision.md", text)
        self.assertIn("baseline", text)

    def test_discovery_requires_traceability_artifacts(self):
        text = stage_text("discovery")
        for artifact in (
            "analysis/sentence-ledger.md",
            "analysis/task-graph.md",
            "analysis/data-audit.md",
            "analysis/ambiguity-register.md",
        ):
            self.assertIn(artifact, text)
        self.assertIn("Mermaid", text)

    def test_discovery_forbids_background_as_numbered_question(self):
        text = stage_text("discovery")
        self.assertIn(
            "Do not treat background paragraphs or submission rules as independent numbered questions",
            text,
        )

    def test_computation_requires_execution_evidence(self):
        text = stage_text("computation")
        for term in (
            "results/result-evidence.json",
            "code/code-manifest.json",
            "run-logs/",
            "baseline",
            "seed",
            "constraint",
            "environment",
        ):
            self.assertIn(term, text)
        self.assertIn("Do not report a value that no successful run produced", text)

    def test_evidence_requires_figure_manifest_fields(self):
        text = stage_text("evidence")
        for term in (
            "figures/figure-manifest.json",
            "claim",
            "source_result_ids",
            "publish",
            "paper_location",
            "caption",
            "generation_command",
        ):
            self.assertIn(term, text)
        self.assertIn("schematic", text)

    def test_evidence_contract_binds_paper_to_computation(self):
        text = (ROOT / "references" / "evidence-contract.md").read_text(encoding="utf-8")
        for term in (
            "Result id",
            "Model identity",
            "sha256",
            "stale",
        ):
            self.assertIn(term, text)
        self.assertIn("Paper prose never overrides computational truth", text)


if __name__ == "__main__":
    unittest.main()
