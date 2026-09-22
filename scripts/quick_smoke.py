"""Synthetic end-to-end contract smoke test.

The smoke run creates a throwaway contest workspace, drives every legal stage
transition, evaluates every gate, and exercises one rework path. It never reads
real contest material, never touches the network, and never invokes XeLaTeX,
Word, LibreOffice or DrawIO.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any

try:  # Support both package imports and direct CLI execution.
    from .common import atomic_write_json, sha256_file
    from .gate_check import check_gate
    from .manuscript_check import main as manuscript_check_main
    from .render_audit import main as render_audit_main
    from .review_ledger import record_review
    from .workflow import Workflow
    from .workspace_init import initialize_workspace
except ImportError:  # pragma: no cover - direct execution path
    from common import atomic_write_json, sha256_file
    from gate_check import check_gate
    from manuscript_check import main as manuscript_check_main
    from render_audit import main as render_audit_main
    from review_ledger import record_review
    from workflow import Workflow
    from workspace_init import initialize_workspace

MODEL_IDENTITY = "linear programming"
MECHANISM = "capacity constraints on a single shared resource"
SOLVER_ALGORITHM = "HiGHS"
OBJECTIVE = 42.5
OBJECTIVE_DISPLAY = "42.50"

COMPUTE_SCRIPT = '''"""Deterministic synthetic computation used only by the smoke test."""

objective = 42.5
print(f"objective={objective:.2f}")
'''

PAPER = """# 合成论文：单资源容量问题

## 问题分析

本文用一个合成问题验证工作流契约，不包含任何真实赛题内容。

## 模型

本文以 $x$ 表示产量，模型身份为 linear programming，作用机制是
capacity constraints on a single shared resource。

## 结果

最优目标值为 42.50。

## 符号说明

$x$ 表示产量，单位为件。

## 图形

![目标值示意图](figures/data/q1.svg)
"""

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="80">'
    '<text x="10" y="40" font-size="14">42.50</text></svg>'
)

DISCOVERY_FILES = {
    "analysis/sentence-ledger.md": "# 句子台账\n\n- Q1：单资源容量问题。\n",
    "analysis/task-graph.md": "```mermaid\ngraph TD\n  Q1 --> R1\n```\n",
    "analysis/data-audit.md": "# 数据审计\n\n- 合成数据，单字段。\n",
    "analysis/ambiguity-register.md": "# 歧义登记\n\n- 无实质歧义。\n",
}

FORMULATION_FILES = {
    "modeling/candidate-models.md": (
        "# 候选模型\n\ncandidate | model identity | mechanism | solver | inputs | outputs | "
        "assumptions | validation | failure conditions | implementation cost | "
        "downstream compatibility\n"
    ),
    "modeling/model-decision.md": "# 模型决策\n\n主模型：linear programming。\n",
    "modeling/formulation.md": "# 数学表述\n\n目标函数与容量约束。\n",
    "modeling/validation-plan.md": "# 验证计划\n\n与基线对比目标值。\n",
}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _minimal_pdf(text: str = "Synthetic paper") -> bytes:
    """Build a small, structurally valid single-page PDF without dependencies."""
    content = f"BT /F1 12 Tf 72 760 Td ({text}) Tj ET\n".encode("ascii")
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(bodies, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(bodies) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size "
        + str(len(bodies) + 1).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF\n"
    )
    return bytes(out)


def _scan_private_paths(root: Path, workspace: Path) -> list[str]:
    """Return public artifacts that leak the throwaway absolute root path."""
    raw = str(root)
    posix = root.as_posix()
    needles = {raw, posix}
    leaks: list[str] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.name == "local-sources.json":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        normalized = text.replace("\\\\", "\\").replace("\\/", "/")
        if any(needle in normalized or needle in text for needle in needles if needle):
            leaks.append(path.relative_to(workspace).as_posix())
    return leaks


def run_smoke() -> dict[str, Any]:
    """Run the synthetic workflow end to end and return a machine-readable summary."""
    with TemporaryDirectory(prefix="huawei-smoke-") as tmp:
        base = Path(tmp).resolve()
        workspace = base / "contest-workspace"
        sources = base / "sources"
        problem = sources / "problem.pdf"
        template = sources / "template.docx"
        rules = sources / "rules.pdf"
        for path, payload in (
            (problem, b"synthetic problem"),
            (template, b"synthetic template"),
            (rules, b"synthetic rules"),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

        initialize_workspace(workspace, problem, template, rules, "docx", "off")
        workflow = Workflow.load(workspace)
        gates: dict[str, bool] = {}
        notes: list[str] = []

        # INTAKE
        workflow.complete("INTAKE", ["inputs/problem/problem.pdf"])
        rules_input = workflow.status()["inputs"]["official_rules"]
        atomic_write_json(
            workspace / ".huawei-modeling" / "rule-snapshot.json",
            {
                "schema_version": 1,
                "competition": "NPGMCM",
                "year": 2026,
                "source_filename": rules_input["filename"],
                "source_sha256": rules_input["sha256"],
                "max_pages": 25,
                "toc_max_depth": 3,
                "anonymity_required": True,
                "anonymity_allowlist": [],
                "filename_pattern": None,
            },
        )
        gates["INTAKE"] = check_gate(workspace, "INTAKE")["passed"]

        # DISCOVERY
        workflow.begin("DISCOVERY")
        for relative, body in DISCOVERY_FILES.items():
            _write(workspace / relative, body)
        workflow.complete("DISCOVERY", list(DISCOVERY_FILES))
        workflow.request_approval("DISCOVERY")
        workflow.approve("DISCOVERY", "smoke: 题意与交付要求确认")
        gates["DISCOVERY"] = check_gate(workspace, "DISCOVERY")["passed"]

        # FORMULATION
        workflow.begin("FORMULATION")
        for relative, body in FORMULATION_FILES.items():
            _write(workspace / relative, body)
        workflow.complete("FORMULATION", list(FORMULATION_FILES))
        workflow.request_approval("FORMULATION")
        workflow.approve("FORMULATION", "smoke: 主模型与备选模型确认")
        gates["FORMULATION"] = check_gate(workspace, "FORMULATION")["passed"]

        # COMPUTATION
        workflow.begin("COMPUTATION")
        code_path = workspace / "code" / "q1.py"
        _write(code_path, COMPUTE_SCRIPT)
        completed = subprocess.run(
            [sys.executable, "code/q1.py"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=180,
        )
        log_path = workspace / "results" / "run-logs" / "q1.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            completed.stdout + completed.stderr, encoding="utf-8"
        )
        if completed.returncode != 0:
            notes.append("synthetic computation exited non-zero")

        atomic_write_json(
            workspace / "results" / "result-evidence.json",
            {
                "schema_version": 1,
                "results": [
                    {
                        "id": "Q1.objective",
                        "problem_ids": ["Q1"],
                        "model_identity": MODEL_IDENTITY,
                        "mechanism": MECHANISM,
                        "solver_algorithm": SOLVER_ALGORITHM,
                        "value": OBJECTIVE,
                        "display_value": OBJECTIVE_DISPLAY,
                        "precision": "2 decimal places",
                        "source_files": [
                            {"path": "code/q1.py", "sha256": sha256_file(code_path)}
                        ],
                        "run_command": "python code/q1.py",
                        "environment": {"python": platform.python_version()},
                        "random_seed": 0,
                    }
                ],
            },
        )
        atomic_write_json(
            workspace / "code" / "code-manifest.json",
            {
                "schema_version": 1,
                "files": [
                    {
                        "path": "code/q1.py",
                        "sha256": sha256_file(code_path),
                        "purpose": "synthetic objective computation",
                        "entry_command": "python code/q1.py",
                    }
                ],
            },
        )
        workflow.complete(
            "COMPUTATION", ["results/result-evidence.json", "code/code-manifest.json"]
        )
        workflow.request_approval("COMPUTATION")
        workflow.approve("COMPUTATION", "smoke: 结果可信，暂不进入增强")
        gates["COMPUTATION"] = check_gate(workspace, "COMPUTATION")["passed"]

        # EVIDENCE
        workflow.begin("EVIDENCE")
        svg_path = workspace / "figures" / "data" / "q1.svg"
        _write(svg_path, SVG)
        _write(
            workspace / "figures" / "data" / "q1.svg.visual.json",
            json.dumps({"figure": "figures/data/q1.svg", "failures": []}),
        )
        atomic_write_json(
            workspace / "figures" / "figure-manifest.json",
            {
                "schema_version": 1,
                "figures": [
                    {
                        "id": "fig-q1",
                        "path": "figures/data/q1.svg",
                        "claim": "验证单资源容量问题的最优目标值量级",
                        "source_result_ids": ["Q1.objective"],
                        "publish": True,
                        "paper_location": "manuscript/source/paper.md#图形",
                        "caption": "目标值示意图",
                        "generation_command": "python code/q1.py",
                    }
                ],
            },
        )
        workflow.complete("EVIDENCE", ["figures/figure-manifest.json"])
        gates["EVIDENCE"] = check_gate(workspace, "EVIDENCE")["passed"]

        # MANUSCRIPT
        workflow.begin("MANUSCRIPT")
        _write(workspace / "manuscript" / "source" / "paper.md", PAPER)
        (workspace / "manuscript" / "paper.pdf").write_bytes(_minimal_pdf())
        with contextlib.redirect_stdout(io.StringIO()):
            manuscript_rc = manuscript_check_main(
                ["--workspace", str(workspace), "--route", "docx"]
            )
            audit_rc = render_audit_main(["--workspace", str(workspace)])
        workflow.complete(
            "MANUSCRIPT", ["manuscript/source/paper.md", "manuscript/paper.pdf"]
        )
        gates["MANUSCRIPT"] = check_gate(workspace, "MANUSCRIPT")["passed"]
        if manuscript_rc != 0:
            notes.append("manuscript check reported blocking issues")
        if audit_rc != 0:
            notes.append("render audit reported blocking issues")

        # REVIEW
        workflow.begin("REVIEW")
        paper = workspace / "manuscript" / "paper.pdf"
        record_review(workspace, [], sha256_file(paper))
        workflow.complete("REVIEW", ["review/issue-ledger.json"])
        workflow.request_approval("REVIEW")
        workflow.approve("REVIEW", "smoke: 终稿候选批准")
        gates["REVIEW"] = check_gate(workspace, "REVIEW")["passed"]

        # DELIVERY
        workflow.begin("DELIVERY")
        source_paper = workspace / "manuscript" / "source" / "paper.md"
        atomic_write_json(
            workspace / "delivery" / "submission-manifest.json",
            {
                "schema_version": 1,
                "files": [
                    {
                        "path": "manuscript/paper.pdf",
                        "sha256": sha256_file(paper),
                        "size_bytes": paper.stat().st_size,
                    },
                    {
                        "path": "manuscript/source/paper.md",
                        "sha256": sha256_file(source_paper),
                        "size_bytes": source_paper.stat().st_size,
                    },
                ],
            },
        )
        workflow.complete("DELIVERY", ["delivery/submission-manifest.json"])
        gates["DELIVERY"] = check_gate(workspace, "DELIVERY")["passed"]
        final_stage = workflow.status()["active_stage"]

        # Recovery from disk
        reloaded = Workflow.load(workspace)
        recovered = reloaded.status()["active_stage"] == final_stage

        # One rework path
        rework_ok = False
        try:
            reloaded.rework("FORMULATION", "smoke: upstream model change")
            rework_status = reloaded.status()
            rework_ok = (
                rework_status["active_stage"] == "FORMULATION"
                and "manuscript/paper.pdf" in rework_status["stale_artifacts"]
            )
        except Exception as exc:  # noqa: BLE001 - reported, never fatal
            notes.append(f"rework drill failed: {exc}")

        leaks = _scan_private_paths(base, workspace)
        checks = {
            "all_gates_passed": all(gates.values()),
            "gate_count": len(gates),
            "recovered_from_disk": recovered,
            "rework_propagates_stale": rework_ok,
        }
        passed = bool(
            checks["all_gates_passed"] and recovered and rework_ok and not leaks
        )
        return {
            "schema_version": 1,
            "passed": passed,
            "final_stage": final_stage,
            "gates": gates,
            "checks": checks,
            "private_path_leaks": leaks,
            "notes": notes,
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the synthetic Huawei Cup workflow smoke test."
    )
    parser.add_argument(
        "--summary",
        type=Path,
        help="optional path to write the JSON summary to",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    summary = run_smoke()
    encoded = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
