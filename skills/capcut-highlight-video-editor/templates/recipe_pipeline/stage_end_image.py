"""Stage 9: 종료 2-3초 전 사전 캡쳐본 추가 (사용자가 미리 준비한 이미지 파일)."""

import pycapcut as cc

SEC = cc.SEC


def add_end_image(
    script: cc.ScriptFile,
    image_path: str,
    total_output_duration_sec: float,
    lead_sec: float = 2.5,
    track_name: str = "end_image",
) -> None:
    start = max(0.0, total_output_duration_sec - lead_sec)
    duration = total_output_duration_sec - start
    image_material = cc.VideoMaterial(image_path)
    segment = cc.VideoSegment(
        image_material,
        cc.Timerange(int(start * SEC), int(duration * SEC)),
    )
    script.add_segment(segment, track_name)
