import json
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
    # sfx_dir: 폴더의 오디오들을 한 트리거에 순환(단순 케이스).
    sfx_dir: Optional[str] = None
    # sfx_trigger: keywords(키워드 cue, .md 필요) | cuts(클립 경계) | both
    sfx_trigger: str = "keywords"
    # sfx_map: 효과음별로 "어디에" 넣을지 명시 (권장 — 순환이 아니라 알맞게 배치).
    #   [{"file": "whoosh.wav", "trigger": "cuts"},
    #    {"file": "ding.wav",   "trigger": "keywords"},
    #    {"file": "pop.wav",    "trigger": "caption_in"}]
    #   trigger: cuts | keywords | caption_in (모든 자막 등장) | end (엔딩 이미지 직전)
    #   같은 trigger 에 여러 file 이면 그 안에서만 순환. sfx_map 이 있으면 sfx_dir/sfx_trigger 무시.
    #   file 은 절대경로거나, sfx_dir/sfx_path 폴더 기준 상대경로.
    sfx_map: Optional[list] = None
    sfx_duration_sec: float = 0.3
    end_image_lead_sec: float = 2.5
    canvas_width: int = 1080
    canvas_height: int = 1920
    canvas_fps: int = 30
    overlay_duration_sec: float = 2.5

    # 컷 호흡 (전에는 stage_transcribe.py에 하드코딩돼 있던 값 — 스타일 프로필로 조정 가능)
    pause_gap_sec: float = 0.5
    max_cue_sec: float = 6.0

    # 자막 스타일
    caption_font: str = "Arimo_Regular"
    # CAPTION_FONTS 에 없는 폰트(한글 등): CapCut draft 에서 뽑은 {resource_id, name} 블록.
    # 있으면 caption_font 보다 우선. capture_font.py 로 추출.
    caption_font_capcut: Optional[dict] = None
    caption_size: float = 10.0
    caption_color: str = "#FFFFFF"
    caption_position: str = "bottom"  # top | center | bottom
    caption_bold: bool = True
    caption_align: int = 1  # 0 left | 1 center | 2 right
    caption_all_caps: bool = False  # 영문만 대문자화 (한글은 무해)

    # 자막 외곽선 (색이 None이면 외곽선 없음)
    caption_outline_color: Optional[str] = None
    caption_outline_width: float = 0.0  # 0~100, CapCut 기준
    caption_outline_alpha: float = 1.0

    # 자막 드롭섀도우 (실험적 — pycapcut이 기본 연결하지 않아 export_material 오버라이드로 주입)
    caption_shadow: bool = False
    caption_shadow_color: str = "#000000"
    caption_shadow_alpha: float = 0.9
    caption_shadow_angle: float = -45.0
    caption_shadow_distance: float = 5.0

    # 자막 배경 박스
    caption_bg: bool = False
    caption_bg_color: str = "#000000"
    caption_bg_alpha: float = 1.0
    caption_bg_radius: float = 0.0  # 0~1

    # 자막 인/아웃 애니메이션 (제네릭 이름 → style_utils가 CapCut enum으로 해석)
    caption_anim_in: str = "none"   # none|fade|pop|slide-up|typewriter|zoom|karaoke
    caption_anim_out: str = "none"  # none|fade|scale-down|slide-down
    caption_anim_duration_sec: float = 0.5

    # 키워드 강조 줌 펀치
    caption_zoom_trigger: str = "keyword"  # keyword | all | none
    caption_zoom_scale: float = 1.15
    caption_zoom_duration_sec: float = 0.3

    # 오버레이(텍스트 노트 키워드 정보) 스타일
    overlay_font: str = "Arimo_Regular"
    overlay_font_capcut: Optional[dict] = None
    overlay_size: float = 7.0
    overlay_color: str = "#FFEB99"
    overlay_position: str = "top"  # top | center | bottom
    overlay_bold: bool = True
    overlay_all_caps: bool = False
    overlay_outline_color: Optional[str] = None
    overlay_outline_width: float = 0.0
    overlay_bg: bool = False
    overlay_bg_color: str = "#000000"
    overlay_bg_alpha: float = 1.0
    overlay_anim_in: str = "none"
    overlay_anim_out: str = "none"
    overlay_anim_duration_sec: float = 0.5

    # 효과음
    sfx_volume: float = 0.7

    # 프로비넌스 / 로깅 전용 (파이프라인 로직엔 영향 없음)
    style_profile_path: Optional[str] = None

    workdir: str = field(default_factory=lambda: None)  # set in ingest stage

    def __post_init__(self):
        if self.workdir is None:
            self.workdir = os.path.join(
                os.path.dirname(os.path.abspath(self.source_video)), ".pipeline_out"
            )

    # ------------------------------------------------------------------
    # 스타일 프로필 로더
    # ------------------------------------------------------------------
    # video-editing-style-analyzer 스킬이 만든 style-profile.json을 읽어
    # PipelineConfig를 구성한다. profile["applied"] 아래 TIER A 필드만 사용하고,
    # profile["advisory"]는 사람 편집자용이라 무시한다.
    # 모든 접근은 .get(...) 방어적으로 — 부분/구버전 프로필도 로드되게.
    @classmethod
    def from_style_profile(
        cls,
        profile_path: str,
        *,
        source_video: str,
        end_image: str,
        output_draft_name: str,
        **overrides,
    ) -> "PipelineConfig":
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)
        applied = profile.get("applied", {}) or {}

        kw = dict(
            source_video=source_video,
            end_image=end_image,
            output_draft_name=output_draft_name,
            style_profile_path=profile_path,
        )

        canvas = applied.get("canvas", {}) or {}
        _set(kw, "canvas_width", canvas.get("width"))
        _set(kw, "canvas_height", canvas.get("height"))
        _set(kw, "canvas_fps", canvas.get("fps"))
        _set(kw, "target_duration_sec", applied.get("target_duration_sec"))

        pacing = applied.get("pacing", {}) or {}
        _set(kw, "pause_gap_sec", pacing.get("pause_gap_sec"))
        _set(kw, "max_cue_sec", pacing.get("max_cue_sec"))
        _set(kw, "gap_threshold_sec", pacing.get("gap_threshold_sec"))

        cap = applied.get("caption", {}) or {}
        _set(kw, "caption_font", cap.get("font"))
        _set(kw, "caption_font_capcut", cap.get("font_capcut"))
        _set(kw, "caption_size", cap.get("size"))
        _set(kw, "caption_color", cap.get("color"))
        _set(kw, "caption_position", cap.get("position"))
        _set(kw, "caption_bold", cap.get("bold"))
        _set(kw, "caption_align", cap.get("align"))
        _set(kw, "caption_all_caps", cap.get("all_caps"))
        _apply_outline(kw, "caption", cap.get("outline"))
        _apply_shadow(kw, "caption", cap.get("shadow"))
        _apply_background(kw, "caption", cap.get("background"))
        _apply_animation(kw, "caption", cap.get("animation"))

        emph = applied.get("caption_emphasis", {}) or {}
        _set(kw, "caption_zoom_trigger", emph.get("trigger"))
        _set(kw, "caption_zoom_scale", emph.get("scale"))
        _set(kw, "caption_zoom_duration_sec", emph.get("duration_sec"))

        ov = applied.get("overlay", {}) or {}
        _set(kw, "overlay_font", ov.get("font"))
        _set(kw, "overlay_font_capcut", ov.get("font_capcut"))
        _set(kw, "overlay_size", ov.get("size"))
        _set(kw, "overlay_color", ov.get("color"))
        _set(kw, "overlay_position", ov.get("position"))
        _set(kw, "overlay_bold", ov.get("bold"))
        _set(kw, "overlay_all_caps", ov.get("all_caps"))
        _apply_outline(kw, "overlay", ov.get("outline"))
        _apply_background(kw, "overlay", ov.get("background"))
        _apply_animation(kw, "overlay", ov.get("animation"))

        sfx = applied.get("sfx", {}) or {}
        _set(kw, "sfx_volume", sfx.get("volume"))
        _set(kw, "sfx_duration_sec", sfx.get("duration_sec"))
        _set(kw, "sfx_trigger", sfx.get("trigger"))
        _set(kw, "sfx_map", sfx.get("map"))
        # sfx.trigger/variety/per_minute 는 분석 힌트일 뿐 — 실제 "어떤 효과음을 어디에"는
        # 스킬이 사용자에게 물어 sfx.map 을 채운다 (음원을 오디오에서 분리 못 하므로).

        kw.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**kw)


def _set(kw: dict, key: str, value):
    if value is not None:
        kw[key] = value


def _apply_outline(kw: dict, prefix: str, outline: Optional[dict]):
    if not outline or not outline.get("enabled"):
        return
    _set(kw, f"{prefix}_outline_color", outline.get("color", "#000000"))
    _set(kw, f"{prefix}_outline_width", outline.get("width"))
    if prefix == "caption":
        _set(kw, "caption_outline_alpha", outline.get("alpha"))


def _apply_shadow(kw: dict, prefix: str, shadow: Optional[dict]):
    if not shadow or not shadow.get("enabled"):
        return
    kw[f"{prefix}_shadow"] = True
    _set(kw, f"{prefix}_shadow_color", shadow.get("color"))
    _set(kw, f"{prefix}_shadow_alpha", shadow.get("alpha"))
    _set(kw, f"{prefix}_shadow_angle", shadow.get("angle"))
    _set(kw, f"{prefix}_shadow_distance", shadow.get("distance"))


def _apply_background(kw: dict, prefix: str, bg: Optional[dict]):
    if not bg or not bg.get("enabled"):
        return
    kw[f"{prefix}_bg"] = True
    _set(kw, f"{prefix}_bg_color", bg.get("color"))
    _set(kw, f"{prefix}_bg_alpha", bg.get("alpha"))
    if prefix == "caption":
        _set(kw, "caption_bg_radius", bg.get("round_radius"))


def _apply_animation(kw: dict, prefix: str, anim: Optional[dict]):
    if not anim:
        return
    _set(kw, f"{prefix}_anim_in", anim.get("in"))
    _set(kw, f"{prefix}_anim_out", anim.get("out"))
    _set(kw, f"{prefix}_anim_duration_sec", anim.get("duration_sec"))
