"""Stage 8: 자동 효과음 추가 (식재료 등장 시점마다).

Deviation from the original plan worth flagging: pycapcut's
`AudioSceneEffectType` (mentioned in the plan) turned out, on inspection, to
be a set of ~200 whimsical voice-changer filters (Bibble, Witch, Elfy, Good
Guy, ...) meant to be applied over spoken audio — not one-shot cue sounds. A
0.3s burst of one of those would sound like a brief voice-warp glitch, not a
"ding"-style ingredient-reveal effect. Using a short local audio file (a real
sound effect) on its own track, added at each ingredient timepoint via
AudioSegment, matches the requirement far better. A default two-tone ding
(`assets/default_ding.wav`) is bundled; swap `config.sfx_path` for a real
effect file if you have one.
"""

from typing import List

import pycapcut as cc

SEC = cc.SEC


def add_sfx_bursts(
    script: cc.ScriptFile,
    new_start_times_sec: List[float],
    sfx_path: str,
    sfx_duration_sec: float = 0.3,
    track_name: str = "sfx",
) -> None:
    sfx_material = cc.AudioMaterial(sfx_path)
    for t in new_start_times_sec:
        segment = cc.AudioSegment(
            sfx_material,
            cc.Timerange(int(t * SEC), int(sfx_duration_sec * SEC)),
            volume=0.7,
        )
        script.add_segment(segment, track_name)
