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
    staged_sfx = stage_ingest.stage_media_file(config.sfx_path)
    _log(1, staged_video)
    video_material = cc.VideoMaterial(staged_video)

    # Stage 2: 자막 스크립트 생성 (local Whisper)
    srt_path = os.path.join(config.workdir, "transcript.srt")
    cues = stage_transcribe.transcribe_to_srt(
        config.source_video, srt_path, config.whisper_model_size
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
    if overlays:
        stage_overlay.add_overlay_segments(
            script,
            overlay_new_starts,
            overlays,
            "recipe_overlay",
            font=style_utils.resolve_font(config.overlay_font),
            font_size=config.overlay_size,
            color=style_utils.hex_to_rgb01(config.overlay_color),
            vertical_position=style_utils.position_to_transform_y(config.overlay_position),
        )

    # Stage 7: 자막 스타일링 + 확대
    stage_caption_style.add_captions(
        script,
        mapped_segments,
        "captions",
        font=style_utils.resolve_font(config.caption_font),
        font_size=config.caption_size,
        color=style_utils.hex_to_rgb01(config.caption_color),
        vertical_position=style_utils.position_to_transform_y(config.caption_position),
    )
    _log(7, "캡션 스타일 적용 완료")

    # Stage 8: 효과음 (식재료 언급된 cue가 시작될 때마다, 블록 시작이 아니라 cue 단위)
    sfx_new_starts = []
    for new_start, seg in mapped_segments:
        offset = new_start - seg.start
        for cue in seg.cues:
            if cue.has_ingredient:
                sfx_new_starts.append(cue.start + offset)
    stage_sfx.add_sfx_bursts(
        script, sfx_new_starts, staged_sfx, config.sfx_duration_sec, "sfx"
    )
    _log(8, f"{len(sfx_new_starts)}개 효과음 삽입")

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
                "sfx_count": len(sfx_new_starts),
                "draft_dir": draft_dir,
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
