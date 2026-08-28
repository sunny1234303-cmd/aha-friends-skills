"""Stage 2: 자막 스크립트 생성 (local Whisper, offline)."""

import os
from typing import List

from faster_whisper import WhisperModel

from .models import TranscriptSegment


def _format_srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _regroup_words_into_cues(
    words, pause_gap_sec: float = 0.5, max_cue_sec: float = 6.0
) -> List[TranscriptSegment]:
    """Whisper's own `segment.text` chunks are ~30s model-window artifacts, not
    real phrase boundaries. Re-derive phrase-level cues from word timestamps by
    splitting on pauses between words (or once a cue gets too long)."""
    cues: List[TranscriptSegment] = []
    current = []

    def flush():
        if current:
            text = "".join(w.word for w in current).strip()
            if text:
                cues.append(
                    TranscriptSegment(
                        start=current[0].start, end=current[-1].end, text=text
                    )
                )

    for w in words:
        if current:
            gap = w.start - current[-1].end
            span = w.end - current[0].start
            if gap >= pause_gap_sec or span >= max_cue_sec:
                flush()
                current = []
        current.append(w)
    flush()
    return cues


def transcribe_to_srt(
    video_path: str,
    srt_out_path: str,
    model_size: str = "small",
    pause_gap_sec: float = 0.5,
    max_cue_sec: float = 6.0,
) -> List[TranscriptSegment]:
    """Runs local Whisper over the video's audio track and writes an SRT file.

    Returns the parsed segments (seconds, relative to the source video) for
    downstream stages, so callers don't need to re-parse the SRT they just wrote.
    """
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    whisper_segments, _info = model.transcribe(
        video_path,
        language="ko",
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        word_timestamps=True,
    )

    all_words = []
    for seg in whisper_segments:
        if seg.words:
            all_words.extend(seg.words)

    segments = _regroup_words_into_cues(all_words, pause_gap_sec, max_cue_sec)

    lines = []
    for i, seg in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(
            f"{_format_srt_timestamp(seg.start)} --> {_format_srt_timestamp(seg.end)}"
        )
        lines.append(seg.text)
        lines.append("")

    os.makedirs(os.path.dirname(srt_out_path), exist_ok=True)
    with open(srt_out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return segments
