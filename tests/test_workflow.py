import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.workflow import CHECKPOINTS, STAGES, TransitionError, Workflow
from tests.helpers import make_workflow_fixture


class WorkflowTest(unittest.TestCase):
    def test_cannot_skip_stage_or_approval(self):
        """Removing ordered transitions or a checkpoint guard would make this fail."""
        with TemporaryDirectory() as tmp:
            workflow = make_workflow_fixture(Path(tmp))
            with self.assertRaises(TransitionError):
                workflow.begin("FORMULATION")
            workflow.complete("INTAKE", ["inputs/problem/problem.pdf"])
            workflow.begin("DISCOVERY")
            artifact = Path(tmp) / "analysis" / "sentence-ledger.md"
            artifact.write_text("interpreted", encoding="utf-8")
            workflow.complete("DISCOVERY", ["analysis/sentence-ledger.md"])
            with self.assertRaises(TransitionError):
                workflow.begin("FORMULATION")

    def test_each_required_checkpoint_blocks_its_downstream_stage(self):
        """Dropping any of the four human checkpoints would make this fail."""
        self.assertEqual(
            CHECKPOINTS,
            {
                "DISCOVERY": "interpretation",
                "FORMULATION": "model_selection",
                "COMPUTATION": "result_trust",
                "REVIEW": "final_draft",
            },
        )
        self.assertEqual(
            STAGES,
            (
                "INTAKE",
                "DISCOVERY",
                "FORMULATION",
                "COMPUTATION",
                "EVIDENCE",
                "MANUSCRIPT",
                "REVIEW",
                "DELIVERY",
            ),
        )
        downstream = {
            "DISCOVERY": "FORMULATION",
            "FORMULATION": "COMPUTATION",
            "COMPUTATION": "EVIDENCE",
            "REVIEW": "DELIVERY",
        }
        for checkpoint_stage, next_stage in downstream.items():
            with self.subTest(stage=checkpoint_stage), TemporaryDirectory() as tmp:
                workflow = make_workflow_fixture(Path(tmp), through=checkpoint_stage)
                approvals_path = Path(tmp) / ".huawei-modeling" / "approvals.json"
                approvals = json.loads(approvals_path.read_text(encoding="utf-8"))
                approvals.pop(checkpoint_stage)
                approvals_path.write_text(json.dumps(approvals), encoding="utf-8")
                workflow = Workflow.load(Path(tmp))
                with self.assertRaises(TransitionError):
                    workflow.begin(next_stage)

    def test_approval_hash_change_blocks_progress(self):
        """Accepting edited artifacts under an old approval would make this fail."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = make_workflow_fixture(root, through="DISCOVERY")
            (root / "analysis" / "sentence-ledger.md").write_text(
                "changed after approval", encoding="utf-8"
            )

            with self.assertRaises(TransitionError):
                workflow.begin("FORMULATION")

    def test_non_checkpoint_artifact_change_requires_rework(self):
        """Silently accepting an edited completed artifact would make this fail."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = make_workflow_fixture(root, through="EVIDENCE")
            (root / "figures" / "figure-manifest.json").write_text(
                '{"schema_version": 1, "changed": true}', encoding="utf-8"
            )

            with self.assertRaises(TransitionError):
                workflow.begin("MANUSCRIPT")

    def test_completion_hashes_artifacts_and_load_recovers_state(self):
        """Omitting hashes or persisting only in memory would make this fail."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = make_workflow_fixture(root)
            workflow.complete("INTAKE", ["inputs/problem/problem.pdf"])

            recovered = Workflow.load(root)
            artifact = recovered.status()["artifacts"]["inputs/problem/problem.pdf"]
            self.assertEqual(artifact["stage"], "INTAKE")
            self.assertEqual(len(artifact["sha256"]), 64)
            self.assertEqual(recovered.status()["stages"]["INTAKE"]["status"], "complete")

    def test_rework_marks_downstream_artifacts_stale_and_invalidates_approvals(self):
        """A silent rollback that preserves downstream truth would make this fail."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = make_workflow_fixture(root, through="MANUSCRIPT")
            workflow.rework("FORMULATION", "model changed")
            status = workflow.status()
            self.assertEqual(status["active_stage"], "FORMULATION")
            self.assertEqual(status["stages"]["FORMULATION"]["status"], "active")
            self.assertEqual(status["stages"]["MANUSCRIPT"]["status"], "pending")
            self.assertIn("manuscript/paper.pdf", status["stale_artifacts"])

            approvals = json.loads(
                (root / ".huawei-modeling" / "approvals.json").read_text(encoding="utf-8")
            )
            self.assertEqual(approvals["FORMULATION"]["decision"], "invalidated")
            self.assertEqual(approvals["COMPUTATION"]["decision"], "invalidated")
            events = [
                json.loads(line)
                for line in (root / ".huawei-modeling" / "events.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(events[-1]["event"], "stage_rework_requested")
            self.assertIn("FORMULATION", events[-1]["details"]["invalidated_approvals"])


if __name__ == "__main__":
    unittest.main()
