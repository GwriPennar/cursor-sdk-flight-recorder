"""Tests for self-evaluation."""

from src.gates import run_gates
from src.self_eval import evaluate_project
from src.trace import load_jsonl

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "demo_trace.jsonl"
TINY_REPO = ROOT / "examples" / "tiny_repo"


def test_evaluate_project_scores():
    records = load_jsonl(FIXTURE)
    gates = run_gates(TINY_REPO, records)
    ev = evaluate_project(records, gates)
    assert 0 <= ev["visual_usefulness_score"] <= 10
    assert 0 <= ev["public_safety_score"] <= 10
    assert 0 <= ev["sdk_usefulness_score"] <= 10


def test_evaluate_project_lists():
    records = load_jsonl(FIXTURE)
    gates = run_gates(TINY_REPO, records)
    ev = evaluate_project(records, gates)
    assert len(ev["what_works"]) >= 3
    assert len(ev["limitations"]) >= 2
    assert len(ev["next_visual_features"]) >= 3
