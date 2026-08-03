---
name: naver-keyword-trend-analyzer
description: |
  네이버 검색광고 API(키워드도구)로 키워드의 PC/모바일 검색량·경쟁정도·연관키워드를 조회하고, 네이버 데이터랩 API로 검색 트렌드와 성수기/비수기를 자동 분석하는 스킬. 구글이 아니라 네이버 검색 기준 키워드 리서치가 필요할 때 쓴다.
  "네이버 키워드 분석해줘", "이 키워드 검색량 알려줘", "성수기 비수기 분석", "데이터랩 트렌드" 등을 언급하면 자동 실행.

  Triggers:
  - "네이버에서 이 키워드 검색량 얼마나 돼?"
  - "연관키워드 뽑아줘"
  - "이 키워드 성수기가 언제야?"
  - "네이버 데이터랩으로 트렌드 확인해줘"

  Use when: 네이버 검색 기준으로 키워드 검색량·경쟁도·계절성을 파악해 콘텐츠/광고 키워드를 고를 때.
allowed-tools: Bash, Read, Write
---

# 네이버 키워드·트렌드 분석 스킬

네이버 **검색광고 API**(키워드도구)로 검색량·경쟁정도·연관키워드를, 네이버 **데이터랩 API**로 검색 트렌드·성수기/비수기를 가져와 하나의 리포트로 합치는 스킬. 결과물은 항상 리포트 하나 — 키워드 검색량 표 + 트렌드/계절성 요약.

## ⚠️ 이 스킬을 쓰기 전에 반드시 읽을 것 — 인증정보 원칙

**이 스킬에는 실제 네이버 광고 계정 정보(고객번호, API 키)나 실제 키워드 조회 결과를 하드코딩하지 않는다.** 인증정보는 `scripts/.env`(gitignore 처리됨)에서만 읽고, `example-output/`에는 가상의 키워드로 만든 합성 예시만 둔다.

- 필요한 값 4~5개는 모두 `scripts/.env`에 저장: `NAVER_AD_ACCESS_LICENSE`, `NAVER_AD_SECRET_KEY`, `NAVER_AD_CUSTOMER_ID`(검색광고 API), `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`(데이터랩/오픈API)
- 실제 리포트(진짜 키워드·검색량 데이터)는 이 스킬 폴더가 아니라 프로젝트 폴더(`./10-projects/{프로젝트명}/keyword-analysis/{YYYYMMDD}/`)에 저장할 것

이 스킬은 로그인 화면이나 다중 사용자 기능이 없다 — Claude Code 세션에서 스크립트를 직접 실행하는 형태라 별도 인증 UI가 필요 없다. GA4(구글 애널리틱스) 연동은 포함하지 않는다 — 이 스킬은 네이버 전용이다.

---

## 전체 워크플로우

```
[1] 사전 준비 — 네이버 검색광고 API + 오픈API(데이터랩) 키 발급 (최초 1회)
       ↓
[2] 키워드도구 API로 검색량·경쟁정도·연관키워드 조회
       ↓
[3] 데이터랩 API로 최근 N일 검색 트렌드 조회 (최대 5개 키워드씩)
       ↓
[4] 트렌드에서 성수기/비수기·추세(상승/하락/유지)·변동성 자동 분석
       ↓
[5] 리포트 생성 (프로젝트 폴더에 저장)
```

---

## Step 1: 사전 준비 (최초 1회)

1. [네이버 검색광고](https://searchad.naver.com) 가입 → 도구 → API 사용 관리에서 **API 라이선스**(Access License), **비밀키**(Secret Key), **고객 ID**(Customer ID) 발급
2. [네이버 개발자센터](https://developers.naver.com/apps)에서 애플리케이션 등록 → **데이터랩(검색어трend)** API 사용 설정 → Client ID/Secret 발급
3. `scripts/.env` 생성 (gitignore 처리되어 커밋 안 됨):
   ```
   NAVER_AD_ACCESS_LICENSE=...
   NAVER_AD_SECRET_KEY=...
   NAVER_AD_CUSTOMER_ID=...
   NAVER_CLIENT_ID=...
   NAVER_CLIENT_SECRET=...
   ```
4. 의존성 설치: `pip install pandas python-dotenv`

---

## Step 2: 키워드 검색량·경쟁정도 조회

```bash
cd .claude/skills/naver-keyword-trend-analyzer/scripts
python3 naver-keyword-trend.py --keywords "여름 원피스,린넨 원피스" --out /tmp/naver-report
```

- `--keywords`: 쉼표로 구분한 키워드 목록 (기준 키워드로 연관키워드까지 자동으로 딸려나옴)
- 키워드도구 API가 PC/모바일 월간 검색량, 평균 클릭수, CTR, 경쟁정도(낮음/중간/높음), 광고 노출 개수를 반환 — 총검색량(PC+모바일) 기준으로 정렬

## Step 3~4: 트렌드 + 성수기/비수기 분석

- 데이터랩 API는 **한 번에 최대 5개 키워드 그룹**만 지원 — 6개 이상이면 앞 5개만 트렌드 분석 대상이 됨(리포트에 명시)
- `--trend-days`(기본 90일) 구간의 일별 검색지수를 가져와 월별 평균을 계산
- 월평균이 전체 평균의 **120% 이상이면 성수기, 80% 이하면 비수기**로 표시
- 추세는 첫 데이터포인트 대비 마지막 데이터포인트 기울기로 상승/하락/유지 판단 (임계값 ±1)
- 변동성은 표준편차/평균 비율로 판단 — 30% 초과면 "계절성 뚜렷", 15~30%면 "보통", 15% 미만이면 "안정적"

---

## Step 5: 리포트 생성

`templates/keyword-trend-report-template.md` 형식으로 작성하고 프로젝트 폴더에 저장한다. 스킬 폴더 안의 `example-output/`에는 실제 데이터를 절대 넣지 않는다.

```markdown
# [주제] 네이버 키워드·트렌드 리포트 ({조회일})

## 1. 키워드 검색량 (총검색량 순)
## 2. 트렌드 요약 (키워드별 성수기/비수기/추세/변동성)
## 3. 다음 액션
```

---

## 트러블슈팅

### `검색광고 API 키가 설정되지 않았습니다`
`scripts/.env`에 `NAVER_AD_ACCESS_LICENSE`/`NAVER_AD_SECRET_KEY`/`NAVER_AD_CUSTOMER_ID` 세 개가 다 있는지 확인.

### 데이터랩 API가 401/403 반환
네이버 개발자센터에서 해당 애플리케이션에 "검색어트렌드(데이터랩)" API 사용 설정이 켜져 있는지 확인 — 앱 등록만으로는 자동 활성화 안 됨.

### 6개 이상 키워드를 넣었는데 일부가 트렌드 분석에서 빠짐
데이터랩 API 자체 제약(키워드 그룹 최대 5개) — 의도된 동작. 중요한 키워드부터 5개 이내로 나눠서 여러 번 실행할 것.

### 검색량이 `< 10`으로 나옴
네이버 API가 월간 검색량이 10 미만이면 정확한 숫자 대신 `< 10`을 반환 — 스크립트가 이를 10으로 처리해 표시(실제 값은 그보다 낮을 수 있음).

---

## 의존성

- `pip install pandas python-dotenv`
- 네이버 검색광고 API 라이선스 + 네이버 개발자센터 데이터랩 API 키 (Step 1)
- 별도 브라우저 인증 흐름 없음 (API 키+시크릿 기반 HMAC 서명 방식)

## 파일 구조

```
naver-keyword-trend-analyzer/
├── SKILL.md
├── scripts/
│   ├── naver-keyword-trend.py   # 키워드도구 + 데이터랩 조회, 성수기/비수기 분석, 리포트 생성
│   └── .env                     # (gitignore) 네이버 API 키 5종 — 사용자가 직접 발급
├── templates/
│   └── keyword-trend-report-template.md
└── example-output/
    └── example-report-20260803.md   # 가상 키워드 기준 합성 예시 (실제 데이터 아님)
```

## 버전 히스토리

- **v1.0.0 (2026-08-03)**: 기존 개인용 Streamlit 키워드 분석 도구(`keyword-analyzer`)에서 네이버 전용 부분(키워드도구+데이터랩)만 뽑아 독립 스킬로 재구성. 로컬 비밀번호 로그인 기능과 GA4 연동은 공유용 스킬에 불필요해 제외. Streamlit GUI 대신 CLI 스크립트 + 마크다운 리포트 형태로 전환해 다른 Aha Friends 스킬과 형식을 통일.
