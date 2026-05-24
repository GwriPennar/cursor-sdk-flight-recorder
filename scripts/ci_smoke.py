#!/usr/bin/env python3
"""CI smoke: load fixtures, run gates, generate report."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gates import run_gates
from src.report import render_html_report, render_markdown_report, save_report
from src.trace import load_jsonl, public_safety_scan

REPO = ROOT / "examples" / "tiny_repo"
FIXTURES = [
    ROOT / "fixtures" / "demo_trace.jsonl",
    ROOT / "fixtures" / "live_sample_redacted.jsonl",
]


def main() -> int:
    reports_dir = ROOT / "reports"
    for fixture in FIXTURES:
        if not fixture.exists():
            if fixture.name == "live_sample_redacted.jsonl":
                print(f"skip missing optional fixture: {fixture.name}")
                continue
            print(f"missing required fixture: {fixture}", file=sys.stderr)
            return 1
        records = load_jsonl(fixture)
        assert records, f"empty trace: {fixture}"
        findings = public_safety_scan(records)
        fails = [f for f in findings if f.get("severity") == "fail"]
        if fails:
            print(f"public safety fail on {fixture.name}: {fails}", file=sys.stderr)
            return 2
        gates = run_gates(REPO, records, live_mode=False)
        md = render_markdown_report(records, gates, title=f"CI Smoke — {fixture.stem}")
        html = render_html_report(md)
        save_report(md, html, reports_dir)
        print(f"ok: {fixture.name} ({len(records)} events, {len(gates)} gates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
