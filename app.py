"""
Cursor SDK Flight Recorder — visual explainer for Cursor Python SDK agent runs.

Run: streamlit run app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.env_loader import load_project_env
from src.gates import run_gates

load_project_env()
from src.report import render_html_report, render_markdown_report, save_report
from src.runner import run_cursor_agent_local
from src.self_eval import evaluate_project
from src.trace import (
    extract_prompt_and_result,
    filter_records,
    load_jsonl,
    public_safety_scan,
)
from src.visuals import (
    gate_matrix_df,
    gate_status_html,
    metric_summary,
    plotly_event_counts,
    plotly_timeline,
    run_health_card,
    status_label,
)

DEMO_FIXTURE = ROOT / "fixtures" / "demo_trace.jsonl"
LIVE_FIXTURE = ROOT / "fixtures" / "live_sample_redacted.jsonl"
DEFAULT_REPO = str(ROOT / "examples" / "tiny_repo")
REPORTS_DIR = ROOT / "reports"

PATH_DEMO = "Learn with demo data"
PATH_LOCAL = "Run Cursor SDK on a local repo"
PATH_SAVED = "Review a saved trace"

PATH_HELP = {
    PATH_DEMO: "Loads a synthetic example trace (JSONL). No API key needed.",
    PATH_LOCAL: "Runs the Cursor Python SDK against a folder on your machine. Requires credentials in `.env`.",
    PATH_SAVED: "Loads a JSONL trace file you already recorded (upload below).",
}

SDK_EXAMPLES = {
    "Quickstart repo summary": (
        "Summarize this repository. Do not modify files. "
        "Return the key files inspected and one safe improvement."
    ),
    "Read-only code review": (
        "Review this repository for one small safe improvement. Do not modify files."
    ),
    "Explain project structure": (
        "Explain the project structure and identify the main entry point. Do not modify files."
    ),
    "Custom prompt": "",
}

RUN_BADGE = {
    "demo": ("Current run: Demo example", "#8b5cf6"),
    "redacted_live": ("Current run: Redacted SDK sample", "#06b6d4"),
    "live": ("Current run: Live local SDK run", "#22c55e"),
    "uploaded": ("Current run: Uploaded trace", "#a855f7"),
    "none": ("Current run: None loaded", "#64748b"),
}

TAB_BLURBS = {
    "timeline": "The timeline shows the order of events captured during the run.",
    "summary": "This chart shows what kinds of events were captured.",
    "table": "This is the raw event trace in table form.",
    "prompt": "This shows what was sent to the agent and what came back.",
    "gates": "These checks help decide whether the run is safe and complete enough to share.",
    "report": "The report packages the run into a Markdown/HTML artefact.",
    "eval": "A deterministic self-check of the demo project, not an LLM judgement.",
}


def _set_trace_source(source: str) -> None:
    st.session_state.trace_source = source


def _init_state() -> None:
    defaults = {
        "records": [],
        "gates": [],
        "report_md": "",
        "self_eval": {},
        "trace_source": "none",
        "repo_path": DEFAULT_REPO,
        "user_path": PATH_DEMO,
        "sdk_example": "Quickstart repo summary",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _apply_gates(live_mode: bool = False) -> None:
    st.session_state.gates = run_gates(
        st.session_state.repo_path,
        st.session_state.records,
        live_mode=live_mode,
    )


def load_demo_trace() -> None:
    st.session_state.records = load_jsonl(DEMO_FIXTURE)
    _set_trace_source("demo")
    _apply_gates(live_mode=False)


def load_redacted_live_sample() -> None:
    st.session_state.records = load_jsonl(LIVE_FIXTURE)
    _set_trace_source("redacted_live")
    _apply_gates(live_mode=False)


def load_uploaded_trace(uploaded) -> None:
    text = uploaded.getvalue().decode("utf-8", errors="replace")
    records = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
            if isinstance(raw, dict):
                records.append(raw)
        except json.JSONDecodeError:
            continue
    if not records:
        st.error("No valid JSONL events found in the uploaded file.")
        return
    from src.trace import normalize_event

    st.session_state.records = [normalize_event(r) for r in records]
    _set_trace_source("uploaded")
    _apply_gates(live_mode=False)


def run_live(repo_path: str, prompt: str, model: str) -> None:
    with st.spinner("Running Cursor SDK agent on your local repo…"):
        records = run_cursor_agent_local(repo_path, prompt, model=model)
    st.session_state.records = records
    _set_trace_source("live")
    _apply_gates(live_mode=True)


def _resolve_prompt(example_key: str, custom_text: str) -> str:
    if example_key == "Custom prompt":
        return custom_text.strip() or SDK_EXAMPLES["Quickstart repo summary"]
    return SDK_EXAMPLES[example_key]


def generate_report() -> None:
    records = st.session_state.records
    gates = st.session_state.gates or run_gates(st.session_state.repo_path, records)
    st.session_state.gates = gates
    md = render_markdown_report(records, gates)
    st.session_state.report_md = md
    html = render_html_report(md)
    paths = save_report(md, html, REPORTS_DIR)
    st.session_state.report_paths = paths


def _render_header() -> None:
    st.title("✈️ Cursor SDK Flight Recorder")
    st.caption("Run a Cursor Python SDK agent on a local repo, then see what happened.")
    st.markdown(
        "Flight Recorder records a Cursor SDK agent run as events, shows the run as a "
        "timeline, checks basic review gates, and exports a Markdown report. "
        "**Demo mode works without an API key.**"
    )


def _render_run_badge() -> None:
    source = st.session_state.get("trace_source", "none")
    label, color = RUN_BADGE.get(source, RUN_BADGE["none"])
    st.markdown(
        f'<span style="background:{color};color:#fff;padding:4px 10px;'
        f'border-radius:6px;font-size:0.85em;">{label}</span>',
        unsafe_allow_html=True,
    )


def _render_onboarding() -> None:
    st.subheader("What this app does")
    st.markdown(
        """
1. **Runs or loads** a Cursor SDK agent run (demo fixture, local SDK, or your JSONL file)
2. **Records** each step as a JSONL event trace
3. **Shows** a visual timeline and event table
4. **Runs review gates** for safety and completeness
5. **Exports** a Markdown/HTML report you can share
        """
    )
    st.markdown("**Simple story:** Run a Cursor SDK agent → record the run → understand what happened → share the result.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Load demo run", type="primary", use_container_width=True):
            load_demo_trace()
            st.session_state.user_path = PATH_DEMO
            st.rerun()
    with c2:
        if st.button("Run on local repo", use_container_width=True):
            st.session_state.user_path = PATH_LOCAL
            st.info("Use the sidebar: choose **Run Cursor SDK on a local repo**, then **Run SDK agent**.")
            st.rerun()


def _render_sidebar() -> tuple[list[str], list[str]]:
    """Return (type_filter, status_filter) selections."""
    with st.sidebar:
        st.header("How to use this app")

        st.markdown("##### Step 1 — Choose your path")
        path_choices = [PATH_DEMO, PATH_LOCAL, PATH_SAVED]
        current_path = st.session_state.get("user_path", PATH_DEMO)
        path_index = (
            path_choices.index(current_path) if current_path in path_choices else 0
        )
        user_path = st.radio(
            "What do you want to do?",
            path_choices,
            index=path_index,
        )
        st.session_state.user_path = user_path
        st.caption(PATH_HELP[user_path])

        st.markdown("##### Step 2 — Local repo (when relevant)")
        if user_path in (PATH_DEMO, PATH_LOCAL):
            st.info(
                "**Local repo only:** Flight Recorder points the Cursor SDK at a folder on "
                "your machine. To use a GitHub repo, clone it first, then enter the local folder path."
            )
            repo_path = st.text_input(
                "Local repo path",
                value=st.session_state.get("repo_path", DEFAULT_REPO),
                help=(
                    "Cursor SDK local mode runs against a directory on your machine. "
                    "Remote GitHub URLs are not supported yet."
                ),
            )
            st.session_state.repo_path = repo_path
            if user_path == PATH_DEMO:
                st.caption("For demo data, this path is only used for review checks—not loaded as the trace.")
        else:
            st.caption("Review checks can use the default example repo path below if your trace omits repo context.")
            st.session_state.repo_path = st.text_input(
                "Local repo path (for review checks)",
                value=st.session_state.get("repo_path", DEFAULT_REPO),
            )

        prompt = ""
        model = "composer-2.5"
        uploaded = None

        if user_path == PATH_LOCAL:
            st.markdown("##### Step 3 — Choose an SDK example")
            example_key = st.radio(
                "Example prompt",
                list(SDK_EXAMPLES.keys()),
                index=list(SDK_EXAMPLES.keys()).index(
                    st.session_state.get("sdk_example", "Quickstart repo summary")
                ),
            )
            st.session_state.sdk_example = example_key
            if example_key == "Custom prompt":
                prompt = st.text_area(
                    "Custom prompt",
                    value=st.session_state.get(
                        "custom_prompt",
                        SDK_EXAMPLES["Quickstart repo summary"],
                    ),
                    height=100,
                )
                st.session_state.custom_prompt = prompt
            else:
                st.caption(SDK_EXAMPLES[example_key])
            prompt = _resolve_prompt(example_key, st.session_state.get("custom_prompt", ""))
            model = st.text_input("Model", value="composer-2.5")

        st.markdown("##### Step 4 — Run or load")
        if user_path == PATH_DEMO:
            if st.button("Load demo run", type="primary", use_container_width=True):
                load_demo_trace()
                st.success(f"Loaded {len(st.session_state.records)} events from demo fixture.")
        elif user_path == PATH_LOCAL:
            if st.button("Run SDK agent", type="primary", use_container_width=True):
                run_live(st.session_state.repo_path, prompt, model)
                st.success(f"Captured {len(st.session_state.records)} events from local SDK run.")
        else:
            uploaded = st.file_uploader(
                "JSONL trace file",
                type=["jsonl", "json"],
                help="One JSON event object per line.",
            )
            if st.button("Load trace", type="primary", use_container_width=True):
                if uploaded is None:
                    st.error("Choose a JSONL file first.")
                else:
                    load_uploaded_trace(uploaded)
                    if st.session_state.records:
                        st.success(f"Loaded {len(st.session_state.records)} events.")

        with st.expander("Advanced: inspect redacted live SDK timeout sample"):
            st.caption(
                "A real partial SDK capture that ended in a bridge timeout. Useful for seeing "
                "status/error events—not a successful tool-rich run."
            )
            if LIVE_FIXTURE.exists():
                if st.button("Load redacted timeout sample", use_container_width=True):
                    load_redacted_live_sample()
                    st.success(f"Loaded {len(st.session_state.records)} events.")
            else:
                st.caption("Sample fixture not found.")

        st.markdown("##### Step 5 — Export")
        if st.button("Generate shareable report", use_container_width=True):
            if not st.session_state.records:
                st.error("Load or run a trace first (Step 4).")
            else:
                generate_report()
                st.success("Report ready in the Report tab and in `reports/latest.md`.")
        if st.session_state.report_md:
            st.download_button(
                "Download Markdown",
                st.session_state.report_md,
                file_name="flight-recorder-report.md",
                mime="text/markdown",
                use_container_width=True,
            )
            st.caption("Also saved under `reports/` when you generate.")

        if st.session_state.records:
            st.divider()
            st.subheader("Filter view")
            all_types = sorted({r.get("type", "") for r in st.session_state.records})
            all_statuses = sorted(
                {r.get("status", "info") for r in st.session_state.records}
            )
            type_filter = st.multiselect("Event types", all_types, default=all_types)
            status_filter = st.multiselect("Statuses", all_statuses, default=all_statuses)
            health = run_health_card(st.session_state.records, st.session_state.gates)
            color = {"pass": "#22c55e", "warn": "#eab308", "fail": "#ef4444"}.get(
                health["health"], "#3b82f6"
            )
            st.markdown(
                f'<div style="padding:12px;border-radius:8px;border:2px solid {color};'
                f'background:#0f172a;">'
                f'<strong>Run health:</strong> {health["label"]}<br/>'
                f'Events: {health["events"]} · Checks ✅{health["gates_pass"]} '
                f'⚠️{health["gates_warn"]} ❌{health["gates_fail"]}</div>',
                unsafe_allow_html=True,
            )
            return type_filter, status_filter

    return [], []


def _render_main_content(
    records: list[dict],
    gates: list[dict],
    type_filter: list[str],
    status_filter: list[str],
) -> None:
    metrics = metric_summary(st.session_state.records, gates)
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total events", metrics["total_events"])
    m2.metric("Duration", metrics["duration"])
    m3.metric("Assistant events", metrics["assistant_events"])
    m4.metric("Tool events", metrics["tool_events"])
    m5.metric("Review checks passed", metrics["gates_passed"])
    m6.metric("Warnings or failures", metrics["warnings_failures"])

    st.markdown("#### How a run flows")
    flow_cols = st.columns(5)
    flow_labels = ["Your prompt", "Cursor SDK", "Event trace", "Review checks", "Report"]
    flow_icons = ["📝", "🤖", "📊", "🛡️", "📄"]
    for col, icon, label in zip(flow_cols, flow_icons, flow_labels):
        col.markdown(
            f"<div style='text-align:center;padding:8px;background:#1e293b;"
            f"border-radius:8px;'>{icon}<br/><b>{label}</b></div>",
            unsafe_allow_html=True,
        )

    (
        tab_timeline,
        tab_counts,
        tab_table,
        tab_details,
        tab_gates,
        tab_report,
        tab_eval,
    ) = st.tabs(
        [
            "Timeline",
            "Event summary",
            "Event table",
            "Prompt and answer",
            "Review checks",
            "Report",
            "Project self-check",
        ]
    )

    with tab_timeline:
        st.caption(TAB_BLURBS["timeline"])
        st.plotly_chart(plotly_timeline(records), use_container_width=True)

    with tab_counts:
        st.caption(TAB_BLURBS["summary"])
        chart_style = st.radio("Chart style", ["bar", "donut"], horizontal=True)
        st.plotly_chart(
            plotly_event_counts(records, chart=chart_style),
            use_container_width=True,
        )

    with tab_table:
        st.caption(TAB_BLURBS["table"])
        df = pd.DataFrame(
            [
                {
                    "index": i,
                    "timestamp": r.get("timestamp"),
                    "type": r.get("type"),
                    "role": r.get("role"),
                    "summary": r.get("summary"),
                    "status": r.get("status"),
                }
                for i, r in enumerate(records, start=1)
            ]
        )
        st.dataframe(df, use_container_width=True, height=360)

    with tab_details:
        st.caption(TAB_BLURBS["prompt"])
        prompt_text, result_text = extract_prompt_and_result(st.session_state.records)
        safety = public_safety_scan(st.session_state.records)
        if safety:
            st.warning(
                f"Public-safety scan: {len(safety)} finding(s). "
                "Review before sharing externally."
            )
        c1, c2 = st.columns(2)
        with c1:
            with st.expander("User prompt", expanded=True):
                st.code(prompt_text or "(none)")
        with c2:
            with st.expander("Final answer", expanded=True):
                st.markdown(result_text or "_(none)_")
        with st.expander("Tool event summaries"):
            tools = [r for r in st.session_state.records if r.get("type") == "tool"]
            if tools:
                for t in tools:
                    st.markdown(
                        f"**{t.get('summary')}** — {status_label(t.get('status', 'info'))}"
                    )
            else:
                st.caption("No tool events in this trace.")
        with st.expander("Raw JSON event sample"):
            st.json(st.session_state.records[:3])
        with st.expander("Inspect one event"):
            idx = st.number_input(
                "Event index",
                min_value=1,
                max_value=max(len(st.session_state.records), 1),
                value=1,
            )
            if st.session_state.records:
                st.json(st.session_state.records[int(idx) - 1])

    with tab_gates:
        st.caption(TAB_BLURBS["gates"])
        if not gates:
            live = st.session_state.get("user_path") == PATH_LOCAL
            gates = run_gates(
                st.session_state.repo_path,
                st.session_state.records,
                live_mode=live,
            )
            st.session_state.gates = gates
        for g in gates:
            st.markdown(
                gate_status_html(g["name"], g["status"], g["detail"]),
                unsafe_allow_html=True,
            )
        st.dataframe(gate_matrix_df(gates), use_container_width=True, hide_index=True)

    with tab_report:
        st.caption(TAB_BLURBS["report"])
        if st.session_state.get("trace_source") == "demo" and st.session_state.report_md:
            st.warning(
                "This report is from the **demo example trace**, not a live SDK run."
            )
        if st.session_state.report_md:
            st.markdown(st.session_state.report_md)
            if st.session_state.get("report_paths"):
                st.caption(f"Files: {st.session_state.report_paths}")
            st.download_button(
                "Download Markdown",
                st.session_state.report_md,
                file_name="flight-recorder-report.md",
                mime="text/markdown",
            )
        else:
            st.info("Use sidebar **Step 5 — Generate shareable report**.")

    with tab_eval:
        st.caption(TAB_BLURBS["eval"])
        ev = evaluate_project(st.session_state.records, gates)
        st.session_state.self_eval = ev
        e1, e2, e3 = st.columns(3)
        e1.metric("Visual usefulness", f"{ev['visual_usefulness_score']}/10")
        e2.metric("Public safety", f"{ev['public_safety_score']}/10")
        e3.metric("SDK usefulness", f"{ev['sdk_usefulness_score']}/10")
        st.markdown("**What works**")
        for item in ev["what_works"]:
            st.markdown(f"- {item}")
        st.markdown("**Limitations**")
        for item in ev["limitations"]:
            st.markdown(f"- {item}")
        st.markdown("**Possible next improvements**")
        for item in ev["next_visual_features"]:
            st.markdown(f"- {item}")


def main() -> None:
    st.set_page_config(
        page_title="Cursor SDK Flight Recorder",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _init_state()
    _render_header()
    _render_run_badge()

    type_filter, status_filter = _render_sidebar()

    records = list(st.session_state.records)
    gates = st.session_state.gates
    if not records:
        _render_onboarding()
        return

    if type_filter or status_filter:
        records = filter_records(
            records,
            types=type_filter if type_filter else None,
            statuses=status_filter if status_filter else None,
        )

    _render_main_content(records, gates, type_filter, status_filter)


if __name__ == "__main__":
    main()
