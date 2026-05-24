"""Tests for trace redaction."""

from pathlib import Path

from src.redact import annotate_redacted_fixture, redact_text, redact_trace
from src.trace import load_jsonl, public_safety_scan

ROOT = Path(__file__).resolve().parents[1]
LIVE_FIXTURE = ROOT / "fixtures" / "live_sample_redacted.jsonl"


def test_redact_api_key_pattern():
    raw = "key=cursor_abcdefghijklmnopqrstuvwxyz1234567890"
    out = redact_text(raw)
    assert "cursor_" not in out
    assert "REDACTED" in out


def test_redact_home_path():
    raw = "read /Users/alice/project/foo.py"
    out = redact_text(raw)
    assert "/Users/alice" not in out
    assert "[REDACTED]" in out


def test_redact_email():
    raw = "contact dev@example.com please"
    out = redact_text(raw)
    assert "dev@example.com" not in out


def test_redact_trace_list():
    records = [
        {
            "timestamp": "t",
            "type": "user",
            "content": "/Users/bob/code and cursor_abc123456789012345678901234567890",
            "summary": "x",
            "status": "info",
            "metadata": {},
        }
    ]
    out = redact_trace(records)
    assert "[REDACTED]" in out[0]["content"]


def test_live_fixture_exists_and_safe():
    assert LIVE_FIXTURE.exists()
    records = load_jsonl(LIVE_FIXTURE)
    assert len(records) >= 2
    assert records[0].get("metadata", {}).get("redacted") is True
    fails = [f for f in public_safety_scan(records) if f.get("severity") == "fail"]
    assert fails == []


def test_annotate_redacted_banner():
    records = [{"type": "user", "summary": "hi", "content": "x", "status": "info"}]
    out = annotate_redacted_fixture(records, note="test note")
    assert out[0]["type"] == "system"
    assert "Redacted" in out[0]["summary"]
