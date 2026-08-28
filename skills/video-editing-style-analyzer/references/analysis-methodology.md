# 분석 방법론 — 지표 정의 + Step 4 비전 체크리스트

## 스크립트가 계산하는 것 (metrics.json)

### shots (extract_frames.py)
ffmpeg `select='gt(scene,0.30)',showinfo` 로 컷 경계의 `pts_time`를 뽑는다.
컷 간격 리스트에서:
- `median_shot_sec`, `mean_shot_sec`, `p10_shot_sec`, `p90_shot_sec`
- `cuts_per_minute` = 컷 수 / (영상 길이 / 60)
- `pct_shots_under_1_5s`, `pct_shots_under_0_5s`

임계값 0.30은 기본값. 컷이 과하게 잡히면(핸드헬드·플리커) 0.40으로, 적게 잡히면 0.22로.
정밀도가 중요하면 `pip install "scenedetect[opencv-headless]"` 후 ContentDetector로 교체 가능(스크립트에 옵션).

### container (extract_frames.py)
pymediainfo로 영상별 `width/height/fps/duration` → 여러 영상의 최빈값(mode).
숏폼이면 보통 1080×1920, 30 또는 60fps.

### audio (analyze_audio.py)
- wav 추출(`-vn -ac 1 -ar 16000`) → 20ms hop RMS → dB 엔벨로프
- **SFX 버스트**: RMS 상승 델타 > 임계(기본 +8dB), 지속 < 150ms, 스펙트럴 센트로이드 상승.
  Step 6의 발화 구간과 겹치는 건 제외(대사 자음 어택 오탐 방지).
  → `sfx_bursts_per_minute`, `sfx_burst_median_sec`, `sfx_level_vs_dialogue_db`
  → 제안 `sfx_volume` = clamp(0.5 + (level_vs_dialogue_db + 6) / 20, 0.4, 1.0) 정도의 휴리스틱
- **BGM**: 발화 공백 창(> 0.6s)의 잔여 에너지. 지속적으로 -40dBFS 이상이면 `present=true`.
  `energy`: 저역 비중 높고 변동 작으면 calm, 아니면 driving. `ducking`: 발화 시작 시 -3dB 이상 감쇠하면 true.

### timing (transcript_timing.py)
.srt(우선) 또는 whisper 결과에서:
- `words_per_caption` (공백/음절 기준, 중앙값)
- `caption_duration_sec` 중앙값·p90
- `chars_per_line`, `lines_per_caption`
- `inter_caption_gap_sec` 중앙값 (자막 사이 빈 시간)
→ pacing 매핑은 schema 문서 참고.

## Step 4 — 비전 체크리스트 (Claude가 프레임 Read하며 채움)

`vision-notes.json` 구조:
```json
{
  "caption": { "<field>": {"value": ..., "confidence": 0.0, "evidence": ["t_1200.jpg"]}, ... },
  "caption_animation": {...},
  "caption_emphasis": {...},
  "zoom": {...},
  "overlay": {...},
  "advisory": { "color_grade": {...}, "hook_structure": {...}, ... }
}
```

프레임 파일명 `t_<ms>.jpg` = 영상 내 밀리초. 같은 자막의 등장~퇴장을 보려면 인접 `t_` 프레임들을 비교.

### caption (자막 본문)
| 필드 | 어떻게 볼지 | value 형식 |
|---|---|---|
| `font_family` | 세리프 여부, 굵기, x-height, 모서리(둥근/각진), 특징적 글자(a/g/t) | 문자열 + `font_alternatives`: [str, str] |
| `bold` | 획 굵기가 굵은지 | bool |
| `all_caps` | 소문자가 하나도 없는지 (여러 자막에서 확인) | bool |
| `size_ratio` | 대문자 글자 높이 / 프레임 높이 | float (예: 0.06 = 프레임의 6%) |
| `color` | 채움색 | `#RRGGBB` |
| `outline` | 글자 테두리 대비 라인이 있는지, 색, 글자획 대비 두께 비율 | `{enabled, color, width_ratio(0~1)}` |
| `shadow` | 한쪽으로 번진 그림자, 방향(시계각), 흐림 | `{enabled, angle_deg, softness}` |
| `background` | 글자 뒤 색 박스, 색, 불투명도, 모서리 라운드, 화면 폭 꽉 채우는지 | `{enabled, color, alpha, round, full_width}` |
| `position` | 세로 위치 대략 | `top`\|`center`\|`bottom` |
| `position_ratio` | 자막 중심 y / 프레임 높이 (0=위, 1=아래) | float |
| `align` | 좌/중앙/우 | 0\|1\|2 |
| `lines` | 보통 몇 줄인지 | int |

### caption_animation
후킹(0~12s) 조밀 프레임에서 한 자막의 첫 등장 전후 3~5프레임 비교:
- `in`: `none` / `fade`(투명도) / `pop`(작았다 커짐/바운스) / `slide-up`(아래→위 이동) / `typewriter`(글자 순차) / `karaoke`(단어별 색 채워짐)
- `out`: `none` / `fade` / `scale-down` / `slide-down`
- `duration_sec`: 전환에 걸리는 대략 시간 (프레임 간격 × 프레임 수)

### caption_emphasis
강조 단어(키워드)가 나머지와 다르게 보이는지:
- `trigger`: `keyword`(일부 단어만 다름) / `all`(모든 자막이 같은 강조 스타일) / `none`
- 다르면 어떻게: 색/박스/크게/줌

### zoom (줌 펀치인)
말하는 사람이 고정된 샷에서 프레이밍이 갑자기/스르륵 확대되는지:
- `present`: bool
- `scale`: 확대 배율 추정 (~1.05~1.20)
- `style`: `snap`(한 프레임에 툭) / `ease`(몇 프레임에 걸쳐)
- → caption_emphasis.scale 로도 반영 가능 (파이프라인은 자막 줌만 지원)

### overlay
자막(본문 자막)과 다른 텍스트 — 타이틀 카드, 화면 상단 라벨, 재료/단계 표시 등. caption과 같은 필드.

### advisory (참고용, 파이프라인 미적용)
- `color_grade`: `contrast`(flat/natural/punchy), `saturation`(muted/natural/high), `temperature`(cool/neutral/warm), `black_level`(lifted/natural/crushed), `look`(자유서술: "teal-orange", "필름 그레인" 등), `vignette`(bool)
- `hook_structure`: 첫 3초에 무엇이 보이는지 한 줄 (예: "얼굴 클로즈업 + 화면 꽉 채우는 중앙 자막 질문")
- `shot_scale_mix`: closeup/medium/wide 대략 비율
- `broll_ratio`: talking_head vs broll
- `text_density`: low/medium/high (화면에 텍스트가 얼마나 상주하는지)
- `emoji_usage`: none/occasional/frequent
- `censor_bleeps`: 삐 소리나 모자이크가 보이는지

## confidence 가이드

- 0.8~1.0: 여러 프레임에서 명확 (색, 위치, all_caps)
- 0.5~0.7: 보이지만 정밀도 낮음 (size_ratio, outline width, 애니메이션 종류)
- 0.2~0.4: 추측 (font_family, color_grade)
- < 0.2: 안 씀 — 필드 생략하고 파이프라인 기본값에 맡김
