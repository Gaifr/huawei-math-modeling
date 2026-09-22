"""Checkpointed workflow state machine for Huawei Cup contest workspaces."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Iterable

try:  # Support both package imports and direct CLI execution.
    from .common import append_event, atomic_write_json, sha256_file
except ImportError:  # pragma: no cover - exercised by direct CLI execution
    from common import append_event, atomic_write_json, sha256_file


STAGES = (
    "INTAKE",
    "DISCOVERY",
    "FORMULATION",
    "COMPUTATION",
    "EVIDENCE",
    "MANUSCRIPT",
    "REVIEW",
    "DELIVERY",
)
CHECKPOINTS = {
    "DISCOVERY": "interpretation",
    "FORMULATION": "model_selection",
    "COMPUTATION": "result_trust",
    "REVIEW": "final_draft",
}


class TransitionError(RuntimeError):
    """Raised when a workflow transition would violate the state contract."""


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Workflow:
    """Load, validate, and persist one initialized contest workflow."""

    def __init__(
        self, workspace: Path, state: dict[str, Any], approvals: dict[str, Any]
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self._state = state
        self._approvals = approvals

    @classmethod
    def load(cls, workspace: Path) -> "Workflow":
        root = Path(workspace).expanduser().resolve()
        control = root / ".huawei-modeling"
        try:
            state = json.loads((control / "state.json").read_text(encoding="utf-8"))
            approvals = json.loads(
                (control / "approvals.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Cannot load initialized workflow at {root}: {error}") from error
        if not isinstance(state, dict) or not isinstance(approvals, dict):
            raise ValueError("Workflow state and approvals must be JSON objects")
        stage_state = state.get("stages")
        if not isinstance(stage_state, dict) or set(stage_state) != set(STAGES):
            raise ValueError("Workflow state does not contain the canonical eight stages")
        return cls(root, state, approvals)

    @property
    def _state_path(self) -> Path:
        return self.workspace / ".huawei-modeling" / "state.json"

    @property
    def _approvals_path(self) -> Path:
        return self.workspace / ".huawei-modeling" / "approvals.json"

    def _require_stage(self, stage: str) -> int:
        if stage not in STAGES:
            raise TransitionError(f"Unknown stage: {stage}")
        return STAGES.index(stage)

    def _artifact_path(self, relative: str) -> Path:
        candidate = Path(relative)
        if candidate.is_absolute() or not relative or relative != candidate.as_posix():
            raise TransitionError(f"Artifact path must be a normalized workspace path: {relative}")
        resolved = (self.workspace / candidate).resolve()
        try:
            resolved.relative_to(self.workspace)
        except ValueError as error:
            raise TransitionError(f"Artifact escapes workspace: {relative}") from error
        return resolved

    def _stage_artifact_hashes(self, stage: str) -> dict[str, str]:
        hashes: dict[str, str] = {}
        artifacts = self._state.get("artifacts", {})
        if not isinstance(artifacts, dict):
            raise TransitionError("Workflow artifact registry is invalid")
        for relative, record in artifacts.items():
            if not isinstance(record, dict) or record.get("stage") != stage:
                continue
            path = self._artifact_path(relative)
            if not path.is_file():
                raise TransitionError(f"Registered artifact is missing: {relative}")
            current_hash = sha256_file(path)
            if current_hash != record.get("sha256"):
                raise TransitionError(
                    f"Registered artifact changed; use rework before continuing: {relative}"
                )
            hashes[relative] = current_hash
        return hashes

    def _require_valid_approval(self, stage: str) -> None:
        approval = self._approvals.get(stage)
        if not isinstance(approval, dict):
            raise TransitionError(f"Human approval is required after {stage}")
        if approval.get("checkpoint") != CHECKPOINTS[stage]:
            raise TransitionError(f"Approval checkpoint does not match {stage}")
        if approval.get("decision") != "approve":
            raise TransitionError(f"Human approval for {stage} is not active")
        current_hashes = self._stage_artifact_hashes(stage)
        if approval.get("artifact_hashes") != current_hashes:
            raise TransitionError(f"Artifacts changed after approval for {stage}")

    def begin(self, stage: str) -> dict[str, Any]:
        index = self._require_stage(stage)
        if index == 0:
            raise TransitionError("INTAKE is activated by workspace initialization")
        previous = STAGES[index - 1]
        if self._state.get("active_stage") != previous:
            raise TransitionError(f"Cannot skip directly to {stage}; expected {previous}")
        if self._state["stages"][previous].get("status") != "complete":
            raise TransitionError(f"Previous stage is not complete: {previous}")
        if self._state["stages"][stage].get("status") != "pending":
            raise TransitionError(f"Stage is not pending: {stage}")
        self._stage_artifact_hashes(previous)
        for checkpoint_stage in CHECKPOINTS:
            if STAGES.index(checkpoint_stage) < index:
                self._require_valid_approval(checkpoint_stage)

        self._state["active_stage"] = stage
        self._state["stages"][stage]["status"] = "active"
        atomic_write_json(self._state_path, self._state)
        append_event(
            self.workspace,
            "stage_begun",
            {"stage": stage, "previous_stage": previous},
        )
        return self.status()

    def complete(self, stage: str, artifacts: Iterable[str]) -> dict[str, Any]:
        self._require_stage(stage)
        if self._state.get("active_stage") != stage:
            raise TransitionError(f"Only the active stage can be completed: {stage}")
        if self._state["stages"][stage].get("status") != "active":
            raise TransitionError(f"Stage is not active: {stage}")
        if isinstance(artifacts, (str, bytes)):
            raise TransitionError("Artifacts must be a collection of workspace paths")

        declared: dict[str, str] = {}
        for raw_relative in artifacts:
            if not isinstance(raw_relative, str):
                raise TransitionError("Artifact paths must be strings")
            relative = Path(raw_relative).as_posix()
            path = self._artifact_path(relative)
            if not path.is_file():
                raise TransitionError(f"Declared artifact is missing: {relative}")
            declared[relative] = sha256_file(path)

        for relative, digest in declared.items():
            self._state["artifacts"][relative] = {"sha256": digest, "stage": stage}
        stale = self._state.get("stale_artifacts", [])
        self._state["stale_artifacts"] = [
            relative for relative in stale if relative not in declared
        ]
        self._state["stages"][stage]["status"] = "complete"
        atomic_write_json(self._state_path, self._state)
        append_event(
            self.workspace,
            "stage_completed",
            {"stage": stage, "artifact_hashes": declared},
        )
        return self.status()

    def request_approval(self, stage: str) -> dict[str, Any]:
        self._require_stage(stage)
        if stage not in CHECKPOINTS:
            raise TransitionError(f"Stage has no human checkpoint: {stage}")
        if self._state.get("active_stage") != stage:
            raise TransitionError(f"Only the active stage can request approval: {stage}")
        if self._state["stages"][stage].get("status") != "complete":
            raise TransitionError(f"Stage must be complete before approval: {stage}")
        artifact_hashes = self._stage_artifact_hashes(stage)
        self._state["stages"][stage]["status"] = "awaiting_approval"
        atomic_write_json(self._state_path, self._state)
        append_event(
            self.workspace,
            "approval_requested",
            {
                "stage": stage,
                "checkpoint": CHECKPOINTS[stage],
                "artifact_hashes": artifact_hashes,
            },
        )
        return self.status()

    def approve(self, stage: str, note: str) -> dict[str, Any]:
        self._require_stage(stage)
        if stage not in CHECKPOINTS:
            raise TransitionError(f"Stage has no human checkpoint: {stage}")
        if self._state.get("active_stage") != stage:
            raise TransitionError(f"Only the active stage can be approved: {stage}")
        if self._state["stages"][stage].get("status") != "awaiting_approval":
            raise TransitionError(f"Approval was not requested for {stage}")
        cleaned_note = str(note).strip()
        if not cleaned_note:
            raise TransitionError("Approval note must not be empty")

        approval = {
            "checkpoint": CHECKPOINTS[stage],
            "decision": "approve",
            "note": cleaned_note,
            "timestamp": _timestamp(),
            "artifact_hashes": self._stage_artifact_hashes(stage),
        }
        self._approvals[stage] = approval
        self._state["stages"][stage]["status"] = "complete"
        atomic_write_json(self._approvals_path, self._approvals)
        atomic_write_json(self._state_path, self._state)
        append_event(
            self.workspace,
            "checkpoint_approved",
            {"stage": stage, **approval},
        )
        return deepcopy(approval)

    def rework(self, stage: str, reason: str) -> dict[str, Any]:
        target_index = self._require_stage(stage)
        active_stage = self._state.get("active_stage")
        active_index = self._require_stage(active_stage)
        if target_index > active_index:
            raise TransitionError(f"Cannot rework a stage not yet reached: {stage}")
        cleaned_reason = str(reason).strip()
        if not cleaned_reason:
            raise TransitionError("Rework reason must not be empty")

        downstream_artifacts = [
            relative
            for relative, record in self._state.get("artifacts", {}).items()
            if isinstance(record, dict)
            and STAGES.index(record.get("stage")) > target_index
        ]
        self._state["stale_artifacts"] = list(
            dict.fromkeys([*self._state.get("stale_artifacts", []), *downstream_artifacts])
        )
        self._state["active_stage"] = stage
        self._state["stages"][stage]["status"] = "active"
        for later_stage in STAGES[target_index + 1 :]:
            self._state["stages"][later_stage]["status"] = "pending"

        invalidated: list[str] = []
        invalidated_at = _timestamp()
        for checkpoint_stage in CHECKPOINTS:
            if STAGES.index(checkpoint_stage) < target_index:
                continue
            approval = self._approvals.get(checkpoint_stage)
            if not isinstance(approval, dict) or approval.get("decision") != "approve":
                continue
            approval["decision"] = "invalidated"
            approval["invalidated_timestamp"] = invalidated_at
            approval["invalidation_reason"] = cleaned_reason
            invalidated.append(checkpoint_stage)

        atomic_write_json(self._approvals_path, self._approvals)
        atomic_write_json(self._state_path, self._state)
        append_event(
            self.workspace,
            "stage_rework_requested",
            {
                "stage": stage,
                "reason": cleaned_reason,
                "stale_artifacts": downstream_artifacts,
                "invalidated_approvals": invalidated,
            },
        )
        return self.status()

    def status(self) -> dict[str, Any]:
        return deepcopy(self._state)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a checkpointed modeling workflow.")
    parser.add_argument("--workspace", type=Path, required=True, help="contest workspace")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("status", help="show current workflow state")
    begin = commands.add_parser("begin", help="begin the next stage")
    begin.add_argument("stage", choices=STAGES)
    complete = commands.add_parser("complete", help="complete the active stage")
    complete.add_argument("stage", choices=STAGES)
    complete.add_argument("artifacts", nargs="+", help="workspace-relative artifact paths")
    request = commands.add_parser(
        "request-approval", help="pause at a required human checkpoint"
    )
    request.add_argument("stage", choices=tuple(CHECKPOINTS))
    approve = commands.add_parser("approve", help="record an explicit human approval")
    approve.add_argument("stage", choices=tuple(CHECKPOINTS))
    approve.add_argument("--note", required=True, help="human decision note")
    rework = commands.add_parser("rework", help="roll back to a root-cause stage")
    rework.add_argument("stage", choices=STAGES)
    rework.add_argument("--reason", required=True, help="reason for rollback")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        workflow = Workflow.load(args.workspace)
        if args.command == "status":
            result = workflow.status()
        elif args.command == "begin":
            result = workflow.begin(args.stage)
        elif args.command == "complete":
            result = workflow.complete(args.stage, args.artifacts)
        elif args.command == "request-approval":
            result = workflow.request_approval(args.stage)
        elif args.command == "approve":
            result = workflow.approve(args.stage, args.note)
        elif args.command == "rework":
            result = workflow.rework(args.stage, args.reason)
        else:  # pragma: no cover - argparse enforces command choices
            raise AssertionError(f"Unhandled command: {args.command}")
    except (OSError, ValueError, TransitionError) as error:
        print(f"workflow command failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
