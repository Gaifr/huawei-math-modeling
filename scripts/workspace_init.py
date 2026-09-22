"""Create an isolated, evidence-tracked Huawei Cup contest workspace."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

try:  # Support both ``python scripts/workspace_init.py`` and package imports.
    from .common import append_event, atomic_write_json, sha256_file
except ImportError:  # pragma: no cover - exercised only by direct CLI execution
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
ROUTES = ("latex", "docx")
AI_DISCLOSURE_OPTIONS = ("required", "off")

RUNTIME_DIRECTORIES = (
    "inputs/problem",
    "inputs/attachments",
    "inputs/official-template",
    "inputs/official-rules",
    "analysis",
    "modeling",
    "code/problems",
    "code/tests",
    "results/metrics",
    "results/tables",
    "results/run-logs",
    "figures/data",
    "figures/schematics",
    "manuscript/source",
    "review/revision-rounds",
    "delivery",
    ".huawei-modeling",
)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _resolve_source(path: Path, label: str) -> Path:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"{label} must be an existing regular file: {source}")
    return source


def _input_metadata(workspace: Path, destination: Path, source: Path) -> dict[str, Any]:
    return {
        "filename": source.name,
        "workspace_path": destination.relative_to(workspace).as_posix(),
        "sha256": sha256_file(destination),
        "size_bytes": destination.stat().st_size,
    }


def initialize_workspace(
    workspace: Path,
    problem: Path,
    template: Path,
    rules: Path,
    route: str,
    ai_disclosure: str,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Create a contest workspace, register immutable source metadata, and return state."""
    skill_repository = Path(__file__).resolve().parents[1]
    target = Path(workspace).expanduser().resolve()
    if _is_within(target, skill_repository):
        raise ValueError("Contest workspace must be outside the Skill repository")
    if route not in ROUTES:
        raise ValueError(f"route must be one of: {', '.join(ROUTES)}")
    if ai_disclosure not in AI_DISCLOSURE_OPTIONS:
        raise ValueError(
            f"ai_disclosure must be one of: {', '.join(AI_DISCLOSURE_OPTIONS)}"
        )

    sources = {
        "problem": _resolve_source(problem, "problem"),
        "official_template": _resolve_source(template, "template"),
        "official_rules": _resolve_source(rules, "rules"),
    }
    if target.exists():
        if force:
            raise FileExistsError(
                f"Refusing to delete or overwrite existing workspace: {target}"
            )
        raise FileExistsError(f"Workspace already exists: {target}")

    target.mkdir(parents=True)
    try:
        for relative in RUNTIME_DIRECTORIES:
            (target / relative).mkdir(parents=True, exist_ok=True)

        destinations = {
            "problem": target / "inputs" / "problem" / sources["problem"].name,
            "official_template": (
                target / "inputs" / "official-template" / sources["official_template"].name
            ),
            "official_rules": (
                target / "inputs" / "official-rules" / sources["official_rules"].name
            ),
        }
        for key, source in sources.items():
            shutil.copy2(source, destinations[key])

        inputs = {
            key: _input_metadata(target, destinations[key], source)
            for key, source in sources.items()
        }
        state = {
            "schema_version": 1,
            "active_stage": "INTAKE",
            "route": route,
            "ai_disclosure": ai_disclosure,
            "stages": {
                stage: {"status": "active" if stage == "INTAKE" else "pending"}
                for stage in STAGES
            },
            "inputs": inputs,
            "artifacts": {},
            "stale_artifacts": [],
            "blocking_issues": [],
        }
        local_sources = {"schema_version": 1}
        local_sources.update(
            {
                key: {"source_path": str(source), "filename": source.name}
                for key, source in sources.items()
            }
        )
        control = target / ".huawei-modeling"
        atomic_write_json(control / "local-sources.json", local_sources)
        atomic_write_json(control / "state.json", state)
        atomic_write_json(control / "approvals.json", {})
        append_event(
            target,
            "workspace_initialized",
            {
                "schema_version": 1,
                "route": route,
                "ai_disclosure": ai_disclosure,
                "inputs": inputs,
            },
        )
    except BaseException:
        # Keep any partially created workspace intact for inspection; never remove user files.
        raise
    return state


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Initialize an isolated Huawei Cup/NPGMCM contest workspace."
    )
    parser.add_argument("--workspace", type=Path, required=True, help="new workspace path")
    parser.add_argument("--problem", type=Path, required=True, help="official problem file")
    parser.add_argument("--template", type=Path, required=True, help="official template file")
    parser.add_argument("--rules", type=Path, required=True, help="current official rules file")
    parser.add_argument("--route", choices=ROUTES, required=True, help="manuscript route")
    parser.add_argument(
        "--ai-disclosure",
        choices=AI_DISCLOSURE_OPTIONS,
        required=True,
        help="whether current official rules require an AI disclosure",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="validate an overwrite request; existing workspaces are never deleted",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        initialize_workspace(
            args.workspace,
            args.problem,
            args.template,
            args.rules,
            args.route,
            args.ai_disclosure,
            force=args.force,
        )
    except (OSError, ValueError) as error:
        print(f"workspace initialization failed: {error}", file=sys.stderr)
        return 2
    print(f"Initialized Huawei Cup contest workspace: {args.workspace.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
