"""Step 6: 자막(.srt) 또는 whisper → 자막 타이밍 통계 + 컷 호흡 매핑.

사용:
  python3 transcript_timing.py <media_dir> [--out DIR] [--whisper-python PATH]

.srt 가 있으면 그걸 쓰고, 없으면 --whisper-python(기본: capcut 프로젝트 venv)의
faster_whisper 로 전사한다. (재설치하지 않는다)
"""
import argparse
import glob
import os
import re
import statistics
import subprocess
import sys

from _common import dump_json, load_json

VIDEO_EXTS = (".mp4", ".webm", ".mkv", ".mov")
# 자막(.srt)이 없을 때만 폴백으로 씀. capcut-highlight-video-editor 프로젝트의 venv에
# faster-whisper 가 이미 있으니 그걸 재사용(재설치 금지). 경로는 env 로 조정.
DEFAULT_WHISPER_PY = os.environ.get(
    "CAPCUT_VENV_PYTHON",
    os.path.expanduser("~/capcut-highlight-video-editor/.venv/bin/python"),
)

_TS = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def _parse_srt(path: str) -> list:
    cues = []
    text_lines, start, end = [], None, None
    for line in open(path, encoding="utf-8", errors="ignore"):
        line = line.strip()
        m = _TS.match(line)
        if m:
            g = list(map(int, m.groups()))
            start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
            end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
            text_lines = []
        elif line and not line.isdigit():
            text_lines.append(line)
        elif not line and start is not None and text_lines:
            cues.append({"start": start, "end": end, "text": " ".join(text_lines)})
            start = None
    if start is not None and text_lines:
        cues.append({"start": start, "end": end, "text": " ".join(text_lines)})
    return cues


def _whisper(py: str, video: str) -> list:
    code = (
        "import sys,json;from faster_whisper import WhisperModel;"
        "m=WhisperModel('small',device='cpu',compute_type='int8');"
        "segs,_=m.transcribe(sys.argv[1],vad_filter=True);"
        "print(json.dumps([{'start':s.start,'end':s.end,'text':s.text} for s in segs]))"
    )
    res = subprocess.run([py, "-c", code, video], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  whisper 실패: {res.stderr[-300:]}", file=sys.stderr)
        return []
    return __import__("json").loads(res.stdout.strip().splitlines()[-1])


def _word_count(text: str) -> int:
    ko = len(re.findall(r"[가-힣]", text))
    other = len(re.findall(r"[A-Za-z]+", text))
    return max(1, round(ko / 2) + other)


def _stats_for(cues: list) -> dict:
    if len(cues) < 2:
        return {}
    durs = [c["end"] - c["start"] for c in cues if c["end"] > c["start"]]
    gaps = [b["start"] - a["end"] for a, b in zip(cues, cues[1:]) if b["start"] - a["end"] >= 0]
    words = [_word_count(c["text"]) for c in cues]
    return {
        "n_cues": len(cues),
        "words_per_caption_median": statistics.median(words),
        "caption_duration_median_sec": round(statistics.median(durs), 2) if durs else None,
        "caption_duration_p90_sec": round(_pct(durs, 90), 2) if durs else None,
        "inter_caption_gap_median_sec": round(statistics.median(gaps), 2) if gaps else None,
    }


def _pct(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media_dir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--whisper-python", default=DEFAULT_WHISPER_PY)
    args = ap.parse_args()

    out = args.out or os.path.dirname(os.path.abspath(args.media_dir.rstrip("/")))
    vids = sorted(
        p for p in glob.glob(os.path.join(args.media_dir, "*"))
        if os.path.splitext(p)[1].lower() in VIDEO_EXTS
    )
    per = []
    for v in vids:
        vid = os.path.splitext(os.path.basename(v))[0]
        srts = sorted(glob.glob(os.path.join(args.media_dir, f"{vid}*.srt")))
        cues = _parse_srt(srts[0]) if srts else []
        src = "srt" if cues else "whisper"
        if not cues and os.path.exists(args.whisper_python):
            cues = _whisper(args.whisper_python, v)
        s = _stats_for(cues)
        if s:
            s.update(video_id=vid, source=src)
            per.append(s)
            print(f"  {vid}: {s['n_cues']} cue ({src})")

    def _agg(key):
        vals = [p[key] for p in per if isinstance(p.get(key), (int, float))]
        return round(statistics.fmean(vals), 2) if vals else None

    gap = _agg("inter_caption_gap_median_sec")
    p90 = _agg("caption_duration_p90_sec")
    timing = {
        "per_video": per,
        "aggregate": {
            "words_per_caption_median": _agg("words_per_caption_median"),
            "caption_duration_median_sec": _agg("caption_duration_median_sec"),
            "caption_duration_p90_sec": p90,
            "inter_caption_gap_median_sec": gap,
        },
        "pacing_suggestion": {
            "pause_gap_sec": round(_clamp(gap, 0.3, 0.8), 2) if gap is not None else None,
            "max_cue_sec": round(_clamp(p90, 3.0, 8.0), 2) if p90 is not None else None,
            "gap_threshold_sec": round(_clamp(gap * 1.2, 0.3, 1.0), 2) if gap is not None else None,
        },
    }
    mpath = os.path.join(out, "metrics.json")
    existing = load_json(mpath) if os.path.exists(mpath) else {}
    existing["timing"] = timing
    dump_json(existing, mpath)
    print(f"\n→ {mpath} [timing]  pacing: {timing['pacing_suggestion']}")


if __name__ == "__main__":
    main()
