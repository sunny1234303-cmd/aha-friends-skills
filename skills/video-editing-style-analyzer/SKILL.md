---
name: video-editing-style-analyzer
description: |
  유튜브 채널/영상 URL만 주면 그 채널의 숏폼 편집 스타일(컷 호흡, 자막 서체·외곽선·애니메이션, 줌 강조, 효과음 빈도, 색보정, 후킹 구조)을 계측해 재사용 가능한 style-profile.json으로 저장하는 스킬. 이 프로필을 capcut-highlight-video-editor 파이프라인에 넣으면 자동 편집 draft가 그 채널 룩을 따라간다. 특정 브랜드 전용이 아니다.

  Triggers:
  - "이 채널 편집 스타일 분석해줘"
  - "이 유튜버처럼 편집되게 스타일 뽑아줘"
  - "영상 편집 스타일 프로필 만들어줘"
  - "이 채널 컷 편집 분석"

  Use when: 벤치마킹할 채널/영상을 주고 그 룩을 자동 편집 파이프라인에 이식하려 할 때. 편집 "스타일"을 수치로 뽑는 게 목적이지, 대본·자막 내용 요약이 아니다.
allowed-tools: Read, Write, Bash, AskUserQuestion
---

# video-editing-style-analyzer 스킬

## 왜 이 스킬이 필요한가

편집 스타일은 말로 옮기기 어렵다. "자막을 크게" "컷을 빠르게"는 사람마다 기준이 다르고, 매번 자막 크기·색·외곽선·컷 길이를 손으로 맞추면 재현이 안 된다. 레퍼런스 채널의 **실제 픽셀과 오디오를 계측**해 수치화하면, `capcut-highlight-video-editor` 파이프라인이 그 수치를 그대로 재생산한다. URL 하나 → 그 채널 룩의 자동 편집.

편집 스타일 분석은 자막 텍스트만으로는 불가능하다 — 서체·외곽선·컷 타이밍·효과음은 영상 프레임과 오디오 파형에서만 나온다. 그래서 이 스킬은 레퍼런스 영상 몇 개를 720p로 내려받아 분석한다.

## 사전 확인 (필수, 순서대로 — 게이트)

1. **`yt-dlp` 미설치 + 영상 다운로드 승인.** `AskUserQuestion`으로 (1) `pip install yt-dlp` (2) 저해상도 숏폼 5개 다운로드를 명시적으로 승인받는다.
   - 저작권/ToS: 이 스킬은 **공개 벤치마킹** 목적이며, 사용자가 분석할 정당한 이유가 있는 채널에만 쓴다. 저해상도(720p 상당, height≤1280)·일시적·재배포 안 함.
   - (`youtube-content-analyzer` 에이전트는 yt-dlp를 금지하지만 그건 그 에이전트 한정 규칙이다. 편집 스타일 분석은 자막만으로 불가능하므로 이 스킬은 명시적 예외다 — `references/ytdlp-and-cost.md` 참고.)
2. **`ffmpeg` PATH에 없음** → `imageio-ffmpeg` 정적 바이너리 사용. 스크립트가 `imageio_ffmpeg.get_ffmpeg_exe()`로 자동 해결한다.
3. **대역폭:** 720p 상당(세로 숏폼 height≤1280), 숏폼만, 5개 ≈ 15~30MB. 장편 채널이면 앞 2분만.
4. **대상 포맷:** 사용자가 숏폼을 만들면 채널의 **Shorts만** 분석한다(장편과 섞으면 프로필이 흐려진다). 채널에 Shorts가 없으면 사용자에게 알리고 장편 분석 여부를 묻는다.
5. **결과 저장 위치** = `capcut-highlight-video-editor` 스킬로 만든 프로젝트의 `style-profiles/` 폴더. 그 프로젝트 경로를 확인한다 (스크립트 기본값 `~/capcut-highlight-video-editor`, `CAPCUT_PROJECT` env 또는 `--capcut-project` 로 조정). faster-whisper 재사용도 그 프로젝트 venv (`CAPCUT_VENV_PYTHON` env).
6. **비용/보안:** 모든 처리는 로컬. 클라우드 STT/비전 API 안 씀. 자막 타이밍은 다운로드된 자막 또는 로컬 whisper(capcut 프로젝트 venv).

## 전체 워크플로우

```
URL (채널 or 영상)
  │
  ▼
[1] select_samples.py   채널 → 대표 숏폼 5개 선정 (조회수 상위 3 + 최신 3)   → samples.json
  │
  ▼
[2] download_samples.py  yt-dlp 720p + 자막                               → <slug>.mp4 / .srt
  │
  ▼
[3] extract_frames.py    ffmpeg 씬컷 감지 · 샷길이 통계 · 컨테이너 probe    → metrics.json (shots/container)
  │                       · 비전용 프레임 샘플링 (컷 직후 · 후킹 조밀 · 중간)  → frames/<slug>/*.jpg
  ▼
[4] (Claude 비전)        프레임을 Read → 자막 타이포/애니메이션/줌/색보정      → vision-notes.json
  │                       references/analysis-methodology.md 체크리스트대로
  ▼
[5] analyze_audio.py     SFX 버스트 ↔ 컷 대조 → sfx.trigger · variety · BGM   → metrics.json (audio)
  │
  ▼
[6] transcript_timing.py 자막/whisper → 큐당 단어수 · 큐 길이 · 컷 호흡        → metrics.json (timing)
  │
  ▼
[6.5] (AskUserQuestion) 효과음 파일·배치를 사용자에게 물어봄 (음원 분리 불가)  → --sfx-map JSON
  │
  ▼
[7] build_profile.py     samples + metrics + vision-notes + sfx-map 병합       → style-profile.json
  │                       + 필드별 confidence + provenance
  ▼
[8] 설치                 style-profile.json → <capcut-project>/style-profiles/<slug>.json
                         사용자에게 CLI 명령 + TIER A/B 안내
```

## Step 1 — 입력 해석 & 샘플 선정

`scripts/select_samples.py <URL> [--count 5] [--format shorts] [--out DIR]`

- 채널 URL(`/@handle`, `/channel/UC…`, `/c/name`) 또는 단일 영상 URL을 받는다.
- **단일 영상**: 샘플셋 = 그 영상 하나. provenance `notes`에 "단일 영상 소스 → 컷 호흡/샘플 신뢰도 낮음" 기록.
- **채널**: `yt-dlp -J --flat-playlist "<channel>/shorts"` → 최근 15개 후보 → 각각 `yt-dlp -J --no-playlist`로 조회수·업로드일·해상도·fps 확보 → (조회수 상위 3) ∪ (최신 3) 중복 제거, 이상치(길이가 채널 중앙값에서 2배 이상 벗어남, 라이브 VOD) 제외.
- 출력: `<out>/samples.json`

Claude는 이 스크립트를 실행한 뒤 `samples.json`을 Read해서 선정 결과를 사용자에게 보여주고 넘어간다.

## Step 2 — 다운로드

`scripts/download_samples.py <out>/samples.json [--out DIR] [--max-height 1280] [--long-seconds 120]`

- 숏폼(<90s): 전체 다운로드 `-f "bv*[height<=1280]+ba/b[height<=1280]"` (세로 숏폼은 height 가 곧 세로 픽셀이라 720p면 1280).
- 장편: `--download-sections "*0-<long-seconds>"`로 앞부분만.
- 자막: `--write-subs --write-auto-subs --sub-langs "ko.*" --convert-subs srt` (en 자막은 자동번역 요청이 늘어 429를 잘 유발 → ko만).
- ffmpeg가 PATH에 없으면 `--ffmpeg-location`에 imageio-ffmpeg 바이너리를 `ffmpeg` 이름으로 심링크한 디렉토리를 넘긴다 (`_common.ffmpeg_bin_dir()`가 처리). 이게 없으면 포맷 병합·srt 변환이 조용히 실패한다.
- 출력: `<out>/media/<video_id>.mp4`, `<video_id>.ko.srt` 등.

## Step 3 — 프레임 + 씬 추출

`scripts/extract_frames.py <out>/media [--out DIR]`

- ffmpeg 씬컷 감지 → 샷 길이 통계(`median_shot_sec`, `cuts_per_minute`, `pct_shots_under_1_5s` 등).
- `pymediainfo`로 해상도·fps·종횡비 → 최빈값.
- 비전용 프레임: 각 컷 0.2s 후 1장(≤25/영상) + 0~12s 4fps 버스트(후킹·자막 인아웃) + 중간 3장 균등. 상한 ~60/영상.
- 출력: `<out>/metrics.json` (shots, container, frame_index), `<out>/frames/<slug>/t_<ms>.jpg`

## Step 4 — 비전 추출 (Claude가 직접)

**스크립트 아님.** Claude가 `<out>/frames/`의 JPG들을 `Read`하고 `references/analysis-methodology.md`의 체크리스트대로 관찰해 `<out>/vision-notes.json`을 작성한다.

각 필드는 `{"value": ..., "confidence": 0.0~1.0, "evidence": ["t_1200.jpg", ...]}` 형태. 추출 항목(자세한 정의는 methodology 문서):

- **자막 타이포그래피**: 폰트 패밀리 추정(+대안 1~2개), 굵기, 케이스(normal/ALL-CAPS), 프레임 높이 대비 글자 크기 비율, 채움색 hex, 외곽선(유무/색/상대두께), 드롭섀도우(유무/방향), 배경 박스(유무/색/불투명도/라운드/풀폭), 세로 위치(상단/중앙/하단 + 정확한 비율), 정렬, 줄 수
- **자막 애니메이션**: 후킹 조밀 프레임 비교 → 인 {none|fade|pop|slide-up|typewriter|karaoke}, 아웃 {none|fade|scale-down|slide-down}, 대략 길이
- **강조/키워드 스타일링**: 강조 단어가 다른 색/박스/스케일을 받는지
- **줌 펀치인**: 고정 샷에서 프레이밍이 단계적으로 확대되는지, 배율(~1.05~1.20), 스냅/이즈
- **오버레이/타이틀 카드**: 자막과 별개 스타일
- **(advisory) 색보정**: 대비/채도/색온도/블랙레벨/필름룩/비네트
- **(advisory) 후킹 구조**: 첫 3초 패턴
- **(advisory) 샷 스케일 믹스, B롤 비율, 텍스트 밀도, 이모지, 검열 삐/모자이크**

## Step 5 — 오디오 분석

`scripts/analyze_audio.py <out>/media [--out DIR]` → `<out>/metrics.json` (audio)
(Step 3 을 먼저 돌려 `shots.cut_times` 가 있어야 SFX-컷 상관이 계산됨)

- ffmpeg로 wav 추출 → RMS 엔벨로프 → SFX 버스트 감지 → `sfx_bursts_per_minute`, 제안 `sfx_volume`, BGM 유무/에너지.
- **SFX 배치 판정**: 각 버스트를 Step 3 의 컷 타임스탬프와 대조 → `cuts_with_sfx_fraction` → `sfx.trigger`(cuts / both / keywords).
- **SFX 다양성**: 버스트들의 스펙트럴 센트로이드 변동계수 → `sfx.variety`(single / varied).

## Step 6 — 자막 타이밍

`scripts/transcript_timing.py <out>/media [--out DIR] [--whisper-python PATH]`

- 다운로드된 `.srt` 우선. 없으면 `capcut-highlight-video-editor` 프로젝트 venv의 faster-whisper 재사용(재설치 금지):
  `--whisper-python` 또는 `CAPCUT_VENV_PYTHON` env (기본 `~/capcut-highlight-video-editor/.venv/bin/python`)
- `words_per_caption`, `caption_duration_sec`(중앙값·p90), `inter_caption_gap_sec` → 컷 호흡 매핑:
  - `pause_gap_sec` ≈ clamp(중앙값 간격, 0.3, 0.8)
  - `max_cue_sec` ≈ clamp(p90 자막 길이, 3.0, 8.0)
  - `gap_threshold_sec` ≈ clamp(중앙값 간격 × 1.2, 0.3, 1.0)

## Step 6.5 — 효과음 배치를 사용자에게 물어본다 (필수)

**분석기는 오디오에서 효과음 음원을 분리하지 못한다.** "컷의 X%에 효과음 · 여러 종류" 같은
힌트만 뽑는다. 실제로 "어떤 효과음 파일을 어디에" 넣을지는 **사람마다 다르므로 반드시 물어본다.**

Step 5 결과(`sfx.trigger`, `sfx.variety`, `sfx.per_minute`)를 사용자에게 보여주고 물어본다:
1. 효과음 파일이 있나? (없으면 `sfx` 생략 — 기본 ding만, 또는 아예 안 넣음)
2. 파일이 있으면 **각 파일을 어디에** 넣을지:
   - `cuts` — 컷(클립 경계)마다 (전환음 whoosh 류)
   - `keywords` — 키워드 언급 시 (`.md` 필요, 강조 딩 류)
   - `caption_in` — 모든 자막 등장마다 (팝 류)
   - `end` — 엔딩 직전 1회

답을 받아 `--sfx-map` JSON 으로 Step 7 에 넘긴다:
```
--sfx-map '[{"file":"whoosh.wav","trigger":"cuts"},{"file":"ding.wav","trigger":"keywords"}]'
```
(같은 trigger 에 파일 여러 개면 그 안에서 순환. `file` 은 사용자가 파이프라인 실행 시 `--sfx-dir` 로 줄 폴더 기준 상대명.)

## Step 7 — 프로필 빌드

`scripts/build_profile.py <out> [--capcut-project PATH] [--slug NAME] [--sfx-map JSON]`

- `samples.json` + `metrics.json` + `vision-notes.json` 병합.
- 폰트 패밀리 문자열 → `cc.FontType` 근사(capcut 프로젝트의 `recipe_pipeline.style_utils.resolve_font` import, 안 되면 vendored 사본). `font_family`(raw)·`font`(resolved)·`font_confidence` 모두 저장.
- 비전 비율 → 파이프라인 단위 변환(크기 비율 → `caption_size` ~4~30, 위치 비율 → top/center/bottom + `transform_y`, 외곽선 상대두께 → 0~100).
- `style-profile.json` 방출 (`schemas/style-profile.schema.md` 준수, provenance + 필드별 confidence).

## Step 8 — capcut 프로젝트에 설치

- `style-profile.json` → `<capcut-project>/style-profiles/<channel-slug>.json` 복사 (build_profile.py `--capcut-project`로 자동 or 수동).
- 사용자에게:
  ```
  cd <capcut-project>
  .venv/bin/python -m recipe_pipeline.cli \
    --video 내영상.mp4 --end-image 엔딩.jpg --draft-name test \
    --style-profile style-profiles/<channel-slug>.json
  ```
- **TIER A**(자동 적용)와 **TIER B**(advisory — 색보정 등은 CapCut에서 수동)를 구분해 안내.

## Step 9 (선택) — 한글 폰트 심기

`build_profile.py` 는 한글 서체를 만나면 `caption.font = "__capcut_default__"` + `font_note`(관찰 서체)만 남긴다. 정확한 폰트를 원하면:
1. 관찰한 서체(`font_note`)를 사용자에게 알려준다.
2. 사용자: CapCut 새 프로젝트 → 텍스트에 그 폰트 지정(자막/오버레이 다르면 2개) → 저장.
3. `python3 scripts/capture_font.py "<draft 폴더>" --profile style-profiles/<채널>.json`
   → draft 에서 폰트 블록 추출 → 프로필 `applied.caption.font_capcut` 에 심음.
4. 이후 그 프로필로 만든 draft 는 실제 폰트로 렌더된다.

## 정확도 한계 / 리스크

- **폰트 추정은 추측이다.** 프레임에서 폰트 패밀리를 정확히 맞히기 어렵다. 한글 서체는 파이프라인이 직접 지정 못 하므로 `font: "__capcut_default__"` + `font_note` 로 남기고, 정확 재현은 Step 9(capture_font.py). raw `font_family`는 항상 보존된다.
- **컷이 자막에 묶인다.** 파이프라인이 자막 cue 를 골라 타임라인을 만들어서, 원본처럼 "내용/샷 기준 컷 + 자막은 독립"은 불가. `gap_threshold_sec`(샷 길이에서 유도)를 키워 덜 잘게 쪼갤 뿐. 프로필 `provenance.limitations` 참고.
- **효과음 음원·배치는 사용자가 정한다.** 분석기는 "컷에 붙는지 / 얼마나 자주 / 몇 종류" 힌트만 뽑고, 믹스된 오디오에서 whoosh/딩 음원을 분리하진 못한다. **Step 6.5 에서 반드시 물어보고** `--sfx-map` 으로 "어떤 파일 → 어디에" 를 받는다. 순환 배치는 map 안에서 같은 trigger 끼리만.
- **애니메이션 감지는 근사.** 후킹 구간을 조밀 샘플링해도 프레임 사이에서 일어나는 애니메이션은 놓칠 수 있다.
- **색보정은 재현 불가.** capcut 파이프라인에 색보정 단계가 없다. `advisory.color_grade`는 참고용 — CapCut에서 조정 레이어/LUT로 직접.
- **혼합 포맷 채널.** Shorts와 장편이 섞이면 프로필이 흐려진다. Step 1에서 한 포맷으로 고정.
- **yt-dlp가 YouTube 변경에 취약.** 실패하면 `yt-dlp -U`로 업데이트. 2~3회 실패하면 중단하고 사용자에게 알린다.

## 파일 구조

```
video-editing-style-analyzer/
├── SKILL.md                        # 이 파일
├── references/
│   ├── analysis-methodology.md     # Step 4 비전 체크리스트 + 지표 정의
│   ├── capcut-integration.md       # 프로필 필드 → PipelineConfig → pycapcut API 매핑
│   └── ytdlp-and-cost.md           # ToS·승인 게이트·대역폭·포맷 선택
├── scripts/
│   ├── requirements.txt
│   ├── select_samples.py
│   ├── download_samples.py
│   ├── extract_frames.py
│   ├── analyze_audio.py
│   ├── transcript_timing.py
│   ├── build_profile.py
│   └── capture_font.py             # (선택) CapCut draft → 한글 폰트 블록 추출·심기
├── schemas/
│   └── style-profile.schema.md
└── example-output/                 # 검증 실행 산출물 (공개 배포 시 frames/ 제거)
```

## 버전 히스토리

- **v1.1.0**: 실제 채널(@살림똑소리) 검증하며 수정 — 다운로드 720p 상향(세로 숏폼 height 필터), yt-dlp `--ffmpeg-location` 심링크, `--sub-langs ko.*`(en 429 회피), `gap_threshold_sec`를 자막 간격이 아닌 **샷 길이**에서 유도(컷 난사 완화), 한글 서체는 `__capcut_default__` + `font_note` 로 두고 `capture_font.py`로 실제 폰트 블록 심기(`caption.font_capcut` → capcut `style_utils.RawFont`), `provenance.limitations` 추가.
- **v1.0.0**: 최초. 채널/영상 URL → yt-dlp 저해상도 샘플 5개 → ffmpeg 씬컷·프레임 샘플링 + Claude 비전 + 오디오/자막 타이밍 분석 → 2티어(TIER A machine-applied / TIER B advisory) style-profile.json. `capcut-highlight-video-editor` v1.2.0의 `--style-profile` 로더와 짝을 이룬다.
