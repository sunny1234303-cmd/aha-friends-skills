"""공용 헬퍼: ffmpeg 경로, yt-dlp 실행, slug."""
import json
import re
import shutil
import subprocess
import sys


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:  # noqa: BLE001
        sys.exit(f"ffmpeg를 찾을 수 없습니다. `pip install imageio-ffmpeg` 필요. ({e})")


def ffprobe_or_ffmpeg() -> str:
    """ffprobe가 있으면 그걸, 없으면 ffmpeg 바이너리를 반환(둘 다 -show 불가 시 대비)."""
    return shutil.which("ffprobe") or ffmpeg_exe()


def ffmpeg_bin_dir() -> str:
    """yt-dlp 의 --ffmpeg-location 용. 시스템 ffmpeg가 있으면 그 디렉토리,
    없으면 imageio-ffmpeg 정적 바이너리를 'ffmpeg'/'ffprobe' 이름으로 심링크한
    캐시 디렉토리를 반환한다 (yt-dlp는 그 디렉토리에서 정확한 이름을 찾는다)."""
    import os
    import tempfile

    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        return os.path.dirname(sys_ff)

    real = ffmpeg_exe()
    cache = os.path.join(tempfile.gettempdir(), "vesa_ffmpeg_bin")
    os.makedirs(cache, exist_ok=True)
    # ffmpeg 만 링크 (ffprobe 로도 링크하면 yt-dlp가 ffmpeg 바이너리를 ffprobe로
    # 호출해 깨진다 — yt-dlp는 ffprobe 없으면 ffmpeg로 폴백한다)
    link = os.path.join(cache, "ffmpeg")
    if not os.path.exists(link):
        try:
            os.symlink(real, link)
        except OSError:
            shutil.copy2(real, link)
    return cache


def yt_dlp(*args: str, capture=True) -> str:
    exe = shutil.which("yt-dlp") or f"{sys.executable} -m yt_dlp"
    cmd = (exe.split() if " " in exe else [exe]) + list(args)
    if capture:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"yt-dlp 실패: {' '.join(args)}\n{res.stderr[-800:]}")
        return res.stdout
    subprocess.run(cmd, check=True)
    return ""


def yt_dlp_json(*args: str) -> dict:
    return json.loads(yt_dlp("-J", *args))


def slugify(text: str, maxlen: int = 40) -> str:
    text = re.sub(r"[^\w\s-]", "", (text or "").strip().lower())
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:maxlen].strip("-") or "channel"


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _json_default(o):
    """numpy 스칼라/배열 → 순수 파이썬 (float32 등 not serializable 방지)."""
    if hasattr(o, "item"):
        return o.item()
    if hasattr(o, "tolist"):
        return o.tolist()
    raise TypeError(f"not JSON serializable: {type(o)}")


def dump_json(obj, path: str) -> None:
    # 임시 파일에 쓰고 rename — 중간에 실패해도 기존 파일이 깨지지 않게
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=_json_default)
    import os

    os.replace(tmp, path)
