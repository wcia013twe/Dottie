"""Brain implementations. One validated output contract, three back ends.

- `FixtureBrain` returns preset plans (tests and dry runs).
- `DirectModelBrain` calls a Databricks foundation model through `Services.complete`.
- `AgentBricksBrain` calls the deployed Personal Intelligence agent through `Services.invoke_agent`.
"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from ..errors import BrainError
from ..paths import ROOT
from .protocol import SYSTEM_PROMPT, response_format, validate_plan


class Brain:
    def decide(self, snapshot: dict[str, Any], schemas: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError


class FixtureBrain(Brain):
    """Returns a fixed plan, a callable, or a queue of plans (for loops)."""

    def __init__(
        self,
        plan: dict[str, Any] | None = None,
        plans: list[dict[str, Any]] | None = None,
        decide: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ):
        self._plan = plan
        self._queue = list(plans or [])
        self._decide = decide

    def decide(self, snapshot: dict[str, Any], schemas: list[dict[str, Any]]) -> dict[str, Any]:
        if self._decide is not None:
            return self._decide(snapshot)
        if self._queue:
            return copy.deepcopy(self._queue.pop(0))
        if self._plan is not None:
            return copy.deepcopy(self._plan)
        raise BrainError("fixture brain has no plan left")


class _ServicesBrain(Brain):
    def __init__(self, config: dict[str, Any], services: Any | None = None):
        self.cfg = config["brain"]
        self._services = services

    def _svc(self):
        if self._services is None:
            from magneto_platform import ServiceConfig, Services

            path = Path(self.cfg["services_config"])
            if not path.is_absolute():
                path = ROOT / path
            sc = ServiceConfig.load(path)
            self._services = Services(replace(sc, model_endpoint=self.cfg["model_endpoint"]))
        return self._services


class DirectModelBrain(_ServicesBrain):
    def decide(self, snapshot: dict[str, Any], schemas: list[dict[str, Any]]) -> dict[str, Any]:
        svc = self._svc()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"snapshot": snapshot, "available_mcp_tools": schemas})},
        ]
        response = svc.complete(
            messages,
            response_format=response_format(schemas),
            max_tokens=self.cfg.get("max_tokens", 600),
            timeout_s=self.cfg.get("timeout_s", 15),
        )
        try:
            raw = response["choices"][0]["message"]["content"]
            plan = json.loads(raw)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise BrainError("model returned an unexpected envelope") from exc
        return validate_plan(plan, snapshot)


class AgentBricksBrain(_ServicesBrain):
    def _svc(self):
        if self._services is None:
            from magneto_platform import ServiceConfig, Services

            path = Path(self.cfg["services_config"])
            if not path.is_absolute():
                path = ROOT / path
            sc = ServiceConfig.load(path)
            self._services = Services(
                replace(sc, model_endpoint=self.cfg["model_endpoint"], agent_app=self.cfg["agent_app"])
            )
        return self._services

    def decide(self, snapshot: dict[str, Any], schemas: list[dict[str, Any]]) -> dict[str, Any]:
        svc = self._svc()
        payload = {"snapshot": snapshot, "available_mcp_tools": schemas}
        response = svc.invoke_agent(
            payload,
            session_id=snapshot["session_id"],
            request_id=snapshot["request_id"],
            timeout_s=self.cfg.get("timeout_s", 15),
        )
        output = response.get("output", response) if isinstance(response, dict) else response
        plan = output.get("plan") if isinstance(output, dict) else None
        if plan is None:
            raise BrainError("companion agent returned no plan")
        return validate_plan(plan, snapshot)


def make_brain(config: dict[str, Any], services: Any | None = None) -> Brain:
    mode = config.get("brain", {}).get("mode", "direct")
    if mode == "fixture":
        return FixtureBrain(plan=_fixture_plan_from_env())
    if mode == "agent":
        return AgentBricksBrain(config, services)
    return DirectModelBrain(config, services)


def _fixture_plan_from_env() -> dict[str, Any] | None:
    raw = os.environ.get("MAGNETO_FIXTURE_PLAN")
    return json.loads(raw) if raw else None
