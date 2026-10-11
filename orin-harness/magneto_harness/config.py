"""Configuration loading and validation for the Orin harness.

The config is a plain dict loaded from YAML with defaults merged in. Keeping it
a dict (rather than a dataclass tree) fits the small device factories that read
slices of it and matches the style of `cane_vision`'s config handling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError
from .paths import DEFAULT_CONFIG

DEFAULTS: dict[str, Any] = {
    "backend": "sim",
    "session": {
        "max_activities": 6,
        "advance_on_correct": True,
        "max_trace": 40,
        "idle_timeout_s": 120,
    },
    "lesson": {"default": "word_cab", "catalog": {}, "prompts": {}},
    "bounds": {
        "max_prompt_chars": 240,
        "max_phrase_chars": 160,
        "max_observe_items": 10,
        "max_outcomes": 20,
        "max_observations": 10,
        "max_cell_text_chars": 64,
    },
    "cell": {"port": "none", "baud": 115200, "letter_hold_s": 3.0, "letter_gap_s": 0.3, "word_gap_s": 1.0},
    "camera": {"source": "none"},
    "detector": {"model": "yolov8s-worldv2.pt", "vocabulary": "vocabulary.txt", "confidence": 0.25, "image_size": 640},
    "cane": {"tip_x": 0.5, "tip_y": 0.85, "reach": 0.06},
    "speech": {"engine": "auto", "phrase": "{object}", "elevenlabs": {}},
    "listening": {
        "enabled": False,
        "engine": "scripted",
        "sample_rate": 16000,
        "frame_ms": 30,
        "vad": "energy",
        "energy_threshold": 500,
        "min_segment_s": 0.25,
        "max_segment_s": 6.0,
        "silence_ms": 800,
        "stt": {"model_id": "scribe_v2", "language": "eng", "timeout_s": 8.0},
        "scripted": [],
    },
    "brain": {
        "mode": "direct",
        "agent_app": "agent-bricks-magneto-companion",
        "model_endpoint": "databricks-qwen3-next-80b-a3b-instruct",
        "services_config": "databricks/platform/services.toml",
        "timeout_s": 15,
        "max_tokens": 600,
    },
    "grading": {"aliases": {}},
}

BACKENDS = {"sim", "real"}
BRAIN_MODES = {"direct", "agent", "fixture"}
LISTEN_ENGINES = {"scripted", "scribe"}
VADS = {"energy", "webrtcvad", "none"}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load config, merging over defaults. Missing file is an error unless the
    default path is used, in which case defaults alone are returned."""

    config_path = Path(path) if path else DEFAULT_CONFIG
    if config_path.exists():
        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - malformed user file
            raise ConfigError(f"cannot parse config {config_path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigError(f"config {config_path} must be a mapping")
    elif path is not None:
        raise ConfigError(f"config not found: {config_path}")
    else:
        raw = {}

    config = _merge(DEFAULTS, raw)
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    backend = config.get("backend")
    if backend not in BACKENDS:
        raise ConfigError(f"backend must be one of {sorted(BACKENDS)}, got {backend!r}")

    brain_mode = config["brain"].get("mode")
    if brain_mode not in BRAIN_MODES:
        raise ConfigError(f"brain.mode must be one of {sorted(BRAIN_MODES)}, got {brain_mode!r}")

    listening = config["listening"]
    if listening.get("engine") not in LISTEN_ENGINES:
        raise ConfigError(f"listening.engine must be one of {sorted(LISTEN_ENGINES)}")
    if listening.get("vad") not in VADS:
        raise ConfigError(f"listening.vad must be one of {sorted(VADS)}")

    catalog = config["lesson"].get("catalog") or {}
    default_lesson = config["lesson"].get("default")
    if default_lesson and default_lesson not in catalog:
        raise ConfigError(f"lesson.default {default_lesson!r} is not in lesson.catalog")

    for scheme in ("max_prompt_chars", "max_phrase_chars", "max_observe_items"):
        if int(config["bounds"][scheme]) <= 0:
            raise ConfigError(f"bounds.{scheme} must be positive")

    for lesson_id, spec in catalog.items():
        targets = spec.get("targets")
        if not isinstance(targets, list) or not targets:
            raise ConfigError(f"lesson {lesson_id!r} needs a non-empty targets list")
        if spec.get("activity") not in {"introduce", "identify", "match", "spell"}:
            raise ConfigError(f"lesson {lesson_id!r} has an invalid activity")
