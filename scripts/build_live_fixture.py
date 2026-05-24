#!/usr/bin/env python3
"""Capture a live SDK trace, redact, and write fixtures/live_sample_redacted.jsonl."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.env_loader import load_project_env
from src.redact import annotate_redacted_fixture
from src.runner import run_cursor_agent_local
from src.trace import public_safety_scan, save_jsonl

LIVE_PROMPT = (
    "Summarize this tiny repository. Do not modify files. "
    "Return the key files inspected and one safe improvement."
)


def main() -> int:
    load_project_env()
    if not os.environ.get("CURSOR_API_KEY", "").strip():
        print("CURSOR_API_KEY not set — cannot capture live fixture.", file=sys.stderr)
        return 1

    repo = ROOT / "examples" / "tiny_repo"
    print("Running live SDK capture (this may take 1–2 minutes)…")
    records = run_cursor_agent_local(str(repo), LIVE_PROMPT, model="composer-2.5")

    note = (
        "Redacted trace from a real local Cursor Python SDK run against examples/tiny_repo. "
        "Secrets and home paths are redacted. Partial captures may occur if the local bridge "
        "times out; status events still reflect real SDK stream output."
    )
    redacted = annotate_redacted_fixture(records, note=note)
    for ev in redacted:
        ev.setdefault("metadata", {})["trace_source"] = "redacted_live"

    findings = public_safety_scan(redacted)
    if any(f.get("severity") == "fail" for f in findings):
        print("Public safety scan failed — not writing fixture:", findings, file=sys.stderr)
        return 2

    out = ROOT / "fixtures" / "live_sample_redacted.jsonl"
    save_jsonl(redacted, out)
    print(f"Wrote {len(redacted)} events to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
