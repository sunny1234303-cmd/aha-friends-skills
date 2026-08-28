"""Shared helpers for turning user-facing style settings (hex color strings,
"top"/"center"/"bottom" position labels, font name strings, generic animation
names) into the values pycapcut's TextStyle/ClipSettings/FontType/TextBorder/
TextBackground/TextIntro/TextOutro actually expect."""

import difflib
import re
from typing import Optional, Tuple

import pycapcut as cc

# Curated subset of pycapcut's ~350 fonts — picked for visual variety and
# reliable rendering, not an exhaustive list. Keys are what the UI shows.
CAPTION_FONTS = {
    "기본 (Arimo)": "Arimo_Regular",
    "임팩트 굵은체 (Anton)": "Anton",
    "얇은 대문자체 (BebasNeue)": "BebasNeue",
    "모던 산세리프 (Montserrat)": "Montserrat",
    "깔끔한 산세리프 (Barlow)": "Barlow",
    "손글씨 굵게 (Amatic)": "Amatic_Bold",
    "코믹 펀치 (Bangers)": "BANGERS",
    "스텐실 (Black Ops One)": "Black_Ops_One_Regular",
    "필기체 (Kaushan Script)": "KaushanScript",
    "세리프 고급 (Cinzel)": "CINZEL",
}

_POSITION_TO_TRANSFORM_Y = {"top": 0.75, "center": 0.0, "bottom": -0.75}

# 분석기가 뽑은 폰트 패밀리 문자열(소문자) → pycapcut FontType 이름.
# 부분 문자열 매칭이라 "montserrat bold" 같은 것도 잡힌다.
_FONT_ALIASES = {
    "montserrat": "Montserrat",
    "anton": "Anton",
    "impact": "Anton",
    "oswald": "Anton",
    "bebas": "BebasNeue",
    "barlow": "Barlow",
    "amatic": "Amatic_Bold",
    "bangers": "BANGERS",
    "black ops": "Black_Ops_One_Regular",
    "kaushan": "KaushanScript",
    "cinzel": "CINZEL",
    "roboto": "Arimo_Regular",
    "arial": "Arimo_Regular",
    "helvetica": "Arimo_Regular",
    "noto sans": "Arimo_Regular",
    "pretendard": "Arimo_Regular",
    "apple sd gothic": "Arimo_Regular",
    "sans": "Arimo_Regular",
}

# 제네릭 애니메이션 이름 → 설치된 pycapcut 빌드에서 실제 확인된 CapCut enum 멤버 이름.
# enum 멤버 이름은 중국어이고 pycapcut 버전에 따라 바뀔 수 있어, resolve 시
# KeyError를 관대하게 처리한다.
_INTRO = {
    "fade": "渐显",
    "pop": "向上弹入",
    "slide-up": "向上滑动",
    "slide": "向上滑动",
    "typewriter": "打字机",
    "zoom": "放大",
    "scale": "放大",
    "karaoke": "卡拉OK",
}
_OUTRO = {
    "fade": "渐隐",
    "scale-down": "缩小",
    "shrink": "缩小",
    "slide-down": "向下滑动",
    "slide": "向下滑动",
}


def hex_to_rgb01(hex_color: str) -> Tuple[float, float, float]:
    hex_color = (hex_color or "").lstrip("#")
    if len(hex_color) != 6:
        return (1.0, 1.0, 1.0)
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return (r / 255, g / 255, b / 255)


def position_to_transform_y(position: str) -> float:
    return _POSITION_TO_TRANSFORM_Y.get(position, -0.75)


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def resolve_font(font_name: str, *, return_meta: bool = False):
    """폰트 이름 문자열 → cc.FontType. 정확 일치 → alias 부분매칭 → difflib 근사 →
    Arimo_Regular 폴백. return_meta=True면 (FontType, 실제로_쓴_이름) 튜플.

    None / "" / "__capcut_default__" 이면 None 을 반환한다 — 이 경우 TextSegment 가
    폰트를 지정하지 않아 CapCut 앱의 기본 폰트로 렌더된다(한글은 Arimo 폴백보다 이게 낫다).
    한글 등 CAPTION_FONTS 에 없는 서체는 파이프라인이 재현할 수 없으니 사용자가
    CapCut 에서 직접 지정해야 한다."""
    if not font_name or font_name == "__capcut_default__":
        return (None, "__capcut_default__") if return_meta else None

    requested = font_name or ""
    chosen = None

    try:
        chosen = cc.FontType[requested].name
    except KeyError:
        pass

    if chosen is None:
        low = requested.lower()
        for alias, target in _FONT_ALIASES.items():
            if alias in low:
                chosen = target
                break

    if chosen is None:
        norm_req = _normalize(requested)
        if norm_req:
            candidates = {_normalize(e.name): e.name for e in cc.FontType}
            match = difflib.get_close_matches(norm_req, list(candidates.keys()), n=1, cutoff=0.6)
            if match:
                chosen = candidates[match[0]]

    if chosen is None:
        chosen = "Arimo_Regular"

    try:
        font = cc.FontType[chosen]
    except KeyError:
        font, chosen = cc.FontType.Arimo_Regular, "Arimo_Regular"

    return (font, chosen) if return_meta else font


def build_text_border(color_hex: Optional[str], width: float, alpha: float = 1.0):
    """외곽선. color_hex가 없으면 None. width는 0~100(CapCut 기준) — pycapcut 내부에서
    width/100*0.2로 매핑하며 소스 주석이 '완전히 정확하지 않을 수 있음'이라 표시한다."""
    if not color_hex or not width:
        return None
    return cc.TextBorder(alpha=alpha, color=hex_to_rgb01(color_hex), width=float(width))


def build_text_background(enabled: bool, color_hex: str, alpha: float = 1.0, radius: float = 0.0):
    """배경 박스. color는 '#RRGGBB' 문자열 그대로."""
    if not enabled:
        return None
    color = color_hex if color_hex and color_hex.startswith("#") else "#000000"
    return cc.TextBackground(color=color, alpha=alpha, round_radius=radius)


def resolve_text_intro(name: Optional[str]):
    """제네릭 인트로 이름 → cc.TextIntro. 없거나 'none'이면 None."""
    if not name or name == "none":
        return None
    member = _INTRO.get(name)
    if member is None:
        return None
    try:
        return cc.TextIntro[member]
    except KeyError:
        return None


class _RawFontMeta:
    """pycapcut TextSegment 이 기대하는 font.value 인터페이스(.resource_id, .name)만 흉내."""

    def __init__(self, resource_id: str, name: str):
        self.resource_id = resource_id
        self.name = name


class RawFont:
    """CAPTION_FONTS/FontType 에 없는 폰트(한글 등)를 쓰기 위한 shim.
    CapCut 에서 그 폰트로 텍스트를 한 번 만들어 저장한 draft 에서 뽑은 font 블록
    ({resource_id, name})을 그대로 넣으면, export 시 그 폰트로 렌더된다.
    `capture_font.py` 스크립트가 draft 에서 이 dict 를 추출한다."""

    def __init__(self, resource_id: str, name: str):
        self.value = _RawFontMeta(str(resource_id), name)


def raw_font(font_capcut: Optional[dict]):
    """{"resource_id": ..., "name": ...} → RawFont. None/불완전하면 None."""
    if not font_capcut or not font_capcut.get("resource_id"):
        return None
    return RawFont(font_capcut["resource_id"], font_capcut.get("name", "CustomFont"))


def resolve_text_outro(name: Optional[str]):
    """제네릭 아웃트로 이름 → cc.TextOutro. 없거나 'none'이면 None."""
    if not name or name == "none":
        return None
    member = _OUTRO.get(name)
    if member is None:
        return None
    try:
        return cc.TextOutro[member]
    except KeyError:
        return None
