"""Step 2: samples.json 의 picked 영상들을 저해상도로 다운로드 + 자막.

사용:
  python3 download_samples.py <out>/samples.json [--out DIR] [--max-height 480] [--long-seconds 120]

주의:
  - yt-dlp 는 포맷 병합·자막 변환에 ffmpeg가 필요하다. 시스템 PATH에 없으면
    imageio-ffmpeg 정적 바이너리를 --ffmpeg-location 으로 넘긴다.
  - en 자막은 자동번역 요청이 늘어 429(rate limit)를 잘 유발한다 → ko 만 받는다.
  - exit code 에 의존하지 않고, 실행 후 미디어 파일 존재 여부로 성공 판정한다.
"""
import argparse
import glob
import os
import subprocess
import sys

from _common import ffmpeg_bin_dir, load_json

VIDEO_EXTS = (".mp4", ".webm", ".mkv", ".mov")


def _has_media(media_dir: str, vid: str) -> bool:
    return any(
        glob.glob(os.path.join(media_dir, f"{vid}.{ext.lstrip('.')}"))
        for ext in VIDEO_EXTS
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("samples")
    ap.add_argument("--out", default=None, help="기본: samples.json 이 있는 폴더/media")
    # 세로 숏폼은 height 가 1280(=720p) 정도 — 자막 서체 분석엔 이 정도 화질이 필요.
    # 숏폼 720p ~30초 ≈ 2~5MB 라 대역폭 부담 크지 않다.
    ap.add_argument("--max-height", type=int, default=1280)
    ap.add_argument("--long-seconds", type=int, default=120)
    ap.add_argument("--sub-langs", default="ko.*")
    args = ap.parse_args()

    samples = load_json(args.samples)
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.samples)), "media")
    os.makedirs(out, exist_ok=True)

    ffmpeg_dir = ffmpeg_bin_dir()
    ytdlp = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
    if not os.path.exists(ytdlp):
        ytdlp = "yt-dlp"

    fmt = (
        f"bv*[height<={args.max_height}][ext=mp4]+ba[ext=m4a]/"
        f"b[height<={args.max_height}][ext=mp4]/"
        f"bv*[height<={args.max_height}]+ba/b[height<={args.max_height}]/b"
    )
    ok = 0
    picked = samples.get("picked", [])
    for m in picked:
        vid, url = m["id"], m["url"]
        dur = m.get("duration_sec") or 0
        cmd = [
            ytdlp, "-f", fmt, "--no-playlist",
            "--merge-output-format", "mp4",
            "--ffmpeg-location", ffmpeg_dir,
            "--write-subs", "--write-auto-subs", "--sub-langs", args.sub_langs,
            "--convert-subs", "srt",
            "--sleep-requests", "2", "--retries", "3",
            "--no-abort-on-error",
            "-o", os.path.join(out, "%(id)s.%(ext)s"),
        ]
        if dur > args.long_seconds + 30:
            cmd += ["--download-sections", f"*0-{args.long_seconds}"]
        subprocess.run(cmd + [url], capture_output=True, text=True)
        if _has_media(out, vid):
            ok += 1
            print(f"  OK  {vid}  {m.get('title')}")
        else:
            print(f"  FAIL {vid}  {m.get('title')}", file=sys.stderr)

    if ok == 0:
        sys.exit("다운로드 0건. `pip install -U yt-dlp` 후 재시도하거나 사용자에게 알리세요.")
    print(f"\n{ok}/{len(picked)} 다운로드 → {out}")


if __name__ == "__main__":
    main()
