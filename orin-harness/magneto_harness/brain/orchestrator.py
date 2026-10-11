"""Bounded orchestration: MCP discovery/read -> brain plan -> validated MCP call.

Mirrors `story_mode/orchestrator.py`: a real MCP stdio session owns the devices,
the brain only selects one validated tool, and the harness validates the plan
against the current revision before any physical action runs.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..errors import HarnessError
from ..paths import HARNESS_DIR
from .protocol import ALLOWED, validate_plan


def server_params(config_path: str | Path | None = None) -> StdioServerParameters:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(HARNESS_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    if config_path:
        env["MAGNETO_HARNESS_CONFIG"] = str(config_path)
    return StdioServerParameters(command=sys.executable, args=["-m", "magneto_harness.mcp.server"], env=env)


def unpack(result: Any) -> dict[str, Any]:
    if result.isError:
        raise HarnessError("MCP tool rejected the action")
    if getattr(result, "structuredContent", None) is not None:
        return result.structuredContent
    return json.loads(next(c.text for c in result.content if c.type == "text"))


@asynccontextmanager
async def connect(config_path: str | Path | None = None) -> AsyncIterator[ClientSession]:
    async with stdio_client(server_params(config_path)) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            yield client


async def _call(client: ClientSession, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    return unpack(await client.call_tool(tool, args))


async def get_state(client: ClientSession, session_id: str) -> dict[str, Any]:
    return await _call(client, "get_companion_state", {"session_id": session_id})


async def brain_tool_schemas(client: ClientSession) -> list[dict[str, Any]]:
    tools = (await client.list_tools()).tools
    return [
        {"name": t.name, "description": t.description, "inputSchema": t.inputSchema}
        for t in tools
        if t.name in ALLOWED
    ]


def build_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    return {"request_id": str(uuid.uuid4()), **{k: v for k, v in state.items() if k != "request_id"}}


async def submit_pending(client: ClientSession, session_id: str) -> list[dict[str, Any]]:
    pending = await _call(client, "poll_speech", {"session_id": session_id})
    accepted = []
    for item in pending.get("transcripts", []):
        result = await _call(
            client,
            "submit_response",
            {"session_id": session_id, "transcript": item.get("transcript", ""), "source": "stt"},
        )
        if result.get("accepted"):
            accepted.append(result)
    return accepted


async def wait_for_response(
    client: ClientSession, session_id: str, timeout_s: float = 30.0, interval_s: float = 0.4
) -> list[dict[str, Any]]:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        accepted = await submit_pending(client, session_id)
        if accepted:
            return accepted
        await asyncio.sleep(interval_s)
    return []


async def run_turn(client: ClientSession, brain: Any, session_id: str) -> dict[str, Any]:
    """One observe -> plan -> validate -> execute cycle."""
    state = await get_state(client, session_id)
    if state["phase"] in ("complete", "stopped"):
        return {"state": state, "tool_called": None, "done": True}
    if state["phase"] == "awaiting_response":
        accepted = await wait_for_response(client, session_id)
        if not accepted:
            state = await get_state(client, session_id)
        state = await get_state(client, session_id)
    snapshot = build_snapshot(state)
    schemas = await brain_tool_schemas(client)
    plan = await asyncio.to_thread(brain.decide, snapshot, schemas)
    validate_plan(plan, snapshot)
    result = await _call(client, plan["tool"], plan["arguments"])
    return {"state": result, "tool_called": plan["tool"], "reason": plan["reason"], "done": False}


async def drive(client: ClientSession, brain: Any, session_id: str, max_turns: int = 16) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for _ in range(max_turns):
        last = await run_turn(client, brain, session_id)
        if last.get("done"):
            break
    return last


async def run_lesson(
    config_path: str | Path | None,
    brain: Any,
    lesson_id: str | None = None,
    max_turns: int = 16,
) -> dict[str, Any]:
    async with connect(config_path) as client:
        created = await _call(client, "create_session", {})
        session_id = created["session_id"]
        await _call(client, "start_session", {"session_id": session_id, "lesson_id": lesson_id})
        result = await drive(client, brain, session_id, max_turns=max_turns)
        result["session_id"] = session_id
        return result


if __name__ == "__main__":  # pragma: no cover - manual entry
    from ..config import load_config
    from .client import make_brain

    async def main() -> None:
        config = load_config()
        brain = make_brain(config)
        try:
            print(json.dumps(await run_lesson(None, brain)))
        except Exception as exc:
            print(json.dumps({"error": "Harness orchestration failed", "error_type": type(exc).__name__}))
            raise SystemExit(1) from exc

    asyncio.run(main())
