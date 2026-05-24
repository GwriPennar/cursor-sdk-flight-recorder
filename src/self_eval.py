"""Deterministic project self-evaluation (offline-safe)."""

from __future__ import annotations

from src.gates import gate_summary
from src.trace import duration_seconds, event_counts, public_safety_scan


def evaluate_project(records: list[dict], gates: list[dict]) -> dict:
    """
    Score and summarize the flight recorder project without calling an LLM.
    """
    gs = gate_summary(gates)
    counts = event_counts(records)
    safety = public_safety_scan(records)
    has_timeline = len(records) >= 5
    has_gates = len(gates) >= 5
    has_assistant = counts.get("assistant", 0) > 0
    has_tool = counts.get("tool", 0) > 0
    dur = duration_seconds(records)

    visual_score = 5
    if has_timeline:
        visual_score += 2
    if has_gates:
        visual_score += 1
    if dur is not None:
        visual_score += 1
    if len(counts) >= 3:
        visual_score += 1
    visual_score = min(visual_score, 10)

    public_score = 10
    if safety:
        public_score -= min(len(safety) * 2, 6)
    if gs.get("fail", 0) > 0:
        public_score -= 2
    public_score = max(0, min(public_score, 10))

    sdk_score = 6
    if has_assistant:
        sdk_score += 2
    if has_tool:
        sdk_score += 1
    if any(r.get("metadata", {}).get("sdk_index") is not None for r in records):
        sdk_score += 1
    sdk_score = min(sdk_score, 10)

    what_works = [
        "Demo mode loads a realistic JSONL fixture without an API key",
        "Streamlit dashboard shows timeline, counts, gates, and reports",
        "Review gates check repo path, prompt, result, and public safety",
        "Markdown and HTML reports export to reports/latest.*",
    ]
    if gs.get("pass", 0) >= 6:
        what_works.append("Most review gates pass on the demo trace")

    limitations = [
        "Live Cursor SDK mode requires cursor-sdk and CURSOR_API_KEY",
        "SDK beta APIs may change event shapes between versions",
        "HTML report is a simple conversion, not full Markdown rendering",
        "No multi-run comparison yet",
    ]

    next_visual_features = [
        "Side-by-side diff of two saved traces",
        "Token/cost overlay when SDK exposes usage metadata",
        "GitHub Actions artifact upload for JSONL traces",
        "PR comment bot that posts gate summary",
        "Interactive tool-call argument inspector with syntax highlight",
    ]

    return {
        "visual_usefulness_score": visual_score,
        "public_safety_score": public_score,
        "sdk_usefulness_score": sdk_score,
        "what_works": what_works,
        "limitations": limitations,
        "next_visual_features": next_visual_features,
    }
