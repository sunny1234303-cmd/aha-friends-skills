"""Shared .md parsing helpers — used by both ingredient_detection (stage 5)
and stage_overlay (stage 6) so the same ingredient list drives both the
keyword list to detect and the text shown in the overlay.

Supports two common ways people write an ingredient list:
  - a bullet list:      ## 재료 \n - 양파 1/2개 \n - 마늘 2쪽
  - a markdown table:   ## 재료 \n | 채소 | 수량 | 금액 | \n |---|---|---| \n | 가지 | ... |
The section header just needs to contain "재료" somewhere (any heading level),
not match "## 재료" exactly — real files vary a lot in how they title this.
"""

import re
from typing import Dict, Optional

# Common leading modifiers in Korean ingredient lines ("다진 마늘", "잘게 썬 양파")
# that aren't the ingredient's name — stripped so the keyword used for both the
# overlay and the subtitle-matching (stage 5) is the actual ingredient noun.
_MODIFIER_PREFIXES = ["다진", "잘게", "채썬", "얇게", "썬", "다져", "신선한", "익힌"]

_SEPARATOR_CELL = re.compile(r":?-+:?")


def _clean(text: str) -> str:
    """Strip markdown emphasis/backticks so "**가지**" -> "가지"."""
    return re.sub(r"[*_`]", "", text).strip()


def _extract_name(text: str) -> Optional[str]:
    words = text.split()
    while words and words[0] in _MODIFIER_PREFIXES:
        words.pop(0)
    if not words:
        return None
    match = re.match(r"(\S+)", words[0])
    return _clean(match.group(1)) if match else None


def parse_ingredient_bullets(md_path: str) -> Dict[str, str]:
    """Returns {ingredient_name: display_text} for every ingredient found in
    the recipe section. Falls back to an empty dict if no such section."""
    with open(md_path, encoding="utf-8") as f:
        content = f.read()

    match = re.search(
        r"^#{1,6}[^\n]*재료[^\n]*$(.*?)(?=^#{1,6}\s|\Z)", content, re.MULTILINE | re.DOTALL
    )
    if not match:
        return {}

    bullets: Dict[str, str] = {}
    table_data_started = False  # true once we've passed a "|---|---|" row

    for line in match.group(1).splitlines():
        line = line.strip()
        if not line:
            table_data_started = False
            continue

        if line.startswith("-") and not line.startswith("|"):
            bullet_text = _clean(line.lstrip("-").strip())
            name = _extract_name(bullet_text)
            if name:
                bullets[name] = bullet_text

        elif line.startswith("|"):
            cells = [_clean(c) for c in line.strip("|").split("|")]
            if all(_SEPARATOR_CELL.fullmatch(c) for c in cells if c):
                table_data_started = True
                continue
            if not table_data_started:
                continue  # header row of the table — not an ingredient
            name = _extract_name(cells[0]) if cells else None
            if name:
                bullets[name] = " ".join(c for c in cells if c)

    return bullets
