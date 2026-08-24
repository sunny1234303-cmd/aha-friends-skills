"""Stage 3: 무자막 구간 컷 편집.

Any video time not covered by a kept cue is, by construction, already
excluded from the output timeline (stage 4 only selects a subset of cues, and
only cue-covered spans become VideoSegments) — so "cutting no-caption
regions" happens implicitly. This module's remaining job is deciding, among
the *selected* cues (stage 4's output), which consecutive ones are close
enough in the original video to bridge into a single continuous VideoSegment
(small natural pause) versus far enough apart that a real cut/jump exists
between them (large gap, or a dropped cue in between).
"""

from typing import List

from .models import SpeechSegment, TranscriptSegment


def merge_cues_into_blocks(
    selected_cues: List[TranscriptSegment], bridge_gap_sec: float = 0.6
) -> List[SpeechSegment]:
    if not selected_cues:
        return []

    ordered = sorted(selected_cues, key=lambda c: c.start)
    blocks: List[SpeechSegment] = []
    current = [ordered[0]]

    for cue in ordered[1:]:
        if cue.start - current[-1].end < bridge_gap_sec:
            current.append(cue)
        else:
            blocks.append(_make_block(current))
            current = [cue]

    blocks.append(_make_block(current))
    return blocks


def _make_block(cues: List[TranscriptSegment]) -> SpeechSegment:
    return SpeechSegment(
        start=cues[0].start,
        end=cues[-1].end,
        cues=list(cues),
        has_ingredient=any(c.has_ingredient for c in cues),
        matched_keywords=sorted({kw for c in cues for kw in c.matched_keywords}),
    )
