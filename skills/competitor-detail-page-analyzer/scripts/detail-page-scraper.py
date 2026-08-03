#!/usr/bin/env python3
"""
경쟁사 상세페이지 이미지 다운로더 (헤드리스 전용 — Cloudflare 없는 사이트에서만 동작)

Playwright로 실제 페이지를 열어(사이트별 어댑터에 따라 탭/더보기 클릭 수행),
상세페이지 이미지를 원본 해상도로 다운로드한다. 별도 API 키 불필요.

⚠️ 올리브영(oliveyoung.co.kr)에서는 Cloudflare 봇 탐지에 막혀 작동하지 않음
   (2026-08-03 실측 확인 — "Verify you are human" 챌린지 페이지가 대신 반환됨).
   올리브영은 SKILL.md의 Step 2-B(Claude in Chrome 인터랙티브 방식)를 사용할 것.
   이 스크립트는 Cloudflare 등 봇 탐지가 없는 사이트 전용으로 남겨둔다.

사용법:
  python3 detail-page-scraper.py <URL> --out <출력폴더> [--headed]

예시:
  python3 detail-page-scraper.py "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000198320" \
      --out /tmp/competitor-detail/estra-atobarrier365-cream
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse


class Colors:
    BLUE = '\033[0;34m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'


def log(text, color=Colors.NC):
    print(f"{color}{text}{Colors.NC}")


# ── 사이트별 어댑터 ──────────────────────────────────────
# 각 어댑터는 detail_image_urls(page) -> list[str] 를 구현한다.
# 올리브영은 실제 상품 페이지에서 라이브로 검증됨 (v1.0.0, 2026-08-03).

def oliveyoung_adapter(page, log_fn):
    # 1. "상품설명" 탭 클릭 (기본 탭이 아닐 수 있음)
    try:
        tab = page.get_by_text("상품설명", exact=True).first
        if tab.count() > 0:
            tab.click()
            page.wait_for_timeout(800)
    except Exception as e:
        log_fn(f"⚠️ 상품설명 탭 클릭 실패 (계속 진행): {e}", Colors.YELLOW)

    # 2. "상품설명 더보기" 버튼 클릭 (짧은 상세페이지는 버튼이 없을 수 있음)
    try:
        more_btn = page.get_by_text("상품설명 더보기", exact=True).first
        if more_btn.count() > 0:
            more_btn.scroll_into_view_if_needed()
            more_btn.click()
            page.wait_for_timeout(1000)
    except Exception as e:
        log_fn(f"ℹ️ 더보기 버튼 없음 또는 클릭 실패 (짧은 상세페이지일 수 있음): {e}", Colors.YELLOW)

    # 3. 상세 이미지 컨테이너에서 이미지 URL 수집
    #    클래스명은 CSS 모듈 해시가 붙으므로 prefix만 매칭
    urls = page.eval_on_selector_all(
        '[class*="GoodsDetailTabs_product-detail-tabs"] img',
        "els => els.map(e => e.currentSrc || e.src).filter(Boolean)"
    )
    return urls


def generic_adapter(page, log_fn):
    # 지연 로딩 유발을 위해 끝까지 스크롤
    page.evaluate("""
        async () => {
            await new Promise((resolve) => {
                let total = 0;
                const step = 600;
                const timer = setInterval(() => {
                    window.scrollBy(0, step);
                    total += step;
                    if (total >= document.body.scrollHeight) {
                        clearInterval(timer);
                        resolve();
                    }
                }, 150);
            });
        }
    """)
    page.wait_for_timeout(1000)

    # 폭 600px 이상, header/nav/footer 밖에 있는 이미지만 수집 (휴리스틱)
    urls = page.eval_on_selector_all(
        "img",
        """els => els
            .filter(e => (e.naturalWidth || e.width) >= 600)
            .filter(e => !e.closest('header, nav, footer'))
            .map(e => e.currentSrc || e.src)
            .filter(Boolean)
        """
    )
    return urls


SITE_ADAPTERS = [
    (re.compile(r"oliveyoung\.co\.kr"), "oliveyoung", oliveyoung_adapter),
]


def pick_adapter(url):
    for pattern, name, fn in SITE_ADAPTERS:
        if pattern.search(url):
            return name, fn
    return "generic", generic_adapter


def guess_extension(content_type, url):
    if content_type:
        if "jpeg" in content_type or "jpg" in content_type:
            return ".jpg"
        if "png" in content_type:
            return ".png"
        if "webp" in content_type:
            return ".webp"
    ext = Path(urlparse(url).path).suffix
    return ext if ext else ".jpg"


def download_images(urls, out_dir, page_url, log_fn):
    import requests

    out_dir.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Referer": page_url,
    }

    saved = []
    seen = set()
    idx = 0
    for raw_url in urls:
        abs_url = urljoin(page_url, raw_url)
        if abs_url in seen:
            continue
        seen.add(abs_url)
        idx += 1

        try:
            resp = requests.get(abs_url, headers=headers, timeout=15)
            resp.raise_for_status()
            ext = guess_extension(resp.headers.get("Content-Type", ""), abs_url)
            filename = f"img-{idx:02d}{ext}"
            filepath = out_dir / filename
            filepath.write_bytes(resp.content)
            saved.append({"file": filename, "source_url": abs_url, "bytes": len(resp.content)})
            log_fn(f"  ✓ {filename} ({len(resp.content)//1024}KB)", Colors.GREEN)
        except Exception as e:
            log_fn(f"  ✗ 다운로드 실패: {abs_url} ({e})", Colors.RED)

    return saved


def take_fallback_screenshot(page, out_dir, log_fn):
    path = out_dir / "fallback-fullpage.png"
    page.screenshot(path=str(path), full_page=True)
    log_fn(f"⚠️ 이미지 추출 실패 — 전체 페이지 스크린샷으로 대체: {path.name}", Colors.YELLOW)
    return path.name


def main():
    parser = argparse.ArgumentParser(description="경쟁사 상세페이지 이미지 다운로더")
    parser.add_argument("url", help="경쟁사 상품 상세페이지 URL")
    parser.add_argument("--out", required=True, help="출력 폴더 경로")
    parser.add_argument("--headed", action="store_true", help="브라우저 창을 띄워서 실행 (디버깅용)")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("❌ playwright가 설치되어 있지 않습니다.", Colors.RED)
        log("   설치: pip install playwright && playwright install chromium", Colors.YELLOW)
        sys.exit(1)

    out_dir = Path(args.out)
    adapter_name, adapter_fn = pick_adapter(args.url)

    log(f"\n{'='*60}", Colors.BLUE)
    log("🖼️  경쟁사 상세페이지 이미지 다운로더", Colors.BLUE)
    log(f"{'='*60}", Colors.BLUE)
    log(f"URL: {args.url}")
    log(f"어댑터: {adapter_name}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        try:
            page.goto(args.url, wait_until="networkidle", timeout=30000)
        except Exception:
            # networkidle 타임아웃은 흔함 (광고/추적 스크립트 계속 통신) — load 상태면 계속 진행
            pass
        page.wait_for_timeout(1500)

        urls = adapter_fn(page, log)
        log(f"🔍 이미지 URL {len(urls)}개 발견", Colors.BLUE)

        saved = []
        if urls:
            saved = download_images(urls, out_dir, args.url, log)

        fallback_screenshot = None
        if not saved:
            out_dir.mkdir(parents=True, exist_ok=True)
            fallback_screenshot = take_fallback_screenshot(page, out_dir, log)

        browser.close()

    meta = {
        "url": args.url,
        "adapter": adapter_name,
        "collected_at": datetime.now().isoformat(),
        "image_count": len(saved),
        "images": saved,
        "fallback_screenshot": fallback_screenshot,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    log(f"\n{'='*60}", Colors.GREEN)
    log(f"✅ 완료: 이미지 {len(saved)}개 저장 → {out_dir}", Colors.GREEN)
    log(f"{'='*60}\n", Colors.GREEN)

    print("💡 다음 단계:")
    print(f"   Claude: '{out_dir} 안의 이미지들 보고 상세페이지 구조 분석해줘'")


if __name__ == "__main__":
    main()
