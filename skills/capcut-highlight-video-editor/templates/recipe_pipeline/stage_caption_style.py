"""Stage 7: 자막 글꼴/크기/위치/확대.

Captions are built as individual TextSegments (not script.import_srt) because
the output timeline is a compressed, discontinuous remix of the source video
(stage 3/4 cut gaps and dropped filler) — a straight SRT import would put
captions at their *original* timestamps, which no longer line up with what's
on screen after the cut. Each caption is placed at its new_start (already
remapped onto the compressed timeline by pipeline.py) instead.

Zoom/emphasis (확대) is applied only to captions whose SpeechSegment mentions
an ingredient, to visually tie the effect to the ingredient reveal.
"""

from typing import List, Tuple

import pycapcut as cc

from .models import SpeechSegment

SEC = cc.SEC


def add_captions(
    script: cc.ScriptFile,
    mapped_segments: List[Tuple[float, SpeechSegment]],
    track_name: str = "captions",
    font: cc.FontType = cc.FontType.Arimo_Regular,
    font_size: float = 10.0,
    color: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    vertical_position: float = -0.75,
) -> None:
    """mapped_segments: list of (new_start_sec, SpeechSegment) in output-timeline order."""
    for new_start, seg in mapped_segments:
        offset = new_start - seg.start
        for cue in seg.cues:
            cue_new_start = cue.start + offset
            cue_new_end = cue.end + offset
            style = cc.TextStyle(
                size=font_size,
                bold=True,
                color=color,
                align=1,
                auto_wrapping=True,
            )
            text_segment = cc.TextSegment(
                cue.text,
                cc.Timerange(
                    int(cue_new_start * SEC), int((cue_new_end - cue_new_start) * SEC)
                ),
                font=font,
                style=style,
                clip_settings=cc.ClipSettings(transform_y=vertical_position),
            )
            if seg.has_ingredient:
                text_segment.add_keyframe(cc.KeyframeProperty.uniform_scale, 0, 1.0)
                text_segment.add_keyframe(
                    cc.KeyframeProperty.uniform_scale, int(0.3 * SEC), 1.15
                )
            script.add_segment(text_segment, track_name)
