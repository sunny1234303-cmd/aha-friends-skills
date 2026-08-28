"""(선택) CapCut draft 에서 폰트 블록을 뽑아 style-profile.json 에 심는다.

파이프라인은 pycapcut FontType(라틴 348종)만 지정할 수 있어 한글 폰트를 재현 못한다.
해결: 사용자가 CapCut 에서 원하는 폰트로 텍스트를 하나 만들어 저장 → 그 draft 에서
font 블록({resource_id, name})을 뽑아 프로필의 caption.font_capcut / overlay.font_capcut 에 넣으면,
이후 파이프라인이 그 폰트로 렌더한다 (style_utils.RawFont).

사용:
  1) CapCut 에서 새 프로젝트 → 텍스트 추가 → 원하는 한글 폰트 지정 → 저장
     (자막용, 오버레이용 서로 다르면 텍스트를 2개 만들고 각각 다른 폰트)
  2) python3 capture_font.py "<draft 폴더 경로>" --profile <style-profile.json> [--which caption|overlay|both]

  --which both (기본): 텍스트가 2개면 첫째=caption, 둘째=overlay. 1개면 둘 다 같은 폰트.
"""
import argparse
import glob
import json
import os
import sys

from _common import dump_json, load_json


def _extract_fonts(draft_dir: str) -> list:
    for fn in ("draft_content.json", "draft_info.json"):
        p = os.path.join(draft_dir, fn)
        if os.path.isfile(p):
            d = json.load(open(p, encoding="utf-8"))
            break
    else:
        sys.exit(f"draft_content.json 없음: {draft_dir}")

    out = []
    for t in d.get("materials", {}).get("texts", []):
        try:
            content = json.loads(t["content"])
            fb = content.get("styles", [{}])[0].get("font")
        except Exception:
            fb = None
        if not fb:
            continue
        rid = str(fb.get("id") or fb.get("resource_id") or "")
        path = fb.get("path", "")
        name = os.path.splitext(os.path.basename(path.replace("C:/", "")))[0] or "CustomFont"
        # Arimo(파이프라인 기본)는 건너뜀 — 사용자가 일부러 바꾼 것만
        if not rid or "arimo" in name.lower():
            continue
        entry = {"resource_id": rid, "name": name}
        if entry not in out:
            out.append(entry)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft_dir", help="CapCut draft 폴더 (…/com.lveditor.draft/<이름>)")
    ap.add_argument("--profile", help="심을 style-profile.json (생략하면 뽑기만)")
    ap.add_argument("--which", choices=["caption", "overlay", "both"], default="both")
    args = ap.parse_args()

    fonts = _extract_fonts(args.draft_dir)
    if not fonts:
        sys.exit("draft 에서 비-Arimo 폰트를 못 찾음. CapCut 에서 텍스트에 폰트를 지정하고 저장했는지 확인.")

    print("추출된 폰트 블록:")
    for i, f in enumerate(fonts):
        print(f"  [{i}] {f['name']}  (resource_id={f['resource_id']})")

    if not args.profile:
        print("\n--profile 을 주면 style-profile.json 에 심습니다.")
        return

    prof = load_json(args.profile)
    applied = prof.setdefault("applied", {})
    cap_font = fonts[0]
    ov_font = fonts[1] if len(fonts) > 1 else fonts[0]

    if args.which in ("caption", "both"):
        applied.setdefault("caption", {})["font_capcut"] = cap_font
        applied["caption"].pop("font", None)  # font_capcut 이 우선이므로 정리
    if args.which in ("overlay", "both"):
        applied.setdefault("overlay", {})["font_capcut"] = ov_font
        applied["overlay"].pop("font", None)

    # limitations 에서 폰트 항목 제거
    lims = prof.get("provenance", {}).get("limitations", [])
    prof["provenance"]["limitations"] = [x for x in lims if "FontType" not in x and "서체" not in x]

    dump_json(prof, args.profile)
    print(f"\n→ {args.profile} 에 심음")
    print(f"  caption.font_capcut = {cap_font['name']}")
    if args.which == "both":
        print(f"  overlay.font_capcut = {ov_font['name']}")


if __name__ == "__main__":
    main()
