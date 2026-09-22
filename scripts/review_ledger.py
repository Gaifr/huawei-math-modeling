"""Root-cause deduplication for technical and judge-style paper reviews.

The ledger is the single record of review findings. Duplicate deductions for the
same root cause are never summed, and findings from a different paper version
are rejected instead of imported.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

try:  # Support both package imports and direct CLI execution.
    from .common import atomic_write_json, utc_timestamp
except ImportError:  # pragma: no cover - direct execution path
    from common import atomic_write_json, utc_timestamp

LEDGER_PATH = Path("review") / "issue-ledger.json"
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
SETTLED_STATUSES = ("accepted", "resolved")


def _higher_severity(left: Any, right: Any) -> str:
    left_value = left if left in SEVERITY_ORDER else "P3"
    right_value = right if right in SEVERITY_ORDER else "P3"
    return left_value if SEVERITY_ORDER[left_value] <= SEVERITY_ORDER[right_value] else right_value


def _union(existing: list[str], incoming: Any) -> list[str]:
    values = list(existing)
    if isinstance(incoming, list):
        for item in incoming:
            text = str(item)
            if text and text not in values:
                values.append(text)
    elif isinstance(incoming, str) and incoming and incoming not in values:
        values.append(incoming)
    return values


def _merge_status(existing: Any, incoming: Any) -> str:
    current = existing if existing in ("open", *SETTLED_STATUSES) else "open"
    candidate = incoming if incoming in ("open", *SETTLED_STATUSES) else current
    if current in SETTLED_STATUSES:
        return current
    return candidate


def _identity(issue: dict[str, Any]) -> tuple[str, str] | None:
    root_stage = issue.get("root_stage")
    root_key = issue.get("root_key")
    if not isinstance(root_stage, str) or not root_stage.strip():
        return None
    if not isinstance(root_key, str) or not root_key.strip():
        return None
    return root_stage.strip(), root_key.strip()


def merge_issues(
    existing: Iterable[dict[str, Any]] | None, incoming: Iterable[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Merge *incoming* into *existing*, keyed by root cause (stage + key)."""
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    order: list[tuple[str, str]] = []
    for batch in (list(existing or []), list(incoming or [])):
        for raw in batch:
            if not isinstance(raw, dict):
                continue
            key = _identity(raw)
            if key is None:
                continue
            if key not in merged:
                merged[key] = {
                    "issue_id": f"{key[0]}:{key[1]}",
                    "root_stage": key[0],
                    "root_key": key[1],
                    "severity": raw.get("severity") if raw.get("severity") in SEVERITY_ORDER else "P3",
                    "locations": [],
                    "messages": [],
                    "evidence": [],
                    "affected_questions": [],
                    "status": "open",
                }
                order.append(key)
            record = merged[key]
            record["severity"] = _higher_severity(record["severity"], raw.get("severity"))
            record["locations"] = _union(record["locations"], raw.get("locations"))
            record["evidence"] = _union(record["evidence"], raw.get("evidence"))
            record["affected_questions"] = _union(
                record["affected_questions"], raw.get("affected_questions")
            )
            message = raw.get("message")
            if isinstance(message, str) and message.strip() and message not in record["messages"]:
                record["messages"].append(message)
            record["status"] = _merge_status(record["status"], raw.get("status"))
    for key in order:
        record = merged[key]
        record["message"] = record["messages"][0] if record["messages"] else ""
    return [merged[key] for key in order]


def summarize_issues(issues: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Count issues by severity, tracking accepted P1 findings separately."""
    counts = {level: 0 for level in SEVERITY_ORDER}
    open_p1 = 0
    total = 0
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        total += 1
        severity = issue.get("severity")
        if severity in counts:
            counts[severity] += 1
        if severity == "P1" and issue.get("status", "open") not in SETTLED_STATUSES:
            open_p1 += 1
    summary: dict[str, Any] = dict(counts)
    summary["total"] = total
    summary["open_P1"] = open_p1
    summary["blocking"] = bool(counts["P0"] or open_p1)
    return summary


def load_ledger(workspace: Path) -> dict[str, Any]:
    """Load the review ledger; raises when it has not been recorded yet."""
    path = Path(workspace) / LEDGER_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"Review ledger not found: {LEDGER_PATH.as_posix()}") from None
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Review ledger is unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Review ledger must be a JSON object")
    return payload


def record_review(
    workspace: Path, incoming: Iterable[dict[str, Any]], paper_sha256: str
) -> dict[str, Any]:
    """Record one review round for a specific paper version and return the ledger."""
    if not isinstance(paper_sha256, str) or not SHA256_PATTERN.match(paper_sha256):
        raise ValueError("paper_sha256 must be a 64-character lowercase hex digest")

    root = Path(workspace)
    path = root / LEDGER_PATH
    existing_issues: list[dict[str, Any]] = []
    revision_round = 1
    if path.is_file():
        current = load_ledger(root)
        recorded = current.get("paper_sha256")
        if isinstance(recorded, str) and recorded and recorded != paper_sha256:
            raise ValueError(
                "Refusing to merge findings from a different paper version: "
                f"ledger has {recorded}, review reports {paper_sha256}"
            )
        existing_issues = [
            issue for issue in current.get("issues", []) if isinstance(issue, dict)
        ]
        previous_round = current.get("revision_round")
        revision_round = (previous_round + 1) if isinstance(previous_round, int) else 2

    issues = merge_issues(existing_issues, incoming)
    ledger = {
        "schema_version": 1,
        "check": "review_ledger",
        "paper_sha256": paper_sha256,
        "revision_round": revision_round,
        "updated_at": utc_timestamp(),
        "issues": issues,
        "summary": summarize_issues(issues),
    }
    atomic_write_json(path, ledger)
    return ledger


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize the recorded review findings."
    )
    parser.add_argument("--workspace", type=Path, required=True, help="contest workspace")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    ledger = load_ledger(args.workspace)
    summary = summarize_issues(ledger.get("issues", []))
    print(
        json.dumps(
            {
                "paper_sha256": ledger.get("paper_sha256"),
                "revision_round": ledger.get("revision_round"),
                "summary": summary,
            },
            ensure_ascii=False,
        )
    )
    return 1 if summary["blocking"] else 0


if __name__ == "__main__":
    sys.exit(main())
