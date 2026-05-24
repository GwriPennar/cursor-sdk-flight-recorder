"""Markdown and HTML report generation."""

from __future__ import annotations

import html as html_module
from datetime import datetime, timezone
from pathlib import Path

from src.trace import (
    duration_seconds,
    event_counts,
    extract_prompt_and_result,
    public_safety_scan,
    timeline_rows,
)


def render_markdown_report(
    records: list[dict],
    gates: list[dict],
    title: str = "Cursor SDK Flight Recorder Report",
) -> str:
    """Build a shareable Markdown report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    counts = event_counts(records)
    prompt, result = extract_prompt_and_result(records)
    dur = duration_seconds(records)
    dur_str = f"{dur:.1f}s" if dur is not None else "n/a"
    safety = public_safety_scan(records)
    timeline = timeline_rows(records)

    lines = [
        f"# {title}",
        "",
        f"**Generated:** {now}",
        "",
        "## Summary metrics",
        "",
        f"- **Total events:** {len(records)}",
        f"- **Duration:** {dur_str}",
        f"- **Event types:** {len(counts)}",
        "",
        "## Event counts",
        "",
    ]
    for etype, n in counts.items():
        lines.append(f"- `{etype}`: {n}")
    lines.extend(["", "## Gate results", ""])
    for g in gates:
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(g.get("status", ""), "•")
        lines.append(f"- {icon} **{g.get('name')}** ({g.get('status')}): {g.get('detail')}")

    lines.extend(
        [
            "",
            "## User prompt",
            "",
            "```",
            prompt or "(none)",
            "```",
            "",
            "## Final result",
            "",
            result or "(none)",
            "",
            "## Timeline summary",
            "",
        ]
    )
    for row in timeline[:20]:
        lines.append(
            f"{row['index']}. `{row['type']}` — {row['label']} ({row['status']})"
        )
    if len(timeline) > 20:
        lines.append(f"\n_…and {len(timeline) - 20} more events._")

    lines.extend(
        [
            "",
            "## Public safety",
            "",
        ]
    )
    if safety:
        for f in safety:
            lines.append(f"- Event {f.get('index')}: {f.get('reason')} ({f.get('severity')})")
    else:
        lines.append("- No public-safety issues detected in trace text.")

    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            "```bash",
            "python -m venv .venv",
            "source .venv/bin/activate",
            'pip install -e ".[dev]"',
            "streamlit run app.py",
            "# Select Demo trace → Load demo → Generate report",
            "```",
            "",
            "## Limitations",
            "",
            "- Cursor Python SDK is in public beta; event shapes may change.",
            "- Live mode requires `CURSOR_API_KEY` and a working local SDK install.",
            "- Tool call payloads are untyped and may vary between SDK versions.",
            "",
            "## Next steps",
            "",
            "- Compare multiple runs side-by-side.",
            "- Add CI/GitHub Actions trace export.",
            "- Stream richer tool-call metadata when the SDK exposes it.",
            "",
        ]
    )
    return "\n".join(lines)


def render_html_report(markdown: str) -> str:
    """Convert Markdown-ish report to simple HTML."""
    escaped = html_module.escape(markdown)
    body_lines = []
    for line in escaped.split("\n"):
        if line.startswith("# "):
            body_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            body_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("- "):
            body_lines.append(f"<li>{line[2:]}</li>")
        elif line.startswith("```"):
            continue
        elif line.strip() == "":
            body_lines.append("<br/>")
        else:
            body_lines.append(f"<p>{line}</p>")
    body = "\n".join(body_lines)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Cursor SDK Flight Recorder Report</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }}
    h1 {{ color: #1a1a2e; }}
    h2 {{ color: #16213e; margin-top: 1.5rem; }}
    li {{ margin: 0.25rem 0; }}
  </style>
</head>
<body>
{body}
</body>
</html>"""


def save_report(
    markdown: str,
    html: str | None,
    reports_dir: str | Path,
) -> dict:
    """Write latest.md and optional latest.html."""
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    md_path = reports_dir / "latest.md"
    md_path.write_text(markdown, encoding="utf-8")
    paths = {"markdown": str(md_path)}
    if html:
        html_path = reports_dir / "latest.html"
        html_path.write_text(html, encoding="utf-8")
        paths["html"] = str(html_path)
    return paths
