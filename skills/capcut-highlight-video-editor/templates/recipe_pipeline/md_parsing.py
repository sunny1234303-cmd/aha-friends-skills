"""Shared .md parsing helpers — used by both keyword detection (stage 5) and
overlay building (stage 6) so the same keyword list drives both what the
pipeline looks for in the transcript and the text shown in the overlay.

Not recipe-specific: this looks for *any* bullet list or markdown table in the
.md and treats its first column/leading word as a keyword — a recipe's
ingredients, a tutorial's steps, a review's product names, a checklist's
items, whatever the source content actually is about.

Supports two common list formats:
  - a bullet list:      ## 재료 \n - 양파 1/2개 \n - 마늘 2쪽
  - a markdown table:   ## 재료 \n | 채소 | 수량 | 금액 | \n |---|---|---| \n | 가지 | ... |

Section detection, in order:
  1. A heading (any level) whose text contains one of a handful of common
     Korean list-section words (재료, 키워드, 항목, 체크리스트, 단계, 포인트,
     리스트) — real files vary a lot in how they title this, so this is a
     loose contains-match, not an exact "## 재료" match.
  2. If no such heading exists, the first bullet-list-or-table block found
     anywhere in the document — so a plain .md with no matching heading at
     all (e.g. just "## Steps" followed by a table) still works.
"""

import re
from typing import Dict, Optional

_SECTION_HEADING_HINTS = ["재료", "키워드", "항목", "체크리스트", "단계", "포인트", "리스트"]

# Common leading modifiers in Korean list lines ("다진 마늘", "잘게 썬 양파")
# that aren't the item's own name — stripped so the keyword used for both the
# overlay and the transcript-matching (stage 5) is the actual noun.
_MODIFIER_PREFIXES = ["다진", "잘게", "채썬", "얇게", "썬", "다져", "신선한", "익힌"]

_SEPARATOR_CELL = re.compile(r":?-+:?")
_HEADING_LINE = re.compile(r"^#{1,6}\s")


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


def _find_list_section(content: str) -> Optional[str]:
    hint_pattern = "|".join(_SECTION_HEADING_HINTS)
    match = re.search(
        rf"^#{{1,6}}[^\n]*(?:{hint_pattern})[^\n]*$(.*?)(?=^#{{1,6}}\s|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    if match:
        return match.group(1)

    # Fallback: first bullet-list-or-table block anywhere, heading or not.
    for block in re.split(r"\n\s*\n", content):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        list_lines = [ln for ln in lines if not _HEADING_LINE.match(ln) and (ln.startswith("-") or ln.startswith("|"))]
        if list_lines:
            return block
    return None


def parse_ingredient_bullets(md_path: str) -> Dict[str, str]:
    """Returns {keyword: display_text} for every list item found in the .md.
    Falls back to an empty dict if no bullet list or table exists at all."""
    with open(md_path, encoding="utf-8") as f:
        content = f.read()

    section = _find_list_section(content)
    if section is None:
        return {}

    bullets: Dict[str, str] = {}
    table_data_started = False  # true once we've passed a "|---|---|" row

    for line in section.splitlines():
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
                continue  # header row of the table — not a keyword
            name = _extract_name(cells[0]) if cells else None
            if name:
                bullets[name] = " ".join(c for c in cells if c)

    return bullets
