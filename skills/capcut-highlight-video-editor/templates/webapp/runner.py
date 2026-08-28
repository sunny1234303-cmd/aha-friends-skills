import threading
import time
import traceback
import uuid
from typing import Dict

from recipe_pipeline.config import DEFAULT_SFX_PATH, PipelineConfig
from recipe_pipeline.pipeline import orchestrate

from .models import RunRequest, RunState, RunSummary, StageStatus

_runs: Dict[str, RunState] = {}
_lock = threading.Lock()

# style-profile 로 프로필을 준 경우, request 값이 아래 기본값과 "다를 때만" 프로필 위에 덮어씀
_OVERRIDE_DEFAULTS = {
    "target_duration_sec": 60.0,
    "gap_threshold_sec": 0.6,
    "pause_gap_sec": None,
    "max_cue_sec": None,
    "caption_font": "Arimo_Regular",
    "caption_size": 10.0,
    "caption_color": "#FFFFFF",
    "caption_position": "bottom",
    "caption_all_caps": False,
    "caption_outline_color": None,
    "caption_outline_width": 0.0,
    "caption_shadow": False,
    "caption_bg": False,
    "caption_bg_color": "#000000",
    "caption_anim_in": "none",
    "caption_anim_out": "none",
    "caption_zoom_trigger": "keyword",
    "caption_zoom_scale": 1.15,
    "sfx_trigger": "keywords",
    "overlay_font": "Arimo_Regular",
    "overlay_size": 7.0,
    "overlay_color": "#FFEB99",
    "overlay_position": "top",
    "overlay_all_caps": False,
    "overlay_outline_color": None,
    "overlay_outline_width": 0.0,
    "overlay_bg": False,
    "overlay_anim_in": "none",
    "overlay_anim_out": "none",
    "sfx_volume": 0.7,
}


def get_run(run_id: str) -> RunState:
    with _lock:
        return _runs[run_id]


def start_run(request: RunRequest) -> str:
    run_id = uuid.uuid4().hex[:8]
    state = RunState(run_id=run_id, status="running", stages=[])
    with _lock:
        _runs[run_id] = state

    thread = threading.Thread(target=_run_pipeline, args=(run_id, request), daemon=True)
    thread.start()
    return run_id


def _build_config(request: RunRequest) -> PipelineConfig:
    common = dict(
        source_video=request.video_path,
        end_image=request.end_image_path,
        output_draft_name=request.draft_name,
    )
    if request.style_profile_path:
        config = PipelineConfig.from_style_profile(request.style_profile_path, **common)
        config.content_md = request.content_md_path
        config.whisper_model_size = request.whisper_model_size
        if request.sfx_path:
            config.sfx_path = request.sfx_path
        if request.sfx_dir:
            config.sfx_dir = request.sfx_dir
        if request.sfx_map:
            config.sfx_map = request.sfx_map
        # request 값이 기본값과 다르면 프로필 위에 덮어씀
        for key, default in _OVERRIDE_DEFAULTS.items():
            val = getattr(request, key)
            if val != default and val is not None:
                setattr(config, key, val)
        return config

    config = PipelineConfig(
        content_md=request.content_md_path,
        whisper_model_size=request.whisper_model_size,
        sfx_path=request.sfx_path or DEFAULT_SFX_PATH,
        sfx_dir=request.sfx_dir,
        sfx_trigger=request.sfx_trigger,
        sfx_map=request.sfx_map,
        target_duration_sec=request.target_duration_sec,
        gap_threshold_sec=request.gap_threshold_sec,
        caption_font=request.caption_font,
        caption_size=request.caption_size,
        caption_color=request.caption_color,
        caption_position=request.caption_position,
        caption_all_caps=request.caption_all_caps,
        caption_outline_color=request.caption_outline_color,
        caption_outline_width=request.caption_outline_width,
        caption_shadow=request.caption_shadow,
        caption_bg=request.caption_bg,
        caption_bg_color=request.caption_bg_color,
        caption_anim_in=request.caption_anim_in,
        caption_anim_out=request.caption_anim_out,
        caption_zoom_trigger=request.caption_zoom_trigger,
        caption_zoom_scale=request.caption_zoom_scale,
        overlay_font=request.overlay_font,
        overlay_size=request.overlay_size,
        overlay_color=request.overlay_color,
        overlay_position=request.overlay_position,
        overlay_all_caps=request.overlay_all_caps,
        overlay_outline_color=request.overlay_outline_color,
        overlay_outline_width=request.overlay_outline_width,
        overlay_bg=request.overlay_bg,
        overlay_anim_in=request.overlay_anim_in,
        overlay_anim_out=request.overlay_anim_out,
        sfx_volume=request.sfx_volume,
        **common,
    )
    if request.pause_gap_sec is not None:
        config.pause_gap_sec = request.pause_gap_sec
    if request.max_cue_sec is not None:
        config.max_cue_sec = request.max_cue_sec
    return config


def _run_pipeline(run_id: str, request: RunRequest) -> None:
    state = _runs[run_id]

    def on_stage(stage_key, label, message):
        with _lock:
            state.stages.append(
                StageStatus(
                    stage_key=str(stage_key), label=label, message=message, ts=time.time()
                )
            )

    try:
        config = _build_config(request)
        result = orchestrate(config, on_stage=on_stage)
        with _lock:
            state.status = "done"
            state.summary = RunSummary(
                draft_dir=result.draft_dir,
                final_duration_sec=result.final_duration_sec,
                kept_segment_count=result.kept_segment_count,
                ingredient_keywords_found=result.ingredient_keywords_found,
                srt_path=result.srt_path,
                log_path=result.log_path,
                style_profile_used=request.style_profile_path,
            )
    except Exception:
        with _lock:
            state.status = "error"
            state.error = traceback.format_exc()
