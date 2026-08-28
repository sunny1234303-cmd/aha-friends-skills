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
    sfx_dir: Optional[str] = None
    sfx_trigger: str = "keywords"
    sfx_map: Optional[list] = None

    # style-profile.json 경로 (있으면 PipelineConfig.from_style_profile로 로드,
    # 아래 non-default 필드만 그 위에 덮어씀)
    style_profile_path: Optional[str] = None

    # 컷 호흡
    pause_gap_sec: Optional[float] = None
    max_cue_sec: Optional[float] = None

    caption_font: str = "Arimo_Regular"
    caption_size: float = 10.0
    caption_color: str = "#FFFFFF"
    caption_position: str = "bottom"
    caption_all_caps: bool = False
    caption_outline_color: Optional[str] = None
    caption_outline_width: float = 0.0
    caption_shadow: bool = False
    caption_bg: bool = False
    caption_bg_color: str = "#000000"
    caption_anim_in: str = "none"
    caption_anim_out: str = "none"
    caption_zoom_trigger: str = "keyword"
    caption_zoom_scale: float = 1.15

    overlay_font: str = "Arimo_Regular"
    overlay_size: float = 7.0
    overlay_color: str = "#FFEB99"
    overlay_position: str = "top"
    overlay_all_caps: bool = False
    overlay_outline_color: Optional[str] = None
    overlay_outline_width: float = 0.0
    overlay_bg: bool = False
    overlay_anim_in: str = "none"
    overlay_anim_out: str = "none"

    sfx_volume: float = 0.7


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
    style_profile_used: Optional[str] = None


class RunState(BaseModel):
    run_id: str
    status: str  # "running" | "done" | "error"
    stages: List[StageStatus] = []
    summary: Optional[RunSummary] = None
    error: Optional[str] = None
