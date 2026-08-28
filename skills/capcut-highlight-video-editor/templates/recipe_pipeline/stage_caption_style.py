"""Stage 7: 자막 글꼴/크기/위치/확대 + (스타일 프로필) 외곽선/그림자/배경/애니메이션.

Captions are built as individual TextSegments (not script.import_srt) because
the output timeline is a compressed, discontinuous remix of the source video
(stage 3/4 cut gaps and dropped filler) — a straight SRT import would put
captions at their *original* timestamps, which no longer line up with what's
on screen after the cut. Each caption is placed at its new_start (already
remapped onto the compressed timeline by pipeline.py) instead.

Zoom/emphasis (확대) trigger:
  - "keyword": 키워드가 언급된 SpeechSegment의 자막에만 (기존 동작)
  - "all": 모든 자막에
  - "none": 끔

드롭섀도우는 pycapcut이 export_material에서 주석 처리해둬서 기본 지원되지 않는다.
아래 _ShadowTextSegment가 그 필드를 직접 주입한다 — 실험적, CapCut에서 육안 확인 필요.
"""

from typing import List, Optional, Tuple

import pycapcut as cc

from .models import SpeechSegment
from .style_utils import hex_to_rgb01

SEC = cc.SEC


class _ShadowTextSegment(cc.TextSegment):
    """pycapcut이 연결하지 않은 드롭섀도우 필드를 export_material에 주입하는 서브클래스.
    실험적 — shadow_point는 angle/distance에서 파생. check_flag |= 32."""

    def __init__(self, *args, shadow: Optional[dict] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._shadow = shadow

    def export_material(self):
        import math

        d = super().export_material()
        if self._shadow:
            angle = float(self._shadow.get("angle", -45.0))
            dist = float(self._shadow.get("distance", 5.0))
            rad = math.radians(angle)
            d.update(
                {
                    "has_shadow": True,
                    "shadow_alpha": float(self._shadow.get("alpha", 0.9)),
                    "shadow_angle": angle,
                    "shadow_color": self._shadow.get("color", "#000000"),
                    "shadow_distance": dist,
                    "shadow_point": {
                        "x": math.cos(rad) * (dist / 8.0),
                        "y": math.sin(rad) * (dist / 8.0),
                    },
                    "shadow_smoothing": 0.45,
                }
            )
            d["check_flag"] = d.get("check_flag", 7) | 32
        return d


def add_captions(
    script: cc.ScriptFile,
    mapped_segments: List[Tuple[float, SpeechSegment]],
    track_name: str = "captions",
    font: cc.FontType = cc.FontType.Arimo_Regular,
    font_size: float = 10.0,
    color: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    vertical_position: float = -0.75,
    *,
    bold: bool = True,
    align: int = 1,
    all_caps: bool = False,
    border=None,
    background=None,
    anim_in=None,
    anim_out=None,
    anim_duration_sec: float = 0.5,
    zoom_trigger: str = "keyword",
    zoom_scale: float = 1.15,
    zoom_duration_sec: float = 0.3,
    shadow_opts: Optional[dict] = None,
) -> None:
    """mapped_segments: list of (new_start_sec, SpeechSegment) in output-timeline order."""
    for new_start, seg in mapped_segments:
        offset = new_start - seg.start
        for cue in seg.cues:
            cue_new_start = cue.start + offset
            cue_new_end = cue.end + offset
            text = cue.text.upper() if all_caps else cue.text
            style = cc.TextStyle(
                size=font_size,
                bold=bold,
                color=color,
                align=align,
                auto_wrapping=True,
            )
            timerange = cc.Timerange(
                int(cue_new_start * SEC), int((cue_new_end - cue_new_start) * SEC)
            )
            common = dict(
                font=font,
                style=style,
                clip_settings=cc.ClipSettings(transform_y=vertical_position),
                border=border,
                background=background,
            )
            if shadow_opts:
                text_segment = _ShadowTextSegment(text, timerange, shadow=shadow_opts, **common)
            else:
                text_segment = cc.TextSegment(text, timerange, **common)

            if anim_in is not None:
                text_segment.add_animation(anim_in, int(anim_duration_sec * 1_000_000))
            if anim_out is not None:
                text_segment.add_animation(anim_out, int(anim_duration_sec * 1_000_000))

            do_zoom = zoom_trigger == "all" or (
                zoom_trigger == "keyword" and seg.has_ingredient
            )
            if do_zoom:
                text_segment.add_keyframe(cc.KeyframeProperty.uniform_scale, 0, 1.0)
                text_segment.add_keyframe(
                    cc.KeyframeProperty.uniform_scale,
                    int(zoom_duration_sec * SEC),
                    zoom_scale,
                )
            script.add_segment(text_segment, track_name)
