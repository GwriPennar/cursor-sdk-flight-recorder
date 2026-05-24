"""JSONL trace load/save and event normalization."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SECRET_PATTERNS = [
    re.compile(r"cursor_[a-zA-Z0-9]{20,}", re.I),
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.I),
    re.compile(r"api[_-]?key\s*[:=]\s*['\"]?\S+", re.I),
    re.compile(r"password\s*[:=]\s*['\"]?\S+", re.I),
    re.compile(r"secret\s*[:=]\s*['\"]?\S+", re.I),
    re.compile(r"token\s*[:=]\s*['\"]?\S+", re.I),
]

PRIVATE_MARKERS = [
    "cortex foundry",
    "nexus",
    "customer data",
    "proprietary",
    "internal only",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_jsonl(path: str | Path) -> list[dict]:
    """Load JSONL trace; skip malformed rows."""
    path = Path(path)
    records: list[dict] = []
    if not path.exists():
        return records
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                records.append(
                    normalize_event(
                        {
                            "type": "warning",
                            "summary": f"Malformed JSONL row at line {line_no}",
                            "status": "warn",
                        }
                    )
                )
                continue
            if isinstance(raw, dict):
                records.append(normalize_event(raw))
    return records


def save_jsonl(records: list[dict], path: str | Path) -> None:
    """Persist normalized records as JSONL."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = [normalize_event(r) for r in records]
    with path.open("w", encoding="utf-8") as f:
        for rec in normalized:
            f.write(json.dumps(rec, default=str) + "\n")


def normalize_event(event: dict) -> dict:
    """Ensure every event follows the flight-recorder schema."""
    ts = event.get("timestamp") or _utc_now_iso()
    etype = str(event.get("type") or "system").lower()
    role = str(event.get("role") or etype)
    summary = str(event.get("summary") or event.get("message") or "")[:500]
    content = str(event.get("content") or event.get("text") or "")
    status = str(event.get("status") or "info").lower()
    if status not in ("pass", "warn", "fail", "info"):
        status = "info"
    metadata = event.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "timestamp": ts,
        "type": etype,
        "role": role,
        "summary": summary,
        "content": content,
        "status": status,
        "metadata": metadata,
    }


def event_counts(records: list[dict]) -> dict[str, int]:
    """Count events by type."""
    counts: dict[str, int] = {}
    for rec in records:
        t = rec.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: (-x[1], x[0])))


def timeline_rows(records: list[dict]) -> list[dict]:
    """Build timeline rows for visualization."""
    rows = []
    for idx, rec in enumerate(records, start=1):
        label = (rec.get("summary") or rec.get("type") or "")[:60]
        rows.append(
            {
                "index": idx,
                "timestamp": rec.get("timestamp", ""),
                "order": idx,
                "type": rec.get("type", "unknown"),
                "role": rec.get("role", ""),
                "label": label,
                "status": rec.get("status", "info"),
                "summary": rec.get("summary", ""),
            }
        )
    return rows


def extract_prompt_and_result(records: list[dict]) -> tuple[str, str]:
    """Extract user prompt and final assistant result from trace."""
    prompt = ""
    result = ""
    for rec in records:
        if rec.get("type") == "user" and not prompt:
            prompt = rec.get("content") or rec.get("summary") or ""
        if rec.get("type") == "assistant":
            text = rec.get("content") or rec.get("summary") or ""
            if text:
                result = text
    if not result:
        for rec in reversed(records):
            if rec.get("type") == "self_eval":
                result = rec.get("content") or rec.get("summary") or ""
                break
    return prompt, result


def duration_seconds(records: list[dict]) -> float | None:
    """Compute duration from first to last timestamp if parseable."""
    stamps: list[datetime] = []
    for rec in records:
        ts = rec.get("timestamp")
        if not ts:
            continue
        try:
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            stamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
        except (ValueError, TypeError):
            continue
    if len(stamps) < 2:
        return None
    delta = max(stamps) - min(stamps)
    return max(delta.total_seconds(), 0.0)


def public_safety_scan(records: list[dict]) -> list[dict]:
    """Return findings for secret-like or private-marker content in trace."""
    findings: list[dict] = []
    for idx, rec in enumerate(records, start=1):
        blob = " ".join(
            str(rec.get(k, ""))
            for k in ("summary", "content", "role")
        )
        lower = blob.lower()
        for pat in SECRET_PATTERNS:
            if pat.search(blob):
                findings.append(
                    {
                        "index": idx,
                        "severity": "fail",
                        "reason": "Possible secret-like value in trace text",
                        "type": rec.get("type"),
                    }
                )
                break
        for marker in PRIVATE_MARKERS:
            if marker in lower:
                findings.append(
                    {
                        "index": idx,
                        "severity": "warn",
                        "reason": f"Private marker detected: {marker}",
                        "type": rec.get("type"),
                    }
                )
    return findings


def filter_records(
    records: list[dict],
    *,
    types: list[str] | None = None,
    statuses: list[str] | None = None,
) -> list[dict]:
    """Filter trace by event type and/or status."""
    out = records
    if types:
        type_set = {t.lower() for t in types}
        out = [r for r in out if r.get("type", "").lower() in type_set]
    if statuses:
        status_set = {s.lower() for s in statuses}
        out = [r for r in out if r.get("status", "info").lower() in status_set]
    return out
