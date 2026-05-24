"""Tests for review gates."""

from pathlib import Path

from src.gates import gate_summary, run_gates
from src.trace import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "demo_trace.jsonl"
LIVE_FIXTURE = ROOT / "fixtures" / "live_sample_redacted.jsonl"
TINY_REPO = ROOT / "examples" / "tiny_repo"


def test_gates_on_demo_trace():
    records = load_jsonl(FIXTURE)
    gates = run_gates(TINY_REPO, records, live_mode=False)
    assert len(gates) >= 7
    names = {g["name"] for g in gates}
    assert "repo_path_exists" in names
    assert "user_prompt_found" in names
    assert "report_renderable" in names


def test_gate_statuses_valid():
    records = load_jsonl(FIXTURE)
    gates = run_gates(TINY_REPO, records)
    for g in gates:
        assert g["status"] in ("pass", "warn", "fail")
        assert g["name"]
        assert g["detail"]


def test_gate_summary_counts():
    records = load_jsonl(FIXTURE)
    gates = run_gates(TINY_REPO, records)
    summary = gate_summary(gates)
    assert summary["pass"] + summary["warn"] + summary["fail"] == len(gates)


def test_gates_on_redacted_live_fixture():
    records = load_jsonl(LIVE_FIXTURE)
    gates = run_gates(TINY_REPO, records, live_mode=False)
    assert len(records) >= 5
    assert any(g["name"] == "user_prompt_found" and g["status"] == "pass" for g in gates)
    assert any(g["name"] == "demo_trace_public_safe" for g in gates)


def test_missing_repo_fails_gate(tmp_path):
    records = load_jsonl(FIXTURE)
    gates = run_gates(tmp_path / "nonexistent", records)
    repo_gate = next(g for g in gates if g["name"] == "repo_path_exists")
    assert repo_gate["status"] == "fail"
