# style-profile.json 스키마 (v1.0)

`build_profile.py`가 방출하고 `capcut-highlight-video-editor` v1.2.0의
`PipelineConfig.from_style_profile()`가 소비한다.

최상위 키: `schema_version`, `provenance`, `applied`(TIER A), `advisory`(TIER B).

`from_style_profile()`는 모든 필드를 `.get(...)` 방어적으로 읽으므로 **부분 프로필도 유효**하다.
없는 필드는 파이프라인 기본값(= 기존 하드코딩값)을 쓴다.

---

## `schema_version`
`"1.0"` 문자열.

## `provenance` (파이프라인 로직엔 영향 없음, 추적용)

| 필드 | 타입 | 설명 |
|---|---|---|
| `source_type` | `"channel"` \| `"video"` | 입력이 채널인지 단일 영상인지 |
| `source_url` | str | 원본 URL |
| `channel_name` | str | 채널 표시명 |
| `format` | `"shorts"` \| `"long"` | 분석한 포맷 |
| `videos_analyzed` | array | `{id, url, title, views, upload_date, duration_sec, width, height, fps, is_short}` |
| `analyzed_at` | ISO8601 str | 분석 시각 |
| `analyzer_version` | str | 이 스킬 버전 |
| `tool_versions` | obj | `{yt_dlp, ffmpeg}` |
| `notes` | str | 신뢰도 관련 메모 (예: "단일 영상 소스 → 컷 호흡 신뢰도 낮음") |
| `field_confidence` | obj | 필드경로 → 0.0~1.0. 낮은 값은 사용자 확인 필요 |

---

## `applied` — TIER A (파이프라인이 자동 적용)

각 필드 옆에 매핑되는 `PipelineConfig` 필드 / 측정 방법.

### `applied.canvas`
| 필드 | 타입 | 범위 | → PipelineConfig | 측정 |
|---|---|---|---|---|
| `width` | int | | `canvas_width` | pymediainfo 최빈값 |
| `height` | int | | `canvas_height` | 〃 |
| `fps` | int | 24~60 | `canvas_fps` | 〃 |

### `applied.target_duration_sec`
float, 10~180 → `target_duration_sec`. 채널 숏폼 길이 중앙값.

### `applied.pacing`
| 필드 | 타입 | 범위 | → PipelineConfig | 측정 (transcript_timing.py) |
|---|---|---|---|---|
| `pause_gap_sec` | float | 0.2~1.5 | `pause_gap_sec` | clamp(자막간격 중앙값, 0.3, 0.8) |
| `max_cue_sec` | float | 2~10 | `max_cue_sec` | clamp(자막길이 p90, 3.0, 8.0) |
| `gap_threshold_sec` | float | 0.1~3 | `gap_threshold_sec` | clamp(자막간격 중앙값 × 1.2, 0.3, 1.0) |

### `applied.caption`
| 필드 | 타입 | → PipelineConfig | 측정 (vision-notes) |
|---|---|---|---|
| `font_family` | str | (raw, 미사용) | 비전 폰트 추정 원문 |
| `font` | str | `caption_font` | `resolve_font(font_family)` 결과. `"__capcut_default__"` = 재현 불가 서체 → CapCut 기본 폰트로 렌더 |
| `font_capcut` | obj `{resource_id, name}` | `caption_font_capcut` | (선택) CapCut draft 에서 `capture_font.py` 로 뽑은 실제 폰트 블록. 있으면 `font` 보다 우선 — 한글 등 커스텀 폰트를 그대로 재현 |
| `font_note` | str | — | `font` 가 `__capcut_default__` 일 때 관찰한 서체 설명 (사용자가 CapCut 에서 고를 때 참고) |
| `font_confidence` | float | (provenance) | 비전 confidence |
| `size` | float 4~30 | `caption_size` | 글자높이/프레임높이 비율 → 스케일 |
| `color` | `#RRGGBB` | `caption_color` | 채움색 |
| `position` | top\|center\|bottom | `caption_position` | 세로 위치 |
| `transform_y` | float -1~1 | (참고, position이 우선) | 정확한 세로 비율 |
| `align` | 0\|1\|2 | `caption_align` | 정렬 |
| `bold` | bool | `caption_bold` | 굵기 |
| `all_caps` | bool | `caption_all_caps` | 전부 대문자인지 |
| `outline` | obj | ↓ | |
| `outline.enabled` | bool | (외곽선 적용 여부) | |
| `outline.color` | `#RRGGBB` | `caption_outline_color` | |
| `outline.width` | float 0~100 | `caption_outline_width` | 상대 두께 → 0~100 |
| `outline.alpha` | float 0~1 | `caption_outline_alpha` | |
| `shadow` | obj | ↓ (실험적) | |
| `shadow.enabled` | bool | `caption_shadow` | |
| `shadow.color` | `#RRGGBB` | `caption_shadow_color` | |
| `shadow.alpha` | float | `caption_shadow_alpha` | |
| `shadow.angle` | float deg | `caption_shadow_angle` | 그림자 방향 |
| `shadow.distance` | float | `caption_shadow_distance` | |
| `background` | obj | ↓ | |
| `background.enabled` | bool | `caption_bg` | |
| `background.color` | `#RRGGBB` | `caption_bg_color` | |
| `background.alpha` | float 0~1 | `caption_bg_alpha` | |
| `background.round_radius` | float 0~1 | `caption_bg_radius` | |
| `animation` | obj | ↓ | |
| `animation.in` | none\|fade\|pop\|slide-up\|typewriter\|zoom\|karaoke | `caption_anim_in` | 후킹 프레임 비교 |
| `animation.out` | none\|fade\|scale-down\|slide-down | `caption_anim_out` | |
| `animation.duration_sec` | float | `caption_anim_duration_sec` | |

### `applied.caption_emphasis`
| 필드 | 타입 | → PipelineConfig |
|---|---|---|
| `trigger` | keyword\|all\|none | `caption_zoom_trigger` |
| `scale` | float 1~1.5 | `caption_zoom_scale` |
| `duration_sec` | float | `caption_zoom_duration_sec` |

### `applied.overlay`
`caption`의 서브셋. 필드: `font_family`, `font`, `size`, `color`, `position`, `bold`,
`all_caps`, `outline{enabled,color,width}`, `background{enabled,color,alpha}`,
`animation{in,out,duration_sec}`.
→ `overlay_font`, `overlay_size`, `overlay_color`, `overlay_position`, `overlay_bold`,
`overlay_all_caps`, `overlay_outline_color/width`, `overlay_bg/overlay_bg_color/overlay_bg_alpha`,
`overlay_anim_in/out/duration_sec`. (오버레이엔 줌·그림자 없음)

### `applied.sfx`
| 필드 | 타입 | → PipelineConfig | 측정 (analyze_audio.py) |
|---|---|---|---|
| `volume` | float 0~1 | `sfx_volume` | 버스트 레벨 vs 대사 레벨 |
| `duration_sec` | float | `sfx_duration_sec` | 버스트 중앙 길이 (0.15~0.5 클램프) |
| `trigger` | keywords\|cuts\|both\|caption_in | `sfx_trigger` | (힌트) SFX 버스트가 컷 타임스탬프(±0.35s)와 얼마나 겹치는지 — 절반↑=cuts, 15%↑=both, 거의없음=keywords |
| `variety` | single\|varied | (힌트) | 버스트 스펙트럴 센트로이드 변동계수 ≥0.25 → varied |
| `per_minute` | float | (힌트) | 분당 버스트 수 (TTS 채널이면 노이즈 큼) |
| `map` | array | `sfx_map` | **실제 배치** — `[{"file": "whoosh.wav", "trigger": "cuts"}, ...]`. 스킬이 Step 6.5 에서 사용자에게 물어 채운다 (음원을 오디오에서 분리 못 하므로). `map` 이 있으면 `trigger`/`variety` 힌트 무시. `trigger` 종류: cuts / keywords(.md 필요) / caption_in(모든 자막) / end. 같은 trigger 에 file 여러 개면 그 안에서만 순환. `file` 은 `--sfx-dir` 폴더 기준 상대명. |

`trigger: cuts` / `caption_in` / `end` 는 `.md` 없이도 동작. `keywords`/`both` 는 `.md` 필요.

---

## `advisory` — TIER B (파이프라인이 **읽지 않음**, 사람 편집자용)

capcut 파이프라인엔 이걸 적용할 단계가 없다. CapCut에서 수동으로 반영한다.

| 필드 | 설명 |
|---|---|
| `shot_pacing` | `{median_shot_sec, mean_shot_sec, cuts_per_minute, pct_shots_under_1_5s, pct_shots_under_0_5s}` |
| `color_grade` | `{contrast, saturation, temperature, black_level, look, vignette, confidence}` — **CapCut 조정 레이어/LUT로 직접** |
| `transitions` | `{hard_cut, whip_pan, zoom, flash}` 비율 (합 ≈ 1.0) |
| `hook_structure` | `{first_3s, pattern, confidence}` |
| `broll_ratio` | `{talking_head, broll}` |
| `bgm` | `{present, energy(calm\|driving), level_db_below_vo, ducking}` |
| `shot_scale_mix` | `{closeup, medium, wide}` |
| `text_density` | `low\|medium\|high` |
| `emoji_usage` | `none\|occasional\|frequent` |
| `censor_bleeps` | bool |

---

## 최소 예시

```json
{
  "schema_version": "1.0",
  "provenance": {
    "source_type": "channel",
    "source_url": "https://www.youtube.com/@example/shorts",
    "channel_name": "Example",
    "format": "shorts",
    "analyzed_at": "2026-08-27T09:00:00Z",
    "analyzer_version": "1.0.0"
  },
  "applied": {
    "canvas": {"width": 1080, "height": 1920, "fps": 30},
    "target_duration_sec": 42,
    "pacing": {"pause_gap_sec": 0.45, "max_cue_sec": 4.0, "gap_threshold_sec": 0.55},
    "caption": {
      "font_family": "Montserrat ExtraBold", "font": "Montserrat", "font_confidence": 0.5,
      "size": 12.5, "color": "#FFFFFF", "position": "center", "align": 1,
      "bold": true, "all_caps": true,
      "outline": {"enabled": true, "color": "#000000", "width": 26.0, "alpha": 1.0},
      "shadow": {"enabled": false},
      "background": {"enabled": false},
      "animation": {"in": "pop", "out": "none", "duration_sec": 0.2}
    },
    "caption_emphasis": {"trigger": "all", "scale": 1.16, "duration_sec": 0.2},
    "overlay": {
      "font_family": "Anton", "font": "Anton", "size": 8.0, "color": "#FFE14D",
      "position": "top", "bold": true, "all_caps": true,
      "outline": {"enabled": true, "color": "#000000", "width": 22.0},
      "background": {"enabled": false},
      "animation": {"in": "slide-up", "out": "none", "duration_sec": 0.2}
    },
    "sfx": {"volume": 0.82, "duration_sec": 0.25}
  },
  "advisory": {
    "shot_pacing": {"median_shot_sec": 1.3, "cuts_per_minute": 40, "pct_shots_under_1_5s": 0.64},
    "color_grade": {"contrast": "punchy", "saturation": "high", "temperature": "warm", "confidence": 0.4},
    "bgm": {"present": true, "energy": "driving", "level_db_below_vo": -16, "ducking": true}
  }
}
```
