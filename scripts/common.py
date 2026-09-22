"""Shared, standard-library helpers for Huawei Cup contest workspaces."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a regular file."""
    candidate = Path(path)
    if not candidate.is_file():
        raise ValueError(f"Expected a regular file: {candidate}")

    digest = hashlib.sha256()
    with candidate.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: Any) -> None:
    """Atomically replace *path* with UTF-8 JSON, creating parents if needed."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, target)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def append_event(workspace: Path, event: str, details: dict[str, Any]) -> dict[str, Any]:
    """Append one durable, public-safe event record and return it."""
    event_name = str(event).strip()
    if not event_name:
        raise ValueError("Event name must not be empty")
    if not isinstance(details, dict):
        raise ValueError("Event details must be an object")

    log_path = Path(workspace) / ".huawei-modeling" / "events.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": event_name,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "details": details,
    }
    encoded = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    if not log_path.exists():
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{log_path.name}.", suffix=".tmp", dir=log_path.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, log_path)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
        return record

    with log_path.open("ab") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return record


def utc_timestamp() -> str:
    """Return the current UTC time as an ISO-8601 string with a Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class IssueLog:
    """Collects every finding instead of stopping at the first failure."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def add(
        self, code: str, severity: str, message: str, paths: Iterable[Any] | None = None
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

    def summary(self) -> dict[str, int]:
        return {
            level: sum(1 for issue in self.items if issue["severity"] == level)
            for level in ("P0", "P1", "P2", "P3")
        }

    def blocking(self) -> bool:
        """True when an unresolved P0 or P1 finding exists."""
        summary = self.summary()
        return bool(summary["P0"] or summary["P1"])
