---
name: capcut-highlight-video-editor
description: |
  원본 영상 1개 + 엔딩 이미지만 넣으면, 로컬 Whisper로 자막 생성 → 무자막 구간 컷 → 목표 길이(기본 60초)까지 하이라이트 선별 → 자막 스타일링/확대 → 엔딩 이미지까지 자동 처리해서 CapCut(macOS)에서 바로 열어 검토·수정할 수 있는 draft를 만드는 pycapcut 기반 자동화 시스템을 처음부터 구축하는 스킬. 요리 영상 전용이 아니라 튜토리얼·리뷰·브이로그 등 어떤 숏폼 영상에도 그대로 쓸 수 있다. 텍스트 노트(.md)를 함께 주면 그 안의 키워드(레시피의 재료, 튜토리얼의 단계, 리뷰의 제품명 등 무엇이든) 등장 구간을 자동 감지해 그 구간 중심으로 하이라이트를 고르고, 텍스트 오버레이와 효과음도 자동으로 붙여준다 — 이 기능은 완전히 선택 사항. CLI와 파일 드래그드롭 지원 로컬 웹 대시보드(FastAPI) 둘 다 만든다. 검증된 코드 템플릿(`templates/`)과 macOS CapCut 연동 과정에서 실제로 겪은 함정·해결책이 전부 포함되어 있어, 처음부터 다시 디버깅하지 않고 바로 동작하는 시스템을 만들 수 있다.

  Triggers:
  - "CapCut 영상 자동 편집 시스템 만들어줘"
  - "숏폼 하이라이트 영상 자동 편집 자동화"
  - "pycapcut으로 하이라이트 영상 만드는 거 구축해줘"
  - "영상 자동 편집 파이프라인"

  Use when: 사용자가 숏폼 영상(요리, 튜토리얼, 리뷰, 브이로그 등 무엇이든)을 pycapcut+Whisper 기반으로 자동 편집하는 시스템을 처음 구축하려고 할 때. 이미 이 스킬로 만든 시스템이 있다면 이 스킬을 다시 쓰지 말고 기존 프로젝트를 직접 수정한다.
allowed-tools: Read, Write, Edit, Bash, AskUserQuestion
---

# capcut-highlight-video-editor 스킬

## 왜 이 스킬이 필요한가

pycapcut(비공식 CapCut 자동화 라이브러리)으로 macOS CapCut과 연동하는 시스템을 처음 만들면, 라이브러리 문서만 보고는 절대 예상 못 하는 macOS 전용 문제를 최소 3개는 반드시 만난다 — draft가 CapCut 목록엔 뜨는데 열면 타임라인이 텅 비어있거나, 미디어를 못 찾는다는 오류가 뜨거나, 클릭해도 아무 반응이 없거나. 전부 실제로 겪고 원인을 찾아 고친 것들이고, 아래 "실전에서 발견한 함정" 섹션에 전부 정리되어 있다. 이 스킬은 그 디버깅을 처음부터 반복하지 않도록, **검증된 코드 템플릿을 그대로 복사해서 시작**하는 방식을 취한다.

## 이 스킬이 만드는 것 — 요리 영상 전용이 아니다

핵심 파이프라인(자막 생성 → 무자막 컷 → 하이라이트 선별 → 자막 스타일링 → 엔딩 이미지 → CapCut draft 저장)은 영상 장르와 무관하게 동작한다. 텍스트 노트(.md) 없이 영상+엔딩이미지만 넣어도 끝까지 완성된다 — 이 경우 하이라이트는 앞에서부터 순서대로 목표 길이까지 채워진다.

텍스트 노트(.md)를 추가로 주면, 그 안의 불릿 목록이나 마크다운 표에서 **키워드**를 자동 추출해 자막에서 그 키워드가 등장하는 구간을 우선적으로 하이라이트에 포함시키고, 그 구간에 텍스트 오버레이와 효과음을 자동으로 붙인다. 이 "키워드"가 무엇인지는 콘텐츠 장르에 따라 완전히 다르게 쓰일 수 있다 — 요리 영상이면 재료, 튜토리얼이면 단계, 제품 리뷰면 제품명, 여행 브이로그면 장소명. `md_parsing.py`는 특정 도메인 단어에 종속되지 않고, 문서에서 "재료/키워드/항목/체크리스트/단계/포인트/리스트" 같은 흔한 리스트 섹션 제목을 찾거나(없으면 문서에서 처음 발견되는 불릿 목록·표를 그대로) 사용한다.

## 사전 확인 (필수, 순서대로)

1. **macOS인지 확인.** 이 스킬은 macOS CapCut 전용이다 (Windows CapCut은 파일명 규칙이 다름 — 아래 함정 섹션 참고). Windows라면 이 스킬을 그대로 쓰지 말고 사용자에게 알린다.
2. **CapCut 데스크톱 앱 설치 여부 확인.** `/Applications`에 CapCut.app이 있는지 확인. 없으면 사용자가 먼저 설치해야 한다.
3. **로컬 Whisper 사용에 대해 사용자에게 먼저 확인한다.** 자막 생성은 로컬 faster-whisper(오프라인, 무료)를 기본으로 쓴다 — 비용·보안 문제를 먼저 확인하는 게 이 워크스페이스의 표준 원칙이다. 클라우드 STT API로 바꾸고 싶다는 요청이 없는 한 로컬 Whisper를 기본값으로 진행한다.
4. **CapCut draft 폴더 경로를 이 기기에서 직접 확인한다.** 보통 `~/Movies/CapCut/User Data/Projects/com.lveditor.draft`이지만 기기마다 다를 수 있다 — CapCut 앱 설정에서 "草稿位置"/Draft location을 확인하거나, `find ~/Movies/CapCut -iname "*draft*"`로 찾는다.
5. **사용자의 실제 콘텐츠 장르를 확인한다.** 요리 영상이 아니어도 전혀 문제없다 — 텍스트 노트를 쓸 계획이라면 그 안의 키워드가 무엇을 의미하는지(재료/단계/제품명 등)만 파악해두면, 코드 수정 없이 그대로 적용된다.

## 빌드 순서

### 1단계 — 프로젝트 뼈대 생성

새 프로젝트 폴더(사용자 워크스페이스의 Johnny Decimal 규칙 등 기존 컨벤션이 있으면 그걸 따른다)에 이 스킬의 `templates/recipe_pipeline/`과 `templates/webapp/`, `templates/requirements.txt`를 그대로 복사한다. (내부 패키지명은 `recipe_pipeline`으로 남아있지만 로직 자체는 범용이다 — 원하면 프로젝트 복사 후 패키지명을 바꿔도 되고, 그대로 써도 무방하다.)

```bash
mkdir -p <새프로젝트경로>
cp -r templates/recipe_pipeline templates/webapp templates/requirements.txt <새프로젝트경로>/
cd <새프로젝트경로>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`.gitignore`도 새로 만든다 (`.venv/`, `__pycache__/`, `*.pyc`, 그리고 파이프라인이 만드는 `sample_data/.pipeline_out/` 같은 산출물 폴더가 있다면 함께).

### 2단계 — 설치 검증 스파이크 (절대 생략하지 말 것)

바로 전체 파이프라인을 돌리지 말고, pycapcut이 이 기기에서 실제로 CapCut과 정상 연동되는지부터 최소 단위로 검증한다:

1. `python3 -c "import pycapcut as cc; print('ok')"` — 설치·임포트 확인. 실패하면 Python 버전을 낮춰본다 (3.11/3.12 venv로 재시도).
2. 아무 짧은 mp4 파일(합성 테스트 영상도 됨, ffmpeg 없으면 `pip install imageio-ffmpeg`로 정적 바이너리 확보 가능)로 최소 draft(영상 세그먼트 1개 + 텍스트 1개)를 만들어보고, `cc.DraftFolder(경로).create_draft(...)` → `script.save()`까지 실행.
3. **`draft_content.json`을 같은 폴더에 `draft_info.json`으로 복사한다** (아래 함정 #1 — 이거 없으면 다음 단계에서 반드시 막힌다). `templates/recipe_pipeline/stage_save.py`가 이미 이 처리를 포함하고 있으니 그대로 쓰면 됨.
4. CapCut 앱을 재시작하고 draft 목록에서 방금 만든 항목을 열어 사용자에게 직접 확인받는다 — 영상/텍스트가 보이는지, 클립을 지워도 draft가 안 깨지는지. **이 확인은 Claude가 대신 할 수 없다** (CapCut은 네이티브 앱이라 브라우저 자동화가 안 통한다) — 반드시 사용자에게 물어본다.

이 단계가 통과하지 않으면 3단계로 넘어가지 않는다.

### 3단계 — 코어 파이프라인 CLI로 끝까지 검증

`templates/recipe_pipeline/`은 이미 완성된 10단계 파이프라인이다 (아래 "파이프라인 단계" 참고). 사용자의 실제 영상 1개 + 엔딩 이미지로 CLI를 끝까지 돌려본다 (텍스트 노트는 선택):

```bash
python3 -m recipe_pipeline.cli \
  --video 영상.mp4 --end-image 엔딩.jpg --draft-name test-1
# 키워드 기반 하이라이트/오버레이/효과음까지 쓰려면:
python3 -m recipe_pipeline.cli \
  --video 영상.mp4 --content-md 노트.md --end-image 엔딩.jpg --draft-name test-1
```

중간 산출물(SRT, `pipeline_log.json`)을 확인하고, CapCut에서 결과 draft를 열어 무자막 컷·하이라이트 선별·자막 스타일·엔딩 이미지(그리고 .md를 줬다면 오버레이·효과음)가 전부 반영됐는지 사용자에게 확인받는다.

### 4단계 — 웹 대시보드 연결

`templates/webapp/`은 파이프라인을 그대로 감싸는 FastAPI 대시보드다 (새 비즈니스 로직 없음, 그대로 씀):

```bash
pip install python-multipart  # requirements.txt에 이미 있음
uvicorn webapp.main:app --reload
```

`http://127.0.0.1:8000`에서 파일 드래그드롭 → 실시간 진행상황 → 완료 요약까지 확인한다. 텍스트 노트 드롭존은 선택 사항으로 표시되어 있다.

## 파이프라인 단계 (원래 사용자 요청 순서, 실제 실행 순서와 다름)

사용자가 이 시스템을 요청할 때 보통 아래 순서로 설명하지만, **4단계(하이라이트 선별)는 5단계(키워드 등장 구간 분석) 결과가 있어야 계산 가능**하므로 실제 코드 실행 순서는 1→2→3→[5]→4→6→7→8→9→10이다. `pipeline.py`의 `STAGE_LABELS`와 로그에 이 재배열이 이미 명시되어 있다. 텍스트 노트(.md)가 없으면 5·6·8단계는 자동으로 빈 결과(0개)로 스킵된다.

1. 영상 삽입
2. 자막 스크립트 생성 (로컬 Whisper)
3. 무자막 구간 컷 편집
4. 목표 길이까지 하이라이트 선별 (텍스트 노트가 있으면 키워드 등장 구간 중심, 없으면 순서대로)
5. (선택) 자막 기반 키워드 등장 구간 분석
6. (선택) 텍스트 노트 내용을 오버레이로 추가
7. 자막 글꼴/크기/위치/확대
8. (선택) 키워드 등장 시점마다 자동 효과음
9. 종료 2~3초 전 엔딩 이미지 삽입
10. 클립 삭제 가능한 편집 가능 상태로 저장 (렌더링 아님)

## 스타일 프로필로 특정 채널 룩 따라가기

`video-editing-style-analyzer` 스킬이 유튜브 채널/영상 URL을 분석해 만든 `style-profile.json`을 이 파이프라인에 넣으면, 자동 편집 draft의 자막·컷 호흡·효과음이 그 채널 스타일을 따라간다.

```bash
python3 -m recipe_pipeline.cli \
  --video 영상.mp4 --end-image 엔딩.jpg --draft-name test-1 \
  --style-profile style-profiles/채널이름.json
```

- 프로필 위치: 프로젝트 루트의 `style-profiles/` 폴더 (analyzer가 여기에 씀, CLI·웹앱이 여기서 읽음, `RECIPE_STYLE_PROFILES_DIR` env로 변경 가능).
- 프로필을 준 뒤에도 개별 CLI 플래그(`--caption-size` 등)를 명시하면 그 항목만 프로필 위에 덮어쓴다.
- 웹 대시보드에서는 고급 설정 맨 위 "스타일 프로필" 블록에서 저장된 프로필을 고르거나 업로드하면 나머지 스타일 입력이 자동으로 채워진다.
- **TIER A (자동 적용됨)**: 캔버스/타깃 길이, 컷 호흡(`pause_gap_sec`/`max_cue_sec`/`gap_threshold_sec`), 자막 폰트·크기·색·위치·정렬·굵기·대문자화·외곽선·그림자·배경박스·인/아웃 애니메이션·키워드 줌, 오버레이 동일 항목, 효과음 볼륨.
- **TIER B (advisory — 자동 적용 안 됨)**: 색보정(대비/채도/색온도), 전환 종류, 후킹 구조, BGM. 색보정은 CapCut에서 조정 레이어/LUT로 직접 얹어야 한다. 프로필의 `advisory` 블록에 측정값이 들어있으니 참고용으로 쓴다.
- **효과음 배치**: `sfx_map`으로 효과음 파일별 위치를 정한다 — `[{"file":"whoosh.wav","trigger":"cuts"},{"file":"ding.wav","trigger":"keywords"}]`. 순환이 아니라 "이 소리는 여기". 음원은 사용자가 준비하고, 어디에 넣을지는 `video-editing-style-analyzer`가 사용자에게 물어 프로필 `sfx.map`에 넣는다. `sfx_map` 없으면 `sfx_trigger` 한 곳에 `sfx_dir` 풀 순환(단순).
- **한글 등 커스텀 폰트**: `caption_font`는 pycapcut FontType(라틴 348종)만 되므로 한글 서체는 못 지정한다. 프로필에 `applied.caption.font_capcut = {resource_id, name}`(CapCut draft에서 뽑은 폰트 블록)이 있으면 `style_utils.RawFont`로 그 폰트를 주입한다. 없으면 `caption_font: "__capcut_default__"`로 CapCut 기본 폰트 렌더. 추출은 `video-editing-style-analyzer/scripts/capture_font.py`.
- `--style-profile` 없이 실행하면 동작은 이전과 완전히 동일하다(모든 신규 필드 기본값 = 기존 하드코딩값).

## 실전에서 발견한 함정 (전부 확인·해결됨, 순서대로 마주치기 쉬움)

### 1. macOS CapCut은 `draft_content.json`이 아니라 `draft_info.json`을 읽는다
pycapcut(그리고 기반 라이브러리 pyJianYingDraft)은 Windows CapCut 파일명인 `draft_content.json`으로 저장한다. **macOS CapCut은 같은 폴더에서 `draft_info.json`을 찾는다** — 내용 스키마는 거의 동일, 파일명만 다르다. 이게 없으면 draft가 목록엔 뜨지만(`draft_meta_info.json`만 있으면 목록엔 뜸) 열면 타임라인이 완전히 비어있다. `stage_save.py`가 저장 직후 자동으로 복사 처리한다.

### 2. CapCut의 macOS 샌드박스가 임의 경로의 미디어 파일을 못 읽는다
워크스페이스 폴더 등 임의 경로에 있는 영상/이미지/오디오를 참조하면 CapCut에서 "미디어 연결"(파일을 찾을 수 없음) 오류가 뜬다 — JSON 경로 자체는 정확한 절대경로인데도 그렇다. **`~/Movies/` 아래 있는 파일은 정상 인식된다.** `stage_ingest.py`가 모든 입력 미디어를 `~/Movies/<프로젝트명>_media/`로 자동 복사한 뒤 그 경로로 draft를 만든다 — 원본 파일은 건드리지 않는다.

### 3. 같은 draft 이름으로 재실행하면 "목록엔 보이는데 클릭해도 안 열림" 버그가 생길 수 있다
CapCut의 프로젝트 목록(`root_meta_info.json`)은 각 draft의 `id`를 별도로 캐싱한다. 파이프라인이 같은 이름의 기존 draft 폴더를 삭제 후 재생성하면 pycapcut이 새 `id`를 발급하는데, `root_meta_info.json`엔 **이전 id가 그대로 남아있어서** 목록·썸네일은 정상인데 클릭하면 (id 불일치로) 아무 반응이 없다. 에러 메시지도 없어서 원인 파악이 까다롭다. `stage_save.py`의 `_sync_root_meta_info()`가 저장 직후 `root_meta_info.json`에서 같은 이름 항목을 찾아 `draft_id`를 새 id로 자동 동기화한다. 이 함수가 없는 상태에서 이 증상을 만나면: `root_meta_info.json`을 읽어서 해당 draft_name 항목의 `draft_id`를 새로 생성된 `draft_info.json`의 `id` 값으로 직접 고쳐주면 즉시 해결된다.

### 4. faster-whisper 기본 세그먼트가 문장이 아니라 ~30초 단위로 뭉친다
Whisper 모델의 내부 처리 윈도우가 30초라서, `vad_filter=True`를 켜도 `segment.text`는 문장 단위가 아니라 ~30초짜리 뭉텅이로 나온다 (특히 TTS처럼 문장 사이 무음이 거의 없는 오디오에서 심함). `word_timestamps=True`로 단어별 타임스탬프를 받아서 단어 간 간격(기본 0.5초) 기준으로 직접 재그룹핑해야 진짜 문장 단위 cue를 얻는다 (`stage_transcribe.py`의 `_regroup_words_into_cues`).

### 5. "무자막 컷"과 "하이라이트 선별"은 gap-merge를 먼저 하면 안 된다
사람이 자연스럽게 말하는 것과 달리 연속적으로 읽는 오디오(TTS 등)는 문장 사이 pause가 거의 없다. gap으로 먼저 발화 블록을 뭉쳐놓고 그 블록 단위로 목표 길이를 선별하면, 전체가 하나의 거대한 블록이 되어 예산을 넘겨 통째로 탈락하는 문제가 생긴다. **cue(구문) 단위로 먼저 선별**하고(`stage_highlight.select_highlight_cues`), 선별된 cue들 중 원본에서 가까운 것끼리만 나중에 하나의 클립으로 묶어야(`stage_gaps.merge_cues_into_blocks`) 이 문제가 생기지 않는다.

### 6. 텍스트 노트 파싱은 특정 도메인 단어에 의존하면 안 되고, 최대한 관대해야 한다
초기 버전은 정확히 `## 재료`만 인식했는데, 실사용자가 준 .md 파일은 `# ... 재료 ...`(레벨 무관) 헤딩에 불릿이 아니라 **마크다운 표**(`| 채소 | 수량 | 금액 |`)였다 — 완전히 실패해서 오버레이·효과음이 0개로 조용히 안 만들어졌다. `md_parsing.py`는 (1) 헤딩에 "재료/키워드/항목/체크리스트/단계/포인트/리스트" 중 하나라도 포함되면 그 섹션을 쓰고, (2) 매칭되는 헤딩이 전혀 없으면 문서에서 처음 발견되는 불릿 목록·표 블록을 그대로 쓴다 — 이렇게 해야 요리 .md든 튜토리얼 .md든 헤딩 문구를 가리지 않고 동작한다. 불릿/표 둘 다 지원하고, 표는 헤더 행(구분선 `|---|---|` 이전 행)을 자동으로 건너뛴다. "다진 마늘"처럼 키워드 앞에 수식어가 붙은 경우 수식어(`_MODIFIER_PREFIXES` 목록)를 걸러내고 핵심 명사만 키워드로 쓴다.

### 7. `AudioSceneEffectType`은 "딩" 효과음이 아니라 보이스 필터다
pycapcut 문서만 보면 효과음에 `AudioSceneEffectType`을 쓸 것 같지만, 실제로 확인해보면 이건 ~200종의 보이스체인저 필터(Bibble, Witch, Elfy, Good Guy 등)다. 짧게 적용해도 "음성이 잠깐 일그러지는" 효과가 나지, "딩" 하는 단발 효과음이 아니다. 진짜 효과음이 필요하면 **로컬 오디오 파일**을 `AudioSegment`로 별도 트랙에 얹는 방식을 쓴다 (`stage_sfx.py`). `recipe_pipeline/assets/default_ding.wav`가 기본 제공되며, `config.sfx_path`로 다른 파일 지정 가능.

### 8. 폰트는 pycapcut의 `FontType`(약 350개)에서 골라야 하고, 전부 실제 CapCut 폰트 ID로 매핑된다
`cc.FontType[이름]`으로 유효성 검증. `style_utils.py`의 `CAPTION_FONTS`에 10개를 큐레이션해뒀지만, 전체 목록이 필요하면 `list(cc.FontType)`로 조회. **주의**: Arimo(기본)는 실제 CapCut 렌더링까지 확인됐지만, 나머지 폰트들은 "유효한 등록 폰트다"까지만 확인됐지 실제 렌더링 결과를 전부 눈으로 검증한 건 아니다 — 사용자가 특정 폰트를 고르면 실제로 CapCut에서 열어서 확인해달라고 요청할 것. `style_utils.resolve_font()`는 이제 정확 일치 실패 시 alias 표 → `difflib` 근사 → Arimo 폴백 순으로 처리하고, `pipeline_log.json`의 `font_requested_vs_used`에 "요청한 이름 → 실제로 쓴 이름"을 남긴다.

### 9. pycapcut의 드롭섀도우는 기본 연결되어 있지 않다 (스타일 프로필 관련)
`text_segment.py`의 `export_material()`에서 `has_shadow`/`shadow_*` 키가 전부 주석 처리돼 있다. `stage_caption_style.py`의 `_ShadowTextSegment` 서브클래스가 이 필드를 직접 주입하고 `check_flag |= 32`를 세팅한다 — **실험적**이며 CapCut에서 실제로 그림자가 보이는지 육안 확인이 필요하다. `caption_shadow=True`일 때만 이 경로를 탄다.

### 10. 텍스트 외곽선 두께 매핑이 불확실하고, 애니메이션 enum 이름이 중국어다 (스타일 프로필 관련)
`TextBorder`는 내부에서 `width/100*0.2`로 매핑하는데 pycapcut 소스가 "此映射可能不完全正确"(완전히 정확하지 않을 수 있음)라고 표시해뒀다 — 외곽선 두께는 CapCut에서 보고 조정. 텍스트 인/아웃 애니메이션(`TextIntro`/`TextOutro`) enum 멤버 이름은 `渐显`, `向上弹入`, `打字机` 같은 중국어이고 pycapcut 버전마다 바뀔 수 있다. `style_utils.resolve_text_intro/outro`가 제네릭 이름(`fade`/`pop`/...)을 매핑하고, KeyError면 조용히 `None`(애니메이션 없음)으로 폴백한다.

## 검증 체크리스트 (매 빌드마다)

- [ ] pycapcut import 성공 (Python 버전 이슈 없는지)
- [ ] 최소 draft가 CapCut에서 실제로 열리는지 (2단계 스파이크, 사용자 확인 필수)
- [ ] 텍스트 노트 없이 영상+엔딩이미지만으로 CLI 끝까지 실행 성공 (순서대로 하이라이트 채우는 폴백 확인)
- [ ] 텍스트 노트를 준다면, 사용자의 실제 .md 형식(표든 불릿이든, 헤딩 문구가 무엇이든)에서 키워드가 정상 감지되는지
- [ ] CapCut에서 결과 draft 확인: 영상/자막/엔딩이미지(그리고 있다면 오버레이/효과음) 전부 반영, 클립 삭제해도 안 깨짐
- [ ] 같은 draft 이름으로 2번 이상 재실행해도 정상적으로 열리는지 (함정 #3 회귀 확인)
- [ ] 웹 대시보드에서 파일 업로드 → 실행 → 완료까지 브라우저로 실제 확인

## 파일 구조

```
capcut-highlight-video-editor/
├── SKILL.md                          # 이 파일
└── templates/
    ├── requirements.txt              # pycapcut, faster-whisper, fastapi 등
    ├── recipe_pipeline/               # 코어 파이프라인 (CLI 포함, 패키지명은 유지되지만 로직은 범용)
    │   ├── cli.py
    │   ├── config.py                 # PipelineConfig — content_md 포함 모든 필드가 선택적으로 확장 가능
    │   ├── pipeline.py               # orchestrate() — 전체 단계 순서 조정
    │   ├── stage_*.py                # 단계별 모듈 (파일명이 곧 역할)
    │   ├── md_parsing.py             # 텍스트 노트에서 키워드 목록 추출 (표+불릿 지원, 도메인 무관)
    │   ├── style_utils.py            # 폰트/색상/위치 변환 헬퍼
    │   └── assets/default_ding.wav
    └── webapp/                        # FastAPI 대시보드 (파이프라인을 감싸기만 함)
        ├── main.py
        ├── runner.py
        ├── models.py
        └── static/{index.html,app.js}
```

## 버전 히스토리

- **v1.2.2**: 효과음 확장 — `sfx_map`(`[{"file","trigger"}]` — 효과음별로 어디에 넣을지 명시, 순환 아님) + `sfx_dir`/`sfx_trigger`(단순 케이스). trigger: cuts(클립 경계) / keywords(.md 필요) / caption_in(모든 자막) / end. `stage_sfx.add_sfx_placements((시각,파일) 쌍)`. style-profile 의 `sfx.map` 으로 자동 설정 — 배치는 스킬이 사용자에게 물어서 정함. CLI `--sfx-map`/`--sfx-dir`/`--sfx-trigger`, webapp 다중 업로드 + map JSON.
- **v1.2.1**: 폰트 처리 개선 — `resolve_font`가 미해결 서체에 Arimo를 강제하는 대신 `None`(CapCut 기본 폰트) 반환 가능(한글에 유리). `caption_font_capcut`/`overlay_font_capcut` dict + `style_utils.RawFont` 로 CapCut draft에서 뽑은 임의 폰트 블록 주입 가능. `gap_threshold` 등 컷 호흡은 style-profile이 샷 길이에서 유도.
- **v1.2.0**: `--style-profile` 옵션 추가 — `video-editing-style-analyzer` 스킬이 만든 `style-profile.json`을 읽어 자막(외곽선·그림자·배경박스·인/아웃 애니메이션·대문자화·정렬), 컷 호흡(`pause_gap_sec`/`max_cue_sec`), 키워드 줌 파라미터, 효과음 볼륨, 오버레이 스타일을 특정 채널 룩에 맞춘다. `PipelineConfig`에 신규 필드 ~30개 추가(전부 기존 하드코딩값을 기본값으로 → `--style-profile` 없으면 동작 불변). `style_utils`에 퍼지 폰트 매칭·`TextBorder`/`TextBackground` 빌더·제네릭 애니메이션 이름 리졸버 추가. 웹 대시보드 고급 설정에 스타일 프로필 선택/업로드 + 신규 스타일 필드. 함정 #9(섀도우 미연결)·#10(외곽선 두께 매핑·애니메이션 enum) 문서화.
- **v1.1.0**: 텍스트 노트(.md)를 완전히 선택 사항으로 변경 — 영상+엔딩이미지만으로도 끝까지 동작(순서대로 하이라이트 채움). `md_parsing.py`가 "재료" 같은 특정 도메인 단어에 의존하지 않고, 흔한 리스트 섹션 제목을 폭넓게 인식하거나(없으면 첫 불릿/표 블록을 자동으로) 쓰도록 일반화 — 요리 영상 전용이 아니라 어떤 숏폼 영상에도 적용 가능하게 됨. 스킬명도 `capcut-recipe-video-editor` → `capcut-highlight-video-editor`로 변경.
- **v1.0.0**: 실제 요리 영상 자동 편집 프로젝트를 처음부터 끝까지(스파이크 → 코어 파이프라인 → 웹 대시보드 → 스타일 커스터마이징 → 실사용자 파일로 검증) 구축한 과정을 일반화. macOS CapCut 연동에서 발견한 8가지 함정(파일명 불일치, 샌드박스 경로 제약, id 캐시 불일치, whisper 세그먼트 문제, gap-merge 순서, .md 파싱 견고성, 효과음 API 오해, 폰트 검증 범위)을 전부 코드와 문서에 반영. 프로젝트/브랜드명에 종속되지 않도록 코드 전체 검토 완료.
