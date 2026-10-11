"""Device adapters for the Orin harness.

Each factory returns a small object with a plain, blocking interface. The
`real` backend lazily imports `cane_vision`/hardware libraries so a simulated
dry run never needs OpenCV, Ultralytics, pyserial or sounddevice installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = [
    "make_cell_device",
    "make_vision_device",
    "make_speech_device",
    "make_listening_device",
]


def _backend(config: dict[str, Any]) -> str:
    return config.get("backend", "sim")


def make_cell_device(config: dict[str, Any], backend: str | None = None):
    from .cell import make_cell_device as _make

    return _make(config, backend or _backend(config))


def make_vision_device(config: dict[str, Any], base_dir: Path, backend: str | None = None):
    from .vision import make_vision_device as _make

    return _make(config, base_dir, backend or _backend(config))


def make_speech_device(config: dict[str, Any], backend: str | None = None):
    from .speech import make_speech_device as _make

    return _make(config, backend or _backend(config))


def make_listening_device(config: dict[str, Any], backend: str | None = None):
    from .listening import make_listening_device as _make

    return _make(config, backend or _backend(config))
