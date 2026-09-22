"""Shared and format-specific consistency checks for Huawei Cup manuscripts.

The checks only prove that the manuscript is bound to current evidence, follows
the registered route, and leaks nothing internal. They never claim that the
writing is good or that the mathematics is correct.
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
except ImportError:  # pragma: no cover - direct execution path
    from common import IssueLog, atomic_write_json, sha256_file, utc_timestamp

SOURCE_DIR = Path("manuscript") / "source"
EVIDENCE_PATH = Path("results") / "result-evidence.json"
FIGURE_MANIFEST_PATH = Path("figures") / "figure-manifest.json"
STATE_PATH = Path(".huawei-modeling") / "state.json"
CHECK_REPORT_PATH = Path("manuscript") / "manuscript-check.json"

SOURCE_SUFFIXES = (".md", ".tex", ".txt")
ROUTES = ("latex", "docx")

PLACEHOLDER_PATTERN = re.compile(r"TODO|TBD|FIXME|XXX|待补|待填|待定|占位", re.IGNORECASE)
LEAKAGE_TERMS = (
    ".huawei-modeling",
    "workflow.py",
    "evidence_check",
    "manuscript_check",
    "gate_check",
    "review_ledger",
    "issue-ledger",
    "stale_artifacts",
    "result-evidence.json",
    "rework",
    "P0",
    "P1",
)
NUMBER_PATTERN = re.compile(r"[-+]?\d+(?:\.\d+)?")
FIGURE_MD_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
FIGURE_TEX_PATTERN = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
MATH_PATTERN = re.compile(r"\$[^$]+\$|\\begin\{equation\}|\\\[")
IGNORED_CONTEXT = (
    "图",
    "表",
    "式",
    "章",
    "节",
    "公式",
    "附录",
    "Figure",
    "Table",
    "Eq",
    "Section",
    "Chapter",
    "Appendix",
)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _collect_sources(root: Path) -> list[Path]:
    directory = root / SOURCE_DIR
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
    )


def _neighbour(text: str, index: int, step: int) -> str:
    position = index + step
    while 0 <= position < len(text) and text[position].isspace():
        position += step
    if 0 <= position < len(text):
        return text[position]
    return ""


def _is_ignored_number(text: str, token: str, start: int, end: int) -> bool:
    """Years, section numbers, citations, equation labels and small counts pass."""
    try:
        number = float(token)
    except ValueError:
        return True
    if number.is_integer() and 1900 <= number <= 2099:
        return True
    before, after = _neighbour(text, start, -1), _neighbour(text, end, 1)
    if before in "[（(" and after in "]）)":
        return True
    window = text[max(0, start - 6) : min(len(text), end + 6)]
    if any(marker in window for marker in IGNORED_CONTEXT):
        return True
    return number.is_integer() and abs(number) < 100


def _close(left: float, right: float) -> bool:
    return abs(left - right) <= max(1e-9, abs(right) * 1e-9)


def _evidence_numbers(results: list[Any]) -> tuple[set[str], list[float]]:
    displays: set[str] = set()
    values: list[float] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        display = result.get("display_value")
        if isinstance(display, str) and display.strip():
            displays.add(display.strip())
        value = result.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
        elif isinstance(value, str):
            try:
                values.append(float(value.replace(",", "").strip()))
            except ValueError:
                pass
    return displays, values


def _figure_references(text: str) -> list[str]:
    raw = FIGURE_MD_PATTERN.findall(text) + FIGURE_TEX_PATTERN.findall(text)
    references = []
    for item in raw:
        cleaned = item.strip().strip("\"'")
        if not cleaned:
            continue
        references.append(cleaned.split()[0] if " " in cleaned else cleaned)
    return references


def _resolve_figure(root: Path, reference: str) -> bool:
    candidates = (
        root / reference,
        root / SOURCE_DIR / reference,
        root / "manuscript" / reference,
    )
    return any(candidate.is_file() for candidate in candidates)


def _manifest_publishable(manifest: Any) -> list[dict[str, Any]]:
    if not isinstance(manifest, dict):
        return []
    figures = manifest.get("figures")
    if not isinstance(figures, list):
        return []
    return [
        figure
        for figure in figures
        if isinstance(figure, dict) and figure.get("publish") is True
    ]


def check_manuscript(workspace: Path, route: str) -> list[dict[str, Any]]:
    """Return every manuscript finding for *workspace*; empty means pass."""
    root = Path(workspace)
    findings = IssueLog()

    sources = _collect_sources(root)
    if not sources:
        findings.add(
            "missing_manuscript_source",
            "P0",
            f"缺少论文源文件目录或内容：{SOURCE_DIR}",
            [SOURCE_DIR.as_posix()],
        )
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace") for path in sources
    )

    for match in PLACEHOLDER_PATTERN.finditer(text):
        findings.add(
            "placeholder_text",
            "P1",
            f"论文中仍有占位文字：{match.group(0)}",
            [SOURCE_DIR.as_posix()],
        )
        break

    leaks = [term for term in LEAKAGE_TERMS if term in text]
    if leaks:
        findings.add(
            "workflow_leakage",
            "P1",
            f"论文中出现内部流程用语：{'、'.join(leaks)}",
            [SOURCE_DIR.as_posix()],
        )

    references = _figure_references(text)
    for reference in references:
        if not _resolve_figure(root, reference):
            findings.add(
                "missing_figure",
                "P1",
                f"论文引用的图不存在：{reference}",
                [reference],
            )

    publishable = _manifest_publishable(_read_json(root / FIGURE_MANIFEST_PATH))
    referenced_names = {Path(reference).name for reference in references}
    for figure in publishable:
        path = figure.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        if Path(path.strip()).name not in referenced_names:
            findings.add(
                "unreferenced_figure",
                "P2",
                f"标记为 publish 的图未被论文引用：{path.strip()}",
                [FIGURE_MANIFEST_PATH.as_posix()],
            )

    evidence = _read_json(root / EVIDENCE_PATH)
    results = evidence.get("results") if isinstance(evidence, dict) else []
    results = results if isinstance(results, list) else []

    displays, values = _evidence_numbers(results)
    untraced: list[str] = []
    for match in NUMBER_PATTERN.finditer(text):
        token = match.group(0)
        if _is_ignored_number(text, token, *match.span()):
            continue
        if token in displays:
            continue
        try:
            number = float(token)
        except ValueError:
            continue
        if any(_close(number, value) for value in values):
            continue
        untraced.append(token)
    if untraced:
        unique = list(dict.fromkeys(untraced))
        findings.add(
            "untraced_numeric_claim",
            "P1",
            f"论文中有 {len(unique)} 个数值无法追溯到证据：{'、'.join(unique[:8])}",
            [SOURCE_DIR.as_posix()],
        )

    model_names = {
        result["model_identity"].strip()
        for result in results
        if isinstance(result, dict)
        and isinstance(result.get("model_identity"), str)
        and result["model_identity"].strip()
    }
    lowered = text.lower()
    if model_names and not any(name.lower() in lowered for name in model_names):
        findings.add(
            "model_name_mismatch",
            "P2",
            f"论文没有出现证据登记的模型身份：{'、'.join(sorted(model_names))}",
            [SOURCE_DIR.as_posix()],
        )

    if MATH_PATTERN.search(text) and not ("符号" in text or "Symbol" in text):
        findings.add(
            "missing_symbol_definitions",
            "P2",
            "论文包含公式但没有符号说明章节",
            [SOURCE_DIR.as_posix()],
        )

    state = _read_json(root / STATE_PATH)
    if isinstance(state, dict):
        if route != state.get("route"):
            findings.add(
                "route_mismatch",
                "P1",
                f"请求的路线 {route} 与工作区登记的 {state.get('route')} 不一致",
                [STATE_PATH.as_posix()],
            )
        ai_disclosure = state.get("ai_disclosure")
        if ai_disclosure == "required" and not ("人工智能" in text or "AI" in text):
            findings.add(
                "ai_disclosure_mismatch",
                "P1",
                "规则要求 AI 使用说明，但论文中没有对应内容",
                [SOURCE_DIR.as_posix()],
            )
        elif ai_disclosure == "off" and (
            "人工智能工具使用说明" in text or "AI 使用说明" in text
        ):
            findings.add(
                "ai_disclosure_mismatch",
                "P1",
                "工作区登记为不需要 AI 说明，但论文中出现了 AI 使用说明",
                [SOURCE_DIR.as_posix()],
            )

        inputs = state.get("inputs")
        template = inputs.get("official_template") if isinstance(inputs, dict) else None
        if isinstance(template, dict):
            relative = template.get("workspace_path")
            declared = template.get("sha256")
            if isinstance(relative, str) and relative.strip():
                candidate = root / relative
                if not candidate.is_file():
                    findings.add(
                        "missing_official_template",
                        "P0",
                        f"官方模板文件缺失：{relative}",
                        [relative],
                    )
                elif isinstance(declared, str) and sha256_file(candidate) != declared:
                    findings.add(
                        "template_hash_mismatch",
                        "P0",
                        f"官方模板已变化，与登记哈希不符：{relative}",
                        [relative],
                    )

    return findings.items


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check a Huawei Cup manuscript against its evidence and template."
    )
    parser.add_argument("--workspace", type=Path, required=True, help="contest workspace")
    parser.add_argument("--route", choices=ROUTES, required=True, help="delivery route")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    workspace = Path(args.workspace)
    issues = check_manuscript(workspace, args.route)
    log = IssueLog()
    log.items = list(issues)
    summary = log.summary()
    report = {
        "schema_version": 1,
        "check": "manuscript",
        "route": args.route,
        "generated_at": utc_timestamp(),
        "summary": summary,
        "issues": issues,
    }
    atomic_write_json(workspace / CHECK_REPORT_PATH, report)
    passed = not log.blocking()
    print(json.dumps({"passed": passed, "summary": summary}, ensure_ascii=False))
    for issue in issues:
        print(f"[{issue['severity']}] {issue['code']}: {issue['message']}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
