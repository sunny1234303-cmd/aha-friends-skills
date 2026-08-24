"""Shared helpers for turning user-facing style settings (hex color strings,
"top"/"center"/"bottom" position labels, font name strings) into the values
pycapcut's TextStyle/ClipSettings/FontType actually expect."""

from typing import Tuple

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


def hex_to_rgb01(hex_color: str) -> Tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (1.0, 1.0, 1.0)
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return (r / 255, g / 255, b / 255)


def position_to_transform_y(position: str) -> float:
    return _POSITION_TO_TRANSFORM_Y.get(position, -0.75)


def resolve_font(font_name: str) -> cc.FontType:
    try:
        return cc.FontType[font_name]
    except KeyError:
        return cc.FontType.Arimo_Regular
