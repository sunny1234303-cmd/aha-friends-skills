"""Stage 5 로직: 자막을 기반으로 식재료 사용 구간 분석.

Executes right after stage 2 (transcription) and before stage 4 (60s highlight
selection) even though the user's original numbering lists it after stage 4 —
stage 4's "ingredient-centric" selection needs this output first. See plan
Context section for the reordering rationale.

Tags each cue in place (has_ingredient / matched_keywords) rather than
producing a separate mention list, since selection now operates at cue
granularity (see stage_highlight.py).

Keyword source: the "## 재료" bullet list in the same content .md used for
stage 6's overlays (no separate ingredient-list file — the .md is already the
single source of truth for what counts as an ingredient in this recipe).
"""

from typing import List

from .md_parsing import parse_ingredient_bullets
from .models import TranscriptSegment


def extract_ingredient_keywords(md_path: str) -> List[str]:
    return list(parse_ingredient_bullets(md_path).keys())


def tag_ingredient_cues(cues: List[TranscriptSegment], keywords: List[str]) -> None:
    for cue in cues:
        matched = [kw for kw in keywords if kw in cue.text]
        if matched:
            cue.has_ingredient = True
            cue.matched_keywords = matched
