"""Plotly and metric helpers for the Streamlit dashboard."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.gates import gate_summary
from src.trace import duration_seconds, event_counts, timeline_rows

STATUS_COLORS = {
    "pass": "#22c55e",
    "warn": "#eab308",
    "fail": "#ef4444",
    "info": "#3b82f6",
}

TYPE_COLORS = {
    "system": "#64748b",
    "user": "#8b5cf6",
    "assistant": "#06b6d4",
    "tool": "#f97316",
    "gate": "#22c55e",
    "error": "#ef4444",
    "warning": "#eab308",
    "self_eval": "#a855f7",
}


def status_label(status: str) -> str:
    """Human-readable status with emoji."""
    icons = {"pass": "✅", "warn": "⚠️", "fail": "❌", "info": "ℹ️"}
    return f"{icons.get(status, '•')} {status.upper()}"


def gate_status_html(name: str, status: str, detail: str) -> str:
    """Compact HTML for gate cards."""
    color = STATUS_COLORS.get(status, "#94a3b8")
    return (
        f'<div style="border-left:4px solid {color};padding:8px 12px;margin:6px 0;'
        f'background:#1e293b22;border-radius:4px;">'
        f"<strong>{name}</strong> — {status_label(status)}<br/>"
        f'<span style="font-size:0.85em;color:#64748b;">{detail}</span></div>'
    )


def metric_summary(records: list[dict], gates: list[dict]) -> dict[str, Any]:
    """Compute top-row metrics."""
    counts = event_counts(records)
    gs = gate_summary(gates)
    assistant_n = counts.get("assistant", 0) + counts.get("thinking", 0)
    tool_n = counts.get("tool", 0) + counts.get("tool_call", 0)
    dur = duration_seconds(records)
    warnings = sum(1 for r in records if r.get("status") in ("warn", "fail"))
    return {
        "total_events": len(records),
        "duration": f"{dur:.1f}s" if dur is not None else "—",
        "assistant_events": assistant_n,
        "tool_events": tool_n,
        "gates_passed": gs.get("pass", 0),
        "warnings_failures": warnings + gs.get("fail", 0) + gs.get("warn", 0),
    }


def plotly_timeline(records: list[dict]) -> go.Figure:
    """Horizontal timeline of events."""
    rows = timeline_rows(records)
    if not rows:
        fig = go.Figure()
        fig.update_layout(title="No events to display")
        return fig
    df = pd.DataFrame(rows)
    df["color"] = df["type"].map(lambda t: TYPE_COLORS.get(t, "#94a3b8"))
    fig = go.Figure()
    for _, row in df.iterrows():
        fig.add_trace(
            go.Scatter(
                x=[row["order"]],
                y=[row["type"]],
                mode="markers+text",
                text=[str(row["index"])],
                textposition="middle center",
                marker=dict(size=28, color=row["color"], line=dict(width=1, color="#fff")),
                name=row["type"],
                hovertemplate=(
                    f"<b>#{row['index']}</b> {row['type']}<br>"
                    f"{row['summary']}<br>"
                    f"Status: {row['status']}<extra></extra>"
                ),
                showlegend=False,
            )
        )
    fig.update_layout(
        title="Event timeline",
        xaxis_title="Event order",
        yaxis_title="Event type",
        height=320,
        template="plotly_dark",
        margin=dict(l=40, r=20, t=50, b=40),
    )
    return fig


def plotly_event_counts(records: list[dict], chart: str = "bar") -> go.Figure:
    """Bar or donut chart of event types."""
    counts = event_counts(records)
    if not counts:
        fig = go.Figure()
        fig.update_layout(title="No event counts")
        return fig
    df = pd.DataFrame(list(counts.items()), columns=["type", "count"])
    colors = [TYPE_COLORS.get(t, "#94a3b8") for t in df["type"]]
    if chart == "donut":
        fig = go.Figure(
            data=[
                go.Pie(
                    labels=df["type"],
                    values=df["count"],
                    hole=0.45,
                    marker=dict(colors=colors),
                )
            ]
        )
        fig.update_layout(title="Event types", template="plotly_dark", height=320)
    else:
        fig = px.bar(
            df,
            x="type",
            y="count",
            color="type",
            color_discrete_map=TYPE_COLORS,
            title="Event type counts",
        )
        fig.update_layout(template="plotly_dark", showlegend=False, height=320)
    return fig


def run_health_card(records: list[dict], gates: list[dict]) -> dict[str, str]:
    """Compact run health summary for sidebar/card."""
    gs = gate_summary(gates)
    fails = gs.get("fail", 0)
    warns = gs.get("warn", 0)
    if fails > 0:
        health = "fail"
        label = "Needs attention"
    elif warns > 0:
        health = "warn"
        label = "Review warnings"
    else:
        health = "pass"
        label = "Healthy run"
    return {
        "health": health,
        "label": label,
        "gates_pass": str(gs.get("pass", 0)),
        "gates_warn": str(warns),
        "gates_fail": str(fails),
        "events": str(len(records)),
    }


def gate_matrix_df(gates: list[dict]) -> pd.DataFrame:
    """Gate results as a dataframe for matrix display."""
    return pd.DataFrame(
        [
            {
                "Gate": g.get("name", ""),
                "Status": g.get("status", ""),
                "Detail": g.get("detail", ""),
            }
            for g in gates
        ]
    )
