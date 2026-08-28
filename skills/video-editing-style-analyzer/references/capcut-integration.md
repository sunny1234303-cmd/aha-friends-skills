# capcut-highlight-video-editor 연동

이 스킬이 만드는 `style-profile.json`은 `capcut-highlight-video-editor` **v1.2.0 이상**의
`--style-profile` 옵션이 소비한다.

## 어떻게 연결되나

```
style-profile.json  ──(--style-profile)──▶  PipelineConfig.from_style_profile()
                                                     │
                                            recipe_pipeline/config.py
                                                     │
        ┌────────────────────────────────────────────┼────────────────────────────┐
        ▼                        ▼                    ▼                            ▼
  stage_transcribe          stage_caption_style   stage_overlay              stage_sfx
  pause_gap_sec             font/size/color/pos   font/size/color/pos       volume
  max_cue_sec               bold/align/all_caps   bold/all_caps
                            outline (TextBorder)  outline (TextBorder)
                            shadow (_ShadowTextSegment, 실험적)
                            background (TextBackground)
                            anim_in/out (TextIntro/TextOutro)
                            zoom keyframe (uniform_scale)
```

## 필드 → PipelineConfig → pycapcut API

| 프로필 경로 | PipelineConfig | pycapcut |
|---|---|---|
| `applied.canvas.{width,height,fps}` | `canvas_width/height/fps` | `DraftFolder.create_draft(w, h, fps=)` |
| `applied.target_duration_sec` | `target_duration_sec` | `stage_highlight.select_highlight_cues` |
| `applied.pacing.pause_gap_sec` | `pause_gap_sec` | `stage_transcribe._regroup_words_into_cues` |
| `applied.pacing.max_cue_sec` | `max_cue_sec` | 〃 |
| `applied.pacing.gap_threshold_sec` | `gap_threshold_sec` | `stage_gaps.merge_cues_into_blocks` |
| `applied.caption.font` | `caption_font` | `style_utils.resolve_font` → `cc.FontType` |
| `applied.caption.size` | `caption_size` | `cc.TextStyle(size=)` |
| `applied.caption.color` | `caption_color` | `cc.TextStyle(color=)` (hex→rgb01) |
| `applied.caption.position` | `caption_position` | `ClipSettings(transform_y=)` (top .75 / center 0 / bottom -.75) |
| `applied.caption.align` | `caption_align` | `cc.TextStyle(align=)` 0/1/2 |
| `applied.caption.bold` | `caption_bold` | `cc.TextStyle(bold=)` |
| `applied.caption.all_caps` | `caption_all_caps` | `text.upper()` (한글 무해) |
| `applied.caption.outline.{color,width,alpha}` | `caption_outline_*` | `cc.TextBorder(color, width, alpha)` — width 0~100, 내부 `/100*0.2` 매핑(부정확할 수 있음) |
| `applied.caption.shadow.*` | `caption_shadow*` | `_ShadowTextSegment.export_material` 주입, `check_flag |= 32` — **실험적** |
| `applied.caption.background.*` | `caption_bg*` | `cc.TextBackground(color, alpha, round_radius)` |
| `applied.caption.animation.in` | `caption_anim_in` | `style_utils.resolve_text_intro` → `cc.TextIntro` |
| `applied.caption.animation.out` | `caption_anim_out` | `resolve_text_outro` → `cc.TextOutro` |
| `applied.caption_emphasis.{trigger,scale,duration_sec}` | `caption_zoom_*` | `add_keyframe(uniform_scale, 0→1.0, dur→scale)` |
| `applied.overlay.*` | `overlay_*` | `stage_overlay.add_overlay_segments` (줌·그림자 없음) |
| `applied.sfx.volume` | `sfx_volume` | `cc.AudioSegment(volume=)` |
| `applied.sfx.duration_sec` | `sfx_duration_sec` | `cc.AudioSegment` timerange |

## 폰트 리졸브

`build_profile.py`는 capcut 프로젝트가 import 가능하면:
```python
from recipe_pipeline.style_utils import resolve_font
font_obj, used_name = resolve_font(font_family, return_meta=True)
```
불가하면 vendored 사본(`scripts/_font_resolve.py`)의 동일 로직 사용.

`resolve_font` 순서: 정확 일치 → alias 표(`montserrat→Montserrat`, `impact/oswald→Anton`,
`bebas→BebasNeue`, `roboto/arial/helvetica/noto sans/pretendard→Arimo_Regular` …)
→ `difflib` 근사(cutoff 0.6) → `Arimo_Regular` 폴백.

`font_confidence`가 낮으면(비전 0.5 미만) 프로필에 그대로 두되, 사용자에게
"CapCut에서 열어 폰트 확인, 아니면 `CAPTION_FONTS`에서 직접 선택" 안내.

### 한글 등 재현 불가 서체 → `font_capcut` 로 심기

pycapcut FontType 은 라틴 348종뿐이라 한글 서체(배민 도현체, 여기어때 잘난체 등)를 지정 못 한다.
`build_profile.py` 는 이런 경우 `caption.font = "__capcut_default__"` 로 두고 `font_note` 에
관찰한 서체를 적는다 → 파이프라인이 폰트 미지정 → CapCut 기본 폰트로 렌더.

정확히 재현하려면 (1회 수동):
1. CapCut 에서 새 프로젝트 → 텍스트 추가 → 원하는 한글 폰트 지정 (CapCut 폰트 패널에 한글 폰트 내장).
   자막용·오버레이용 다르면 텍스트 2개, 첫째=자막 둘째=오버레이. 저장.
2. `python3 scripts/capture_font.py "<draft 폴더>" --profile style-profiles/<채널>.json`
   → draft 에서 `{resource_id, name}` 추출 → 프로필의 `applied.caption.font_capcut` 에 심음.
3. 이후 그 프로필로 만든 draft 는 `style_utils.RawFont` 로 그 폰트 블록을 주입 → 실제 폰트로 렌더.

`font_capcut` 이 있으면 `resolve_font` 대신 `raw_font()` 결과가 쓰인다 (pipeline.py).

## 제네릭 애니메이션 이름 → CapCut enum

| 제네릭 | TextIntro 멤버 | | 제네릭 | TextOutro 멤버 |
|---|---|---|---|---|
| fade | 渐显 | | fade | 渐隐 |
| pop | 向上弹入 | | scale-down | 缩小 |
| slide-up | 向上滑动 | | slide-down | 向下滑动 |
| typewriter | 打字机 | | | |
| zoom | 放大 | | | |
| karaoke | 卡拉OK | | | |

enum 멤버 이름은 pycapcut 버전마다 바뀔 수 있어, capcut 쪽 `resolve_text_intro/outro`가
KeyError면 조용히 `None`(애니메이션 없음)으로 폴백한다.

## 회귀 안전성

모든 신규 `PipelineConfig` 필드는 **기존 하드코딩값을 기본값**으로 한다.
`--style-profile` 없이, 또는 프로필에 특정 필드가 없으면 동작은 v1.1.0과 동일하다.
