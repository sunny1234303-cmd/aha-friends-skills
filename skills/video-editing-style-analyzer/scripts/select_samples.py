"""Step 1: 채널/영상 URL → 대표 샘플 영상 선정 → samples.json

채널: 최근 shorts 15개 후보 → 조회수/업로드일 확보 → (조회수 상위 3) ∪ (최신 3) 중복제거.
단일 영상: 그 영상 하나.

사용:
  python3 select_samples.py <URL> [--count 5] [--format shorts|videos] [--out DIR]
"""
import argparse
import os
import statistics
import sys

from _common import dump_json, slugify, yt_dlp_json


def _is_channel(url: str) -> bool:
    return any(s in url for s in ("/@", "/channel/", "/c/", "/user/")) and "/watch" not in url and "/shorts/" not in url


def _channel_base(url: str) -> str:
    url = url.rstrip("/")
    for tail in ("/shorts", "/videos", "/streams", "/featured", "/about"):
        if url.endswith(tail):
            url = url[: -len(tail)]
    return url


def _entry_meta(video_url: str) -> dict:
    d = yt_dlp_json("--no-playlist", video_url)
    return {
        "id": d.get("id"),
        "url": d.get("webpage_url") or video_url,
        "title": d.get("title"),
        "views": d.get("view_count"),
        "upload_date": d.get("upload_date"),
        "duration_sec": d.get("duration"),
        "width": d.get("width"),
        "height": d.get("height"),
        "fps": d.get("fps"),
        "is_short": (d.get("duration") or 999) <= 60,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--format", default="shorts", choices=["shorts", "videos"])
    ap.add_argument("--candidates", type=int, default=15)
    ap.add_argument("--out", default="./sty-out")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    if not _is_channel(args.url):
        meta = _entry_meta(args.url)
        samples = {
            "source_type": "video",
            "source_url": args.url,
            "channel_name": None,
            "format": "shorts" if meta["is_short"] else "long",
            "picked": [meta],
            "selection_reason": "단일 영상 입력 — 컷 호흡/샘플 신뢰도 낮음",
        }
        dump_json(samples, os.path.join(args.out, "samples.json"))
        print(f"단일 영상: {meta['title']}")
        return

    base = _channel_base(args.url)
    listing_url = f"{base}/{args.format}"
    print(f"채널 목록 조회: {listing_url}")
    try:
        listing = yt_dlp_json("--flat-playlist", "--playlist-end", str(args.candidates), listing_url)
    except RuntimeError as e:
        sys.exit(f"채널 {args.format} 목록을 못 읽었습니다. Shorts가 없는 채널일 수 있습니다.\n{e}")

    channel_name = listing.get("channel") or listing.get("uploader") or listing.get("title")
    entries = [e for e in (listing.get("entries") or []) if e.get("id")][: args.candidates]
    if not entries:
        sys.exit(f"{args.format} 항목이 없습니다.")

    print(f"후보 {len(entries)}개 메타 조회 중...")
    metas = []
    for e in entries:
        vurl = e.get("url") or f"https://www.youtube.com/watch?v={e['id']}"
        try:
            metas.append(_entry_meta(vurl))
        except RuntimeError as err:
            print(f"  건너뜀 {e['id']}: {err}", file=sys.stderr)

    if not metas:
        sys.exit("후보 영상 메타를 하나도 못 읽었습니다.")

    # 이상치 제거: 길이가 채널 중앙값의 2배 밖
    durs = [m["duration_sec"] for m in metas if m["duration_sec"]]
    med = statistics.median(durs) if durs else None
    if med:
        metas = [m for m in metas if m["duration_sec"] and 0.4 * med <= m["duration_sec"] <= 2.5 * med] or metas

    by_views = sorted(metas, key=lambda m: m["views"] or 0, reverse=True)
    by_recent = sorted(metas, key=lambda m: m["upload_date"] or "", reverse=True)

    picked, seen = [], set()
    half = max(1, args.count // 2)
    for m in by_views[:half + 1] + by_recent[: args.count]:
        if m["id"] not in seen:
            seen.add(m["id"])
            picked.append(m)
        if len(picked) >= args.count:
            break

    samples = {
        "source_type": "channel",
        "source_url": args.url,
        "channel_name": channel_name,
        "channel_slug": slugify(channel_name or args.url),
        "format": "shorts" if args.format == "shorts" else "long",
        "picked": picked,
        "selection_reason": f"조회수 상위권 + 최신순 섞어 {len(picked)}개 (후보 {len(metas)}개 중), 중복/이상치 제거",
    }
    dump_json(samples, os.path.join(args.out, "samples.json"))
    print(f"\n채널: {channel_name}  선정 {len(picked)}개:")
    for m in picked:
        print(f"  [{m['upload_date']}] {(m['views'] or 0):>9,}회  {m['duration_sec']}s  {m['title']}")


if __name__ == "__main__":
    main()
