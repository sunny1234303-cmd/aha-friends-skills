import argparse
import json

from .config import DEFAULT_DRAFT_FOLDER, DEFAULT_SFX_PATH, PipelineConfig
from .pipeline import orchestrate

# --style-profile 로 프로필을 주면 이 필드들은 프로필 값이 기본이 되고,
# 아래 CLI 플래그를 명시적으로 준 것만 프로필 위에 덮어쓴다.
# (argparse.SUPPRESS 라서 "안 준" 플래그는 args 에 아예 나타나지 않는다)
_STYLE_FLAGS = {
    "caption_font", "caption_size", "caption_color", "caption_position",
    "caption_bold", "caption_align", "caption_all_caps",
    "caption_outline_color", "caption_outline_width",
    "caption_shadow", "caption_bg", "caption_bg_color",
    "caption_anim_in", "caption_anim_out", "caption_anim_duration_sec",
    "caption_zoom_trigger", "caption_zoom_scale", "caption_zoom_duration_sec",
    "overlay_font", "overlay_size", "overlay_color", "overlay_position",
    "overlay_bold", "overlay_all_caps", "overlay_outline_color", "overlay_outline_width",
    "overlay_bg", "overlay_bg_color", "overlay_anim_in", "overlay_anim_out",
    "pause_gap_sec", "max_cue_sec", "gap_threshold_sec", "target_duration_sec",
    "sfx_volume", "sfx_dir", "sfx_trigger", "sfx_map",
}

_ANIM_IN = ["none", "fade", "pop", "slide-up", "typewriter", "zoom", "karaoke"]
_ANIM_OUT = ["none", "fade", "scale-down", "slide-down"]


def main():
    parser = argparse.ArgumentParser(description="숏폼 하이라이트 영상 자동 편집 파이프라인")
    parser.add_argument("--video", required=True)
    parser.add_argument(
        "--content-md",
        default=None,
        help="텍스트 노트 .md (선택, 재료/단계/제품명 등 리스트가 있는 어떤 내용이든). 없으면 키워드 감지·오버레이·효과음 없이 순서대로 하이라이트 선별",
    )
    parser.add_argument("--end-image", required=True)
    parser.add_argument("--draft-name", required=True)
    parser.add_argument("--draft-folder", default=DEFAULT_DRAFT_FOLDER)
    parser.add_argument("--whisper-model", default="small")
    parser.add_argument("--sfx", default=DEFAULT_SFX_PATH)
    parser.add_argument(
        "--style-profile",
        default=None,
        help="video-editing-style-analyzer 스킬이 만든 style-profile.json. 주면 자막/컷호흡/효과음 스타일이 그 채널 룩을 따라간다.",
    )

    # 스타일/호흡 플래그 — SUPPRESS: 명시적으로 준 것만 args에 나타남
    S = argparse.SUPPRESS
    parser.add_argument("--target-duration", dest="target_duration_sec", type=float, default=S)
    parser.add_argument("--gap-threshold", dest="gap_threshold_sec", type=float, default=S)
    parser.add_argument("--pause-gap", dest="pause_gap_sec", type=float, default=S)
    parser.add_argument("--max-cue", dest="max_cue_sec", type=float, default=S)

    parser.add_argument("--caption-font", dest="caption_font", default=S)
    parser.add_argument("--caption-size", dest="caption_size", type=float, default=S)
    parser.add_argument("--caption-color", dest="caption_color", default=S)
    parser.add_argument("--caption-position", dest="caption_position", choices=["top", "center", "bottom"], default=S)
    parser.add_argument("--caption-align", dest="caption_align", type=int, choices=[0, 1, 2], default=S)
    parser.add_argument("--caption-bold", dest="caption_bold", action="store_true", default=S)
    parser.add_argument("--caption-all-caps", dest="caption_all_caps", action="store_true", default=S)
    parser.add_argument("--caption-outline-color", dest="caption_outline_color", default=S)
    parser.add_argument("--caption-outline-width", dest="caption_outline_width", type=float, default=S)
    parser.add_argument("--caption-shadow", dest="caption_shadow", action="store_true", default=S)
    parser.add_argument("--caption-bg", dest="caption_bg", action="store_true", default=S)
    parser.add_argument("--caption-bg-color", dest="caption_bg_color", default=S)
    parser.add_argument("--caption-anim-in", dest="caption_anim_in", choices=_ANIM_IN, default=S)
    parser.add_argument("--caption-anim-out", dest="caption_anim_out", choices=_ANIM_OUT, default=S)
    parser.add_argument("--caption-anim-duration", dest="caption_anim_duration_sec", type=float, default=S)
    parser.add_argument("--caption-zoom-trigger", dest="caption_zoom_trigger", choices=["keyword", "all", "none"], default=S)
    parser.add_argument("--caption-zoom-scale", dest="caption_zoom_scale", type=float, default=S)
    parser.add_argument("--caption-zoom-duration", dest="caption_zoom_duration_sec", type=float, default=S)

    parser.add_argument("--overlay-font", dest="overlay_font", default=S)
    parser.add_argument("--overlay-size", dest="overlay_size", type=float, default=S)
    parser.add_argument("--overlay-color", dest="overlay_color", default=S)
    parser.add_argument("--overlay-position", dest="overlay_position", choices=["top", "center", "bottom"], default=S)
    parser.add_argument("--overlay-all-caps", dest="overlay_all_caps", action="store_true", default=S)
    parser.add_argument("--overlay-outline-color", dest="overlay_outline_color", default=S)
    parser.add_argument("--overlay-outline-width", dest="overlay_outline_width", type=float, default=S)
    parser.add_argument("--overlay-bg", dest="overlay_bg", action="store_true", default=S)
    parser.add_argument("--overlay-bg-color", dest="overlay_bg_color", default=S)
    parser.add_argument("--overlay-anim-in", dest="overlay_anim_in", choices=_ANIM_IN, default=S)
    parser.add_argument("--overlay-anim-out", dest="overlay_anim_out", choices=_ANIM_OUT, default=S)

    parser.add_argument("--sfx-volume", dest="sfx_volume", type=float, default=S)
    parser.add_argument("--sfx-dir", dest="sfx_dir", default=S, help="효과음 폴더")
    parser.add_argument("--sfx-trigger", dest="sfx_trigger", choices=["keywords", "cuts", "both", "caption_in"], default=S)
    parser.add_argument(
        "--sfx-map", dest="sfx_map", default=S,
        help='효과음별 배치 JSON, 예: \'[{"file":"whoosh.wav","trigger":"cuts"},{"file":"ding.wav","trigger":"keywords"}]\'',
    )

    args = parser.parse_args()

    if args.style_profile:
        config = PipelineConfig.from_style_profile(
            args.style_profile,
            source_video=args.video,
            end_image=args.end_image,
            output_draft_name=args.draft_name,
        )
        config.content_md = args.content_md
        config.draft_folder = args.draft_folder
        config.whisper_model_size = args.whisper_model
        if args.sfx != DEFAULT_SFX_PATH:
            config.sfx_path = args.sfx
    else:
        config = PipelineConfig(
            source_video=args.video,
            content_md=args.content_md,
            end_image=args.end_image,
            output_draft_name=args.draft_name,
            draft_folder=args.draft_folder,
            whisper_model_size=args.whisper_model,
            sfx_path=args.sfx,
        )

    # 명시적으로 준 스타일/호흡 플래그만 덮어쓰기
    for key in _STYLE_FLAGS:
        if hasattr(args, key):
            val = getattr(args, key)
            if key == "sfx_map" and isinstance(val, str):
                val = json.loads(val)
            setattr(config, key, val)

    result = orchestrate(config)
    print()
    print("=== 완료 ===")
    print(f"draft: {result.draft_dir}")
    print(f"최종 길이: {result.final_duration_sec:.1f}초")
    print(f"선택된 구간: {result.kept_segment_count}개")
    print(f"키워드: {', '.join(result.ingredient_keywords_found) or '없음'}")
    print(f"SRT: {result.srt_path}")
    print(f"로그: {result.log_path}")


if __name__ == "__main__":
    main()
