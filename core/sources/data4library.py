"""도서관 정보나루 인기 대출 도서 수집 (PRD FR-41, 「서점 vs 도서관」 비교).

근거: input/도서관정보나루_API_Manual.md (v20260620) 9~12쪽 loanItemSrch
- 조건 없이 부르면 성별, 연령, 지역, 부가기호, 주제 전체 대출 기준이다(전국, 아동책 포함. 10-29 결정).
- 최근 30일(어제까지) 대출 기준. 한 번에 최대 300권을 받아 같은 제목의 여러 권을 한 줄로 묶는다.
  상위 100권 중 「흔한남매」가 권만 달리 22권 들어 있어서(10-29 확인) 묶지 않으면 목록이 한 시리즈로 채워진다.
  순위는 가장 많이 빌린 한 권 기준(정보나루 순위 그대로)이다. 대출을 더하면 상위가 아동 시리즈로만 채워져서(10-29 결정).
- bookImageURL은 비영리 화면 표시에만 쓸 수 있고 저장과 AI 입력이 금지되어(12쪽) 받지도 담지도 않는다.
- 매뉴얼 주소는 http지만 https도 응답해서(10-29 확인) 키가 암호화되어 가게 https로 부른다.
- 하루 1회만 부르고 store/library_today.json에 덮어써 둔다. 그날 첫 호출이 실패하면 직전 보관분을 쓴다(yes24.py와 같은 방식).

터미널 확인: python -m core.sources.data4library
"""
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from core import config
from core.sources._http import ApiError, get_json
from core.sources.library_search import clean_authors, clean_title

URL = "https://data4library.kr/api/loanItemSrch"
KST = timezone(timedelta(hours=9))


@dataclass
class LoanResult:
    books: pd.DataFrame   # 순위, 제목, 저자, 출판사, 출판년도, 주제, 대출 건수, 권 수, 상세 링크
    start: str            # 대출 기간 시작일(yyyy-mm-dd)
    end: str              # 대출 기간 종료일
    num_found: int
    from_cache: bool = False
    stale_error: str = None


def _merge_volumes(docs):
    """같은 제목은 한 줄로: 가장 순위가 높은 권(docs는 순위순)의 대출 건수와 정보를 쓰고, 나머지 권은 수만 센다."""
    rows = {}
    for doc in docs:
        title = clean_title(doc.get("bookname"))
        if title in rows:
            rows[title]["권 수"] += 1
            continue
        rows[title] = {
            "제목": title,
            "저자": clean_authors(doc.get("authors")),
            "출판사": (doc.get("publisher") or "").strip(),
            "출판년도": (doc.get("publication_year") or "").strip(),
            "주제": (doc.get("class_nm") or "").strip(),
            "대출 건수": int(doc.get("loan_count") or 0),
            "권 수": 1,
            "상세 링크": doc.get("bookDtlUrl"),
        }
    books = pd.DataFrame(list(rows.values())[:config.LIBRARY_TOP_N])
    if not books.empty:
        books.insert(0, "순위", range(1, len(books) + 1))
    return books


def collect_popular_loans():
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=config.LIBRARY_DAYS - 1)
    data = get_json("도서관 정보나루", URL, params={
        "authKey": config.get_key("DATA4LIBRARY_API_KEY"), "startDt": start.isoformat(), "endDt": end.isoformat(),
        "pageNo": 1, "pageSize": config.LIBRARY_FETCH_N, "format": "json",
    })
    body = data.get("response") or {}
    if "error" in body:
        raise ApiError("도서관 정보나루", 200, str(body["error"])[:200])
    docs = [entry.get("doc", entry) for entry in body.get("docs", [])]
    return LoanResult(_merge_volumes(docs), start.isoformat(), end.isoformat(), int(body.get("numFound") or 0))


def _save_cache(result, fetched_on):
    config.LIBRARY_CACHE.parent.mkdir(exist_ok=True)
    config.LIBRARY_CACHE.write_text(json.dumps({
        "fetched_on": fetched_on, "start": result.start, "end": result.end, "num_found": result.num_found,
        "books": result.books.to_dict(orient="records"),
    }, ensure_ascii=False), encoding="utf-8")


def _load_cache():
    if not config.LIBRARY_CACHE.exists():
        return None, None
    raw = json.loads(config.LIBRARY_CACHE.read_text(encoding="utf-8"))
    return raw["fetched_on"], LoanResult(pd.DataFrame(raw["books"]), raw["start"], raw["end"], raw["num_found"],
                                         from_cache=True)


def collect_popular_loans_daily():
    """오늘(KST) 이미 받았으면 보관분을, 아니면 API를 불러 보관분을 덮어쓴다."""
    today = datetime.now(KST).date().isoformat()
    fetched_on, cached = _load_cache()
    if cached is not None and fetched_on == today:
        return cached
    try:
        result = collect_popular_loans()
    except (ApiError, KeyError) as e:
        if cached is None:
            raise
        cached.stale_error = f"{e} ({fetched_on}에 받은 목록을 대신 씀)"
        return cached
    _save_cache(result, today)
    return result


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    result = collect_popular_loans()
    books = result.books
    print(f"대출 기간 {result.start} ~ {result.end}, 묶은 뒤 {len(books)}줄 (받은 {config.LIBRARY_FETCH_N}권, 전체 {result.num_found}권, 호출 1회)")
    for _, row in books.head(15).iterrows():
        vols = f" (외 {row['권 수'] - 1}권)" if row["권 수"] > 1 else ""
        print(f"  {row['순위']}. {row['제목']}{vols} / {row['저자']} / 대출 {row['대출 건수']:,} / {row['주제']}")
