"""Tests for report generation."""

from pathlib import Path

from src.gates import run_gates
from src.report import render_html_report, render_markdown_report, save_report
from src.trace import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "demo_trace.jsonl"
TINY_REPO = ROOT / "examples" / "tiny_repo"


def test_markdown_report_sections():
    records = load_jsonl(FIXTURE)
    gates = run_gates(TINY_REPO, records)
    md = render_markdown_report(records, gates)
    assert "# Cursor SDK Flight Recorder Report" in md
    assert "## Gate results" in md
    assert "## User prompt" in md
    assert "## Final result" in md
    assert "## Public safety" in md
    assert "## Reproducibility" in md
    assert "## Limitations" in md


def test_html_report_generated():
    md = "# Title\n\n## Section\n\n- item"
    html = render_html_report(md)
    assert "<html" in html
    assert "Title" in html


def test_save_report_writes_files(tmp_path):
    records = load_jsonl(FIXTURE)
    gates = run_gates(TINY_REPO, records)
    md = render_markdown_report(records, gates)
    html = render_html_report(md)
    paths = save_report(md, html, tmp_path)
    assert Path(paths["markdown"]).exists()
    assert Path(paths["html"]).exists()
