"""Deterministic grading of a learner transcript against the expected target.

This is evidence, not mastery. It reports an exact/partial/none match and one
of correct/incorrect/unrecognized, and says nothing about the learner's
knowledge. Spoken-letter aliases (see, bee, ...) are honored so short answers
transcribe reliably; words match on whole tokens.
"""

from __future__ import annotations

import re
from typing import Any

DEFAULT_ALIASES: dict[str, list[str]] = {
    "a": ["a", "ay", "aye"],
    "b": ["b", "bee", "be"],
    "c": ["c", "see", "sea"],
    "d": ["d", "dee"],
    "e": ["e", "ee"],
    "g": ["g", "gee"],
    "i": ["i", "eye"],
    "j": ["j", "jay"],
    "k": ["k", "kay"],
    "o": ["o", "oh"],
    "p": ["p", "pea", "pee"],
    "q": ["q", "cue", "queue"],
    "r": ["r", "are"],
    "t": ["t", "tea", "tee"],
    "u": ["u", "you"],
    "v": ["v", "vee"],
    "y": ["y", "why"],
    "z": ["z", "zee", "zed"],
}

_WORD = re.compile(r"[a-z]+")


def normalize(text: str | None) -> str:
    return " ".join(_WORD.findall((text or "").lower()))


def _tokens(text: str | None) -> list[str]:
    return normalize(text).split()


def _aliases_for(expected: str, aliases: dict[str, list[str]]) -> set[str]:
    if len(expected) != 1:
        return {expected}
    merged = set(DEFAULT_ALIASES.get(expected, [])) | set(aliases.get(expected, []))
    merged.add(expected)
    return merged


def grade(transcript: str | None, expected: str | None, aliases: dict[str, list[str]] | None = None) -> tuple[str, str]:
    """Return (match, outcome). match in {exact, partial, none}; outcome in
    {correct, incorrect, unrecognized}."""

    exp = normalize(expected)
    tokens = _tokens(transcript)
    if not exp:
        return "none", "unrecognized"
    if not tokens:
        return "none", "unrecognized"

    table = dict(DEFAULT_ALIASES)
    for key, values in (aliases or {}).items():
        table[key] = list({*table.get(key, []), *values})

    exp_aliases = _aliases_for(exp, table)
    if len(tokens) == 1 and tokens[0] in exp_aliases:
        return "exact", "correct"
    if any(token in exp_aliases for token in tokens):
        return "partial", "correct"
    # A longer expected word may appear inside a spoken phrase.
    if len(exp) > 1 and exp in normalize(transcript):
        return "partial", "correct"
    return "none", "incorrect"


def grade_config(config: dict[str, Any]) -> dict[str, list[str]]:
    return config.get("grading", {}).get("aliases") or {}
