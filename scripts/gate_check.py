"""Stage gate aggregation with machine-readable, reproducible output.

A gate never proves that the mathematics is correct. It only proves that the
current workspace still satisfies the workflow's artifact, freshness, evidence
and review contracts, and it fails closed when they are not met.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

try:  # Support both package imports and direct CLI execution.
    from .common import IssueLog, atomic_write_json, sha256_file, utc_timestamp
    from .evidence_check import validate_evidence
    from .render_audit import PAPER_PATH, REPORT_PATH, load_report, report_is_fresh
    from .workflow import STAGES
except ImportError:  # pragma: no cover - direct execution path
    from common import IssueLog, atomic_write_json, sha256_file, utc_timestamp
    from evidence_check import validate_evidence
    from render_audit import PAPER_PATH, REPORT_PATH, load_report, report_is_fresh
    from workflow import STAGES

STATE_PATH = Path(".huawei-modeling") / "state.json"
APPROVALS_PATH = Path(".huawei-modeling") / "approvals.json"
REVIEW_LEDGER_PATH = Path("review") / "issue-ledger.json"
MANUSCRIPT_CHECK_PATH = Path("manuscript") / "manuscript-check.json"
SUBMISSION_MANIFEST_PATH = Path("delivery") / "submission-manifest.json"
RULE_SNAPSHOT_PATH = Path(".huawei-modeling") / "rule-snapshot.json"
VISUAL_QA_PATH = Path("figures") / "visual-qa.json"

DISCOVERY_ARTIFACTS = (
    "analysis/sentence-ledger.md",
    "analysis/task-graph.md",
    "analysis/data-audit.md",
    "analysis/ambiguity-register.md",
)
FORMULATION_ARTIFACTS = (
    "modeling/candidate-models.md",
    "modeling/model-decision.md",
    "modeling/formulation.md",
    "modeling/validation-plan.md",
)
COMPUTATION_ARTIFACTS = (
    "results/result-evidence.json",
    "code/code-manifest.json",
)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _require_file(root: Path, relative: str, findings: IssueLog, hashes: dict[str, str]) -> None:
    candidate = root / relative
    if not candidate.is_file():
        findings.add("missing_required_artifact", "P0", f"缺少必需产物：{relative}", [relative])
        return
    hashes[relative] = sha256_file(candidate)


def _require_approval(approvals: Any, stage: str, findings: IssueLog) -> None:
    record = approvals.get(stage) if isinstance(approvals, dict) else None
    if not isinstance(record, dict) or record.get("decision") != "approve":
        findings.add(
            "missing_checkpoint_approval",
            "P0",
            f"{stage} 缺少有效的人工确认",
            [APPROVALS_PATH.as_posix()],
        )


def _check_registered_artifacts(
    root: Path, state: dict[str, Any], stage: str, findings: IssueLog, hashes: dict[str, str]
) -> None:
    artifacts = state.get("artifacts")
    if not isinstance(artifacts, dict):
        return
    stale = {str(item) for item in state.get("stale_artifacts", []) if isinstance(item, str)}
    stage_index = STAGES.index(stage)
    for relative, record in sorted(artifacts.items()):
        if not isinstance(record, dict):
            continue
        artifact_stage = record.get("stage")
        if artifact_stage not in STAGES or STAGES.index(artifact_stage) > stage_index:
            continue
        if relative in stale:
            findings.add(
                "stale_artifact",
                "P0",
                f"产物已过期，必须先返工：{relative}",
                [relative],
            )
            continue
        candidate = root / relative
        if not candidate.is_file():
            findings.add("missing_artifact", "P0", f"登记产物缺失：{relative}", [relative])
            continue
        actual = sha256_file(candidate)
        hashes[relative] = actual
        declared = record.get("sha256")
        if isinstance(declared, str) and actual != declared:
            findings.add(
                "artifact_hash_mismatch", "P0", f"登记产物已变化：{relative}", [relative]
            )


def _check_intake(
    root: Path, state: dict[str, Any], approvals: Any, findings: IssueLog,
    unverified: list[str], hashes: dict[str, str],
) -> None:
    inputs = state.get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        findings.add(
            "missing_official_inputs", "P0", "INTAKE 未登记任何官方材料", [STATE_PATH.as_posix()]
        )
        return
    for key, label in (
        ("problem", "赛题"),
        ("official_template", "官方模板"),
        ("official_rules", "官方规则"),
    ):
        record = inputs.get(key)
        if not isinstance(record, dict):
            findings.add(
                "missing_official_inputs", "P0", f"缺少{label}登记", [STATE_PATH.as_posix()]
            )
            continue
        relative = record.get("workspace_path")
        if not isinstance(relative, str) or not (root / relative).is_file():
            findings.add(
                "missing_official_inputs",
                "P0",
                f"{label}文件缺失：{relative}",
                [relative if isinstance(relative, str) else STATE_PATH.as_posix()],
            )
            continue
        actual = sha256_file(root / relative)
        hashes[relative] = actual
        declared = record.get("sha256")
        if isinstance(declared, str) and actual != declared:
            findings.add(
                "official_input_changed", "P0", f"{label}与登记哈希不符：{relative}", [relative]
            )


def _check_discovery(
    root: Path, state: dict[str, Any], approvals: Any, findings: IssueLog,
    unverified: list[str], hashes: dict[str, str],
) -> None:
    for relative in DISCOVERY_ARTIFACTS:
        _require_file(root, relative, findings, hashes)
    _require_approval(approvals, "DISCOVERY", findings)


def _check_formulation(
    root: Path, state: dict[str, Any], approvals: Any, findings: IssueLog,
    unverified: list[str], hashes: dict[str, str],
) -> None:
    for relative in FORMULATION_ARTIFACTS:
        _require_file(root, relative, findings, hashes)
    _require_approval(approvals, "FORMULATION", findings)


def _check_computation(
    root: Path, state: dict[str, Any], approvals: Any, findings: IssueLog,
    unverified: list[str], hashes: dict[str, str],
) -> None:
    for relative in COMPUTATION_ARTIFACTS:
        _require_file(root, relative, findings, hashes)
    for issue in validate_evidence(root):
        findings.add(
            issue["code"],
            issue["severity"],
            issue["message"],
            issue.get("paths", []),
        )
    _require_approval(approvals, "COMPUTATION", findings)


def _check_evidence(
    root: Path, state: dict[str, Any], approvals: Any, findings: IssueLog,
    unverified: list[str], hashes: dict[str, str],
) -> None:
    manifest_path = Path("figures") / "figure-manifest.json"
    payload = _read_json(root / manifest_path)
    if not isinstance(payload, dict):
        findings.add(
            "missing_figure_manifest", "P0", "缺少图表清单", [manifest_path.as_posix()]
        )
        return
    figures = payload.get("figures")
    if not isinstance(figures, list) or not figures:
        findings.add(
            "empty_figure_manifest", "P1", "图表清单为空", [manifest_path.as_posix()]
        )
        return
    for index, figure in enumerate(figures):
        if not isinstance(figure, dict):
            findings.add(
                "invalid_figure_entry", "P1", f"图表清单第 {index + 1} 条不是对象",
                [manifest_path.as_posix()],
            )
            continue
        for field in ("claim", "source_result_ids", "publish", "caption"):
            if field not in figure:
                findings.add(
                    "incomplete_figure_entry",
                    "P1",
                    f"图表清单第 {index + 1} 条缺少字段：{field}",
                    [manifest_path.as_posix()],
                )
    visual_reports = sorted(root.glob("figures/**/*.visual.json"))
    if not (root / VISUAL_QA_PATH).is_file() and not visual_reports:
        findings.add(
            "missing_visual_qa",
            "P1",
            "图表缺少任何视觉检查结果（figures/visual-qa.json 或 *.visual.json）",
            [VISUAL_QA_PATH.as_posix()],
        )


def _require_manuscript_check(root: Path, findings: IssueLog, hashes: dict[str, str]) -> None:
    payload = _read_json(root / MANUSCRIPT_CHECK_PATH)
    if not isinstance(payload, dict):
        findings.add(
            "missing_manuscript_check",
            "P1",
            "缺少论文一致性检查报告 manuscript/manuscript-check.json",
            [MANUSCRIPT_CHECK_PATH.as_posix()],
        )
        return
    hashes[MANUSCRIPT_CHECK_PATH.as_posix()] = sha256_file(root / MANUSCRIPT_CHECK_PATH)
    summary = payload.get("summary")
    if isinstance(summary, dict) and (summary.get("P0") or summary.get("P1")):
        findings.add(
            "manuscript_check_failed",
            "P1",
            "论文一致性检查仍有 P0/P1 问题",
            [MANUSCRIPT_CHECK_PATH.as_posix()],
        )


def _require_render_audit(root: Path, findings: IssueLog, hashes: dict[str, str]) -> None:
    paper = root / PAPER_PATH
    if not paper.is_file() or paper.stat().st_size == 0:
        findings.add(
            "missing_final_pdf", "P0", f"缺少最终 PDF：{PAPER_PATH.as_posix()}",
            [PAPER_PATH.as_posix()],
        )
        return
    report = load_report(root)
    if report is None:
        findings.add(
            "missing_render_audit", "P1", "缺少最终版面审计报告",
            [REPORT_PATH.as_posix()],
        )
        return
    if not report_is_fresh(report, root):
        findings.add(
            "stale_render_audit", "P1", "版面审计报告与当前 PDF 不一致",
            [REPORT_PATH.as_posix()],
        )
        return
    hashes[REPORT_PATH.as_posix()] = sha256_file(root / REPORT_PATH)
    if report.get("status") == "blocked":
        findings.add(
            "render_audit_blocked", "P0", "版面审计未通过", [REPORT_PATH.as_posix()]
        )


ANONYMITY_PATTERNS = (
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("mobile", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    (
        "labelled_identity",
        re.compile(
            r"(作者|单位|学校|学院|指导教师|指导老师|学号|队号|队员)\s*[:：]\s*\S+"
        ),
    ),
)


def _check_rule_snapshot(
    root: Path, state: dict[str, Any], findings: IssueLog, unverified: list[str]
) -> dict[str, Any] | None:
    """Load the current-year rule snapshot; missing or stale blocks compliance claims."""
    payload = _read_json(root / RULE_SNAPSHOT_PATH)
    if not isinstance(payload, dict):
        findings.add(
            "missing_rule_snapshot",
            "P0",
            (
                "缺少当届官方规则快照 .huawei-modeling/rule-snapshot.json，"
                "无法声明论文格式合规"
            ),
            [RULE_SNAPSHOT_PATH.as_posix()],
        )
        return None
    recorded = payload.get("source_sha256")
    if not isinstance(recorded, str) or not re.fullmatch(r"[a-f0-9]{64}", recorded):
        findings.add(
            "invalid_rule_snapshot",
            "P0",
            "规则快照缺少合法的 source_sha256",
            [RULE_SNAPSHOT_PATH.as_posix()],
        )
        return payload
    inputs = state.get("inputs")
    rules = inputs.get("official_rules") if isinstance(inputs, dict) else None
    declared = rules.get("sha256") if isinstance(rules, dict) else None
    if isinstance(declared, str) and declared != recorded:
        findings.add(
            "rule_snapshot_stale",
            "P0",
            "规则快照与工作区登记的官方规则文件不一致，必须先更新快照",
            [RULE_SNAPSHOT_PATH.as_posix()],
        )
    return payload


def _check_layout_limits(
    root: Path, snapshot: dict[str, Any], findings: IssueLog, unverified: list[str]
) -> None:
    report = load_report(root)
    if not isinstance(report, dict):
        unverified.append("page_limit: 缺少版面审计报告，无法比对页数与目录深度")
        return
    max_pages = snapshot.get("max_pages")
    page_count = report.get("page_count")
    if isinstance(max_pages, int) and max_pages > 0:
        if isinstance(page_count, int) and page_count > max_pages:
            findings.add(
                "page_limit_exceeded",
                "P0",
                f"论文 {page_count} 页，超过当届规则上限 {max_pages} 页",
                [REPORT_PATH.as_posix()],
            )
    else:
        unverified.append("page_limit: 规则快照未登记 max_pages，页数上限未验证")
    toc_limit = snapshot.get("toc_max_depth")
    toc_depth = report.get("toc_max_depth")
    if isinstance(toc_limit, int) and toc_limit > 0:
        if isinstance(toc_depth, int) and toc_depth > toc_limit:
            findings.add(
                "toc_depth_exceeded",
                "P0",
                f"目录深度 {toc_depth} 超过当届规则上限 {toc_limit}",
                [REPORT_PATH.as_posix()],
            )
        elif not isinstance(toc_depth, int):
            unverified.append("toc_depth: 版面审计未记录目录层级")
    else:
        unverified.append("toc_depth: 规则快照未登记 toc_max_depth，目录深度未验证")


def _check_anonymity(
    root: Path, snapshot: dict[str, Any], findings: IssueLog, unverified: list[str]
) -> None:
    required = snapshot.get("anonymity_required")
    if required is not True:
        if required is None:
            unverified.append("anonymity: 规则快照未登记 anonymity_required，匿名性未验证")
        return
    allowlist = [
        re.compile(item)
        for item in snapshot.get("anonymity_allowlist", [])
        if isinstance(item, str)
    ]
    source_dir = root / "manuscript" / "source"
    if not source_dir.is_dir():
        unverified.append("anonymity: 没有 manuscript/source/ 可供扫描")
        return
    hits: list[str] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        reported = False
        for label, pattern in ANONYMITY_PATTERNS:
            for match in pattern.finditer(text):
                captured = match.group(0)
                if any(item.search(captured) for item in allowlist):
                    continue
                hits.append(f"{path.relative_to(root).as_posix()}（{label}）")
                reported = True
                break
            if reported:
                break
    if hits:
        unique = list(dict.fromkeys(hits))
        findings.add(
            "anonymity_leak",
            "P0",
            f"论文源文件疑似包含身份信息：{'；'.join(unique[:5])}",
            [item.split("（", 1)[0] for item in unique[:5]],
        )


def _check_filenames(
    root: Path, snapshot: dict[str, Any], findings: IssueLog, unverified: list[str]
) -> None:
    pattern = snapshot.get("filename_pattern")
    manifest = _read_json(root / SUBMISSION_MANIFEST_PATH)
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(files, list) or not files:
        return
    compiled = None
    if isinstance(pattern, str) and pattern.strip():
        try:
            compiled = re.compile(pattern)
        except re.error:
            findings.add(
                "invalid_rule_snapshot",
                "P0",
                f"规则快照的 filename_pattern 不是合法正则：{pattern}",
                [RULE_SNAPSHOT_PATH.as_posix()],
            )
            return
    else:
        unverified.append("filename_pattern: 规则快照未登记命名规则，仅检查不可用字符")
    for entry in files:
        if not isinstance(entry, dict):
            continue
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative.strip():
            continue
        name = Path(relative.strip()).name
        if compiled is not None:
            if not compiled.match(name):
                findings.add(
                    "filename_violation",
                    "P0",
                    f"提交文件名不符合当届命名规则：{name}",
                    [relative.strip()],
                )
        elif any(ch in name for ch in '\\/:*?"<>|') or any(ch.isspace() for ch in name):
            findings.add(
                "filename_violation",
                "P1",
                f"提交文件名包含不可用字符：{name}",
                [relative.strip()],
            )


def _check_manuscript(
    root: Path, state: dict[str, Any], approvals: Any, findings: IssueLog,
    unverified: list[str], hashes: dict[str, str],
) -> None:
    snapshot = _check_rule_snapshot(root, state, findings, unverified)
    inputs = state.get("inputs")
    template = inputs.get("official_template") if isinstance(inputs, dict) else None
    if isinstance(template, dict):
        relative = template.get("workspace_path")
        declared = template.get("sha256")
        if isinstance(relative, str) and (root / relative).is_file():
            if isinstance(declared, str) and sha256_file(root / relative) != declared:
                findings.add(
                    "template_hash_mismatch", "P0",
                    f"官方模板已变化：{relative}", [relative],
                )
    _require_manuscript_check(root, findings, hashes)
    _require_render_audit(root, findings, hashes)
    if snapshot is not None:
        _check_layout_limits(root, snapshot, findings, unverified)


def _check_review_ledger(
    root: Path, findings: IssueLog, unverified: list[str]
) -> None:
    payload = _read_json(root / REVIEW_LEDGER_PATH)
    if not isinstance(payload, dict):
        findings.add(
            "missing_review_ledger", "P0", "缺少审稿台账",
            [REVIEW_LEDGER_PATH.as_posix()],
        )
        return
    issues = payload.get("issues")
    issues = issues if isinstance(issues, list) else []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        severity = issue.get("severity")
        status = issue.get("status", "open")
        message = str(issue.get("message", ""))
        if severity == "P0":
            findings.add(
                "unresolved_p0", "P0", f"审稿 P0 未解决：{message}",
                [REVIEW_LEDGER_PATH.as_posix()],
            )
        elif severity == "P1" and status not in ("accepted", "resolved"):
            findings.add(
                "unaccepted_p1", "P1", f"审稿 P1 未被接受：{message}",
                [REVIEW_LEDGER_PATH.as_posix()],
            )

    declared = payload.get("paper_sha256")
    paper = root / PAPER_PATH
    if isinstance(declared, str) and declared:
        if not paper.is_file():
            findings.add(
                "missing_final_pdf", "P0", f"缺少最终 PDF：{PAPER_PATH.as_posix()}",
                [PAPER_PATH.as_posix()],
            )
        elif sha256_file(paper) != declared:
            findings.add(
                "review_hash_mismatch",
                "P1",
                "审稿台账对应的论文版本与当前 PDF 不一致",
                [REVIEW_LEDGER_PATH.as_posix(), PAPER_PATH.as_posix()],
            )
    else:
        unverified.append("review_paper_hash: 审稿台账未登记 paper_sha256")


def _check_review(
    root: Path, state: dict[str, Any], approvals: Any, findings: IssueLog,
    unverified: list[str], hashes: dict[str, str],
) -> None:
    _check_review_ledger(root, findings, unverified)
    _require_approval(approvals, "REVIEW", findings)


def _check_delivery(
    root: Path, state: dict[str, Any], approvals: Any, findings: IssueLog,
    unverified: list[str], hashes: dict[str, str],
) -> None:
    snapshot = _check_rule_snapshot(root, state, findings, unverified)
    _require_render_audit(root, findings, hashes)
    _require_manuscript_check(root, findings, hashes)
    _check_review_ledger(root, findings, unverified)
    if snapshot is not None:
        _check_layout_limits(root, snapshot, findings, unverified)
        _check_anonymity(root, snapshot, findings, unverified)
        _check_filenames(root, snapshot, findings, unverified)

    payload = _read_json(root / SUBMISSION_MANIFEST_PATH)
    if not isinstance(payload, dict):
        findings.add(
            "missing_submission_manifest",
            "P0",
            "缺少交付清单 delivery/submission-manifest.json",
            [SUBMISSION_MANIFEST_PATH.as_posix()],
        )
    else:
        files = payload.get("files")
        if not isinstance(files, list) or not files:
            findings.add(
                "incomplete_submission_manifest",
                "P1",
                "交付清单没有登记任何文件",
                [SUBMISSION_MANIFEST_PATH.as_posix()],
            )
        else:
            for entry in files:
                if not isinstance(entry, dict):
                    continue
                relative = entry.get("path")
                if not isinstance(relative, str) or not relative.strip():
                    continue
                relative = relative.strip()
                candidate = root / relative
                if not candidate.is_file():
                    findings.add(
                        "missing_submission_file", "P0",
                        f"交付清单登记的文件不存在：{relative}", [relative],
                    )
                    continue
                declared = entry.get("sha256")
                if isinstance(declared, str) and sha256_file(candidate) != declared:
                    findings.add(
                        "submission_hash_mismatch", "P0",
                        f"交付清单哈希不匹配：{relative}", [relative],
                    )


_STAGE_CHECKS = {
    "INTAKE": _check_intake,
    "DISCOVERY": _check_discovery,
    "FORMULATION": _check_formulation,
    "COMPUTATION": _check_computation,
    "EVIDENCE": _check_evidence,
    "MANUSCRIPT": _check_manuscript,
    "REVIEW": _check_review,
    "DELIVERY": _check_delivery,
}


def check_gate(workspace: Path, stage: str) -> dict[str, Any]:
    """Evaluate *stage* for *workspace* and persist `.huawei-modeling/gates/<stage>.json`."""
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage}")

    root = Path(workspace)
    findings = IssueLog()
    unverified: list[str] = []
    hashes: dict[str, str] = {}

    state = _read_json(root / STATE_PATH)
    if not isinstance(state, dict):
        findings.add(
            "missing_workflow_state", "P0", "缺少工作流状态文件",
            [STATE_PATH.as_posix()],
        )
    else:
        _check_registered_artifacts(root, state, stage, findings, hashes)
        approvals = _read_json(root / APPROVALS_PATH)
        _STAGE_CHECKS[stage](root, state, approvals, findings, unverified, hashes)

    result = {
        "schema_version": 1,
        "stage": stage,
        "passed": not findings.blocking(),
        "issues": findings.items,
        "checked_hashes": hashes,
        "unverified": unverified,
        "summary": findings.summary(),
        "timestamp": utc_timestamp(),
    }
    atomic_write_json(root / ".huawei-modeling" / "gates" / f"{stage}.json", result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a Huawei Cup stage gate.")
    parser.add_argument("--workspace", type=Path, required=True, help="contest workspace")
    parser.add_argument("--stage", choices=STAGES, required=True, help="stage to evaluate")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = check_gate(args.workspace, args.stage)
    print(
        json.dumps(
            {"stage": result["stage"], "passed": result["passed"], "summary": result["summary"]},
            ensure_ascii=False,
        )
    )
    for issue in result["issues"]:
        print(f"[{issue['severity']}] {issue['code']}: {issue['message']}")
    for item in result["unverified"]:
        print(f"[unverified] {item}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
