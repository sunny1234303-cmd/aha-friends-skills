#!/usr/bin/env python3
"""네이버 키워드도구 + 데이터랩 리포트: 검색량/경쟁정도 + 성수기/비수기 트렌드 분석.

이 스크립트에는 실제 계정 정보나 키워드 데이터를 하드코딩하지 않는다.
NAVER_AD_ACCESS_LICENSE 등 5개 값은 .gitignore로 제외된 로컬 scripts/.env에서만 읽는다.

의존성: pip install pandas python-dotenv
"""

import argparse
import hashlib
import hmac
import base64
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR / ".env")

import os

NAVER_AD_ACCESS_LICENSE = os.getenv("NAVER_AD_ACCESS_LICENSE")
NAVER_AD_SECRET_KEY = os.getenv("NAVER_AD_SECRET_KEY")
NAVER_AD_CUSTOMER_ID = os.getenv("NAVER_AD_CUSTOMER_ID")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

MAX_TREND_KEYWORDS = 5  # 데이터랩 API 자체 제약


def _require_ad_keys():
    if not all([NAVER_AD_ACCESS_LICENSE, NAVER_AD_SECRET_KEY, NAVER_AD_CUSTOMER_ID]):
        sys.exit(
            "[오류] 검색광고 API 키가 설정되지 않았습니다. "
            "scripts/.env에 NAVER_AD_ACCESS_LICENSE / NAVER_AD_SECRET_KEY / NAVER_AD_CUSTOMER_ID를 넣으세요."
        )


def generate_signature(timestamp: str, method: str, uri: str) -> str:
    message = f"{timestamp}.{method}.{uri}"
    signature = hmac.new(
        NAVER_AD_SECRET_KEY.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).digest()
    return base64.b64encode(signature).decode("utf-8")


def get_keyword_stats(keywords, include_related: bool = True):
    _require_ad_keys()
    timestamp = str(int(time.time() * 1000))
    uri = "/keywordstool"
    signature = generate_signature(timestamp, "GET", uri)

    headers = {
        "X-Timestamp": timestamp,
        "X-API-KEY": NAVER_AD_ACCESS_LICENSE,
        "X-Customer": NAVER_AD_CUSTOMER_ID,
        "X-Signature": signature,
        "Content-Type": "application/json",
    }
    params = {"hintKeywords": ",".join(keywords), "showDetail": "1"}
    if include_related:
        params["includeHintKeywords"] = "1"

    url = "https://api.searchad.naver.com" + uri + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, method="GET", headers=headers)
    try:
        response = urllib.request.urlopen(request)
        return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit(f"[오류] 키워드도구 API 오류: {e.code}")


def get_trend(keywords, days: int = 90, time_unit: str = "month"):
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        sys.exit(
            "[오류] 데이터랩 API 키가 설정되지 않았습니다. "
            "scripts/.env에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET을 넣으세요."
        )

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    keyword_groups = [{"groupName": kw, "keywords": [kw]} for kw in keywords[:MAX_TREND_KEYWORDS]]

    body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": time_unit,
        "keywordGroups": keyword_groups,
    }

    url = "https://openapi.naver.com/v1/datalab/search"
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    request.add_header("Content-Type", "application/json")
    try:
        response = urllib.request.urlopen(request, data=json.dumps(body).encode("utf-8"))
        return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit(f"[오류] 데이터랩 API 오류: {e.code}")


def parse_volume(value):
    if isinstance(value, str):
        return 10 if "< 10" in value else int(value.replace(",", ""))
    return value or 0


def normalize_competition(comp):
    if not comp or comp == "-":
        return "낮음"
    mapping = {
        "HIGH": "높음", "high": "높음", "높음": "높음",
        "MEDIUM": "중간", "medium": "중간", "중간": "중간", "보통": "중간",
        "LOW": "낮음", "low": "낮음", "낮음": "낮음",
    }
    return mapping.get(str(comp).strip(), "낮음")


def format_keyword_results(api_result) -> pd.DataFrame:
    if not api_result or "keywordList" not in api_result:
        return pd.DataFrame()
    rows = []
    for kw in api_result["keywordList"]:
        pc_qc = parse_volume(kw.get("monthlyPcQcCnt", 0))
        mo_qc = parse_volume(kw.get("monthlyMobileQcCnt", 0))
        rows.append({
            "연관키워드": kw.get("relKeyword", ""),
            "PC": pc_qc,
            "모바일": mo_qc,
            "PC_클릭": round(float(kw.get("monthlyAvePcClkCnt", 0) or 0), 1),
            "모바일_클릭": round(float(kw.get("monthlyAveMobileClkCnt", 0) or 0), 1),
            "경쟁정도": normalize_competition(kw.get("compIdx")),
            "광고수": int(float(kw.get("plAvgDepth", 0) or 0)),
            "_총검색량": pc_qc + mo_qc,
        })
    df = pd.DataFrame(rows)
    return df.sort_values(by="_총검색량", ascending=False, ignore_index=True)


def format_trend_results(api_result) -> pd.DataFrame:
    if not api_result or "results" not in api_result:
        return pd.DataFrame()
    rows = []
    for group in api_result["results"]:
        for point in group["data"]:
            rows.append({"키워드": group["title"], "날짜": point["period"], "검색지수": point["ratio"]})
    df = pd.DataFrame(rows)
    if len(df):
        df["날짜"] = pd.to_datetime(df["날짜"])
        df = df.sort_values(by="날짜")
    return df


def analyze_trend_seasons(trend_df: pd.DataFrame):
    if trend_df is None or len(trend_df) == 0:
        return {}

    analysis = {}
    for kw in trend_df["키워드"].unique():
        kw_data = trend_df[trend_df["키워드"] == kw].copy()
        kw_data["월"] = kw_data["날짜"].dt.month
        kw_data["월이름"] = kw_data["날짜"].dt.strftime("%m월")

        overall_avg = kw_data["검색지수"].mean()
        monthly_avg = kw_data.groupby(["월", "월이름"])["검색지수"].mean().reset_index().sort_values("월")

        high_threshold = overall_avg * 1.2
        low_threshold = overall_avg * 0.8
        peak_months = monthly_avg[monthly_avg["검색지수"] >= high_threshold]["월이름"].tolist()
        off_months = monthly_avg[monthly_avg["검색지수"] <= low_threshold]["월이름"].tolist()

        if len(kw_data) >= 2:
            y = kw_data["검색지수"].values
            slope = (y[-1] - y[0]) / len(y)
            trend = "상승" if slope > 1 else "하락" if slope < -1 else "유지"
        else:
            trend = "데이터 부족"

        std = kw_data["검색지수"].std()
        volatility = (std / overall_avg * 100) if overall_avg else 0
        volatility_desc = "높음 (계절성 뚜렷)" if volatility > 30 else "보통" if volatility > 15 else "낮음 (안정적)"

        analysis[kw] = {
            "overall_avg": round(overall_avg, 1),
            "peak_months": peak_months or ["없음"],
            "off_months": off_months or ["없음"],
            "trend": trend,
            "volatility": volatility_desc,
        }
    return analysis


def build_report(keyword_df, trend_analysis, keywords, days) -> str:
    lines = [f"# 네이버 키워드·트렌드 리포트 ({datetime.now().date()})\n"]

    lines.append("## 1. 키워드 검색량 (총검색량 순)\n")
    lines.append("| 연관키워드 | PC | 모바일 | PC 클릭 | 모바일 클릭 | 경쟁정도 | 광고수 |")
    lines.append("|---|---|---|---|---|---|---|")
    for _, r in keyword_df.iterrows():
        lines.append(f"| {r['연관키워드']} | {r['PC']} | {r['모바일']} | {r['PC_클릭']} | {r['모바일_클릭']} | {r['경쟁정도']} | {r['광고수']} |")

    lines.append(f"\n## 2. 트렌드 요약 (최근 {days}일, 최대 {MAX_TREND_KEYWORDS}개 키워드)\n")
    if len(keywords) > MAX_TREND_KEYWORDS:
        skipped = keywords[MAX_TREND_KEYWORDS:]
        lines.append(f"> 데이터랩 API 제약으로 다음 키워드는 트렌드 분석에서 제외됨: {', '.join(skipped)}\n")
    lines.append("| 키워드 | 평균 검색지수 | 성수기 | 비수기 | 추세 | 변동성 |")
    lines.append("|---|---|---|---|---|---|")
    for kw, a in trend_analysis.items():
        lines.append(f"| {kw} | {a['overall_avg']} | {', '.join(a['peak_months'])} | {', '.join(a['off_months'])} | {a['trend']} | {a['volatility']} |")

    lines.append("\n## 3. 다음 액션\n")
    lines.append("- 경쟁정도 낮고 총검색량 높은 키워드부터 콘텐츠/광고 우선순위로 검토")
    lines.append("- 성수기 1~2개월 전에 관련 콘텐츠를 미리 준비해 검색 상승기에 노출 확보")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="네이버 키워드도구 + 데이터랩 리포트 생성")
    parser.add_argument("--keywords", required=True, help="쉼표로 구분한 키워드 목록")
    parser.add_argument("--trend-days", type=int, default=90)
    parser.add_argument("--out", default=None, help="결과 저장 경로 (미지정 시 표준출력)")
    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    keyword_raw = get_keyword_stats(keywords)
    keyword_df = format_keyword_results(keyword_raw)
    if keyword_df.empty:
        sys.exit("[알림] 키워드 조회 결과가 없습니다.")

    trend_raw = get_trend(keywords, days=args.trend_days)
    trend_df = format_trend_results(trend_raw)
    trend_analysis = analyze_trend_seasons(trend_df)

    report = build_report(keyword_df, trend_analysis, keywords, args.trend_days)

    if args.out:
        out_path = Path(args.out)
        if str(out_path).startswith(str(SCRIPT_DIR.parent)):
            sys.exit("[오류] 실제 데이터 리포트를 스킬 폴더 안에 저장하려고 합니다 — SKILL.md 상단 원칙 위반. "
                      "프로젝트 폴더(예: 10-projects/{프로젝트명}/keyword-analysis/)를 지정하세요.")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"저장 완료: {out_path}")
    else:
        print(report)


if __name__ == "__main__":
    main()
