from typing import List, Optional

from pydantic import BaseModel


class RunRequest(BaseModel):
    video_path: str
    end_image_path: str
    content_md_path: Optional[str] = None
    draft_name: str
    whisper_model_size: str = "small"
    target_duration_sec: float = 60.0
    gap_threshold_sec: float = 0.6
    sfx_path: Optional[str] = None

    caption_font: str = "Arimo_Regular"
    caption_size: float = 10.0
    caption_color: str = "#FFFFFF"
    caption_position: str = "bottom"

    overlay_font: str = "Arimo_Regular"
    overlay_size: float = 7.0
    overlay_color: str = "#FFEB99"
    overlay_position: str = "top"


class StageStatus(BaseModel):
    stage_key: str
    label: str
    message: str = ""
    ts: float


class RunSummary(BaseModel):
    draft_dir: str
    final_duration_sec: float
    kept_segment_count: int
    ingredient_keywords_found: List[str]
    srt_path: str
    log_path: str


class RunState(BaseModel):
    run_id: str
    status: str  # "running" | "done" | "error"
    stages: List[StageStatus] = []
    summary: Optional[RunSummary] = None
    error: Optional[str] = None
