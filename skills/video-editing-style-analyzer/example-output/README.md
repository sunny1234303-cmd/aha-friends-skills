# example-output/

## salim-ddoksori-20260827/

`@살림똑소리` 채널 Shorts 5개를 실제로 분석한 산출물 (2026-08-27).

| 파일 | 만든 주체 | 내용 |
|---|---|---|
| `samples.json` | `select_samples.py` | 선정된 영상 5개 (조회수 상위 + 최신) |
| `metrics.json` | `extract_frames.py` + `analyze_audio.py` + `transcript_timing.py` | 씬컷·샷길이(컷/분 22, 중앙 샷 2.0s)·컨테이너·오디오(BGM 있음, SFX 버스트)·자막타이밍(컷 호흡 0.3s 플로어 — TTS라 자막 간격 거의 0) |
| `vision-notes.json` | Claude (Step 4) | 프레임 관찰: 러닝 캡션 = 검정 두꺼운 라운드 고딕 + 두꺼운 흰 외곽선, 중앙, 강조는 별도 핑크 손글씨 레이어, 훅카드는 컬러 3줄 + 스피드라인, 얼굴 없음(손+제품 탑다운) |
| `style-profile.json` | `build_profile.py` | 최종 프로필 — capcut `--style-profile style-profiles/salim-ddoksori.json` 로 소비 |

**공개 배포 시 주의:** `frames/<video_id>/*.jpg` 와 원본 mp4 는 저작권 때문에 넣지 않는다
(`metrics.json` 의 `frame_index` 는 어떤 프레임을 샘플링했는지 기록만 남긴 것). 위 4개 JSON 은 수치·관찰만 담겨 배포 가능.

**검증 상태:** 이 프로필로 capcut 파이프라인 e2e 실행 확인(자막 외곽선·pop 애니메이션·오버레이 slide-up·캔버스 1080x1920·컷 호흡 draft JSON 반영). **CapCut 앱에서 실제 draft 육안 확인은 사용자 몫** — 외곽선 두께(28), 폰트 렌더링(한글이라 Arimo 폴백 → CapCut 기본 한글 폰트), pop 애니메이션 느낌.
