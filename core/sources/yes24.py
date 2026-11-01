"""YES24 베스트셀러 수집 (PRD FR-40, 6.2).

근거: https://developers.yes24.com/api-doc/category-bestseller, FAQ (2026-10-26 확인)
- 전체 도서 정보를 모아 쌓는 것은 금지된다. data.json에는 화면에 보일 필드만 담고 빌드 때마다 덮어쓴다(책 소개는 담지 않음).
- 하루 1회만 부른다(10-27 결정). 받은 결과는 분석용으로 store/yes24_today.json에 하루치 한 벌만 덮어써 두고, 같은 날 빌드는 이것을 쓴다.
  그날 첫 호출이 실패하면 직전 보관분을 쓰고 실패 사실을 stale_error에 남긴다.
- 화면에는 예스24 출처 표기와 상세 링크(link)를 반드시 함께 보인다.

터미널 확인: python -m core.sources.yes24
"""
from dataclasses import dataclass
from datetime import datetime

import json
from datetime import timedelta, timezone

import pandas as pd

from core import config
from core.sources._http import ApiError, get_json
from core.sources.naver_news import clean_text

URL = "https://apis.yes24.com/v1/category/bestseller"
KST = timezone(timedelta(hours=9))


@dataclass
class BookResult:
    books: pd.DataFrame   # 순위, 제목, 저자, 출판사, ISBN, 상세 링크, 책 소개, 책 요약
    pub_date: datetime    # YES24 meta.pubDate (데이터 기준 시각)
    total_count: int
    from_cache: bool = False
    stale_error: str = None   # 오늘 호출이 실패해 직전 보관분을 쓴 경우 그 사유


def _save_cache(result, fetched_on):
    config.YES24_CACHE.parent.mkdir(exist_ok=True)
    config.YES24_CACHE.write_text(json.dumps({
        "fetched_on": fetched_on,
        "pub_date": result.pub_date.isoformat() if result.pub_date else None,
        "total_count": result.total_count,
        "books": result.books.to_dict(orient="records"),
    }, ensure_ascii=False), encoding="utf-8")


def _load_cache():
    if not config.YES24_CACHE.exists():
        return None, None
    raw = json.loads(config.YES24_CACHE.read_text(encoding="utf-8"))
    pub_date = datetime.fromisoformat(raw["pub_date"]) if raw["pub_date"] else None
    return raw["fetched_on"], BookResult(pd.DataFrame(raw["books"]), pub_date, raw["total_count"], from_cache=True)


def collect_bestsellers_daily(top_n=None):
    """오늘(KST) 이미 받았으면 보관분을, 아니면 API를 불러 보관분을 덮어쓴다."""
    today = datetime.now(KST).date().isoformat()
    fetched_on, cached = _load_cache()
    if cached is not None and fetched_on == today:
        return cached
    try:
        result = collect_bestsellers(top_n)
    except (ApiError, KeyError) as e:
        if cached is None:
            raise
        cached.stale_error = f"{e} ({fetched_on}에 받은 목록을 대신 씀)"
        return cached
    _save_cache(result, today)
    return result


def collect_bestsellers(top_n=None):
    top_n = top_n or config.YES24_TOP_N
    data = get_json("YES24", URL, headers={"X-Api-Key": config.get_key("YES24_API_KEY")},
                    params={"categoryId": config.YES24_CATEGORY_ID, "pageSize": top_n})
    body = data.get("data") or {}
    rows = []
    for item in body.get("items", []):
        detail = item.get("contentDetail") or {}
        rows.append({
            "순위": item.get("sortOrder"),
            "분류": item.get("goodsSortNm"),  # 예: 국내도서-소설/시/희곡 (categoryId=001은 국내도서 종합)
            "제목": clean_text(item.get("title")),
            "저자": clean_text(item.get("author")),
            "출판사": clean_text(item.get("publisher")),
            "ISBN": item.get("isbn13"),
            "상세 링크": item.get("link"),
            "책 소개": clean_text(detail.get("bookIntroduction")),
            "책 요약": clean_text(detail.get("bookSummary")),
        })
    pub_date = datetime.fromisoformat(body["meta"]["pubDate"]) if body.get("meta") else None
    return BookResult(pd.DataFrame(rows), pub_date, body.get("totalCount", 0))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    result = collect_bestsellers()
    books = result.books
    print(f"기준 시각 {result.pub_date}, 받은 {len(books)}권 / 전체 {result.total_count}권 (호출 1회)")
    print(f"책 소개가 있는 책 {(books['책 소개'] != '').sum()}권, 책 요약이 있는 책 {(books['책 요약'] != '').sum()}권")
    print(f"상세 링크가 빠진 책 {books['상세 링크'].isna().sum()}권")
    for _, row in books.head(5).iterrows():
        print(f"  {row['순위']}. {row['제목']} / {row['저자']} / 소개 {len(row['책 소개'])}자")
