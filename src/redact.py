"""Redact secrets and PII from trace text before saving public fixtures."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

# API / token patterns
_REDACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"cursor_[a-zA-Z0-9]{16,}", re.I), "[REDACTED_CURSOR_KEY]"),
    (re.compile(r"crsr_[a-zA-Z0-9]{16,}", re.I), "[REDACTED_CURSOR_KEY]"),
    (re.compile(r"sk-[a-zA-Z0-9]{20,}", re.I), "[REDACTED_TOKEN]"),
    (re.compile(r"api[_-]?key\s*[:=]\s*['\"]?\S+", re.I), "api_key=[REDACTED]"),
    (re.compile(r"Bearer\s+[a-zA-Z0-9._\-]+", re.I), "Bearer [REDACTED]"),
    # Long opaque tokens (32+ alnum)
    (re.compile(r"\b[a-zA-Z0-9_\-]{32,}\b"), "[REDACTED_TOKEN]"),
    # Email-like
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[REDACTED_EMAIL]"),
    # Unix home paths
    (re.compile(r"/Users/[a-zA-Z0-9._\-]+"), "/Users/[REDACTED]"),
    (re.compile(r"/home/[a-zA-Z0-9._\-]+"), "/home/[REDACTED]"),
    # Windows user paths
    (re.compile(r"[A-Za-z]:\\Users\\[^\\]+", re.I), "C:/Users/[REDACTED]"),
]


def redact_text(text: str) -> str:
    """Apply redaction patterns to a string."""
    if not text:
        return text
    out = text
    for pattern, replacement in _REDACT_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def redact_value(value: Any) -> Any:
    """Recursively redact strings inside dict/list structures."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    return value


def redact_event(event: dict) -> dict:
    """Return a copy of an event with redacted string fields."""
    out = deepcopy(event)
    for key in ("summary", "content", "role"):
        if key in out and isinstance(out[key], str):
            out[key] = redact_text(out[key])
    if "metadata" in out:
        out["metadata"] = redact_value(out.get("metadata", {}))
    return out


def redact_trace(records: list[dict]) -> list[dict]:
    """Redact all events in a trace."""
    return [redact_event(r) for r in records]


def annotate_redacted_fixture(records: list[dict], *, note: str) -> list[dict]:
    """Prepend or update system event noting redaction / capture context."""
    from src.trace import normalize_event

    banner = normalize_event(
        {
            "type": "system",
            "role": "system",
            "summary": "Redacted live SDK sample trace",
            "content": note,
            "status": "info",
            "metadata": {
                "fixture": "live_sample_redacted",
                "redacted": True,
                "public_safe": True,
            },
        }
    )
    # Avoid duplicate banners on re-run
    if records and records[0].get("metadata", {}).get("fixture") == "live_sample_redacted":
        return [banner] + records[1:]
    return [banner] + redact_trace(records)
