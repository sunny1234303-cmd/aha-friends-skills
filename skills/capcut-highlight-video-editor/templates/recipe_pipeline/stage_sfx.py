"""Stage 8: 자동 효과음 추가.

pycapcut 의 `AudioSceneEffectType` 은 (문서와 달리) 보이스체인저 필터 ~200종이라
"딩" 같은 단발 효과음이 아니다 — 로컬 오디오 파일을 별도 트랙에 AudioSegment 로
얹는 방식을 쓴다. `assets/default_ding.wav` 기본 제공.

배치 방식:
  - add_sfx_placements: (시각, 파일) 쌍 목록 — "어떤 효과음을 어디에" 를 pipeline.py 가
    sfx_map 으로 정해서 넘긴다 (권장).
  - add_sfx_bursts: 한 트리거에 파일 목록을 순환 (단순 케이스).
"""

from typing import List, Sequence, Tuple, Union

import pycapcut as cc

SEC = cc.SEC


def add_sfx_placements(
    script: cc.ScriptFile,
    placements: Sequence[Tuple[float, str]],
    sfx_duration_sec: float = 0.3,
    track_name: str = "sfx",
    volume: float = 0.7,
) -> int:
    """placements: [(start_sec, audio_path), ...]. 같은 파일이 여러 번 와도 됨.
    한 트랙에서 겹치지 않도록 0.15초 내 중복은 앞의 것만 남긴다."""
    seen: List[float] = []
    mats: dict = {}
    placed = 0
    for t, path in sorted(placements, key=lambda p: p[0]):
        if seen and t - seen[-1] < 0.15:
            continue
        seen.append(t)
        if path not in mats:
            mats[path] = cc.AudioMaterial(path)
        script.add_segment(
            cc.AudioSegment(
                mats[path],
                cc.Timerange(int(t * SEC), int(sfx_duration_sec * SEC)),
                volume=volume,
            ),
            track_name,
        )
        placed += 1
    return placed


def add_sfx_bursts(
    script: cc.ScriptFile,
    new_start_times_sec: List[float],
    sfx_paths: Union[str, List[str]],
    sfx_duration_sec: float = 0.3,
    track_name: str = "sfx",
    volume: float = 0.7,
) -> None:
    paths = [sfx_paths] if isinstance(sfx_paths, str) else list(sfx_paths)
    if not paths:
        return
    placements = [
        (t, paths[i % len(paths)]) for i, t in enumerate(sorted(new_start_times_sec))
    ]
    add_sfx_placements(script, placements, sfx_duration_sec, track_name, volume)
