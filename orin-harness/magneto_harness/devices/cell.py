"""Braille cell device: hold a single pattern, spell text, or clear.

Real: `cane_vision.serial_cell.make_cell` (Arduino over serial, or the console
preview when no board is present). Simulated: records actions in memory.

`hold` uses the firmware's `DOTS <dots>` command so a single letter stays up
while the learner reads it; `spell` uses the Arduino's timed `SPELL`.
"""

from __future__ import annotations

import time
from typing import Any

from ..errors import DeviceError

HOLD_ACK_TIMEOUT_S = 0.4


def _dots_command(mask: int) -> str:
    numbers = [str(n + 1) for n in range(6) if mask & (1 << n)]
    return "DOTS " + " ".join(numbers) if numbers else "CLEAR"


class SimulatedCellDevice:
    def __init__(self) -> None:
        self.mask = 0
        self.char = ""
        self.actions: list[tuple] = []

    def hold(self, mask: int, char: str = "") -> dict[str, Any]:
        self.mask, self.char = mask, char
        self.actions.append(("hold", mask, char))
        return {"shown": True, "cell_ack": True}

    def show_text(self, text: str) -> dict[str, Any]:
        self.actions.append(("text", text))
        return {"shown": True, "cell_ack": True}

    def clear(self) -> dict[str, Any]:
        self.mask, self.char = 0, ""
        self.actions.append(("clear",))
        return {"shown": True, "cell_ack": True}

    def state(self) -> dict[str, Any]:
        return {"connected": False, "ready": True, "mask": self.mask, "char": self.char}

    def close(self) -> None:
        return None


class RealCellDevice:
    """Wraps either a `SerialCell` (has `send`) or a `CellPlayer` preview."""

    def __init__(self, cell: Any, hold_s: float = 3.0):
        self._cell = cell
        self._hold_s = hold_s
        self._serial = hasattr(cell, "send")

    def _acked(self, mask: int) -> bool:
        if not self._serial:
            return True
        deadline = time.monotonic() + HOLD_ACK_TIMEOUT_S
        while time.monotonic() < deadline:
            if getattr(self._cell, "mask", None) == mask:
                return True
            time.sleep(0.02)
        return False

    def hold(self, mask: int, char: str = "") -> dict[str, Any]:
        if self._serial:
            self._cell.send(_dots_command(mask))
            return {"shown": True, "cell_ack": self._acked(mask)}
        self._cell.stop()
        self._cell.mask, self._cell.char = mask, char
        self._cell.sink.show(mask)
        return {"shown": True, "cell_ack": True}

    def show_text(self, text: str) -> dict[str, Any]:
        self._cell.spell(text)
        return {"shown": True, "cell_ack": True}

    def clear(self) -> dict[str, Any]:
        if self._serial:
            self._cell.send("CLEAR")
        else:
            self._cell.stop()
        return {"shown": True, "cell_ack": True}

    def state(self) -> dict[str, Any]:
        return {
            "connected": self._serial,
            "ready": True,
            "mask": getattr(self._cell, "mask", 0),
            "char": getattr(self._cell, "char", ""),
        }

    def close(self) -> None:
        try:
            self._cell.close()
        except Exception as exc:  # pragma: no cover - hardware teardown
            raise DeviceError(f"cell close failed: {exc}") from exc


def make_cell_device(config: dict[str, Any], backend: str):
    if backend != "real":
        return SimulatedCellDevice()

    from cane_vision.braille import Timing
    from cane_vision.serial_cell import make_cell

    cell_cfg = config.get("cell", {})
    timing = Timing(
        letter_hold_s=float(cell_cfg.get("letter_hold_s", 3.0)),
        letter_gap_s=float(cell_cfg.get("letter_gap_s", 0.3)),
        word_gap_s=float(cell_cfg.get("word_gap_s", 1.0)),
    )
    cell = make_cell(cell_cfg, timing)
    return RealCellDevice(cell, hold_s=timing.letter_hold_s)
