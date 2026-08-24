"""Stage 4: 총 60초 클립 편집 (식재료 등장 구간 중심 선별).

Depends on stage 5's has_ingredient tags (already set on each cue by
ingredient_detection.tag_ingredient_cues before this runs).

Operates at cue (phrase) granularity, not on gap-merged blocks — a
continuously-narrated video may have near-zero pauses between sentences, in
which case gap-merging alone would produce one giant atomic block that either
entirely fits the budget or entirely doesn't, making "prioritize ingredient
segments" meaningless. Selecting per-cue lets the pipeline actually drop
non-ingredient cues to make room, matching the user's intent (order preserved,
less-important parts skipped). Selected cues are re-merged into contiguous
video blocks afterward in stage_gaps.merge_cues_into_blocks.

Selection rule (confirmed with user): keep chronological order; prioritize
cues that mention an ingredient; fill remaining budget with non-ingredient
cues in original order; if ingredient cues alone exceed the target, keep them
in chronological order up to budget and drop the rest.
"""

from typing import List

from .models import TranscriptSegment


def select_highlight_cues(
    cues: List[TranscriptSegment], target_duration_sec: float = 60.0
) -> List[TranscriptSegment]:
    if not cues:
        return []

    ordered = sorted(cues, key=lambda c: c.start)

    kept: List[TranscriptSegment] = []
    total = 0.0

    # Pass 1: chronological order, ingredient cues only, up to budget.
    for cue in ordered:
        duration = cue.end - cue.start
        if cue.has_ingredient and total + duration <= target_duration_sec:
            kept.append(cue)
            total += duration

    # Pass 2: fill remaining budget with filler cues, chronological order.
    if total < target_duration_sec:
        for cue in ordered:
            if cue in kept:
                continue
            duration = cue.end - cue.start
            if total + duration <= target_duration_sec:
                kept.append(cue)
                total += duration

    kept.sort(key=lambda c: c.start)
    return kept
