"""Map raw model class names to what we say and what we spell."""

from __future__ import annotations

from dataclasses import dataclass

# COCO names that read badly when spoken or take too long to spell.
DEFAULT_RENAMES: dict[str, str] = {
    "dining table": "table",
    "potted plant": "plant",
    "cell phone": "phone",
    "tv": "TV",
    "fire hydrant": "hydrant",
    "parking meter": "meter",
    "sports ball": "ball",
    "wine glass": "glass",
    "hair drier": "hair dryer",
    "baseball bat": "bat",
    "baseball glove": "glove",
    "tennis racket": "racket",
}


# Names that are already plural take no article ("you're looking at stairs").
PLURALS = {"stairs", "steps", "scissors", "glasses", "shoes", "clothes"}


def with_article(word: str) -> str:
    """'chair' -> 'a chair', 'elevator' -> 'an elevator', 'stairs' -> 'stairs'."""
    if word.lower() in PLURALS:
        return word
    return f"{'an' if word[:1].lower() in 'aeiou' else 'a'} {word}"


def format_phrase(phrase: str, word: str) -> str:
    """Fill `{object}` (the bare word) and `{a_object}` (with a/an) in a phrase."""
    return phrase.format(object=word, a_object=with_article(word))


@dataclass(frozen=True)
class Announcement:
    spoken: str
    braille: str


class LabelMap:
    def __init__(
        self,
        renames: dict[str, str] | None = None,
        ignore: list[str] | None = None,
        min_confidence: dict[str, float] | None = None,
    ):
        self.renames = {**DEFAULT_RENAMES, **(renames or {})}
        self.ignore = set(ignore or [])
        self.min_confidence = min_confidence or {}

    def allowed(self, label: str, confidence: float = 1.0) -> bool:
        """False for ignored classes and for scores below that class's own
        threshold (on top of the detector-wide `confidence`)."""
        return label not in self.ignore and confidence >= self.min_confidence.get(label, 0.0)

    def __call__(self, label: str) -> Announcement:
        word = self.renames.get(label, label)
        return Announcement(spoken=word, braille=word.lower())
