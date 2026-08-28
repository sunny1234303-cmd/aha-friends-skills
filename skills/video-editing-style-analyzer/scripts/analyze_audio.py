"""Step 5: 오디오 → SFX 버스트(빈도·배치·다양성) + BGM 유무 → metrics.json["audio"].

- SFX 버스트를 감지하고, extract_frames 가 남긴 컷 타임스탬프(metrics.json shots.per_video.cut_times)와
  대조해 "컷마다 효과음이 붙는지"를 계산한다 → sfx.trigger 판정 근거.
- 버스트들의 스펙트럴 특성 분산으로 "효과음이 1종인지 여러 종인지" 대략 추정.

사용:
  python3 analyze_audio.py <media_dir> [--out DIR]
  (extract_frames.py 를 먼저 돌려 metrics.json 에 shots.cut_times 가 있어야 컷 상관 계산됨)
"""
import argparse
import glob
import os
import statistics
import subprocess
import sys
import tempfile

import numpy as np

from _common import dump_json, ffmpeg_exe, load_json

VIDEO_EXTS = (".mp4", ".webm", ".mkv", ".mov")
SR = 16000
HOP = 320  # 20ms
CUT_WINDOW_SEC = 0.35  # 버스트가 컷에서 이 안에 있으면 "컷에 붙은 효과음"


def _wav(ffmpeg: str, path: str) -> np.ndarray:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run(
        [ffmpeg, "-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-y", tmp.name],
        capture_output=True,
    )
    try:
        import soundfile as sf

        data, _ = sf.read(tmp.name, dtype="float32")
    finally:
        os.unlink(tmp.name)
    return data if data.ndim == 1 else data.mean(axis=1)


def _envelope_db(x: np.ndarray) -> np.ndarray:
    n = len(x) // HOP
    frames = x[: n * HOP].reshape(n, HOP)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-9)
    return 20 * np.log10(rms + 1e-9)


def _spectral_centroid(seg: np.ndarray) -> float:
    if seg.size < 64:
        return 0.0
    win = seg * np.hanning(len(seg))
    mag = np.abs(np.fft.rfft(win)) + 1e-9
    freqs = np.fft.rfftfreq(len(win), 1.0 / SR)
    return float((freqs * mag).sum() / mag.sum())


def _analyze_one(ffmpeg: str, path: str, cut_times: list) -> dict:
    x = _wav(ffmpeg, path)
    if x.size == 0:
        return {}
    db = _envelope_db(x)
    dur_sec = len(x) / SR
    dur_min = dur_sec / 60.0
    floor = float(np.percentile(db, 20))
    speech = db > (floor + 12)

    d = np.diff(db, prepend=db[0])
    bursts = []  # (start_frame, end_frame)
    i = 0
    while i < len(db) - 1:
        if d[i] > 10 and not speech[max(0, i - 4):i + 1].any():
            j = i
            while j < len(db) - 1 and db[j] > floor + 6 and j - i < 10:
                j += 1
            bursts.append((i, j))
            i = j + 2
        else:
            i += 1

    burst_times = [f0 * HOP / SR for f0, _ in bursts]
    burst_lens = [(j - i) * HOP / SR for i, j in bursts]
    burst_peak = [db[i:j].max() for i, j in bursts if j > i]
    speech_level = float(np.median(db[speech])) if speech.any() else floor

    # 컷 상관: 각 컷 타임스탬프 근처(±window)에 버스트가 있나 / 각 버스트가 컷 근처인가
    cuts = sorted(cut_times or [])
    cuts_with_sfx = 0
    for c in cuts:
        if any(abs(bt - c) <= CUT_WINDOW_SEC for bt in burst_times):
            cuts_with_sfx += 1
    bursts_on_cut = 0
    for bt in burst_times:
        if cuts and min(abs(bt - c) for c in cuts) <= CUT_WINDOW_SEC:
            bursts_on_cut += 1

    # 다양성: 버스트별 (스펙트럴 센트로이드, 길이) → 정규화 후 표준편차
    variety = None
    if len(bursts) >= 4:
        feats = []
        for f0, f1 in bursts:
            s0, s1 = f0 * HOP, min(len(x), f1 * HOP + HOP)
            feats.append([_spectral_centroid(x[s0:s1]), (f1 - f0) * HOP / SR])
        feats = np.array(feats)
        if feats[:, 0].std() > 0:
            cv_centroid = feats[:, 0].std() / (feats[:, 0].mean() + 1e-9)
            variety = round(float(cv_centroid), 3)

    # BGM
    gap_energy = []
    run = 0
    for k, s in enumerate(speech):
        if not s:
            run += 1
        else:
            if run > 30:
                gap_energy.extend(db[k - run:k].tolist())
            run = 0
    bgm_level = float(np.median(gap_energy)) if gap_energy else floor

    return {
        "video_id": os.path.splitext(os.path.basename(path))[0],
        "sfx_bursts_per_minute": round(len(bursts) / dur_min, 2) if dur_min else 0,
        "sfx_burst_median_sec": round(statistics.median(burst_lens), 3) if burst_lens else None,
        "sfx_peak_vs_speech_db": round(float(np.median(burst_peak)) - speech_level, 1) if burst_peak else None,
        "n_bursts": len(bursts),
        "n_cuts": len(cuts),
        "cuts_with_sfx_fraction": round(cuts_with_sfx / len(cuts), 3) if cuts else None,
        "bursts_on_cut_fraction": round(bursts_on_cut / len(bursts), 3) if bursts else None,
        "sfx_variety_cv": variety,  # 높을수록 여러 종류의 소리
        "bgm_present": bool(bgm_level > -45),
        "bgm_level_db_below_vo": round(bgm_level - speech_level, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media_dir")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    ffmpeg = ffmpeg_exe()
    out = args.out or os.path.dirname(os.path.abspath(args.media_dir.rstrip("/")))
    mpath = os.path.join(out, "metrics.json")
    existing = load_json(mpath) if os.path.exists(mpath) else {}
    cut_map = {
        s.get("video_id"): s.get("cut_times", [])
        for s in existing.get("shots", {}).get("per_video", [])
    }

    vids = sorted(
        p for p in glob.glob(os.path.join(args.media_dir, "*"))
        if os.path.splitext(p)[1].lower() in VIDEO_EXTS
    )
    if not vids:
        sys.exit(f"영상 없음: {args.media_dir}")

    per = []
    for p in vids:
        vid = os.path.splitext(os.path.basename(p))[0]
        r = _analyze_one(ffmpeg, p, cut_map.get(vid, []))
        if r:
            per.append(r)
            print(f"  {vid}: SFX {r['sfx_bursts_per_minute']}/min, "
                  f"컷당 효과음 {r['cuts_with_sfx_fraction']}, "
                  f"다양성 {r['sfx_variety_cv']}, BGM {r['bgm_present']}")

    def _agg(key):
        vals = [r[key] for r in per if isinstance(r.get(key), (int, float))]
        return round(statistics.fmean(vals), 3) if vals else None

    peak_vs_speech = _agg("sfx_peak_vs_speech_db")
    suggested_volume = 0.7
    if peak_vs_speech is not None:
        suggested_volume = round(min(1.0, max(0.4, 0.7 + peak_vs_speech / 20.0)), 2)

    cuts_with_sfx = _agg("cuts_with_sfx_fraction")
    variety_cv = _agg("sfx_variety_cv")
    # trigger 판정: 컷의 절반 이상에 효과음 → cuts, 아주 드물면 keywords, 중간이면 both
    if cuts_with_sfx is not None and cuts_with_sfx >= 0.45:
        trigger = "cuts"
    elif cuts_with_sfx is not None and cuts_with_sfx >= 0.15:
        trigger = "both"
    else:
        trigger = "keywords"
    variety = "varied" if (variety_cv or 0) >= 0.25 else "single"

    audio = {
        "per_video": per,
        "aggregate": {
            "sfx_bursts_per_minute": _agg("sfx_bursts_per_minute"),
            "sfx_burst_median_sec": _agg("sfx_burst_median_sec"),
            "suggested_sfx_volume": suggested_volume,
            "cuts_with_sfx_fraction": cuts_with_sfx,
            "sfx_trigger": trigger,
            "sfx_variety": variety,
            "sfx_variety_cv": variety_cv,
            "bgm_present": sum(r["bgm_present"] for r in per) > len(per) / 2 if per else False,
            "bgm_level_db_below_vo": _agg("bgm_level_db_below_vo"),
        },
    }
    existing["audio"] = audio
    dump_json(existing, mpath)
    print(f"\n→ {mpath} [audio]  trigger={trigger}, variety={variety}")


if __name__ == "__main__":
    main()
