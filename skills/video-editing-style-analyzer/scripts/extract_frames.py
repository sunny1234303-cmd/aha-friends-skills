"""Step 3: ffmpeg 씬컷 감지 + 샷 길이 통계 + 컨테이너 probe + 비전용 프레임 샘플링.

사용:
  python3 extract_frames.py <media_dir> [--out DIR] [--scene 0.30] [--max-frames 60]

출력:
  <out>/metrics.json  (shots, container, frame_index)
  <out>/frames/<video_id>/t_<ms>.jpg
"""
import argparse
import glob
import os
import re
import statistics
import subprocess
import sys

from _common import dump_json, ffmpeg_exe

VIDEO_EXTS = (".mp4", ".webm", ".mkv", ".mov")


def _duration_sec(ffmpeg: str, path: str) -> float:
    # ffmpeg -i 는 stderr 에 Duration 을 찍는다
    res = subprocess.run([ffmpeg, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
    if not m:
        return 0.0
    h, mm, ss = m.groups()
    return int(h) * 3600 + int(mm) * 60 + float(ss)


def _scene_cuts(ffmpeg: str, path: str, thresh: float) -> list:
    # 240px 로 다운스케일 후 씬 감지 — 컷 경계는 그대로 잡히고 4~5배 빠르다
    res = subprocess.run(
        [ffmpeg, "-i", path, "-filter:v",
         f"scale=-2:240,select='gt(scene,{thresh})',showinfo",
         "-an", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return sorted(float(x) for x in re.findall(r"pts_time:(\d+\.?\d*)", res.stderr))


def _container(path: str) -> dict:
    try:
        from pymediainfo import MediaInfo

        info = MediaInfo.parse(path)
        for t in info.tracks:
            if t.track_type == "Video":
                return {
                    "width": t.width,
                    "height": t.height,
                    "fps": round(float(t.frame_rate), 2) if t.frame_rate else None,
                    "duration_sec": (t.duration or 0) / 1000.0 if t.duration else None,
                }
    except Exception as e:  # noqa: BLE001
        print(f"  pymediainfo 실패({os.path.basename(path)}): {e}", file=sys.stderr)
    return {}


def _shot_stats(cuts: list, duration: float) -> dict:
    bounds = [0.0] + cuts + [duration]
    lengths = [b - a for a, b in zip(bounds, bounds[1:]) if b - a > 0.05]
    if not lengths:
        return {"n_shots": 0}
    n = len(lengths)
    return {
        "n_shots": n,
        "median_shot_sec": round(statistics.median(lengths), 3),
        "mean_shot_sec": round(statistics.fmean(lengths), 3),
        "p10_shot_sec": round(_pct(lengths, 10), 3),
        "p90_shot_sec": round(_pct(lengths, 90), 3),
        "cuts_per_minute": round(len(cuts) / (duration / 60.0), 2) if duration else None,
        "pct_shots_under_1_5s": round(sum(x < 1.5 for x in lengths) / n, 3),
        "pct_shots_under_0_5s": round(sum(x < 0.5 for x in lengths) / n, 3),
    }


def _pct(xs: list, p: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def _sample_times(cuts: list, duration: float, cap: int) -> list:
    times = set()
    for c in cuts[:25]:
        times.add(round(c + 0.2, 2))
    t = 0.0
    while t < min(12.0, duration):  # 후킹 조밀 (4fps)
        times.add(round(t, 2))
        t += 0.25
    for i in (1, 2, 3):
        times.add(round(duration * i / 4.0, 2))
    times = sorted(x for x in times if 0 <= x < duration)
    if len(times) > cap:
        step = len(times) / cap
        times = [times[int(i * step)] for i in range(cap)]
    return times


def _extract(ffmpeg: str, path: str, times: list, out_dir: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    names = []
    for t in times:
        name = f"t_{int(t * 1000)}.jpg"
        dst = os.path.join(out_dir, name)
        subprocess.run(
            [ffmpeg, "-ss", str(t), "-i", path, "-frames:v", "1", "-q:v", "3", "-y", dst],
            capture_output=True,
        )
        if os.path.exists(dst):
            names.append(name)
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media_dir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--scene", type=float, default=0.30)
    ap.add_argument("--max-frames", type=int, default=60)
    args = ap.parse_args()

    ffmpeg = ffmpeg_exe()
    out = args.out or os.path.dirname(os.path.abspath(args.media_dir.rstrip("/")))
    os.makedirs(out, exist_ok=True)

    vids = sorted(
        p for p in glob.glob(os.path.join(args.media_dir, "*"))
        if os.path.splitext(p)[1].lower() in VIDEO_EXTS
    )
    if not vids:
        sys.exit(f"영상 파일 없음: {args.media_dir}")

    per_video, containers, frame_index = [], [], {}
    for path in vids:
        vid = os.path.splitext(os.path.basename(path))[0]
        dur = _duration_sec(ffmpeg, path)
        cuts = _scene_cuts(ffmpeg, path, args.scene)
        stats = _shot_stats(cuts, dur)
        stats["video_id"] = vid
        stats["duration_sec"] = round(dur, 2)
        stats["cut_times"] = [round(c, 3) for c in cuts]  # analyze_audio 가 SFX-컷 상관 계산에 씀
        per_video.append(stats)
        c = _container(path)
        if c:
            containers.append(c)
        times = _sample_times(cuts, dur, args.max_frames)
        names = _extract(ffmpeg, path, times, os.path.join(out, "frames", vid))
        frame_index[vid] = names
        print(f"  {vid}: {dur:.0f}s, 컷 {len(cuts)}개, 프레임 {len(names)}장")

    def _agg(key):
        vals = [s[key] for s in per_video if s.get(key) is not None]
        return round(statistics.fmean(vals), 3) if vals else None

    def _mode(key):
        vals = [c[key] for c in containers if c.get(key)]
        return statistics.mode(vals) if vals else None

    metrics = {
        "shots": {
            "per_video": per_video,
            "aggregate": {
                k: _agg(k) for k in (
                    "median_shot_sec", "mean_shot_sec", "p10_shot_sec", "p90_shot_sec",
                    "cuts_per_minute", "pct_shots_under_1_5s", "pct_shots_under_0_5s",
                )
            },
        },
        "container": {
            "width": _mode("width"),
            "height": _mode("height"),
            "fps": _mode("fps"),
            "aspect": (
                f"{_mode('width')}:{_mode('height')}" if _mode("width") and _mode("height") else None
            ),
            "duration_median_sec": round(
                statistics.median([c["duration_sec"] for c in containers if c.get("duration_sec")]), 1
            ) if any(c.get("duration_sec") for c in containers) else None,
        },
        "frame_index": frame_index,
    }
    # 기존 metrics.json 있으면 병합
    mpath = os.path.join(out, "metrics.json")
    existing = {}
    if os.path.exists(mpath):
        from _common import load_json

        existing = load_json(mpath)
    existing.update(metrics)
    dump_json(existing, mpath)
    print(f"\n→ {mpath}")
    print(f"→ 프레임: {os.path.join(out, 'frames')}  (Step 4에서 Claude가 Read)")


if __name__ == "__main__":
    main()
