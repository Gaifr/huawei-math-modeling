"""Deterministic validation of result evidence and model identity.

An empty finding list means machine validation passed. Findings never claim that
the mathematics is correct; they only prove that every recorded result is bound
to real, current, traceable artifacts.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any

try:  # Support both package imports and direct CLI execution.
    from .common import atomic_write_json, sha256_file
except ImportError:  # pragma: no cover - direct execution path
    from common import atomic_write_json, sha256_file

EVIDENCE_PATH = Path("results") / "result-evidence.json"
CODE_MANIFEST_PATH = Path("code") / "code-manifest.json"
FIGURE_MANIFEST_PATH = Path("figures") / "figure-manifest.json"
STATE_PATH = Path(".huawei-modeling") / "state.json"
CHECK_REPORT_PATH = Path("results") / "evidence-check.json"

SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
RESULT_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*(\.[A-Za-z0-9][A-Za-z0-9_-]*)+$")

# Solver or heuristic names that must never be registered as a model identity.
SOLVER_NAMES = (
    "gurobi",
    "cplex",
    "highs",
    "glpk",
    "scip",
    "ipopt",
    "cbc",
    "mosek",
    "xpress",
    "lindo",
    "genetic algorithm",
    "particle swarm",
    "simulated annealing",
    "branch and bound",
    "ant colony",
    "differential evolution",
    "tabu search",
    "or tools",
    "cp sat",
    "fmincon",
    "lsqnonlin",
)

# Words that show a model identity really names a model rather than a solver.
MODEL_KEYWORDS = (
    "model",
    "programming",
    "optimisation",
    "optimization",
    "equation",
    "regression",
    "clustering",
    "network",
    "differential",
    "statistical",
    "markov",
    "simulation",
    "queueing",
    "graph",
    "dynamics",
    "forecast",
    "classification",
    "evaluation",
    "theory",
)

DECIMAL_PATTERNS = (
    re.compile(r"(\d+)\s*(?:decimal places?|decimals?)", re.IGNORECASE),
    re.compile(r"(\d+)\s*位小数"),
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Findings:
    """Accumulates every finding instead of stopping at the first failure."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def add(
        self, code: str, severity: str, message: str, paths: list[Any] | None = None
    ) -> None:
        self.items.append(
            {
                "issue_id": f"{code}-{len(self.items) + 1:03d}",
                "severity": severity,
                "code": code,
                "message": message,
                "paths": [str(item) for item in (paths or [])],
            }
        )


def _read_json(path: Path) -> tuple[Any, str | None]:
    if not path.is_file():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, str(exc)


def _nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return bool(value)
    return value is not None


def _looks_like_solver(model_identity: str) -> bool:
    normalized = " ".join(model_identity.lower().replace("-", " ").split())
    if any(keyword in normalized for keyword in MODEL_KEYWORDS):
        return False
    tokens = set(normalized.replace(",", " ").split())
    for name in SOLVER_NAMES:
        candidate = name.replace("-", " ")
        if " " in candidate:
            if candidate in normalized:
                return True
        elif candidate in tokens:
            return True
    return False


def _stale_artifacts(root: Path) -> list[str]:
    state, error = _read_json(root / STATE_PATH)
    if error or not isinstance(state, dict):
        return []
    stale = state.get("stale_artifacts")
    if not isinstance(stale, list):
        return []
    return [str(item) for item in stale if isinstance(item, str)]


def _is_stale(relative: str, stale: list[str]) -> bool:
    cleaned = relative.strip().lstrip("./")
    for item in stale:
        entry = item.strip().lstrip("./")
        if not entry:
            continue
        if cleaned == entry or cleaned.startswith(entry.rstrip("/") + "/"):
            return True
    return False


def _figure_index(root: Path) -> tuple[set[str], set[str]]:
    manifest, error = _read_json(root / FIGURE_MANIFEST_PATH)
    if error or not isinstance(manifest, dict):
        return set(), set()
    identifiers: set[str] = set()
    paths: set[str] = set()
    for entry in manifest.get("figures", []) if isinstance(manifest.get("figures"), list) else []:
        if not isinstance(entry, dict):
            continue
        for key in ("id", "figure_id"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                identifiers.add(value.strip())
        value = entry.get("path")
        if isinstance(value, str) and value.strip():
            paths.add(value.strip())
    return identifiers, paths


def _check_source_entry(
    root: Path, entry: Any, label: str, stale: list[str], findings: Findings
) -> None:
    if not isinstance(entry, dict):
        findings.add(
            "invalid_source_entry", "P1", f"{label} 的 source_files 条目不是对象", [EVIDENCE_PATH]
        )
        return
    relative = entry.get("path")
    if not isinstance(relative, str) or not relative.strip():
        findings.add(
            "invalid_source_entry", "P1", f"{label} 的 source_files 条目缺少 path", [EVIDENCE_PATH]
        )
        return
    relative = relative.strip()
    if _is_stale(relative, stale):
        findings.add(
            "stale_evidence", "P0", f"{label} 的证据来自过期产物：{relative}", [relative]
        )
    candidate = root / relative
    if not candidate.is_file():
        findings.add(
            "source_file_missing", "P0", f"{label} 引用的源文件不存在：{relative}", [relative]
        )
        return
    declared = entry.get("sha256")
    if not isinstance(declared, str) or not SHA256_PATTERN.match(declared):
        findings.add(
            "source_hash_missing", "P0", f"{label} 的源文件缺少合法 sha256：{relative}", [relative]
        )
        return
    if sha256_file(candidate) != declared:
        findings.add(
            "source_hash_mismatch", "P0", f"{label} 的源文件哈希不匹配：{relative}", [relative]
        )


def _check_precision(result: dict[str, Any], label: str, findings: Findings) -> None:
    precision = result.get("precision")
    display = result.get("display_value")
    if not isinstance(precision, str) or not isinstance(display, str):
        return
    expected: int | None = None
    for pattern in DECIMAL_PATTERNS:
        match = pattern.search(precision)
        if match:
            expected = int(match.group(1))
            break
    if expected is None:
        return
    cleaned = display.strip().replace(",", "").replace("%", "")
    match = re.fullmatch(r"[+-]?\d+(?:\.(\d+))?", cleaned)
    if not match:
        return
    digits = match.group(1) or ""
    if len(digits) != expected:
        findings.add(
            "precision_mismatch",
            "P2",
            f"{label} 的 display_value 与 precision 不一致：{display} / {precision}",
            [EVIDENCE_PATH],
        )


def _check_citations(
    root: Path,
    result: dict[str, Any],
    label: str,
    figure_ids: set[str],
    figure_paths: set[str],
    findings: Findings,
) -> None:
    citations = result.get("citations")
    if not isinstance(citations, list):
        return
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        figure = citation.get("figure")
        if isinstance(figure, str) and figure.strip():
            relative = figure.strip()
            if relative not in figure_paths and not (root / relative).is_file():
                findings.add(
                    "missing_citation_target",
                    "P1",
                    f"{label} 引用的图不存在：{relative}",
                    [relative],
                )
        figure_id = citation.get("figure_id")
        if isinstance(figure_id, str) and figure_id.strip():
            if figure_id.strip() not in figure_ids:
                findings.add(
                    "missing_citation_target",
                    "P1",
                    f"{label} 引用的图 id 不在 figure-manifest 中：{figure_id.strip()}",
                    [FIGURE_MANIFEST_PATH],
                )
        location = citation.get("paper_location")
        if isinstance(location, str) and location.strip():
            target = location.split("#", 1)[0].strip()
            if target and not (root / target).is_file():
                findings.add(
                    "missing_citation_target",
                    "P1",
                    f"{label} 引用的论文位置不存在：{location.strip()}",
                    [target],
                )


def _check_result(
    root: Path,
    result: Any,
    index: int,
    seen_ids: set[str],
    stale: list[str],
    figure_ids: set[str],
    figure_paths: set[str],
    findings: Findings,
) -> None:
    if not isinstance(result, dict):
        findings.add(
            "invalid_result_entry", "P1", f"results[{index}] 不是对象", [EVIDENCE_PATH]
        )
        return

    raw_id = result.get("id")
    if not isinstance(raw_id, str) or not raw_id.strip():
        label = f"results[{index}]"
        findings.add("invalid_result_id", "P1", f"{label} 缺少结果 id", [EVIDENCE_PATH])
    else:
        result_id = raw_id.strip()
        label = result_id
        if result_id in seen_ids:
            findings.add(
                "duplicate_result_id", "P0", f"结果 id 重复：{result_id}", [EVIDENCE_PATH]
            )
        elif not RESULT_ID_PATTERN.match(result_id):
            findings.add(
                "unstable_result_id",
                "P1",
                f"结果 id 不符合稳定命名（应为 <问题>.<短名>）：{result_id}",
                [EVIDENCE_PATH],
            )
        seen_ids.add(result_id)

    model_identity = result.get("model_identity")
    if not isinstance(model_identity, str) or not model_identity.strip():
        findings.add(
            "missing_model_identity", "P1", f"{label} 缺少 model_identity", [EVIDENCE_PATH]
        )
    elif _looks_like_solver(model_identity):
        findings.add(
            "solver_as_model",
            "P0",
            f"{label} 把求解器登记为模型身份：{model_identity}",
            [EVIDENCE_PATH],
        )

    if not _nonempty(result.get("mechanism")):
        findings.add("missing_mechanism", "P2", f"{label} 缺少 mechanism", [EVIDENCE_PATH])
    if not _nonempty(result.get("solver_algorithm")):
        findings.add(
            "missing_solver_algorithm", "P2", f"{label} 缺少 solver_algorithm", [EVIDENCE_PATH]
        )

    sources = result.get("source_files")
    source_entries = sources if isinstance(sources, list) else []
    if not source_entries:
        findings.add(
            "missing_source_file", "P0", f"{label} 没有登记任何 source_files", [EVIDENCE_PATH]
        )
    for entry in source_entries:
        _check_source_entry(root, entry, label, stale, findings)

    if not _nonempty(result.get("run_command")) or not _nonempty(result.get("environment")):
        findings.add(
            "missing_run_record",
            "P1",
            f"{label} 缺少 run_command 或 environment",
            [EVIDENCE_PATH],
        )

    _check_precision(result, label, findings)
    _check_citations(root, result, label, figure_ids, figure_paths, findings)


def _check_code_manifest(root: Path, manifest: Any, findings: Findings) -> None:
    if not isinstance(manifest, dict):
        return
    files = manifest.get("files")
    if not isinstance(files, list):
        return
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
                "code_manifest_missing_file",
                "P1",
                f"code-manifest 登记的文件不存在：{relative}",
                [relative],
            )
            continue
        declared = entry.get("sha256")
        if isinstance(declared, str) and SHA256_PATTERN.match(declared):
            if sha256_file(candidate) != declared:
                findings.add(
                    "code_manifest_hash_mismatch",
                    "P1",
                    f"code-manifest 哈希不匹配：{relative}",
                    [relative],
                )


def validate_evidence(workspace: Path) -> list[dict[str, Any]]:
    """Return every evidence-contract finding for *workspace*; empty means pass."""
    root = Path(workspace)
    findings = Findings()

    evidence, error = _read_json(root / EVIDENCE_PATH)
    if error == "missing":
        findings.add(
            "missing_evidence_file",
            "P0",
            f"缺少证据文件：{EVIDENCE_PATH}",
            [EVIDENCE_PATH],
        )
        return findings.items
    if error:
        findings.add(
            "invalid_evidence_json",
            "P0",
            f"{EVIDENCE_PATH} 无法解析：{error}",
            [EVIDENCE_PATH],
        )
        return findings.items

    results = evidence.get("results") if isinstance(evidence, dict) else None
    if not isinstance(results, list):
        findings.add(
            "invalid_evidence_json",
            "P0",
            f"{EVIDENCE_PATH} 缺少 results 数组",
            [EVIDENCE_PATH],
        )
        return findings.items

    code_manifest, manifest_error = _read_json(root / CODE_MANIFEST_PATH)
    if manifest_error and manifest_error != "missing":
        findings.add(
            "invalid_code_manifest",
            "P1",
            f"{CODE_MANIFEST_PATH} 无法解析：{manifest_error}",
            [CODE_MANIFEST_PATH],
        )
        code_manifest = None

    stale = _stale_artifacts(root)
    figure_ids, figure_paths = _figure_index(root)
    seen_ids: set[str] = set()
    for index, result in enumerate(results):
        _check_result(
            root, result, index, seen_ids, stale, figure_ids, figure_paths, findings
        )

    _check_code_manifest(root, code_manifest, findings)
    return findings.items


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Huawei Cup result evidence and model identity."
    )
    parser.add_argument("--workspace", type=Path, required=True, help="contest workspace")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    workspace = Path(args.workspace)
    issues = validate_evidence(workspace)
    summary = {
        level: sum(1 for issue in issues if issue["severity"] == level)
        for level in ("P0", "P1", "P2", "P3")
    }
    report = {
        "schema_version": 1,
        "check": "evidence",
        "generated_at": _timestamp(),
        "summary": summary,
        "issues": issues,
    }
    atomic_write_json(workspace / CHECK_REPORT_PATH, report)
    passed = summary["P0"] == 0 and summary["P1"] == 0
    print(json.dumps({"passed": passed, "summary": summary}, ensure_ascii=False))
    for issue in issues:
        print(f"[{issue['severity']}] {issue['code']}: {issue['message']}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
