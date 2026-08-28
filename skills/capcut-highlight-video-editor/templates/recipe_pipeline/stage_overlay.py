"""Stage 6: 미리 제시해준 내용(.md) 활용하여 내용 추가 (키워드 관련 텍스트 오버레이).

Parses the "## 재료" bullet list out of the content .md and, for each kept
highlight segment that mentions an ingredient, attaches the matching bullet
line(s) as a TextOverlay anchored at the segment's (original-timeline) start.
Timestamps get remapped onto the compressed output timeline later in pipeline.py.
"""

from typing import List, Tuple

import pycapcut as cc

from .md_parsing import parse_ingredient_bullets
from .models import SpeechSegment, TextOverlay

SEC = cc.SEC


def build_ingredient_overlays(
    highlight_segments: List[SpeechSegment],
    md_path: str,
    overlay_duration_sec: float = 2.5,
) -> List[TextOverlay]:
    bullets = parse_ingredient_bullets(md_path)
    overlays: List[TextOverlay] = []
    shown_keywords = set()

    for seg in highlight_segments:
        if not seg.has_ingredient:
            continue
        for kw in seg.matched_keywords:
            bullet = None
            for ing_name, text in bullets.items():
                if ing_name in kw or kw in ing_name:
                    bullet = text
                    break
            if kw in shown_keywords:
                continue
            shown_keywords.add(kw)
            overlays.append(
                TextOverlay(
                    start=seg.start,
                    duration=overlay_duration_sec,
                    text=bullet if bullet else kw,
                    source_ingredient=kw,
                )
            )
    return overlays


def add_overlay_segments(
    script: cc.ScriptFile,
    overlays_with_new_start: List[float],
    overlays: List[TextOverlay],
    track_name: str = "recipe_overlay",
    font: cc.FontType = None,
    font_size: float = 7.0,
    color: Tuple[float, float, float] = (1.0, 0.92, 0.6),
    vertical_position: float = 0.75,
    *,
    bold: bool = True,
    all_caps: bool = False,
    border=None,
    background=None,
    anim_in=None,
    anim_out=None,
    anim_duration_sec: float = 0.5,
) -> None:
    """overlays_with_new_start: new_start_sec for each entry in `overlays`,
    already remapped onto the compressed output timeline by pipeline.py.
    font=None 이면 CapCut 기본 폰트로 렌더 (한글 등 재현 불가 서체)."""
    for new_start, overlay in zip(overlays_with_new_start, overlays):
        style = cc.TextStyle(
            size=font_size,
            bold=bold,
            color=color,
            align=1,
            auto_wrapping=True,
        )
        text_segment = cc.TextSegment(
            overlay.text.upper() if all_caps else overlay.text,
            cc.Timerange(int(new_start * SEC), int(overlay.duration * SEC)),
            font=font,
            style=style,
            clip_settings=cc.ClipSettings(transform_y=vertical_position),
            border=border,
            background=background,
        )
        if anim_in is not None:
            text_segment.add_animation(anim_in, int(anim_duration_sec * 1_000_000))
        if anim_out is not None:
            text_segment.add_animation(anim_out, int(anim_duration_sec * 1_000_000))
        script.add_segment(text_segment, track_name)
