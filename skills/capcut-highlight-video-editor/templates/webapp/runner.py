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
        config = PipelineConfig(
            source_video=request.video_path,
            content_md=request.content_md_path,
            end_image=request.end_image_path,
            output_draft_name=request.draft_name,
            whisper_model_size=request.whisper_model_size,
            target_duration_sec=request.target_duration_sec,
            gap_threshold_sec=request.gap_threshold_sec,
            sfx_path=request.sfx_path or DEFAULT_SFX_PATH,
            caption_font=request.caption_font,
            caption_size=request.caption_size,
            caption_color=request.caption_color,
            caption_position=request.caption_position,
            overlay_font=request.overlay_font,
            overlay_size=request.overlay_size,
            overlay_color=request.overlay_color,
            overlay_position=request.overlay_position,
        )
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
            )
    except Exception:
        with _lock:
            state.status = "error"
            state.error = traceback.format_exc()
