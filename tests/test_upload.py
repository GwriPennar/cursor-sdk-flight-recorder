"""Tests for JSONL upload parsing used by the UI."""

import json

from src.trace import normalize_event


def test_upload_jsonl_parsing():
    lines = [
        json.dumps({"type": "user", "summary": "hi", "content": "hello"}),
        "not-json",
        json.dumps({"type": "assistant", "summary": "ok", "content": "done"}),
    ]
    records = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
            if isinstance(raw, dict):
                records.append(normalize_event(raw))
        except json.JSONDecodeError:
            continue
    assert len(records) == 2
    assert records[0]["type"] == "user"
