from dataclasses import dataclass, field
from typing import List


@dataclass
class TranscriptSegment:
    """One SRT cue, times in seconds relative to the source video."""

    start: float
    end: float
    text: str
    has_ingredient: bool = False
    matched_keywords: List[str] = field(default_factory=list)


@dataclass
class SpeechSegment:
    """A run of TranscriptSegments merged across small gaps (stage 3 output)."""

    start: float
    end: float
    cues: List[TranscriptSegment]
    has_ingredient: bool = False
    matched_keywords: List[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def text(self) -> str:
        return " ".join(c.text for c in self.cues)


@dataclass
class IngredientMention:
    """One TranscriptSegment cue that mentions an ingredient (stage 5 output)."""

    start: float
    end: float
    text: str
    matched_keywords: List[str]


@dataclass
class TextOverlay:
    """A recipe/ingredient info overlay derived from the .md content (stage 6)."""

    start: float
    duration: float
    text: str
    source_ingredient: str
