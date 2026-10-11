"""Outcome reporting: build and persist companion-outcome records."""

from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from ..errors import ContractError


def build_outcome(session: dict[str, Any], response: dict[str, Any], execution: dict[str, Any] | None = None) -> dict[str, Any]:
    """Turn a controller response + presentation flags into a companion-outcome."""

    execution = execution or {}
    device = session.get("device", {})
    outcome = {
        "schema_version": "1.0",
        "outcome_id": str(uuid.uuid4()),
        "session_id": session["session_id"],
        "revision": session["revision"],
        "target": response.get("expected") or session.get("target") or "",
        "activity": session.get("activity") or "identify",
        "expected": response.get("expected", ""),
        "transcript": response.get("transcript", ""),
        "match": response.get("match", "none"),
        "outcome": response.get("outcome", "unrecognized"),
        "source": response.get("source", "stt"),
        "execution": {
            "spoken": bool(execution.get("spoken", False)),
            "shown": bool(execution.get("shown", False)),
            "cell_ack": bool(execution.get("cell_ack", False)),
            "cell_connected": bool(device.get("cell_connected", False)),
        },
        "received_at_ms": int(response.get("received_at_ms", 0)),
    }
    _validate(outcome)
    return outcome


def _validate(outcome: dict[str, Any]) -> None:
    if not outcome["target"]:
        raise ContractError("outcome has no target")
    if outcome["match"] not in ("exact", "partial", "none"):
        raise ContractError(f"invalid match {outcome['match']!r}")
    if outcome["outcome"] not in ("correct", "incorrect", "help", "unrecognized"):
        raise ContractError(f"invalid outcome {outcome['outcome']!r}")


class OutcomeLog:
    """Append-only JSONL log, idempotent on outcome_id (retries never duplicate)."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._seen: set[str] = set()
        self._lock = threading.Lock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, outcome: dict[str, Any]) -> bool:
        oid = outcome["outcome_id"]
        with self._lock:
            if oid in self._seen:
                return False
            self._seen.add(oid)
            if self.path:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(outcome, sort_keys=True) + "\n")
            return True
