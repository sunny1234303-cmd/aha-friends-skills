import os
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_DRAFT_FOLDER = os.path.expanduser(
    "~/Movies/CapCut/User Data/Projects/com.lveditor.draft"
)
DEFAULT_SFX_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "default_ding.wav"
)


@dataclass
class PipelineConfig:
    source_video: str
    end_image: str
    output_draft_name: str
    content_md: Optional[str] = None  # 없으면 식재료 감지/오버레이 없이 순서대로 하이라이트 선별
    draft_folder: str = DEFAULT_DRAFT_FOLDER
    whisper_model_size: str = "small"
    target_duration_sec: float = 60.0
    gap_threshold_sec: float = 0.6
    sfx_path: str = DEFAULT_SFX_PATH
    sfx_duration_sec: float = 0.3
    end_image_lead_sec: float = 2.5
    canvas_width: int = 1080
    canvas_height: int = 1920
    canvas_fps: int = 30
    overlay_duration_sec: float = 2.5

    # 자막 스타일
    caption_font: str = "Arimo_Regular"
    caption_size: float = 10.0
    caption_color: str = "#FFFFFF"
    caption_position: str = "bottom"  # top | center | bottom

    # 오버레이(텍스트 노트 키워드 정보) 스타일
    overlay_font: str = "Arimo_Regular"
    overlay_size: float = 7.0
    overlay_color: str = "#FFEB99"
    overlay_position: str = "top"  # top | center | bottom

    workdir: str = field(default_factory=lambda: None)  # set in ingest stage

    def __post_init__(self):
        if self.workdir is None:
            self.workdir = os.path.join(
                os.path.dirname(os.path.abspath(self.source_video)), ".pipeline_out"
            )
