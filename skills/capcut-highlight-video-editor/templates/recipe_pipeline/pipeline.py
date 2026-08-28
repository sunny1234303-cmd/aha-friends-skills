"""Orchestrates all 10 conceptual stages the user described.

Execution order note (design decision, see plan Context): stage 5 (ingredient
detection) actually runs before stage 4 (60s highlight selection), because
stage 4 needs to know which segments mention ingredients to prioritize them.
The STAGE_LABELS below keep the user's original numbering; stage 4 and 5 are
logged as completing together.
"""

import json
import os
import shutil
from dataclasses import dataclass
from typing import List

import pycapcut as cc

from . import ingredient_detection, stage_caption_style, stage_end_image
from . import stage_gaps, stage_highlight, stage_ingest, stage_overlay
from . import stage_save, stage_sfx, stage_transcribe, style_utils
from .config import PipelineConfig
from .models import SpeechSegment, TextOverlay

SEC = cc.SEC

STAGE_LABELS = {
    1: "영상 삽입",
    2: "자막 스크립트 생성",
    3: "무자막 구간 컷 편집",
    "4_5": "하이라이트 편집 + 키워드 등장 구간 분석 (4단계는 5단계 결과에 의존해 함께 계산됨)",
    6: "미리 제시해준 내용(.md) 활용하여 내용 추가",
    7: "자막 글꼴/크기/위치/확대",
    8: "자동 효과음 추가",
    9: "종료 2-3초 전 사전 캡쳐본 추가",
    10: "클립 삭제 가능한 상태로 프로그램 저장",
}


@dataclass
class PipelineResult:
    draft_dir: str
    final_duration_sec: float
    kept_segment_count: int
    ingredient_keywords_found: List[str]
    srt_path: str
    log_path: str


def _resolve_sfx_file(config: PipelineConfig, name: str):
    """sfx_map 의 상대 파일명 → 실제 경로 (sfx_dir 우선, 없으면 sfx_path 폴더)."""
    for base in (config.sfx_dir, os.path.dirname(config.sfx_path)):
        if base:
            cand = os.path.join(base, name)
            if os.path.isfile(cand):
                return cand
    return name if os.path.isfile(name) else None


def orchestrate(config: PipelineConfig, on_stage=None) -> PipelineResult:
    """on_stage: optional callback(stage_key, label, message) invoked as each
    stage completes, in addition to the console log — the local dashboard
    (Milestone 2) uses this to stream live per-stage status."""

    def _log(stage_key, msg: str = ""):
        label = STAGE_LABELS[stage_key]
        print(f"[{stage_key}] {label}" + (f" — {msg}" if msg else ""))
        if on_stage:
            on_stage(stage_key, label, msg)

    os.makedirs(config.workdir, exist_ok=True)

    # Stage 1: 영상 삽입 (+ CapCut이 읽을 수 있는 위치로 미디어 스테이징)
    staged_video = stage_ingest.stage_media_file(config.source_video)
    staged_end_image = stage_ingest.stage_media_file(config.end_image)

    _AUDIO_EXT = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg")
    if config.sfx_dir and os.path.isdir(config.sfx_dir):
        pool = sorted(
            os.path.join(config.sfx_dir, f)
            for f in os.listdir(config.sfx_dir)
            if os.path.splitext(f)[1].lower() in _AUDIO_EXT
        )
        staged_sfx_pool = [stage_ingest.stage_media_file(p) for p in pool] or [
            stage_ingest.stage_media_file(config.sfx_path)
        ]
    else:
        staged_sfx_pool = [stage_ingest.stage_media_file(config.sfx_path)]
    _log(1, staged_video)
    video_material = cc.VideoMaterial(staged_video)

    # Stage 2: 자막 스크립트 생성 (local Whisper)
    srt_path = os.path.join(config.workdir, "transcript.srt")
    cues = stage_transcribe.transcribe_to_srt(
        config.source_video,
        srt_path,
        config.whisper_model_size,
        pause_gap_sec=config.pause_gap_sec,
        max_cue_sec=config.max_cue_sec,
    )
    _log(2, f"{len(cues)}개 cue, {srt_path}")

    # Stage 5 로직 (4단계보다 먼저 계산): 식재료 사용 구간 분석 (cue 단위 태깅)
    # content_md가 없으면 키워드 자체가 없으므로 태깅 없이 넘어감 — 이 경우
    # 4단계는 자동으로 "앞에서부터 순서대로 목표 길이까지" 선별로 대체된다.
    keywords = (
        ingredient_detection.extract_ingredient_keywords(config.content_md)
        if config.content_md
        else []
    )
    ingredient_detection.tag_ingredient_cues(cues, keywords)

    # Stage 4: 총 60초 클립 편집 (식재료 중심, cue 단위 선별)
    selected_cues = stage_highlight.select_highlight_cues(cues, config.target_duration_sec)
    found_keywords = sorted({kw for c in selected_cues for kw in c.matched_keywords})
    _log(
        "4_5",
        f"{len(selected_cues)}/{len(cues)}개 cue 선택, "
        f"총 {sum(c.end - c.start for c in selected_cues):.1f}초, "
        f"키워드: {', '.join(found_keywords) if found_keywords else '없음'}",
    )

    if not selected_cues:
        raise ValueError("선택된 구간이 없습니다 — 자막/키워드를 확인하세요.")

    # Stage 3: 무자막 구간 컷 편집 — 선택된 cue들 중 원본에서 가까운 것끼리만
    # 하나의 연속 클립으로 묶고, 멀리 떨어진 것(또는 사이 cue가 스킵된 경우)은
    # 별도 클립으로 분리한다. 이 결과가 곧 "무자막/스킵 구간이 잘려나간" 상태.
    kept = stage_gaps.merge_cues_into_blocks(selected_cues, config.gap_threshold_sec)
    _log(3, f"{len(kept)}개 연속 클립으로 병합")

    # If a draft with this name already exists (e.g. a previous run CapCut once
    # opened with broken media), delete it first — confirmed via manual testing
    # that CapCut can get stuck refusing to reopen a draft whose internal cache
    # (Timelines/, Resources/) was built while media was missing, even after the
    # JSON is fixed. A clean folder avoids that stale-cache class of bug.
    existing_draft_dir = os.path.join(config.draft_folder, config.output_draft_name)
    if os.path.isdir(existing_draft_dir):
        shutil.rmtree(existing_draft_dir)

    # Timeline assembly: place kept segments back-to-back on a new compressed
    # output timeline, and add one VideoSegment per kept segment.
    script = cc.DraftFolder(config.draft_folder).create_draft(
        config.output_draft_name,
        config.canvas_width,
        config.canvas_height,
        fps=config.canvas_fps,
        allow_replace=True,
    )
    script.add_track(cc.TrackType.video, "video_main")
    script.add_track(cc.TrackType.text, "captions")
    script.add_track(cc.TrackType.text, "recipe_overlay")
    script.add_track(cc.TrackType.audio, "sfx")
    script.add_track(cc.TrackType.video, "end_image")

    mapped_segments = []
    cursor = 0.0
    for seg in kept:
        mapped_segments.append((cursor, seg))
        video_segment = cc.VideoSegment(
            video_material,
            cc.Timerange(int(cursor * SEC), int(seg.duration * SEC)),
            source_timerange=cc.Timerange(int(seg.start * SEC), int(seg.duration * SEC)),
        )
        script.add_segment(video_segment, "video_main")
        cursor += seg.duration
    total_output_duration = cursor

    # Stage 6: .md 내용 오버레이 (content_md 없으면 스킵 — 빈 결과로 자연스럽게 없음 처리)
    overlays: List[TextOverlay] = (
        stage_overlay.build_ingredient_overlays(kept, config.content_md, config.overlay_duration_sec)
        if config.content_md
        else []
    )
    overlay_new_starts = []
    for overlay in overlays:
        for new_start, seg in mapped_segments:
            if seg.start <= overlay.start <= seg.end:
                overlay_new_starts.append(new_start + (overlay.start - seg.start))
                break
    # Overlays land on one track and can't overlap (ingredients mentioned close
    # together would otherwise collide) — enforce sequential, non-overlapping
    # placement in chronological order, pushing a start forward if needed.
    order = sorted(range(len(overlay_new_starts)), key=lambda i: overlay_new_starts[i])
    prev_end = 0.0
    for i in order:
        if overlay_new_starts[i] < prev_end:
            overlay_new_starts[i] = prev_end
        prev_end = overlay_new_starts[i] + overlays[i].duration
    _log(6, f"{len(overlays)}개 오버레이" + ("" if config.content_md else " (텍스트 노트 없음)"))

    overlay_font, overlay_font_used = style_utils.resolve_font(
        config.overlay_font, return_meta=True
    )
    caption_font, caption_font_used = style_utils.resolve_font(
        config.caption_font, return_meta=True
    )
    # CapCut draft 에서 뽑은 커스텀 폰트 블록이 있으면 그게 우선 (한글 등)
    if style_utils.raw_font(config.caption_font_capcut):
        caption_font = style_utils.raw_font(config.caption_font_capcut)
        caption_font_used = f"capcut:{(config.caption_font_capcut or {}).get('name')}"
    if style_utils.raw_font(config.overlay_font_capcut):
        overlay_font = style_utils.raw_font(config.overlay_font_capcut)
        overlay_font_used = f"capcut:{(config.overlay_font_capcut or {}).get('name')}"
    caption_anim_in = style_utils.resolve_text_intro(config.caption_anim_in)
    caption_anim_out = style_utils.resolve_text_outro(config.caption_anim_out)
    overlay_anim_in = style_utils.resolve_text_intro(config.overlay_anim_in)
    overlay_anim_out = style_utils.resolve_text_outro(config.overlay_anim_out)
    caption_shadow_opts = (
        {
            "color": config.caption_shadow_color,
            "alpha": config.caption_shadow_alpha,
            "angle": config.caption_shadow_angle,
            "distance": config.caption_shadow_distance,
        }
        if config.caption_shadow
        else None
    )

    if overlays:
        stage_overlay.add_overlay_segments(
            script,
            overlay_new_starts,
            overlays,
            "recipe_overlay",
            font=overlay_font,
            font_size=config.overlay_size,
            color=style_utils.hex_to_rgb01(config.overlay_color),
            vertical_position=style_utils.position_to_transform_y(config.overlay_position),
            bold=config.overlay_bold,
            all_caps=config.overlay_all_caps,
            border=style_utils.build_text_border(
                config.overlay_outline_color, config.overlay_outline_width
            ),
            background=style_utils.build_text_background(
                config.overlay_bg, config.overlay_bg_color, config.overlay_bg_alpha
            ),
            anim_in=overlay_anim_in,
            anim_out=overlay_anim_out,
            anim_duration_sec=config.overlay_anim_duration_sec,
        )

    # Stage 7: 자막 스타일링 + 확대
    stage_caption_style.add_captions(
        script,
        mapped_segments,
        "captions",
        font=caption_font,
        font_size=config.caption_size,
        color=style_utils.hex_to_rgb01(config.caption_color),
        vertical_position=style_utils.position_to_transform_y(config.caption_position),
        bold=config.caption_bold,
        align=config.caption_align,
        all_caps=config.caption_all_caps,
        border=style_utils.build_text_border(
            config.caption_outline_color,
            config.caption_outline_width,
            config.caption_outline_alpha,
        ),
        background=style_utils.build_text_background(
            config.caption_bg,
            config.caption_bg_color,
            config.caption_bg_alpha,
            config.caption_bg_radius,
        ),
        anim_in=caption_anim_in,
        anim_out=caption_anim_out,
        anim_duration_sec=config.caption_anim_duration_sec,
        zoom_trigger=config.caption_zoom_trigger,
        zoom_scale=config.caption_zoom_scale,
        zoom_duration_sec=config.caption_zoom_duration_sec,
        shadow_opts=caption_shadow_opts,
    )
    _log(7, "캡션 스타일 적용 완료")

    # Stage 8: 효과음
    # 트리거별 시각(출력 타임라인 기준):
    keyword_starts, cut_starts, caption_starts = [], [], []
    for i, (new_start, seg) in enumerate(mapped_segments):
        offset = new_start - seg.start
        for cue in seg.cues:
            caption_starts.append(cue.start + offset)
            if cue.has_ingredient:
                keyword_starts.append(cue.start + offset)
        if i > 0:  # 첫 클립 시작(0초)엔 안 넣음
            cut_starts.append(new_start)
    trigger_times = {
        "keywords": sorted(keyword_starts),
        "cuts": sorted(cut_starts),
        "caption_in": sorted(caption_starts),
        "both": sorted(keyword_starts + cut_starts),
        "end": [max(0.0, total_output_duration - config.end_image_lead_sec - 0.1)],
    }

    placements = []  # [(time, staged_path)]
    if config.sfx_map:
        # 사용자가 지정: 효과음별로 어디에
        by_trigger = {}
        for entry in config.sfx_map:
            f = entry.get("file")
            trg = entry.get("trigger", "cuts")
            if not f:
                continue
            path = f if os.path.isabs(f) else _resolve_sfx_file(config, f)
            if not path:
                continue
            by_trigger.setdefault(trg, []).append(stage_ingest.stage_media_file(path))
        for trg, files in by_trigger.items():
            for k, t in enumerate(trigger_times.get(trg, [])):
                placements.append((t, files[k % len(files)]))
        _pairs = [str(e.get("file")) + "→" + str(e.get("trigger")) for e in config.sfx_map]
        sfx_desc = "map: " + ", ".join(_pairs)
    else:
        # 단순: 한 트리거 + 풀 순환
        times = trigger_times.get(config.sfx_trigger, trigger_times["keywords"])
        for k, t in enumerate(times):
            placements.append((t, staged_sfx_pool[k % len(staged_sfx_pool)]))
        sfx_desc = f"trigger={config.sfx_trigger}, 음원 {len(staged_sfx_pool)}종 순환"

    n_sfx = stage_sfx.add_sfx_placements(
        script, placements, config.sfx_duration_sec, "sfx", volume=config.sfx_volume
    )
    _log(8, f"{n_sfx}개 효과음 삽입 ({sfx_desc})")

    # Stage 9: 엔딩 이미지
    stage_end_image.add_end_image(
        script, staged_end_image, total_output_duration, config.end_image_lead_sec, "end_image"
    )
    _log(9, f"{config.end_image_lead_sec}초 전부터 삽입")

    # Stage 10: 저장 (편집 가능한 상태, 렌더링 아님)
    draft_dir = stage_save.save_editable_draft(
        config.draft_folder, config.output_draft_name, script
    )
    _log(10, draft_dir)

    log_path = os.path.join(config.workdir, "pipeline_log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "kept_segments": [
                    {
                        "start": s.start,
                        "end": s.end,
                        "has_ingredient": s.has_ingredient,
                        "matched_keywords": s.matched_keywords,
                        "text": s.text,
                    }
                    for s in kept
                ],
                "final_duration_sec": total_output_duration,
                "ingredient_keywords_found": found_keywords,
                "overlays": [
                    {"text": o.text, "source_ingredient": o.source_ingredient}
                    for o in overlays
                ],
                "sfx_count": n_sfx,
                "draft_dir": draft_dir,
                "style_profile_path": config.style_profile_path,
                "font_requested_vs_used": {
                    "caption": [config.caption_font, caption_font_used],
                    "overlay": [config.overlay_font, overlay_font_used],
                },
                "caption_anim_resolved": {
                    "in": getattr(caption_anim_in, "name", None),
                    "out": getattr(caption_anim_out, "name", None),
                },
                "pacing_applied": {
                    "pause_gap_sec": config.pause_gap_sec,
                    "max_cue_sec": config.max_cue_sec,
                    "gap_threshold_sec": config.gap_threshold_sec,
                },
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return PipelineResult(
        draft_dir=draft_dir,
        final_duration_sec=total_output_duration,
        kept_segment_count=len(kept),
        ingredient_keywords_found=found_keywords,
        srt_path=srt_path,
        log_path=log_path,
    )
