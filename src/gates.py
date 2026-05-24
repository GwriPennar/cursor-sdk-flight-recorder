"""Review gates for agent run traces."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.report import render_markdown_report
from src.trace import extract_prompt_and_result, public_safety_scan


def _gate(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def run_gates(
    repo_path: str | Path,
    records: list[dict],
    *,
    live_mode: bool = False,
) -> list[dict]:
    """Run all review gates and return structured results."""
    repo = Path(repo_path)
    gates: list[dict[str, str]] = []

    # Repo path exists
    if repo.exists() and repo.is_dir():
        gates.append(_gate("repo_path_exists", "pass", f"Repository path exists: {repo}"))
    else:
        gates.append(_gate("repo_path_exists", "fail", f"Repository path not found: {repo}"))

    # Trace non-empty
    if records:
        gates.append(_gate("trace_non_empty", "pass", f"Trace has {len(records)} events"))
    else:
        gates.append(_gate("trace_non_empty", "fail", "Trace is empty"))

    # User prompt
    prompt, result = extract_prompt_and_result(records)
    if prompt.strip():
        gates.append(_gate("user_prompt_found", "pass", "User prompt present in trace"))
    else:
        gates.append(_gate("user_prompt_found", "fail", "No user prompt event found"))

    # Assistant result
    if result.strip():
        gates.append(_gate("assistant_result_found", "pass", "Assistant or result event found"))
    else:
        gates.append(_gate("assistant_result_found", "warn", "No final assistant result in trace"))

    # Secret scan in displayed trace
    safety = public_safety_scan(records)
    secret_fails = [f for f in safety if f.get("severity") == "fail"]
    if secret_fails:
        gates.append(
            _gate(
                "no_secret_patterns",
                "fail",
                f"{len(secret_fails)} event(s) may contain secret-like values",
            )
        )
    else:
        gates.append(_gate("no_secret_patterns", "pass", "No obvious secret patterns in trace"))

    # Report renderable
    try:
        md = render_markdown_report(records, gates)
        if md and "# " in md:
            gates.append(_gate("report_renderable", "pass", "Markdown report renders successfully"))
        else:
            gates.append(_gate("report_renderable", "warn", "Report rendered but looks minimal"))
    except Exception as exc:  # noqa: BLE001
        gates.append(_gate("report_renderable", "fail", f"Report failed: {exc}"))

    # .env exists warning only
    env_path = repo / ".env"
    if env_path.exists():
        gates.append(
            _gate(
                "env_file_present",
                "warn",
                ".env file exists in repo — never display or log its contents",
            )
        )
    else:
        gates.append(_gate("env_file_present", "pass", "No .env file in target repo path"))

    # Demo trace public-safe
    warn_markers = [f for f in safety if f.get("severity") == "warn"]
    if warn_markers:
        gates.append(
            _gate(
                "demo_trace_public_safe",
                "warn",
                f"{len(warn_markers)} public-safety warning(s) in trace",
            )
        )
    else:
        gates.append(_gate("demo_trace_public_safe", "pass", "Trace passes public-safety scan"))

    # Live mode API key
    if live_mode:
        if os.environ.get("CURSOR_API_KEY", "").strip():
            gates.append(_gate("live_api_key", "pass", "CURSOR_API_KEY is set (value not shown)"))
        else:
            gates.append(
                _gate(
                    "live_api_key",
                    "warn",
                    "CURSOR_API_KEY not set — use demo mode or export the key",
                )
            )
    else:
        gates.append(_gate("live_api_key", "pass", "Demo mode — API key not required"))

    # Never display .env contents (meta gate)
    gates.append(
        _gate(
            "no_env_contents_displayed",
            "pass",
            "Flight recorder does not read or display .env file contents",
        )
    )

    return gates


def gate_summary(gates: list[dict]) -> dict[str, int]:
    """Count gates by status."""
    summary: dict[str, int] = {"pass": 0, "warn": 0, "fail": 0}
    for g in gates:
        s = g.get("status", "warn")
        if s in summary:
            summary[s] += 1
    return summary
