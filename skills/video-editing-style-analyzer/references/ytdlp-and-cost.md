# yt-dlp · 비용 · ToS 게이트

## 왜 yt-dlp가 필요한가

편집 스타일(자막 서체·외곽선·컷 타이밍·효과음·색보정)은 **영상 프레임과 오디오 파형에서만**
측정된다. 자막 텍스트나 메타데이터만으로는 불가능하다. 그래서 레퍼런스 영상 몇 개를
저해상도로 내려받아 ffmpeg로 뜯어봐야 한다.

`youtube-content-analyzer` 에이전트는 yt-dlp를 금지한다 — 그 에이전트는 대본/자막 추출이
목적이라 자막 API로 충분하기 때문이다. **이 스킬은 다른 목적**(픽셀 기반 스타일 계측)이므로
yt-dlp가 필수이고, 그래서 명시적 예외로 둔다.

## 게이트 (매 실행)

`AskUserQuestion`으로 아래를 함께 승인받는다:
1. `pip install yt-dlp` (scripts venv에)
2. 채널의 저해상도 숏폼 N개(기본 5개) 다운로드

## ToS / 저작권 스탠스

- **공개 벤치마킹 목적.** 편집 스타일이라는 형식적 특징을 계측하는 것이지 콘텐츠를 복제·재배포하지 않는다.
- 사용자가 **분석할 정당한 이유가 있는 채널**에만 쓴다 (레퍼런스로 삼고 싶은 채널, 경쟁 분석 등).
- 다운로드 파일은 **720p 상당(세로 숏폼 height≤1280)·일시적**. 분석 후 `example-output/`에 프레임 일부와 산출물만 남기고, 원본 mp4는 삭제 권장.
- **재배포·업로드 안 함.** 프로필 JSON에는 영상 자체가 아니라 수치만 들어간다.
- 공개 저장소(aha-friends-skills)에 올릴 땐 `frames/`와 실제 채널 mp4를 반드시 제거하고 합성/벤치마크 샘플만 남긴다.

## 대역폭 예산

| 항목 | 크기 |
|---|---|
| 숏폼 1개 720p (~30초) | 2~5 MB |
| 숏폼 5개 | 15~30 MB |
| 장편 앞 2분 720p | 20~50 MB |
| 프레임 JPG (~60장 × 5영상) | 5~15 MB |
| wav 추출 (16kHz mono, 임시) | 영상당 1~3 MB |

## yt-dlp 명령 레퍼런스

```bash
# 채널 shorts 목록 (메타만)
yt-dlp -J --flat-playlist "https://www.youtube.com/@handle/shorts"

# 단일 영상 상세 메타
yt-dlp -J --no-playlist "<video_url>"

# 저해상도 다운로드 + 자막
yt-dlp -f "bv*[height<=1280]+ba/b[height<=1280]" --no-playlist \
  --ffmpeg-location <imageio-ffmpeg dir> --merge-output-format mp4 \
  --write-subs --write-auto-subs --sub-langs "ko.*" --convert-subs srt \
  -o "media/%(id)s.%(ext)s" "<video_url>"

# 장편 앞부분만
yt-dlp -f "bv*[height<=1280]+ba/b[height<=1280]" --no-playlist \
  --ffmpeg-location <imageio-ffmpeg dir> \
  --download-sections "*0-120" -o "media/%(id)s.%(ext)s" "<video_url>"
```

## 실패 대응

- yt-dlp가 YouTube 변경으로 깨지는 일이 잦다 → `pip install -U yt-dlp` 또는 `yt-dlp -U`.
- 403/429 → 잠시 후 재시도, `--sleep-requests 2` 추가.
- **2~3회 실패하면 중단**하고 사용자에게 상황 설명 + 수동 대안(직접 화면 녹화 파일 제공) 안내.
- 지역 제한/연령 제한 영상은 건너뛰고 `samples.json`에서 다른 후보로 대체.
