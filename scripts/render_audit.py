"""Final-size figure and PDF audit with optional external tool adapters.

Optional tools (pdftoppm, mutool, magick, PyMuPDF) are discovered at runtime.
Anything that cannot be checked is recorded as ``unverified`` in the report
instead of silently passing.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

try:  # Support both package imports and direct CLI execution.
    from .common import IssueLog, atomic_write_json, sha256_file, utc_timestamp
except ImportError:  # pragma: no cover - direct execution path
    from common import IssueLog, atomic_write_json, sha256_file, utc_timestamp

PAPER_PATH = Path("manuscript") / "paper.pdf"
REPORT_PATH = Path("manuscript") / "pdf-layout-report.json"
VISUAL_QA_PATH = Path("figures") / "visual-qa.json"

RENDER_TOOLS = ("pdftoppm", "mutool", "magick")
FIGURE_GLOBS = (
    "figures/**/*.png",
    "figures/**/*.jpg",
    "figures/**/*.jpeg",
    "figures/**/*.webp",
    "figures/**/*.svg",
    "figures/**/*.eps",
    "figures/**/*.pdf",
)
MIN_POINT_SIZE = 9.0
PAGE_PATTERN = re.compile(rb"/Type\s*/Page[^s]")


def _tool_version(command: str) -> str:
    for flag in ("-v", "--version"):
        try:
            completed = subprocess.run(
                [command, flag], capture_output=True, text=True, timeout=20
            )
        except (OSError, subprocess.SubprocessError):
            continue
        text = (completed.stdout or completed.stderr or "").strip().splitlines()
        if text:
            return text[0][:200]
    return "unknown"


def _discover_renderer() -> tuple[str, str] | None:
    for command in RENDER_TOOLS:
        if shutil.which(command):
            return command, _tool_version(command)
    return None


def _fallback_page_count(paper: Path) -> int:
    try:
        data = paper.read_bytes()
    except OSError:
        return 0
    return len(PAGE_PATTERN.findall(data))


def _render_pages(paper: Path, unavailable: list[str]) -> dict[str, Any] | None:
    discovered = _discover_renderer()
    if discovered is None:
        unavailable.append(
            "page_rasterisation: none of " + ", ".join(RENDER_TOOLS) + " is installed"
        )
        return None
    command, version = discovered
    with tempfile.TemporaryDirectory(prefix="huawei-render-") as directory:
        output = Path(directory)
        try:
            if command == "pdftoppm":
                subprocess.run(
                    [command, "-r", "110", "-png", str(paper), str(output / "page")],
                    check=True,
                    capture_output=True,
                    timeout=600,
                )
            elif command == "mutool":
                subprocess.run(
                    [command, "draw", "-r", "110", "-o", str(output / "page-%d.png"), str(paper)],
                    check=True,
                    capture_output=True,
                    timeout=600,
                )
            else:
                subprocess.run(
                    [command, "-density", "110", str(paper), str(output / "page-%d.png")],
                    check=True,
                    capture_output=True,
                    timeout=600,
                )
        except (OSError, subprocess.SubprocessError) as exc:
            unavailable.append(f"page_rasterisation: {command} failed: {exc}")
            return None
        pages = sorted(output.glob("*.png"))
        return {"tool": command, "version": version, "rendered_pages": len(pages)}


def _flag_overlaps(page_number: int, spans: list[dict[str, Any]], findings: IssueLog) -> None:
    """Report at most one suspicious text intersection per page."""
    candidates: list[tuple[str, Any, float]] = []
    for span in spans:
        text = str(span.get("text", "")).strip()
        bbox = span.get("bbox")
        if not text or not bbox:
            continue
        area = max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])
        if area < 40:
            continue
        candidates.append((text, bbox, area))
    if len(candidates) > 300:
        candidates = candidates[:300]
    for index, (text_a, box_a, area_a) in enumerate(candidates):
        for text_b, box_b, area_b in candidates[index + 1 :]:
            if text_a == text_b:
                continue
            width = min(box_a[2], box_b[2]) - max(box_a[0], box_b[0])
            height = min(box_a[3], box_b[3]) - max(box_a[1], box_b[1])
            if width <= 0 or height <= 0:
                continue
            if (width * height) / min(area_a, area_b) >= 0.6:
                findings.add(
                    "text_overlap",
                    "P1",
                    (
                        f"第 {page_number} 页存在可疑文本重叠："
                        f"「{text_a[:12]}」与「{text_b[:12]}」"
                    ),
                    [PAPER_PATH.as_posix()],
                )
                return


def _inspect_layout(
    paper: Path, findings: IssueLog, unavailable: list[str], strict: bool = False
) -> dict[str, Any]:
    """Record page geometry and typography findings, or mark them unverified."""
    result: dict[str, Any] = {
        "page_count": 0,
        "page_sizes": [],
        "checked_pages": [],
        "uninspected_pages": [],
        "toc_max_depth": None,
        "pdf_library": "none",
    }
    if importlib.util.find_spec("fitz") is None:
        unavailable.append("pdf_layout_checks: PyMuPDF (fitz) is not importable")
        page_count = _fallback_page_count(paper)
        result["page_count"] = page_count
        result["uninspected_pages"] = list(range(1, page_count + 1))
        if strict and page_count:
            findings.add(
                "uninspected_pages",
                "P1",
                f"strict 模式要求逐页版面检查，但 {page_count} 页未被检查（缺少 PyMuPDF）",
                [PAPER_PATH.as_posix()],
            )
        return result

    import fitz  # type: ignore[import-not-found]

    result["pdf_library"] = f"pymupdf {getattr(fitz, '__version__', 'unknown')}"
    try:
        document = fitz.open(paper)
    except Exception as exc:  # noqa: BLE001 - any parser failure is reported, not raised
        findings.add(
            "unreadable_pdf", "P0", f"无法解析最终 PDF：{exc}", [PAPER_PATH.as_posix()]
        )
        unavailable.append("pdf_layout_checks: PyMuPDF could not open the file")
        return result

    with document:
        result["page_count"] = document.page_count
        toc_levels = [
            entry[0]
            for entry in document.get_toc(simple=True)
            if entry and isinstance(entry[0], int)
        ]
        result["toc_max_depth"] = max(toc_levels) if toc_levels else 0
        for index in range(document.page_count):
            page = document[index]
            number = index + 1
            result["checked_pages"].append(number)
            result["page_sizes"].append(
                {
                    "page": number,
                    "width": round(page.rect.width, 2),
                    "height": round(page.rect.height, 2),
                }
            )
            spans: list[dict[str, Any]] = []
            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                for line in block.get("lines", []):
                    spans.extend(line.get("spans", []))
            if not spans:
                findings.add(
                    "empty_page",
                    "P1",
                    f"第 {number} 页没有任何文本内容",
                    [PAPER_PATH.as_posix()],
                )
            _flag_overlaps(number, spans, findings)
            for span in spans:
                text = str(span.get("text", "")).strip()
                if not text:
                    continue
                size = float(span.get("size") or 0.0)
                if size and size < MIN_POINT_SIZE:
                    findings.add(
                        "text_below_min_size",
                        "P1",
                        f"第 {number} 页存在小于 {MIN_POINT_SIZE} pt 的文本（{size:.1f} pt）",
                        [PAPER_PATH.as_posix()],
                    )
                bbox = span.get("bbox")
                if bbox and (
                    bbox[0] < -1
                    or bbox[1] < -1
                    or bbox[2] > page.rect.width + 1
                    or bbox[3] > page.rect.height + 1
                ):
                    findings.add(
                        "clipped_text",
                        "P1",
                        f"第 {number} 页存在超出页面的文本",
                        [PAPER_PATH.as_posix()],
                    )
    return result


def _figure_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for pattern in FIGURE_GLOBS:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                hashes[path.relative_to(root).as_posix()] = sha256_file(path)
    return hashes


def _visual_qa(root: Path, findings: IssueLog) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("figures/**/*.visual.json")):
        relative = path.relative_to(root).as_posix()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            findings.add("invalid_visual_report", "P1", f"无法解析 {relative}：{exc}", [relative])
            continue
        declared: list[str] = []
        for key in ("failures", "label_failures", "font_failures", "overlap_failures"):
            value = payload.get(key) if isinstance(payload, dict) else None
            if isinstance(value, list):
                declared.extend(str(item) for item in value)
        if declared:
            findings.add(
                "figure_visual_failure",
                "P1",
                f"{relative} 声明了视觉问题：{'；'.join(declared)}",
                [relative],
            )
        records.append({"report": relative, "declared_failures": declared})
    return {
        "schema_version": 1,
        "generated_at": utc_timestamp(),
        "figures": records,
    }


def _build_report(
    status: str,
    paper_hash: str | None,
    layout: dict[str, Any],
    renderer: dict[str, Any] | None,
    unavailable: list[str],
    findings: IssueLog,
    *,
    strict: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "check": "render_audit",
        "generated_at": utc_timestamp(),
        "status": status,
        "strict": strict,
        "passed": not findings.blocking(),
        "paper_sha256": paper_hash,
        "page_count": layout.get("page_count", 0),
        "checked_pages": layout.get("checked_pages", []),
        "uninspected_pages": layout.get("uninspected_pages", []),
        "toc_max_depth": layout.get("toc_max_depth"),
        "page_sizes": layout.get("page_sizes", []),
        "renderer": renderer or {"tool": "none", "version": "none", "rendered_pages": 0},
        "pdf_library": layout.get("pdf_library", "none"),
        "findings": findings.items,
        "unavailable": unavailable,
        "summary": findings.summary(),
    }


def _write_reports(root: Path, report: dict[str, Any], visual: dict[str, Any]) -> None:
    atomic_write_json(root / REPORT_PATH, report)
    atomic_write_json(root / VISUAL_QA_PATH, visual)


def audit_rendered_output(workspace: Path, strict: bool = False) -> dict[str, Any]:
    """Audit the final PDF and figures; always persist a machine-readable report."""
    root = Path(workspace)
    findings = IssueLog()
    unavailable: list[str] = []
    paper = root / PAPER_PATH

    if not paper.is_file() or paper.stat().st_size == 0:
        findings.add(
            "missing_final_pdf", "P0", f"缺少最终 PDF：{PAPER_PATH.as_posix()}", [PAPER_PATH.as_posix()]
        )
        visual = _visual_qa(root, findings)
        report = _build_report("blocked", None, {}, None, unavailable, findings, strict=strict)
        report["figure_hashes"] = _figure_hashes(root)
        _write_reports(root, report, visual)
        return report

    paper_hash = sha256_file(paper)
    renderer = _render_pages(paper, unavailable)
    layout = _inspect_layout(paper, findings, unavailable, strict=strict)
    visual = _visual_qa(root, findings)

    status = "pass"
    if findings.blocking():
        status = "blocked"
    elif unavailable or any(
        issue["severity"] in {"P2", "P3"} for issue in findings.items
    ):
        status = "warn"

    report = _build_report(status, paper_hash, layout, renderer, unavailable, findings, strict=strict)
    report["figure_hashes"] = _figure_hashes(root)
    report["paper_size_bytes"] = paper.stat().st_size
    _write_reports(root, report, visual)
    return report


def load_report(workspace: Path) -> dict[str, Any] | None:
    """Load the saved layout report when it exists."""
    try:
        return json.loads((Path(workspace) / REPORT_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def report_is_fresh(report: dict[str, Any] | None, workspace: Path) -> bool:
    """True only when *report* exists and still matches the current PDF bytes."""
    paper = Path(workspace) / PAPER_PATH
    if not isinstance(report, dict) or not paper.is_file():
        return False
    declared = report.get("paper_sha256")
    if not isinstance(declared, str) or not declared:
        return False
    return sha256_file(paper) == declared


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit the rendered Huawei Cup paper and its figures."
    )
    parser.add_argument("--workspace", type=Path, required=True, help="contest workspace")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail on missing or stale reports, tiny text, clipping and unusable pages",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    workspace = Path(args.workspace)
    report = audit_rendered_output(workspace, strict=args.strict)
    print(
        json.dumps(
            {"status": report["status"], "passed": report["passed"], "summary": report["summary"]},
            ensure_ascii=False,
        )
    )
    for issue in report["findings"]:
        print(f"[{issue['severity']}] {issue['code']}: {issue['message']}")
    for item in report["unavailable"]:
        print(f"[unverified] {item}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
