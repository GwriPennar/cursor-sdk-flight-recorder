"""Cursor Python SDK runner with defensive fallbacks."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.env_loader import load_project_env
from src.trace import normalize_event


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(
    etype: str,
    summary: str,
    *,
    role: str = "",
    content: str = "",
    status: str = "info",
    metadata: dict | None = None,
) -> dict:
    return normalize_event(
        {
            "timestamp": _utc_now_iso(),
            "type": etype,
            "role": role or etype,
            "summary": summary,
            "content": content,
            "status": status,
            "metadata": metadata or {},
        }
    )


def _sdk_message_to_event(msg: Any, idx: int) -> dict | None:
    """Best-effort conversion of SDK message to normalized event."""
    msg_type = getattr(msg, "type", None) or (msg.get("type") if isinstance(msg, dict) else None)
    if not msg_type:
        return None
    msg_type = str(msg_type).lower()
    summary = f"SDK message: {msg_type}"
    content = ""
    status = "info"
    role = msg_type

    if msg_type == "assistant":
        blocks = []
        message = getattr(msg, "message", None)
        if message is not None:
            for block in getattr(message, "content", []) or []:
                btype = getattr(block, "type", None)
                if btype == "text":
                    blocks.append(getattr(block, "text", "") or "")
        content = "\n".join(blocks) if blocks else str(msg)
        summary = "Assistant response"
        status = "pass"
    elif msg_type == "tool_call":
        name = getattr(msg, "name", "tool")
        tstatus = getattr(msg, "status", "running")
        summary = f"Tool: {name} ({tstatus})"
        content = str(getattr(msg, "result", "") or getattr(msg, "args", ""))[:2000]
        role = "tool"
        status = "pass" if tstatus == "completed" else "info"
    elif msg_type == "user":
        summary = "User message (SDK)"
        content = str(msg)[:2000]
    elif msg_type == "status":
        status_val = getattr(msg, "status", None) or "status"
        msg_text = getattr(msg, "message", None) or ""
        summary = str(status_val)
        content = str(msg_text or status_val)
        status = "fail" if str(status_val).lower() == "error" else "info"
    elif msg_type == "thinking":
        summary = "Thinking"
        content = (getattr(msg, "text", "") or "")[:2000]
        role = "assistant"
    elif msg_type == "system":
        summary = getattr(msg, "subtype", None) or "system"
        content = str(getattr(msg, "model", "") or summary)[:1500]
    elif msg_type == "task":
        summary = f"Task: {getattr(msg, 'status', 'task')}"
        content = (getattr(msg, "text", "") or "")[:2000]
    else:
        content = str(msg)[:1500]

    out_type = "tool" if msg_type == "tool_call" else msg_type
    return _event(
        out_type,
        summary,
        role=role,
        content=content,
        status=status,
        metadata={"sdk_index": idx, "sdk_message_type": msg_type},
    )


def run_cursor_agent_local(
    repo_path: str,
    prompt: str,
    model: str = "composer-2.5",
) -> list[dict]:
    """
    Run a local Cursor SDK agent and return normalized trace events.

    Never prints or exposes secrets. Falls back to structured errors when SDK
    or API key is unavailable.
    """
    load_project_env()
    records: list[dict] = []
    repo = Path(repo_path).resolve()

    records.append(
        _event(
            "system",
            "Flight recorder starting local SDK run",
            content=f"repo={repo.name}, model={model}",
            status="info",
        )
    )

    if not repo.exists():
        records.append(
            _event(
                "error",
                f"Repository path does not exist: {repo}",
                status="fail",
            )
        )
        return records

    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not api_key:
        records.append(
            _event(
                "warning",
                "CURSOR_API_KEY is not set — demo mode still works without a key",
                status="warn",
                metadata={"hint": "export CURSOR_API_KEY for live runs"},
            )
        )
        return records

    try:
        from cursor_sdk import Agent, CursorAgentError, LocalAgentOptions  # noqa: F401
    except ImportError:
        records.append(
            _event(
                "error",
                "cursor-sdk package not installed — pip install -e '.[sdk]' or use demo mode",
                status="fail",
            )
        )
        return records

    records.append(
        _event(
            "user",
            "User prompt submitted",
            role="user",
            content=prompt,
            status="info",
        )
    )

    try:
        from cursor_sdk import Agent, CursorAgentError, LocalAgentOptions

        with Agent.create(
            model=model,
            api_key=api_key,
            local=LocalAgentOptions(cwd=str(repo)),
        ) as agent:
            records[0].setdefault("metadata", {})["agent_id"] = getattr(agent, "agent_id", "")
            run = agent.send(prompt)
            idx = 0
            stream_error: str | None = None
            try:
                for message in run.messages():
                    ev = _sdk_message_to_event(message, idx)
                    if ev:
                        ev["metadata"]["trace_source"] = "live"
                        records.append(ev)
                    idx += 1
            except Exception as stream_exc:  # noqa: BLE001
                stream_error = f"{type(stream_exc).__name__}: {stream_exc}"[:500]
                records.append(
                    _event(
                        "warning",
                        "SDK message stream interrupted",
                        content=stream_error,
                        status="warn",
                    )
                )
            result = run.wait()
            final = getattr(result, "result", None) or getattr(run, "result", "") or ""
            status = getattr(result, "status", "finished")
            run_status = "pass" if status == "finished" else "warn"
            if status == "error" and not final and stream_error:
                final = f"Run ended with error. Stream note: {stream_error}"
            records.append(
                _event(
                    "assistant",
                    "Run completed",
                    role="assistant",
                    content=str(final)[:8000],
                    status=run_status,
                    metadata={
                        "run_id": getattr(run, "id", ""),
                        "run_status": str(status),
                        "trace_source": "live",
                    },
                )
            )
    except Exception as exc:
        from cursor_sdk import CursorAgentError

        if isinstance(exc, CursorAgentError):
            records.append(
                _event(
                    "error",
                    f"SDK error: {getattr(exc, 'message', str(exc))}",
                    content=str(getattr(exc, "message", ""))[:500],
                    status="fail",
                    metadata={
                        "retryable": getattr(exc, "is_retryable", None),
                        "trace_source": "live",
                    },
                )
            )
        else:
            records.append(
                _event(
                    "error",
                    f"Local run failed: {type(exc).__name__}",
                    content=str(exc)[:500],
                    status="fail",
                    metadata={"trace_source": "live"},
                )
            )

    for rec in records:
        rec.setdefault("metadata", {}).setdefault("trace_source", "live")

    return records
