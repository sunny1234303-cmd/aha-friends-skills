"""Step 7: samples.json + metrics.json + vision-notes.json → style-profile.json

사용:
  python3 build_profile.py <out_dir> [--capcut-project PATH] [--slug NAME] [--install]

vision-notes.json 은 Step 4에서 Claude가 작성한다 (references/analysis-methodology.md).
없으면 비전 파트는 비우고 파이프라인 기본값에 맡긴다.

폰트: 여기선 가벼운 alias 매핑만. 실제 fuzzy 해석(difflib 포함)은 capcut 파이프라인의
recipe_pipeline.style_utils.resolve_font 가 실행 시점에 한다.
"""
import argparse
import datetime as dt
import json
import os
import shutil

from _common import dump_json, load_json, slugify

_FONT_ALIASES = {
    "montserrat": "Montserrat", "anton": "Anton", "impact": "Anton", "oswald": "Anton",
    "bebas": "BebasNeue", "barlow": "Barlow", "amatic": "Amatic_Bold", "bangers": "BANGERS",
    "black ops": "Black_Ops_One_Regular", "kaushan": "KaushanScript", "cinzel": "CINZEL",
    "roboto": "Arimo_Regular", "arial": "Arimo_Regular", "helvetica": "Arimo_Regular",
    "noto sans": "Arimo_Regular", "pretendard": "Arimo_Regular", "gothic": "Arimo_Regular",
}
ANALYZER_VERSION = "1.0.0"


def _alias_font(family: str):
    low = (family or "").lower()
    for a, t in _FONT_ALIASES.items():
        if a in low:
            return t
    # 라틴 폰트명이면 그대로 (파이프라인 resolve_font 가 difflib 로 처리).
    # 한글 등 CAPTION_FONTS 에 없는 서체는 "__capcut_default__" → 파이프라인이
    # 폰트를 지정하지 않고 CapCut 기본 폰트로 렌더 (Arimo 강제보다 나음).
    # 정확한 서체는 사용자가 CapCut 에서 직접 골라야 한다.
    import re as _re

    if family and _re.fullmatch(r"[A-Za-z0-9 _\-]+", family):
        return family
    return "__capcut_default__"


def _v(node, default=None):
    """vision-notes 필드 {value,confidence,evidence} 에서 value 꺼내기 (또는 raw)."""
    if isinstance(node, dict) and "value" in node:
        return node["value"]
    return node if node is not None else default


def _conf(node):
    return node.get("confidence") if isinstance(node, dict) else None


def _size_from_ratio(ratio, lo=5.0, hi=30.0):
    """대문자 글자높이/프레임높이 비율 → 파이프라인 caption_size.
    보정 기준: 0.04→8(기본급), 0.08→15(큰 자막), 0.12→22(초대형). 정밀치 아님 — CapCut 확인 필요."""
    if ratio is None:
        return None
    return round(min(hi, max(lo, 175.0 * float(ratio) + 1.0)), 1)


def _pos_from_ratio(r):
    if r is None:
        return None
    return "top" if r < 0.33 else ("bottom" if r > 0.66 else "center")


def _outline(node):
    if not isinstance(node, dict):
        return {"enabled": False}
    val = node.get("value", node)
    if not val or not val.get("enabled"):
        return {"enabled": False}
    wr = val.get("width_ratio")  # 외곽선 두께 / 글자 획 두께 (대략)
    return {
        "enabled": True,
        "color": val.get("color", "#000000"),
        "width": round(min(60.0, max(5.0, (wr or 0.3) * 70.0)), 1),
        "alpha": val.get("alpha", 1.0),
    }


def _bg(node):
    val = node.get("value", node) if isinstance(node, dict) else {}
    if not val or not val.get("enabled"):
        return {"enabled": False}
    return {
        "enabled": True,
        "color": val.get("color", "#000000"),
        "alpha": val.get("alpha", 1.0),
        "round_radius": val.get("round", 0.0),
    }


def _shadow(node):
    val = node.get("value", node) if isinstance(node, dict) else {}
    if not val or not val.get("enabled"):
        return {"enabled": False}
    return {
        "enabled": True,
        "color": val.get("color", "#000000"),
        "alpha": val.get("alpha", 0.9),
        "angle": val.get("angle_deg", -45.0),
        "distance": val.get("distance", 5.0),
    }


def _anim(node):
    val = node.get("value", node) if isinstance(node, dict) else {}
    if not isinstance(val, dict):
        val = {}
    return {
        "in": val.get("in", "none") or "none",
        "out": val.get("out", "none") or "none",
        "duration_sec": val.get("duration_sec", 0.3),
    }


def _text_block(vn: dict, key: str) -> dict:
    """vision-notes 의 caption/overlay 블록 → applied.caption/overlay."""
    b = vn.get(key, {}) or {}
    family = _v(b.get("font_family")) or ""
    out = {
        "font_family": family or None,
        "font": _alias_font(family) if family else None,
        "font_confidence": _conf(b.get("font_family")) if family else None,
        "size": _size_from_ratio(_v(b.get("size_ratio"))),
        "color": _v(b.get("color")),
        "position": _v(b.get("position")) or _pos_from_ratio(_v(b.get("position_ratio"))),
        "align": _v(b.get("align")),
        "bold": _v(b.get("bold")),
        "all_caps": _v(b.get("all_caps")),
        "outline": _outline(b.get("outline")),
        "background": _bg(b.get("background")),
        "animation": _anim(vn.get(f"{key}_animation") or b.get("animation")),
    }
    if key == "caption":
        out["shadow"] = _shadow(b.get("shadow"))
        if _v(b.get("position_ratio")) is not None:
            out["transform_y"] = round(1.0 - 2.0 * float(_v(b["position_ratio"])), 3)
    if out.get("font") == "__capcut_default__":
        out["font_note"] = (
            f"파이프라인이 재현 못하는 서체 — CapCut에서 직접 지정 필요. 관찰: {family}"
        )
    # None 과 빈 문자열 제거 (빈 값은 파이프라인 기본값에 맡긴다)
    return {k: v for k, v in out.items() if v is not None and v != ""}


def _limitations(caption: dict, overlay: dict) -> list:
    """capcut-highlight-video-editor 파이프라인이 구조적으로 재현 못하는 것들."""
    lims = [
        "컷 편집이 자막(cue) 경계에 묶임 — 원본 채널처럼 '자막과 무관하게 내용/샷 기준으로 컷'은 불가. gap_threshold_sec 를 키워 덜 잘게 쪼갤 수는 있음.",
        "색보정(advisory.color_grade)은 적용 단계가 없음 — CapCut 조정 레이어/LUT 수동.",
        "전환 효과(스피드라인/whip 등), 이모지 스티커, 고정 워터마크/CTA 오버레이는 파이프라인 밖.",
    ]
    if caption.get("font") == "__capcut_default__" or overlay.get("font") == "__capcut_default__":
        lims.append(
            "자막/오버레이 서체가 pycapcut FontType(라틴 348종)에 없음 → CapCut 기본 폰트로 렌더. "
            "정확한 한글 서체는 CapCut 에서 직접 지정."
        )
    return lims


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--capcut-project", default=os.environ.get(
        "CAPCUT_PROJECT",
        os.path.expanduser("~/capcut-highlight-video-editor")))
    ap.add_argument("--slug", default=None)
    ap.add_argument("--install", action="store_true", help="capcut 프로젝트 style-profiles/ 에 복사")
    ap.add_argument(
        "--sfx-map", default=None,
        help='사용자가 정한 효과음 배치 JSON. 예: \'[{"file":"whoosh.wav","trigger":"cuts"}]\'. '
             "스킬이 사용자에게 물어본 뒤 넘긴다.",
    )
    args = ap.parse_args()

    out = args.out_dir
    samples = load_json(os.path.join(out, "samples.json"))
    metrics = load_json(os.path.join(out, "metrics.json"))
    vn_path = os.path.join(out, "vision-notes.json")
    vn = load_json(vn_path) if os.path.exists(vn_path) else {}
    if not vn:
        print("⚠ vision-notes.json 없음 — 자막 서체/애니메이션 파트는 비움 (Step 4 필요)")

    shots = metrics.get("shots", {}).get("aggregate", {})
    container = dict(metrics.get("container", {}))
    # 캔버스는 다운로드본(저해상도)이 아니라 원본 해상도 기준. 세로면 1080x1920로 스냅.
    orig = [(v.get("width"), v.get("height")) for v in samples.get("picked", []) if v.get("width") and v.get("height")]
    if orig:
        from collections import Counter

        w, h = Counter(orig).most_common(1)[0][0]
        if h > w:  # 세로 숏폼
            w, h = 1080, 1920
        container["width"], container["height"] = w, h
    audio = metrics.get("audio", {}).get("aggregate", {})
    timing = metrics.get("timing", {})
    pacing = timing.get("pacing_suggestion", {})

    slug = args.slug or samples.get("channel_slug") or slugify(
        samples.get("channel_name") or samples.get("source_url"))

    caption = _text_block(vn, "caption")
    overlay = _text_block(vn, "overlay")

    emph = vn.get("caption_emphasis", {}) or {}
    zoom = vn.get("zoom", {}) or {}
    emphasis = {
        "trigger": _v(emph.get("trigger"), "keyword"),
        "scale": _v(zoom.get("scale")) or _v(emph.get("scale")) or 1.15,
        "duration_sec": 0.25,
    }

    durs = [v.get("duration_sec") for v in samples.get("picked", []) if v.get("duration_sec")]
    target_dur = round(sorted(durs)[len(durs) // 2]) if durs else None

    # gap_threshold_sec 는 자막 간격이 아니라 "샷이 얼마나 길게 유지되는지"에서 온다.
    # 이 값이 클수록 stage_gaps 가 선택된 cue 들을 더 길게 이어붙여(사이 footage 유지)
    # 컷이 덜 잘게 쪼개진다. 자막 간격 기반이면 TTS 채널에서 0.3 플로어라 컷이 난사됨.
    median_shot = shots.get("median_shot_sec")
    pacing = dict(pacing)
    if median_shot:
        pacing["gap_threshold_sec"] = round(min(4.0, max(0.6, median_shot * 1.5)), 2)

    profile = {
        "schema_version": "1.0",
        "provenance": {
            "source_type": samples.get("source_type"),
            "source_url": samples.get("source_url"),
            "channel_name": samples.get("channel_name"),
            "format": samples.get("format"),
            "videos_analyzed": [
                {
                    "id": v.get("id"), "url": v.get("url"), "title": v.get("title"),
                    "views": v.get("views"), "upload_date": v.get("upload_date"),
                    "duration_sec": v.get("duration_sec"), "width": v.get("width"),
                    "height": v.get("height"), "fps": v.get("fps"), "is_short": v.get("is_short"),
                }
                for v in samples.get("picked", [])
            ],
            "analyzed_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "analyzer_version": ANALYZER_VERSION,
            "notes": samples.get("selection_reason", ""),
            "limitations": _limitations(caption, overlay),
        },
        "applied": {
            "canvas": {
                "width": container.get("width"),
                "height": container.get("height"),
                "fps": int(container["fps"]) if container.get("fps") else None,
            },
            "target_duration_sec": target_dur,
            "pacing": {k: pacing.get(k) for k in ("pause_gap_sec", "max_cue_sec", "gap_threshold_sec")},
            "caption": caption,
            "caption_emphasis": emphasis,
            "overlay": overlay,
            "sfx": {
                "volume": audio.get("suggested_sfx_volume", 0.7),
                # 감지된 마이크로 트랜지언트 길이는 너무 짧아 그대로 못 씀 — 0.15~0.5 로 클램프
                "duration_sec": round(min(0.5, max(0.15, audio.get("sfx_burst_median_sec") or 0.3)), 2),
                # 분석 힌트 (실제 배치는 map 이 우선)
                "trigger": audio.get("sfx_trigger", "keywords"),
                "variety": audio.get("sfx_variety", "single"),
                "per_minute": audio.get("sfx_bursts_per_minute"),
                # map: 사용자가 정한 "효과음별 배치". 스킬이 물어본 뒤 --sfx-map 으로 넣는다.
                #   [{"file":"whoosh.wav","trigger":"cuts"}, {"file":"ding.wav","trigger":"keywords"}]
                **({"map": json.loads(args.sfx_map)} if getattr(args, "sfx_map", None) else {}),
            },
        },
        "advisory": {
            "shot_pacing": shots,
            "color_grade": vn.get("advisory", {}).get("color_grade", {}),
            "hook_structure": vn.get("advisory", {}).get("hook_structure", {}),
            "shot_scale_mix": vn.get("advisory", {}).get("shot_scale_mix", {}),
            "broll_ratio": vn.get("advisory", {}).get("broll_ratio", {}),
            "text_density": _v(vn.get("advisory", {}).get("text_density")),
            "emoji_usage": _v(vn.get("advisory", {}).get("emoji_usage")),
            "censor_bleeps": _v(vn.get("advisory", {}).get("censor_bleeps")),
            "bgm": {
                "present": audio.get("bgm_present"),
                "level_db_below_vo": audio.get("bgm_level_db_below_vo"),
            },
        },
    }

    # 빈 dict/None 정리
    profile["applied"]["pacing"] = {k: v for k, v in profile["applied"]["pacing"].items() if v is not None}
    profile["applied"]["canvas"] = {k: v for k, v in profile["applied"]["canvas"].items() if v is not None}

    dst = os.path.join(out, "style-profile.json")
    dump_json(profile, dst)
    print(f"→ {dst}")

    if args.install:
        pdir = os.path.join(args.capcut_project, "style-profiles")
        os.makedirs(pdir, exist_ok=True)
        installed = os.path.join(pdir, f"{slug}.json")
        shutil.copyfile(dst, installed)
        print(f"→ 설치: {installed}")
        print(f"\n실행:\n  cd {args.capcut_project}\n  .venv/bin/python -m recipe_pipeline.cli \\\n"
              f"    --video 내영상.mp4 --end-image 엔딩.jpg --draft-name test \\\n"
              f"    --style-profile style-profiles/{slug}.json")


if __name__ == "__main__":
    main()
