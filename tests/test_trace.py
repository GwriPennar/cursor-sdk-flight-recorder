"""Tests for trace module."""

import json
from pathlib import Path

import pytest

from src.trace import (
    duration_seconds,
    event_counts,
    extract_prompt_and_result,
    load_jsonl,
    normalize_event,
    public_safety_scan,
    save_jsonl,
    timeline_rows,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "demo_trace.jsonl"


def test_load_demo_fixture():
    records = load_jsonl(FIXTURE)
    assert len(records) >= 10


def test_save_and_reload(tmp_path):
    records = load_jsonl(FIXTURE)
    out = tmp_path / "out.jsonl"
    save_jsonl(records, out)
    again = load_jsonl(out)
    assert len(again) == len(records)


def test_malformed_row_skipped(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"type":"user","summary":"ok"}\nnot json\n{"type":"assistant","summary":"x"}\n')
    records = load_jsonl(path)
    assert len(records) >= 2
    assert any(r.get("type") == "warning" for r in records)


def test_event_counts():
    records = load_jsonl(FIXTURE)
    counts = event_counts(records)
    assert counts.get("user", 0) >= 1
    assert counts.get("assistant", 0) >= 1


def test_extract_prompt_and_result():
    records = load_jsonl(FIXTURE)
    prompt, result = extract_prompt_and_result(records)
    assert "Summarize" in prompt
    assert "greet" in result.lower() or "docstring" in result.lower()


def test_duration_seconds():
    records = load_jsonl(FIXTURE)
    dur = duration_seconds(records)
    assert dur is not None
    assert dur >= 0


def test_timeline_rows():
    records = load_jsonl(FIXTURE)
    rows = timeline_rows(records)
    assert rows[0]["index"] == 1
    assert "label" in rows[0]


def test_normalize_event_defaults():
    ev = normalize_event({})
    assert ev["type"] == "system"
    assert "timestamp" in ev


def test_public_safety_scan_clean():
    records = load_jsonl(FIXTURE)
    assert public_safety_scan(records) == []


def test_public_safety_detects_secret_pattern():
    records = [
        normalize_event(
            {
                "type": "assistant",
                "content": "key=cursor_abcdefghijklmnopqrstuvwxyz123456",
            }
        )
    ]
    findings = public_safety_scan(records)
    assert len(findings) >= 1
