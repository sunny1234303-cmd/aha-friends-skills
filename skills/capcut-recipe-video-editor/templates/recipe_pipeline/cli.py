import argparse

from .config import DEFAULT_DRAFT_FOLDER, DEFAULT_SFX_PATH, PipelineConfig
from .pipeline import orchestrate


def main():
    parser = argparse.ArgumentParser(description="레시피 숏폼 영상 자동 편집 파이프라인")
    parser.add_argument("--video", required=True)
    parser.add_argument("--content-md", required=True)
    parser.add_argument("--end-image", required=True)
    parser.add_argument("--draft-name", required=True)
    parser.add_argument("--draft-folder", default=DEFAULT_DRAFT_FOLDER)
    parser.add_argument("--whisper-model", default="small")
    parser.add_argument("--target-duration", type=float, default=60.0)
    parser.add_argument("--gap-threshold", type=float, default=0.6)
    parser.add_argument("--sfx", default=DEFAULT_SFX_PATH)

    parser.add_argument("--caption-font", default="Arimo_Regular")
    parser.add_argument("--caption-size", type=float, default=10.0)
    parser.add_argument("--caption-color", default="#FFFFFF")
    parser.add_argument("--caption-position", default="bottom", choices=["top", "center", "bottom"])

    parser.add_argument("--overlay-font", default="Arimo_Regular")
    parser.add_argument("--overlay-size", type=float, default=7.0)
    parser.add_argument("--overlay-color", default="#FFEB99")
    parser.add_argument("--overlay-position", default="top", choices=["top", "center", "bottom"])
    args = parser.parse_args()

    config = PipelineConfig(
        source_video=args.video,
        content_md=args.content_md,
        end_image=args.end_image,
        output_draft_name=args.draft_name,
        draft_folder=args.draft_folder,
        whisper_model_size=args.whisper_model,
        target_duration_sec=args.target_duration,
        gap_threshold_sec=args.gap_threshold,
        sfx_path=args.sfx,
        caption_font=args.caption_font,
        caption_size=args.caption_size,
        caption_color=args.caption_color,
        caption_position=args.caption_position,
        overlay_font=args.overlay_font,
        overlay_size=args.overlay_size,
        overlay_color=args.overlay_color,
        overlay_position=args.overlay_position,
    )
    result = orchestrate(config)
    print()
    print("=== 완료 ===")
    print(f"draft: {result.draft_dir}")
    print(f"최종 길이: {result.final_duration_sec:.1f}초")
    print(f"선택된 구간: {result.kept_segment_count}개")
    print(f"식재료: {', '.join(result.ingredient_keywords_found)}")
    print(f"SRT: {result.srt_path}")
    print(f"로그: {result.log_path}")


if __name__ == "__main__":
    main()
