"""데이터 빌드: 수집과 분석 결과를 web/data.json으로 만든다. 화면(web/index.html)은 이 파일만 읽는다.

실행: .venv\\Scripts\\python build.py   (네이버 뉴스 최대 70회 + 처음 보는 단어의 전체 건수 조회, YES24는 하루 1회)
- 키는 .env 또는 환경 변수에서만 읽고 data.json에는 넣지 않는다(PRD NFR-01).
- 한 출처가 실패하면 그 부분만 비우고 실패 사실을 data.json에 적는다. 모두 실패하면 기존 data.json을 그대로 둔다(FR-03).
- YES24는 하루 1회만 부르고(core/sources/yes24.py), data.json에는 화면에 보일 필드만 담는다(책 소개 제외). 빌드 때마다 덮어쓴다.
- 도서관 정보나루 인기 대출도 하루 1회(core/sources/data4library.py). 표지 URL은 받지도 담지도 않는다.
- 뉴스는 빌드마다 store/news_store.json에 쌓고, 쌓인 최근 N시간치로 분석한다(core/news_store.py). 주기는 30분.
"""
import json
import sys
from datetime import datetime, timedelta, timezone

from core import config, keywords, news_store
from core.sources._http import ApiError
from core.sources.data4library import collect_popular_loans_daily
from core.sources.naver_news import collect_news
from core.sources.yes24 import collect_bestsellers_daily
from core.text import PLACE_STOPWORDS, STOPWORD_GROUPS

KST = timezone(timedelta(hours=9))


def iso(dt):
    return dt.isoformat() if dt else None


def article_json(row):
    return {
        "title": row["제목"], "link": row["원문 링크"], "domain": row["도메인"],
        "published": iso(row["발행 시각"]),
    }


def build():
    errors, news, books, library = [], None, None, None
    try:
        news = collect_news()
    except (ApiError, KeyError) as e:
        errors.append(f"네이버 뉴스: {e}")
    try:
        books = collect_bestsellers_daily()
        if books.stale_error:
            errors.append(f"YES24: {books.stale_error}")
    except (ApiError, KeyError) as e:
        errors.append(f"YES24: {e}")
    try:
        library = collect_popular_loans_daily()
        if library.stale_error:
            errors.append(f"도서관 정보나루: {library.stale_error}")
    except (ApiError, KeyError) as e:
        errors.append(f"도서관 정보나루: {e}")
    store = news_store.update(news) if news is not None or config.NEWS_STORE.exists() else None
    if store is None and books is None and library is None:
        sys.exit("[중단] 모든 출처 수집 실패, 기존 data.json을 그대로 둔다:\n  " + "\n  ".join(errors))

    data = {
        "generated_at": iso(datetime.now(KST)),
        "errors": errors,
        "method": {
            "queries": config.NEWS_QUERIES,
            "target_hours": config.NEWS_WINDOW_HOURS,
            "stopwords": {group: sorted(words) for group, words in STOPWORD_GROUPS.items()},
            "book_excluded_sorts": list(config.BOOK_EXCLUDE_SORTS),
            "issue_formula": "고유명사·영문 약어(지명 제외)를 제목에 쓴 언론사 수 × log10(N / 네이버 뉴스 전체 건수)",
            "cloud_formula": "명사·영문 약어를 제목에 쓴 언론사 수 × log10(N / 네이버 뉴스 전체 건수)",
            "idf_n": config.IDF_N,
            "generic_total": config.GENERIC_TOTAL,
            "issue_min_outlets": config.ISSUE_MIN_OUTLETS,
            "rescue_lift": config.RESCUE_LIFT,
            "generic_excluded": [],
            "generic_rescued": [],
        },
        "news": None, "books": None, "library": None, "issues": [], "clouds": {}, "common": [],
    }

    news_counts, book_counts = None, None
    if store is not None:
        arts = store.articles
        nouns_per_title = keywords.title_nouns(arts)
        data["news"] = {
            "collected_at": iso(store.now),
            "window_start": iso(store.window_start),
            "covered_hours": round(store.covered_hours, 1),
            "gaps": [[iso(s), iso(e)] for s, e in store.gaps],
            "builds": store.builds,
            "article_count": len(arts),
            "outlet_count": int(arts["도메인"].nunique()) if not arts.empty else 0,
            # 이번 빌드의 수집 기록(수집이 실패했으면 비어 있음)
            "last_build": {
                "covered_hours": round(news.covered_hours, 1), "per_query": news.per_query, "calls": news.calls,
            } if news is not None else None,
        }
        try:
            every = keywords.outlet_counts(arts, nouns_per_title)
            cloud_r = keywords.rarity_scores(every, config.CLOUD_POOL)
            proper = keywords.outlet_counts(arts, nouns_per_title, proper_only=True, drop=PLACE_STOPWORDS)
            issue_r = keywords.rarity_scores(proper, config.ISSUE_POOL, config.ISSUE_MIN_OUTLETS,
                                             baseline=cloud_r.baseline)
        except ApiError as e:
            errors.append(f"네이버 뉴스(전체 건수 조회): {e}")
        else:
            news_counts = cloud_r.scores
            data["news"]["totals_calls"] = cloud_r.calls + issue_r.calls
            data["method"]["generic_excluded"] = sorted(set(issue_r.generic) | set(cloud_r.generic))
            rescued = {**cloud_r.rescued, **issue_r.rescued}
            data["method"]["generic_rescued"] = [[w, round(x, 1)] for w, x in
                                                 sorted(rescued.items(), key=lambda t: -t[1])]
            for word, score in issue_r.scores.most_common(config.ISSUE_TOP_N):
                related = keywords.articles_with(arts, nouns_per_title, word)
                data["issues"].append({
                    "word": word, "score": round(score, 1), "outlet_count": proper[word],
                    "article_count": len(related), "naver_total": issue_r.totals[word],
                    "articles": [article_json(row) for _, row in related.head(config.ISSUE_ARTICLES_N).iterrows()],
                })
            data["clouds"]["news"] = [[w, round(s, 1)] for w, s in news_counts.most_common(config.CLOUD_TOP_N)]

    if books is not None:
        book_counts = keywords.book_keywords(books.books, use_intro=True,
                                             exclude_sorts=config.BOOK_EXCLUDE_SORTS)
        data["books"] = {
            "pub_date": iso(books.pub_date),
            "from_cache": books.from_cache,
            "items": books.books[["순위", "분류", "제목", "저자", "출판사", "상세 링크"]]
                .rename(columns={"순위": "rank", "분류": "sort", "제목": "title", "저자": "author",
                                 "출판사": "publisher", "상세 링크": "link"})
                .to_dict(orient="records"),
        }
        data["clouds"]["books"] = book_counts.most_common(config.CLOUD_TOP_N)

    if library is not None:
        data["library"] = {
            "start": library.start, "end": library.end, "from_cache": library.from_cache,
            "items": library.books.rename(columns={
                "순위": "rank", "제목": "title", "저자": "author", "출판사": "publisher", "출판년도": "year",
                "주제": "subject", "대출 건수": "loans", "권 수": "volumes", "상세 링크": "link",
            }).to_dict(orient="records"),
        }

    if news_counts is not None and book_counts is not None:
        data["clouds"]["combined"] = [[w, round(s, 3)] for w, s in
                                      keywords.combined(news_counts, book_counts).most_common(config.CLOUD_TOP_N)]
        data["common"] = keywords.common(news_counts, book_counts)[:30]

    config.DATA_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    result = build()
    n = result["news"] or {}
    print(f"[완료] {config.DATA_JSON.relative_to(config.ROOT)} 생성 {result['generated_at']}")
    last = n.get("last_build") or {}
    print(f"  이번 수집: {last.get('covered_hours')}시간, 호출 {last.get('calls')}회 + 전체 건수 조회 {n.get('totals_calls')}회")
    print(f"  누적: 뉴스 {n.get('article_count')}건, 언론사 {n.get('outlet_count')}곳, "
          f"최근 {config.NEWS_WINDOW_HOURS}시간 중 {n.get('covered_hours')}시간 덮음, 빈 구간 {len(n.get('gaps') or [])}개, 빌드 {n.get('builds')}회")
    print(f"  도서 {len(result['books']['items']) if result['books'] else 0}권, "
          f"도서관 인기 대출 {len(result['library']['items']) if result['library'] else 0}줄")
    print(f"  이슈: {', '.join(i['word'] for i in result['issues'])}")
    rescued = ", ".join(f"{w}({x}배)" for w, x in result["method"]["generic_rescued"])
    print(f"  건져 올린 일반 단어: {rescued or '없음'}")
    for err in result["errors"]:
        print(f"  [실패] {err}")
