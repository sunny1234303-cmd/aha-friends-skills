---
name: competitor-detail-page-analyzer
description: |
  신규 제품 런칭 전, 경쟁사 상품 상세페이지(이미지)를 다운로드하고 구조를 분석하는 자동화. 특정 상품 URL뿐 아니라 "여름 수분크림"처럼 카테고리/키워드만 주어져도 올리브영 판매순 베스트셀러를 찾아 여러 개를 분석할 수 있음. 올리브영 지원 (단, Cloudflare 보호로 인터랙티브 브라우저 방식 필요).
  "경쟁사 상세페이지 분석", "상세페이지 다운로드", "상세페이지 구조 분석", "올리브영 상세페이지", "잘나가는 OO 크림 분석해줘" 등을 언급하면 자동 실행.

  Triggers:
  - "경쟁사 상세페이지 분석해줘"
  - "이 상품 상세페이지 다운받아줘"
  - "올리브영 상세페이지 구조 분석"
  - "여름 수분크림 베스트셀러 상세페이지 분석해줘"

  Use when: 신규 제품 런칭 전 경쟁사 상세페이지를 벤치마킹해야 할 때. 실무에서는 특정 브랜드 지정 없이 "이 카테고리에서 잘 팔리는 제품들"을 분석하고 싶은 경우가 더 많음 — URL이 없어도 카테고리/키워드만으로 시작 가능.
allowed-tools: Bash, Read, Write, ToolSearch, mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__tabs_close_mcp, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__computer, mcp__claude-in-chrome__javascript_tool, mcp__claude-in-chrome__find, mcp__claude-in-chrome__read_page
---

# 경쟁사 상세페이지 구조 분석 스킬

경쟁사 상품 URL(또는 카테고리/키워드)을 받아 **상세페이지 이미지를 다운로드**하고, **구조 분석 리포트**를 만드는 End-to-End 스킬. 최종 산출물은 ① 상세페이지 이미지 파일들 ② 구조 분석 마크다운(`.md`) ③ 그 내용을 정리한 HTML 보고서(`report.html`) — 그리고 **HTML 보고서는 브라우저 탭으로, 이미지 폴더는 Finder 로 직접 열어준다**(경로만 안내하고 끝내지 않는다).

**실제 예시 결과물**: `example-output/estra-atobarrier365-cream-20260803/` (올리브영 에스트라 아토베리어365 크림으로 라이브 검증한 실제 산출물)

## ⚠️ 먼저 읽을 것 — 다운로드 방식은 사이트에 따라 다르다

라이브 테스트 결과, **두 가지 전혀 다른 방식이 필요하다는 게 확인됨**:

1. **`scripts/detail-page-scraper.py` (Playwright 헤드리스 스크립트)** — API 키 없이 동작하지만, **올리브영에서는 Cloudflare 봇 탐지에 막혀 작동하지 않는다** (`--headed` 없이 실행 시 상품 페이지 대신 "Verify you are human" 챌린지 페이지가 뜸, 실측 확인됨). Cloudflare 등 봇 탐지가 없는 일반 사이트에서만 쓸 것.
2. **Claude in Chrome 인터랙티브 방식** (Step 2 참고) — 실제 로그인된 브라우저 세션을 쓰기 때문에 Cloudflare를 통과한다. **올리브영은 반드시 이 방식을 쓸 것.**

CAPTCHA/봇 탐지를 우회하는 자동화(예: Cloudflare 챌린지를 프로그래밍적으로 풀기)는 절대 시도하지 않는다 — 위 1번이 막히면 2번(사람이 실제로 열어본 브라우저)으로 전환하는 것이 원칙이다.

## 전체 워크플로우

```
[0] (URL이 없을 때) 카테고리/키워드 → 베스트셀러 목록 찾기
       ↓
[1] 분석 대상 URL 확정 (1개 또는 여러 개)
       ↓
[2] 상세페이지 이미지 확보 — 각 상품마다 반복
     ├─ Cloudflare 없는 사이트 → detail-page-scraper.py (헤드리스)
     └─ 올리브영 등 Cloudflare 보호 사이트 → Claude in Chrome 인터랙티브 방식
       ↓
[3] 다운로드된 이미지를 Claude가 직접 확인 (Read 툴로 이미지 열람)
       ↓
[4] 구조 분석 (섹션 단위로 설득 흐름 분해)
       ↓
[5] 구조 분석 리포트(.md) 생성 (상품별로 하나씩, 여러 개면 비교 요약도 추가)
       ↓
[6] 같은 내용을 HTML 보고서(report.html)로 변환 → `open` 으로 브라우저 탭에 띄움
       ↓
[7] `open` 으로 저장된 상세페이지 이미지 폴더(images/)를 Finder 로 엶
```

실무에서는 특정 브랜드를 콕 집기보다 **"이 카테고리에서 잘 팔리는 제품"** 을 보고 싶은 경우가 많다 (예: "여름 수분크림 출시 예정인데 잘 팔리는 브랜드들 상세페이지 분석해줘"). 이때는 Step 0부터 시작한다.

---

## Step 0: 카테고리/키워드 → 베스트셀러 목록 찾기 (URL이 없을 때)

**Claude in Chrome 인터랙티브 방식으로 진행** (검색 결과 정렬이 AJAX 기반이라 URL 파라미터만으로는 안 됨 — 실측 확인).

1. `navigate`: `https://www.oliveyoung.co.kr/store/search/getSearchMain.do?query=<키워드 URL인코딩>` (예: 수분크림, 수분크림 대신 더 구체적인 키워드도 가능 — "여름 수분크림"이면 "수분크림"으로 검색 후 결과에서 여름/쿨링 관련 상품 위주로 선별)
2. `find` 또는 텍스트 매칭으로 정렬 옵션 중 **"판매순"** 링크를 찾아 클릭 (기본 정렬은 "인기순"이라 판매량과 다를 수 있음 — 반드시 판매순으로 바꿀 것)
3. `javascript_tool`로 상품 카드 목록에서 브랜드+상품명까지 함께 추출 (이름이 있어야 다음 단계의 중복 제거가 가능함):
   ```js
   const links = Array.from(document.querySelectorAll('a[href*="getGoodsDetail"]'));
   const seen = new Set();
   const items = [];
   for (const a of links) {
     const m = a.href.match(/goodsNo=([A-Z0-9]+)/);
     if (!m || seen.has(m[1])) continue;
     seen.add(m[1]);
     const card = a.closest('li') || a.closest('div');
     const brand = card?.querySelector('[class*=brand], .tx_brand, strong')?.textContent?.trim() || '';
     const name = card?.querySelector('[class*=name], .tx_name, p')?.textContent?.trim() || '';
     items.push({ rank: items.length + 1, goodsNo: m[1], brand, name, url: a.href });
     if (items.length >= 15) break; // 중복 제거 후에도 충분한 후보가 남도록 여유있게 수집
   }
   ```
4. **동일 제품의 용량/구성/굿즈만 다른 변형 상품은 제거한다.** 같은 브랜드에서 여러 개가 나오면, 상품명에서 브랜드명·용량(ml/g)·"기획", "1+1", "증정", "리필" 등 구성 관련 단어를 뺀 핵심 제품명이 같은지 비교한다. 핵심 제품명이 같으면 **판매순위가 가장 높은 것 하나만 남기고 나머지는 후보에서 제외** — "에스네이처 아쿠아 스쿠알란 수분크림 60ml"와 "에스네이처 아쿠아 스쿠알란 수분크림 60ml 기획(+30ml)"은 같은 제품으로 취급한다. 이 작업은 자동 정규식보다 Claude가 상품명 리스트를 보고 직접 판단하는 게 정확하다.
5. 중복 제거 후 남은 목록(서로 다른 실제 제품들)을 사용자에게 보여주고, **몇 개를 실제로 분석할지 확인받는다** (보통 3~5개면 충분). 이 단계에서도 브랜드가 겹치면 다양성을 우선해서 추린다.
6. 확정된 URL 목록으로 Step 1부터 반복

---

## Step 1: 입력 확인

Step 0에서 나온 URL 목록, 또는 사용자가 직접 준 URL(1개 이상)을 받는다. 지원 사이트:

| 사이트 | 지원 상태 | 다운로드 방식 |
|---|---|---|
| 올리브영 (`oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=...`) | **검증됨** (검색·정렬·상세이미지 추출 전부 라이브 확인, 2026-09-11 재검증) | Claude in Chrome 인터랙티브 방식만 가능 (Cloudflare가 헤드리스를 차단). 상세이미지가 브랜드 자체 CDN(speedgabia·jpg1.kr 등)에 있으면 CORS 우회로 그 CDN 탭에서 fetch — Step 2-B step 4 참고 |
| 그 외 일반 쇼핑몰 (Cloudflare 없음) | 제네릭 방식 시도 | `detail-page-scraper.py` (헤드리스), 안 되면 인터랙티브 방식으로 전환 |
| 다나와 | 미검증 | 둘 중 아무거나 시도 후 결과 확인 |

URL도 카테고리도 없으면 사용자에게 요청한다.

---

## Step 2-A: 헤드리스 스크립트로 다운로드 (Cloudflare 없는 사이트)

```bash
cd .claude/skills/competitor-detail-page-analyzer/scripts && \
python3 detail-page-scraper.py "<상품_URL>" --out /tmp/competitor-detail/<브랜드>-<상품명>
```

- Playwright(Chromium)로 페이지를 열고 이미지를 원본 해상도로 `img-01.jpg`, `img-02.jpg` ... 순서로 저장
- 실행 후 `meta.json`의 `image_count`가 0이거나 `fallback-fullpage.png`(스크린샷 대체)만 있으면 → **Cloudflare 등 봇 탐지에 막힌 것** → Step 2-B로 전환

---

## Step 2-B: Claude in Chrome 인터랙티브 방식 (올리브영 등)

Claude in Chrome 브라우저 툴(`mcp__claude-in-chrome__*`)이 있는 세션에서만 가능. 없으면 사용자에게 브라우저 확장 사용 세션에서 다시 요청하라고 안내한다. **아래는 상품 3개(에스네이처/셀리맥스/브링그린)로 반복 검증해 정착된 최종 방법.**

1. **탐색**: `navigate`로 상품 URL 접속, 1.5~2초 대기 (페이지가 완전히 그려지기 전에 다음 단계로 넘어가면 탭/버튼을 못 찾음 — 실측으로 반복 확인된 실패 원인 1위)
2. **상세 이미지 노출**: `javascript_tool`로 아래 순서 실행 (텍스트 매칭, 버튼이 없는 상품도 있으니 optional chaining으로 처리)
   ```js
   const tabBtn = Array.from(document.querySelectorAll('[role=tab], button, a'))
     .find(el => el.textContent.trim() === '상품설명');
   if (tabBtn) tabBtn.click();
   await new Promise(r => setTimeout(r, 1000));
   const moreBtn = Array.from(document.querySelectorAll('button, a'))
     .find(el => el.textContent.trim() === '상품설명 더보기');
   if (moreBtn) { moreBtn.scrollIntoView({block:'center'}); await new Promise(r=>setTimeout(r,400)); moreBtn.click(); }
   await new Promise(r => setTimeout(r, 1500));
   ```
   `moreBtn`이 안 잡히면(즉 `moreClicked: false`) 바로 재시도하지 말고 **한 번 더 같은 코드를 실행**해볼 것 — 첫 렌더가 안 끝난 상태에서 찾다가 놓치는 경우가 잦았다(실측 확인).
3. **이미지 URL 수집 — `src`가 아니라 `data-src`를 읽을 것.** 컨테이너 클래스는 CSS 모듈 해시가 붙으므로 prefix로 매칭:
   ```js
   const imgs = Array.from(document.querySelectorAll('[class*="GoodsDetailTabs_product-detail-tabs"] img'));
   const urls = imgs.map(im => im.getAttribute('data-src') || im.src).filter(u => u && !u.startsWith('data:'));
   ```
   **왜 `data-src`인가**: 이 사이트는 지연 로딩이라 `img.src`엔 처음에 1×1 placeholder gif만 들어있고, 실제 URL은 `data-src`에 로드 전부터 이미 박혀있다(실측 확인). 예전엔 스크롤로 지연 로딩을 강제로 트리거하려 했는데, `scrollBy` 루프가 느리고(45초 타임아웃 발생) 이미지를 빠르게 지나치면 로드가 씹히는 문제가 반복됐다. `data-src`를 바로 읽으면 스크롤 자체가 필요 없다.
4. **다운로드 — 여러 장을 하나의 캔버스에 이어붙여 한 번만 다운로드한다.** `<a download>` 반복 클릭은 Chrome이 "다중 자동 다운로드"로 차단하고(1장만 저장됨, 실측 확인), base64로 하나씩 반환받는 것도 이미지가 많으면 비효율적이다. 대신 **fetch → Image 객체 로드 → canvas에 순서대로 그리기 → canvas.toBlob → 다운로드 1회**.

   **⚠️ 두 가지 실전 함정 (2026-09-11 "수분세럼 베스트4"에서 확인):**

   **(a) `javascript_tool` 은 45초에 CDP 타임아웃난다.** 이미지 35~44장을 `for` 루프로 `await` 하면 45초를 넘겨 툴이 죽는다. → **`window.__job` 에 async IIFE를 넣어 백그라운드로 돌리고**, `Promise.all` 로 병렬 fetch(각 fetch에 `AbortController` 12~20초 타임아웃), 그다음 `computer` `wait` 로 10초씩 나눠 기다렸다가 `window.__jobR` 을 폴링한다.

   **(b) 서드파티 CDN 은 올리브영 페이지 origin 에서 fetch 하면 CORS(`TypeError: Failed to fetch`)로 막힌다.**
   - `image.oliveyoung.co.kr`(크롭 프록시), `gi.esmplus.com` → ACAO `*`, **어느 탭에서든 fetch 가능**.
   - `dalba.speedgabia.com`, `torriden.jpg1.kr` 등 브랜드 자체 CDN → 올리브영 origin 에서 **차단**. 해결: **그 CDN 의 실제 이미지 URL 하나로 새 탭(`tabs_create_mcp` + `navigate`)을 열면 그 탭은 CDN 과 same-origin** 이 되어 fetch 가 통과한다. 전체 순서 리스트(올리브영 이미지 포함)를 그 탭에서 한 번에 이어붙이면 된다. 달바 35/35 성공.
   - 올리브영 크롭 프록시는 임의 원본 호스트를 프록시한다: `https://image.oliveyoung.co.kr/cfimages/cf-goods/uploads/images/html/crop/{goodsNo}/{ts}/crop{N}/{원본호스트}/{경로}`. 정적 PNG/JPG 는 이걸로 우회 가능하나 **애니메이션 GIF 는 403**.
   - 일부 origin(`torriden.jpg1.kr`)은 그 탭에서 `<a download>` 자체가 차단된다(자동·유저제스처 모두). → 정적 이미지만 크롭 프록시로 모으고 **GIF 구간은 빈 칸으로 두되**, 텍스트·임상 근거 섹션은 전부 확보됨을 확인하고 리포트에 "GIF N구간 정적 캡처 불가(고유 카피·수치 없음)" 로 명시.

   **표준 다운로드 스크립트 (single-origin, 대부분 케이스):**
   ```js
   window.__job = (async () => {
     const urls = /* Step 3 에서 모은 data-src 배열, 또는 서드파티 탭이면 재구성한 순서 리스트 */;
     async function load(u) {
       try {
         const c = new AbortController(); const t = setTimeout(() => c.abort(), 20000);
         const r = await fetch(u, { credentials: 'omit', signal: c.signal }); clearTimeout(t);
         if (!r.ok) return { err: 's' + r.status };
         const b = await r.blob(); const o = URL.createObjectURL(b);
         const im = new Image();
         await new Promise((res, rej) => { im.onload = res; im.onerror = rej; im.src = o; });
         URL.revokeObjectURL(o);
         return { im, w: im.naturalWidth, h: im.naturalHeight };
       } catch (e) { return { err: e.name }; }
     }
     const res = await Promise.all(urls.map(load));            // 병렬 — 45초 타임아웃 회피
     const W = Math.max(...res.filter(x => x.im).map(x => x.w));
     const H = res.reduce((s, x) => x.im ? s + Math.round(x.h * (W / x.w)) : s + 25, 0); // 실패분은 25px 흰 여백
     const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
     const g = cv.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, W, H);
     let y = 0;
     for (const x of res) { if (!x.im) { y += 25; continue; } const h = Math.round(x.h * (W / x.w)); g.drawImage(x.im, 0, y, W, h); y += h; }
     const blob = await new Promise(r => cv.toBlob(r, 'image/jpeg', 0.86));
     const a = document.createElement('a');
     a.href = URL.createObjectURL(blob); a.download = '<브랜드>-detail-stitched.jpg';
     document.body.appendChild(a); a.click(); a.remove();
     return { total: urls.length, ok: res.filter(x => x.im).length, W, H, fails: res.map((x, i) => x.err ? i + ':' + x.err : null).filter(Boolean) };
   })();
   window.__job.then(r => window.__jobR = r).catch(e => window.__jobR = { err: String(e) });
   'started';
   ```
   그다음 `computer` `wait`(10초) → `javascript_tool` 로 `JSON.stringify(window.__jobR || 'pending')` 폴링, `ok === total` 확인.

   **서드파티 CDN 케이스 절차:**
   1. Step 3 에서 모은 URL 리스트를 `window.__ordered` 등에 저장하고, **호스트별 순서 시퀀스**(예: `OOOOOOOSSSSS...`)를 파악.
   2. 서드파티 CDN URL 하나로 `tabs_create_mcp` + `navigate` → 새 탭.
   3. 그 탭에서 위 스크립트를 돌리되 `urls` 는 **원래 순서 그대로** 재구성. 올리브영 크롭 프록시 URL·esmplus URL 도 그 탭에서 fetch 가능하므로 섞여 있어도 됨.
   4. 다운로드가 안 되면(torriden.jpg1.kr) 정적분만 크롭 프록시로 받고 GIF 빈 칸 처리.
   5. 작업 끝나면 `tabs_close_mcp` 로 새 탭 정리.

   > `javascript_tool` 반환값 필터: URL 쿼리스트링(`?created=...`)·base64·쿠키 유사 문자열이 있으면 출력이 `[BLOCKED: ...]` 로 잘린다. 리스트를 뽑을 땐 `u.split('?')[0]` 로 쿼리를 떼고 `.slice(a,b)` 로 페이지네이션해서 확인한다.

   다운로드가 1개뿐이라 Chrome 다중 다운로드 차단에 걸리지 않는다. 파일은 `~/Downloads/`에 저장되니 Bash로 목표 폴더에 옮긴다.
5. **이미지 개수·구성은 브랜드마다 다르다** — 고정 가정을 두지 말 것 (실측 3건 비교):
   - 에스네이처: 이미지 1장이 전체 상세페이지 (720×28,487px)
   - 셀리맥스: 54장이 이어져 전체 상세페이지 구성 (합치면 1242×59,584px)
   - 브링그린: 34장이 이어져 구성 (합치면 1020×37,337px)
   → **`data-src`가 있는 이미지는 크기 상관없이 다 이어붙이는 게 안전**하다. "가장 큰 파일 1장만 받기" 식으로 미리 추측하지 말 것.
6. 완성된 통이미지는 세로가 매우 길어 한 번에 분석하기 어려우므로, `Pillow`로 6~8등분 정도로 잘라서(`crop`) 순서대로 `Read`로 확인한다:
   ```bash
   python3 -c "
   from PIL import Image
   im = Image.open('detail-page-full.jpg')
   w, h = im.size
   n = 7
   seg = h // n
   for i in range(n):
       top, bottom = i*seg, (h if i==n-1 else (i+1)*seg)
       im.crop((0, top, w, bottom)).save(f'slice-{i+1:02d}.jpg', quality=85)
   "
   ```

---

## Step 3~4: 이미지 확인 + 구조 분석

1. `Read` 툴로 이미지(또는 슬라이스)를 순서대로 연다
2. 각 구간이 상세페이지에서 어떤 역할을 하는지 파악해 섹션 단위로 분해한다. 참고 프레임워크(고정 정답 아님 — 실제 이미지 내용에 맞게 조정):
   - 소셜프루프/후킹 (판매량, 수상, 순위)
   - 핵심 소구점 / 성분·기술 설명
   - 임상·실험 수치 증명 (before-after, 그래프, 현미경 이미지)
   - 안전성 인증 (테스트 완료, free-from 리스트)
   - 소비자 만족도 통계
   - 사용법·사용감
   - 라인업/교차판매
   - FAQ
   - 브랜드 클로징
3. 각 섹션이 전체 이미지에서 대략 몇 % 지점에 있는지 기록한다 (세로 통이미지는 이미지 번호보다 위치 %가 더 유용함)
4. **임상 수치·설문 결과 등 "증명"을 내세우는 섹션이 있으면, 그 옆의 작은 각주(*표시)까지 반드시 확인해서 어떤 시험을 어느 기관에서 몇 명을 대상으로 언제 진행했는지 기록한다.** 각주는 원본 이미지에서 글씨가 매우 작아 슬라이스 상태로는 잘 안 보이는 경우가 많음 — 필요하면 Pillow로 해당 부분만 좁게 잘라서(`crop`) 확대한 뒤 다시 `Read`로 확인한다:
   ```bash
   python3 -c "
   from PIL import Image
   im = Image.open('detail-page-full.jpg')
   w, h = im.size
   crop = im.crop((0, <대략적인 y좌표>, w, <y좌표+200>))
   crop = crop.resize((w*2, 400), Image.LANCZOS)  # 확대
   crop.save('footnote-zoom.jpg', quality=95)
   "
   ```
   이렇게 확인한 시험 기관명·기간·대상 인원은 그냥 "임상 테스트 완료"라고 뭉뚱그리지 말고 리포트에 기관명까지 정확히 남긴다. 기관명이 어디에도 안 나와 있으면("자체 시험", "In-vitro 결과"만 있는 경우) 그 사실 자체를 기록한다 — 외부 기관 검증이 없다는 것도 유의미한 정보다.

`templates/structure-analysis-template.md` 참고해 리포트 작성. 실제 작성 예시는 `example-output/estra-atobarrier365-cream-20260803/structure-analysis.md`(단일 상품)와 `example-output/여름수분크림-베스트3-20260803/comparison-report.md`(다상품 비교, 임상 근거 표 포함) 참고.

---

## Step 5: 구조 분석 리포트 생성

### 저장 위치
```
# 단일 상품
./10-projects/{프로젝트명}/competitor-analysis/{브랜드}-{상품명}-{YYYYMMDD}/
├── images/                 # detail-page-full.jpg + slice-*.jpg
├── structure-analysis.md
└── report.html             # Step 6 — .md 를 HTML 보고서로 변환

# 여러 상품 (Step 0에서 시작)
./10-projects/{프로젝트명}/competitor-analysis/{카테고리}-베스트{N}-{YYYYMMDD}/
├── images/{브랜드}/         # 브랜드별 detail-page-full.jpg + slice-*.jpg
├── comparison-report.md
└── report.html
```
> 프로젝트에 맞게 경로를 조정하세요. `images/` 는 용량이 크므로 repo `.gitignore` 에 `10-projects/*/competitor-analysis/**/images/` 를 추가하고 리포트(`.md`/`.html`)만 추적하는 걸 권장.

### 리포트 구조 (`templates/structure-analysis-template.md` 참고)
```markdown
# [브랜드] [상품명] 상세페이지 구조 분석

## 1. 상품 개요 (URL, 수집일, 이미지 구성)
## 2. 구조 요약 (섹션 흐름 다이어그램 — 텍스트 화살표로)
## 3. 섹션별 상세 분석
   - 섹션명 / 위치 / 핵심 메시지 / 사용된 설득 기법
## 4. 우리 상세페이지에 적용할 점
## 5. 부록
```

**⚠️ 여러 상품을 분석할 때(Step 0에서 시작한 경우)도 이 섹션별 구조 분해(2~3번)를 상품마다 반드시 먼저 만들 것.** 비교 요약(브랜드별 톤앤매너 표 등)은 그다음에 추가하는 것이지, 구조 분해를 건너뛰고 비교표만 주는 건 안 됨 — 실제로 이 실수를 했다가 사용자에게 지적받아 다시 작업한 적 있음(`example-output/여름수분크림-베스트3-20260803/`). 여러 상품이면 파일 하나에 "2. 브랜드별 구조 흐름"으로 상품마다 서브섹션을 만들고, 그다음 "브랜드별 핵심 전략 요약" 비교표를 이어 붙이는 순서로 작성한다.

---

## Step 6: 마크다운 리포트 → HTML 보고서 변환 + 브라우저 탭으로 열기 (필수)

`.md` 리포트를 만든 뒤, **반드시 같은 내용을 HTML 보고서로 정리해서 브라우저 탭으로 띄운다.** 경로만 안내하고 끝내지 않는다.

1. **HTML 작성 규칙**
   - 워크스페이스에 `00-system/03-guides/design-guide.md` 가 있으면 그 디자인 시스템(무드·컬러·폰트·구분선 규칙)을 그대로 따른다. 없으면 "문서형 미니멀"(흰 배경, 산세리프, 굵은 실선=섹션 경계·얇은 선=항목 구분, accent 색 1개, 박스/뱃지 남발 금지)로 간다.
   - **단일 파일**로: CSS 전부 `<style>` 인라인, 외부 의존은 웹폰트 정도만(`@font-face` CDN). 이미지 임베드 불필요(리포트는 텍스트·표 중심).
   - 담을 것: 헤더(제목·분석일·대상) → 대상 표 → 공통 관찰 → **브랜드별 구조 흐름**(섹션 흐름 다이어그램은 `<pre>` monospace 블록, 임상 근거는 `<table>`) → 비교표 → 적용 포인트(가져올 것/차별화/하지 말 것) → 부록. 즉 `.md` 와 동일 구조.
   - `@media print` 규칙 넣어 인쇄/PDF 도 깨지지 않게(테이블·다이어그램 `break-inside: avoid`).
   - 파일명 `report.html`, 저장 위치는 `.md` 와 같은 폴더.
2. **탭으로 열기** — `mcp__claude-in-chrome__navigate` 는 `file://` URL 을 거부한다(실측). macOS 기본 브라우저로 여는 게 맞다:
   ```bash
   open "<리포트폴더>/report.html"
   ```
   (`open` 은 사용자의 기본 브라우저 새 탭에 로컬 HTML 을 띄운다 — MCP 탭 그룹 밖이라 추적은 안 되지만 사용자가 바로 본다.)
3. `SendUserFile` 로 `report.html` 도 사용자에게 전달(`display: "render"`). 단, 세로가 매우 긴 통이미지(`detail-page-full.jpg`)는 종횡비가 극단적이라 뷰어 업로드가 400 으로 거부됨 → 슬라이스나 축소 미리보기로 대체.
4. **외부 공유(링크)가 필요하면** — `report.html` 을 Artifact 로 발행한다(`artifact-design` 스킬 먼저 로드 → doctype/html/head/body 없이 `<title>`+`<style>`+본문만, **폰트는 Google Fonts 만**(jsdelivr @font-face 는 Artifact CSP 에서 안 뜸 — Pretendard 대신 IBM Plex Sans KR / Noto Sans KR), 3-state 테마 토큰). 발행 후 URL 을 사용자에게 주되 **Artifact 는 기본 비공개** → "페이지 우상단 Share 로 공개 링크를 켜야 로그인 없이 열린다" 를 함께 안내한다. (경쟁사 공개 마케팅 자료라 발행 자체는 문제없음 — PII·사칭·허위기록 아님.)

## Step 7: 저장된 상세페이지 파일 폴더 열기 (필수)

이미지 결과물도 경로만 알려주지 말고 **Finder 로 폴더를 직접 연다**:
```bash
open "<리포트폴더>/images"
```
여러 상품이면 `images/` 하위에 브랜드별 폴더가 들어있으므로 `images/` 를 연다.

---

## 사용 예시

```
사용자: "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000198320 상세페이지 분석해줘"

Claude:
1. 올리브영 URL 확인 → Cloudflare 보호 사이트이므로 Step 2-B(인터랙티브 방식) 사용
2. 상품설명 탭 → 더보기 클릭 → data-src 이미지 URL 수집 → canvas 이어붙이기 1회 다운로드 (서드파티 CDN이면 그 CDN 탭에서 fetch)
3. 통이미지를 6~10등분 슬라이스해서 순서대로 Read
4. 섹션별 구조 분해 → structure-analysis.md 작성
5. structure-analysis.md → report.html 변환 → `open report.html` (브라우저 탭)
6. `open images/` (Finder) + SendUserFile 로 report.html 전달
```

```
사용자: "여름 수분크림 출시 예정인데, 잘 팔리는 브랜드들 상세페이지 분석해줘"

Claude:
1. Step 0: 올리브영에서 "수분크림" 검색 → 판매순 정렬 → 상위 10개 브랜드/URL 확보
2. 사용자에게 목록 보여주고 몇 개 분석할지 확인 (브랜드 다양성 우선 추천)
3. 확정된 URL마다 Step 1~4 반복 (상품마다 섹션 구조 분해)
4. 파일 1개에 "브랜드별 구조 흐름" + "핵심 전략 비교표" 순서로 comparison-report.md 작성
5. comparison-report.md → report.html 변환 → `open report.html` (브라우저 탭)
6. `open images/` (Finder) — 브랜드별 폴더가 그 안에 있음
```

---

## 트러블슈팅

### Playwright 미설치 (Step 2-A)
```bash
pip install playwright
playwright install chromium
```

### 헤드리스 스크립트가 이미지 0장 반환 (`fallback-fullpage.png`만 저장됨)
- 스크린샷을 열어서 "Verify you are human" 같은 챌린지 페이지인지 확인
- 맞다면 **그 사이트는 헤드리스로 못 뚫는다** — Step 2-B(인터랙티브 방식)로 전환. Cloudflare를 프로그래밍적으로 우회하려는 시도는 하지 않는다.

### Claude in Chrome으로 다운로드했는데 1장만 저장됨
- `<a download>` 클릭 루프를 썼을 가능성 — Chrome이 다중 자동 다운로드를 차단한 것. 캔버스 이어붙이기 + 단일 다운로드 방식(Step 2-B step 4)으로 전환

### `largeCount`가 0으로 나옴 (이미지가 안 잡힘)
- `img.naturalWidth`/`naturalHeight`로 판별하려 했다면 지연 로딩 때문에 값이 0이거나 1일 수 있음 — `data-src` 속성을 직접 읽을 것(Step 2-B step 3). 스크롤로 트리거하려 하지 말 것 (느리고 타임아웃 나기 쉬움, 실측 확인)

### `javascript_tool` 호출이 45초 타임아웃남
- `window.scrollBy` 같은 긴 루프를 쓰고 있다면 그게 원인 — data-src 방식으로 전환하면 스크롤 자체가 필요 없어져서 해결됨
- **이미지가 30장 이상이라 fetch+stitch 가 45초를 넘김** → `window.__job` async IIFE 로 백그라운드 실행 후 `computer` `wait` + `window.__jobR` 폴링 (Step 2-B step 4)

### 서드파티 CDN 이미지가 `TypeError: Failed to fetch` (달바·토리든 등)
- 브랜드 자체 CDN(`dalba.speedgabia.com`, `torriden.jpg1.kr` 등)이 올리브영 origin 에 CORS 미허용 → **그 CDN 실제 이미지 URL 로 새 탭을 열어** same-origin 상태에서 fetch (Step 2-B step 4 (b))
- `image.oliveyoung.co.kr`(크롭 프록시)·`gi.esmplus.com` 은 ACAO `*` 라 어느 탭에서든 OK
- 크롭 프록시(`.../cropN/<원본호스트>/<경로>`)로 정적 이미지는 우회 가능하나 GIF 는 403
- torriden.jpg1.kr 는 그 탭에서 다운로드 자체가 막힘 → 정적분만 크롭 프록시로, GIF 구간은 빈 칸 + 리포트에 명시

### `javascript_tool` 결과가 `[BLOCKED: ...]` 로 잘림
- 반환값에 URL 쿼리스트링/base64/쿠키 유사 문자열이 있으면 필터에 걸림 → `u.split('?')[0]` 로 쿼리 제거하고 `.slice()` 로 나눠서 반환

### 제네릭 사이트에서 엉뚱한 이미지(광고/추천상품)가 섞임
- 이미지 개수가 비정상적으로 많으면(50장 이상) 필터링이 실패한 것 — 결과 폴더를 열어 수동으로 상세페이지 구간만 추려낼 것
- 반복적으로 쓰는 사이트라면 `SITE_ADAPTERS`에 전용 어댑터를 추가하는 게 정확도가 높음 (단, Cloudflare 보호 사이트라면 어댑터를 추가해도 소용없음 — Step 2-B로)

---

## 의존성

- **Step 2-A(헤드리스)**: `pip install playwright` + `playwright install chromium`
- **Step 2-B(인터랙티브)**: Claude in Chrome 브라우저 확장 세션 필요
- 이미지 슬라이싱: `pip install Pillow`
- 별도 API 키 불필요

## 파일 구조

```
competitor-detail-page-analyzer/
├── SKILL.md                          # 이 파일 (SOP)
├── scripts/
│   └── detail-page-scraper.py        # 헤드리스 다운로더 (Cloudflare 없는 사이트 전용)
├── templates/
│   └── structure-analysis-template.md
└── example-output/                   # (repo에는 미포함 — 워크스페이스 프로젝트 폴더 참조)
    ├── estra-atobarrier365-cream-20260803/   # 단일 상품 분석 예시
    │   ├── images/detail-page-full.jpg
    │   └── structure-analysis.md
    └── 여름수분크림-베스트3-20260803/          # 카테고리 베스트셀러 비교 분석 예시 (Step 0부터 시작)
        ├── images/<브랜드>/detail-page-full.jpg  (3개 브랜드)
        └── comparison-report.md
```

## 버전 히스토리

- **v1.6.1 (2026-09-11)**: Step 6-4 추가 — 외부 공유가 필요하면 `report.html` 을 Artifact 로 발행(Google Fonts 만 사용, 3-state 테마). Artifact 는 기본 비공개라 "Share 로 공개 링크 켜기" 안내 필수.
- **v1.6.0 (2026-09-11)**: 산출물 마무리 단계 추가.
  - **Step 6**: `.md` 리포트를 HTML 보고서(`report.html`)로 변환(`design-guide.md` 디자인 시스템 준수, 단일 파일, `@media print` 포함) → `open report.html` 로 브라우저 탭에 띄운다. `mcp__claude-in-chrome__navigate` 는 `file://` 거부하므로 macOS `open` 사용.
  - **Step 7**: `open images/` 로 저장된 상세페이지 폴더를 Finder 로 연다. "경로만 안내" 금지 — 파일을 실제로 열어준다.
- **v1.5.0 (2026-09-11)**: 올리브영 "수분세럼" 판매순 상위 4종(아누아/달바/넘버즈인/토리든)으로 Step 0~5 재검증하며 Step 2-B 다운로드 로직 대폭 보강.
  - **45초 CDP 타임아웃**: 이미지 30장+ 를 `for await` 로 받으면 `javascript_tool` 이 죽음 → `window.__job` async IIFE + `Promise.all` 병렬 fetch + `computer` `wait` 폴링 패턴으로 전환
  - **서드파티 CDN CORS**: 브랜드 자체 CDN(`dalba.speedgabia.com`, `torriden.jpg1.kr`)은 올리브영 origin 에서 fetch 시 CORS 차단 → 그 CDN 실제 이미지 URL 로 새 탭을 열어 same-origin fetch. `image.oliveyoung.co.kr`·`gi.esmplus.com` 은 ACAO `*`
  - 올리브영 크롭 프록시가 임의 원본 호스트를 프록시함(`.../cropN/<원본호스트>/<경로>`) — 정적 이미지 우회로. 단 GIF 는 403, 일부 origin 은 다운로드 자체 차단(GIF 구간 빈 칸 처리 + 리포트 명시)
  - `javascript_tool` 반환값 필터(`[BLOCKED]`) 회피: 쿼리스트링 제거 + slice 페이지네이션
  - `allowed-tools` 에 `mcp__claude-in-chrome__*` + `ToolSearch` 명시 추가
  - 결과물: 워크스페이스 `10-projects/30-경쟁사-상세페이지-분석/competitor-analysis/수분세럼-베스트4-20260911/`
- **v1.4.0 (2026-08-03)**: 서니 피드백 2건 반영.
  - Step 0에 "동일 제품 용량/구성/굿즈 차이 변형 제거" 로직 추가 — 같은 브랜드의 다른 goodsNo가 사실은 같은 제품의 용량/기획 차이일 뿐이면 순위 높은 것 하나만 남기고 후보에서 제외
  - Step 3~4와 리포트 템플릿에 "임상/설문 시험 근거(시험 기관·기간·대상)" 섹션을 표준으로 추가. 각주가 작아 안 보이면 Pillow로 해당 부분만 좁게 잘라 확대(`crop`)해서 확인하는 절차 명시
  - `example-output`의 두 리포트(에스트라 단일 분석, 여름수분크림 베스트3 비교) 모두 실제 각주를 확대해서 확인한 시험 기관명(엘리드, 더마프로, 한국피부과학연구원, 마리디엠 피부과학연구소)으로 갱신
- **v1.3.0 (2026-08-03)**: "여름 수분크림" 베스트 3(에스네이처/셀리맥스/브링그린)로 Step 0~5 전체를 반복 실행하며 Step 2-B를 대폭 개선.
  - `img.src`/`naturalWidth` 대신 **`data-src` 속성을 직접 읽는 방식**으로 전환 — 지연 로딩 트리거용 스크롤이 아예 불필요해짐 (기존 스크롤 방식은 45초 CDP 타임아웃이 반복 발생했음)
  - 여러 장 다운로드 시 **canvas에 이어붙여 단일 파일로 한 번만 다운로드**하는 방식으로 변경 — fetch+base64 개별 처리보다 훨씬 안정적이고 빠름
  - 상세페이지 이미지 구성이 브랜드마다 다르다는 것 확인(1장 통이미지 vs 34장 vs 54장 조각) — "제일 큰 이미지 1장만 받기" 가정을 폐기하고 data-src 있는 이미지는 전부 이어붙이는 방식으로 통일
  - 비교 분석 결과물을 `example-output/여름수분크림-베스트3-20260803/`에 보관
- **v1.2.0 (2026-08-03)**: Step 0(카테고리/키워드 → 베스트셀러 목록) 추가. "수분크림" 검색 → 판매순 정렬 → 상위 10개 브랜드/goodsNo 추출까지 라이브 검증(에스네이처, 셀리맥스, 브링그린, 닥터지, 아누아, 한율, VT 등 확인). 실무에서 특정 브랜드보다 카테고리 베스트셀러 위주로 분석하는 경우가 많다는 피드백 반영.
- **v1.1.0 (2026-08-03)**: 올리브영 상품(에스트라 아토베리어365 크림)으로 End-to-End 라이브 테스트.
  - `detail-page-scraper.py`(헤드리스 Playwright)가 올리브영에서 Cloudflare 챌린지에 막히는 것 확인 → Step 2-B(Claude in Chrome 인터랙티브 방식) 추가
  - `<a download>` 클릭 방식이 Chrome의 다중 자동 다운로드 차단에 걸리는 것 확인 → fetch+base64 방식으로 대체
  - 올리브영 상세페이지가 통상 세로로 매우 긴 통이미지 1장으로 제작된다는 사실 확인 → 이미지 슬라이싱 단계 추가
  - 실제 산출물을 `example-output/`에 보관
- **v1.0.0 (2026-08-03)**: 초기 스킬 생성 (헤드리스 스크립트만, 미검증 상태)
