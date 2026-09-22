"""Small public-API fixtures shared by workflow integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.common import atomic_write_json
from scripts.workflow import CHECKPOINTS, STAGES, Workflow
from scripts.workspace_init import initialize_workspace


_ARTIFACTS = {
    "INTAKE": "inputs/problem/problem.pdf",
    "DISCOVERY": "analysis/sentence-ledger.md",
    "FORMULATION": "modeling/model-decision.md",
    "COMPUTATION": "results/result-evidence.json",
    "EVIDENCE": "figures/figure-manifest.json",
    "MANUSCRIPT": "manuscript/paper.pdf",
    "REVIEW": "review/issue-ledger.json",
    "DELIVERY": "delivery/submission-manifest.json",
}


def _initialize_fixture_workspace(root: Path) -> Workflow:
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise ValueError("fixture root must be absent or empty")
    if root.exists():
        root.rmdir()

    with TemporaryDirectory(dir=root.parent) as source_tmp:
        source_root = Path(source_tmp)
        problem = source_root / "problem.pdf"
        template = source_root / "template.docx"
        rules = source_root / "rules.pdf"
        problem.write_bytes(b"synthetic problem")
        template.write_bytes(b"synthetic template")
        rules.write_bytes(b"synthetic rules")
        initialize_workspace(root, problem, template, rules, "docx", "off")
    return Workflow.load(root)


def _write_artifact(root: Path, stage: str, severities: list[str] | None) -> str:
    relative = _ARTIFACTS[stage]
    target = root / relative
    if stage == "INTAKE":
        return relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if stage == "REVIEW":
        issues = [
            {
                "root_stage": "REVIEW",
                "root_key": f"fixture.{index}",
                "severity": severity,
                "locations": ["synthetic"],
                "message": "synthetic review issue",
            }
            for index, severity in enumerate(severities or [])
        ]
        target.write_text(
            json.dumps({"schema_version": 1, "issues": issues}), encoding="utf-8"
        )
    elif target.suffix == ".json":
        target.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    else:
        target.write_bytes(f"synthetic {stage.lower()} artifact".encode("utf-8"))
    return relative


def make_workflow_fixture(
    root: Path,
    through: str | None = None,
    severities: list[str] | None = None,
    stale: list[str] | None = None,
) -> Workflow:
    """Create a synthetic initialized workflow and progress it via public methods."""
    workspace = Path(root)
    workflow = _initialize_fixture_workspace(workspace)
    if through is not None and through not in STAGES:
        raise ValueError(f"unknown stage: {through}")

    final_index = STAGES.index(through) if through is not None else -1
    for index, stage in enumerate(STAGES[: final_index + 1]):
        if index:
            workflow.begin(stage)
        relative = _write_artifact(workspace, stage, severities)
        workflow.complete(stage, [relative])
        if stage in CHECKPOINTS:
            workflow.request_approval(stage)
            workflow.approve(stage, f"fixture approval for {stage}")

    if stale:
        state = workflow.status()
        state["stale_artifacts"] = list(dict.fromkeys([*state["stale_artifacts"], *stale]))
        atomic_write_json(workspace / ".huawei-modeling" / "state.json", state)
        workflow = Workflow.load(workspace)
    return workflow
