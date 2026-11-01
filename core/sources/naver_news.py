"""네이버 뉴스 수집 (PRD FR-10, FR-11, 6.1의 1~3단계).

근거: input/NAVER_API_HUB_Search_News_Manual.md
- 검색어마다 sort=date, display=100으로 받는다.
- 가장 오래된 기사가 N시간 전보다 이전이 되거나 start 한계(1,000건)에 이르면 멈춘다.
- 모든 검색어가 덮은 가장 짧은 시간을 실제 기간으로 정하고 그 안의 기사만 남긴다.

터미널 확인: python -m core.sources.naver_news
"""
import html
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import pandas as pd

from core import config
from core.sources._http import get_json

URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"
KST = timezone(timedelta(hours=9))
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class NewsResult:
    articles: pd.DataFrame        # 제목, 요약, 원문 링크, 네이버 링크, 발행 시각, 도메인, 검색어
    collected_at: datetime
    window_start: datetime        # 실제 기간의 시작
    target_hours: int
    per_query: list = field(default_factory=list)  # 검색어별 받은 건수, 덮은 시간, 한계 도달 여부
    calls: int = 0

    @property
    def covered_hours(self):
        return (self.collected_at - self.window_start).total_seconds() / 3600


def clean_text(text):
    """<b> 태그와 HTML 엔티티(&quot; 등)를 지운다."""
    return html.unescape(TAG_RE.sub("", text or "")).strip()


def domain_of(url):
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _headers():
    return {
        "X-NCP-APIGW-API-KEY-ID": config.get_key("NAVER_CLIENT_ID"),
        "X-NCP-APIGW-API-KEY": config.get_key("NAVER_CLIENT_SECRET"),
    }


def _fetch_query(query, target_start, headers):
    """한 검색어를 최신순으로 target_start까지(또는 한계까지) 받는다."""
    items, calls, hit_limit = [], 0, False
    for start in range(1, config.NEWS_MAX_START + 1, config.NEWS_PAGE_SIZE):
        data = get_json("네이버 뉴스", URL, headers=headers, params={
            "query": query, "display": config.NEWS_PAGE_SIZE, "start": start,
            "sort": "date", "format": "json",
        })
        calls += 1
        page = data.get("items", [])
        for item in page:
            item["_published"] = parsedate_to_datetime(item["pubDate"])
            item["_query"] = query
        items.extend(page)
        # 한 페이지가 100건보다 적게 오는 일이 가끔 있어(10-27 확인), 건수가 아니라 빈 페이지와 total로 끝을 판단한다
        if not page or start - 1 + len(page) >= data.get("total", 0):
            break
        if page[-1]["_published"] < target_start:
            break
    else:
        hit_limit = True
    oldest = min((i["_published"] for i in items), default=target_start)
    # 한계에 걸려 target_start까지 못 갔으면 가장 오래된 기사 시각까지만 덮은 것이다
    covered_from = max(oldest, target_start)
    return items, calls, hit_limit, covered_from


def word_totals(words):
    """단어마다 네이버 뉴스 전체 건수(total). 평소 얼마나 흔한 단어인지 보는 데 쓴다(PRD 6.1).
    하루 사이에는 거의 변하지 않으므로 그날(KST) 조회한 값은 보관해 두고 다시 쓴다. (건수, 새로 조회한 횟수)를 돌려준다."""
    today = datetime.now(KST).date().isoformat()
    cache = {}
    if config.WORD_TOTALS_CACHE.exists():
        raw = json.loads(config.WORD_TOTALS_CACHE.read_text(encoding="utf-8"))
        if raw.get("date") == today:
            cache = raw["totals"]
    missing = [w for w in words if w not in cache]
    if missing:
        headers = _headers()
        for word in missing:
            data = get_json("네이버 뉴스", URL, headers=headers, params={"query": word, "display": 1})
            cache[word] = max(int(data.get("total", 0)), 1)
        config.WORD_TOTALS_CACHE.parent.mkdir(exist_ok=True)
        config.WORD_TOTALS_CACHE.write_text(json.dumps({"date": today, "totals": cache}, ensure_ascii=False),
                                            encoding="utf-8")
    return {w: cache[w] for w in words}, len(missing)


def collect_news(now=None):
    now = now or datetime.now(KST)
    target_start = now - timedelta(hours=config.NEWS_WINDOW_HOURS)
    headers = _headers()

    all_items, per_query, calls, covered = [], [], 0, []
    for query in config.NEWS_QUERIES:
        items, n_calls, hit_limit, covered_from = _fetch_query(query, target_start, headers)
        all_items.extend(items)
        calls += n_calls
        covered.append(covered_from)
        per_query.append({
            "검색어": query, "받은 건수": len(items), "호출": n_calls,
            "덮은 시간": round((now - covered_from).total_seconds() / 3600, 1),
            "한계 도달": hit_limit,
        })

    # 모든 검색어가 덮은 가장 짧은 시간 = 덮기 시작한 시각 중 가장 늦은 것
    window_start = max(covered)

    rows = {}
    for item in all_items:
        if item["_published"] < window_start:
            continue
        link = item.get("originallink") or item.get("link")
        if link in rows:
            if item["_query"] not in rows[link]["검색어"]:
                rows[link]["검색어"].append(item["_query"])
            continue
        rows[link] = {
            "제목": clean_text(item.get("title")),
            "요약": clean_text(item.get("description")),
            "원문 링크": link,
            "네이버 링크": item.get("link"),
            "발행 시각": item["_published"],
            "도메인": domain_of(link),
            "검색어": [item["_query"]],
        }

    articles = pd.DataFrame(rows.values())
    if not articles.empty:
        articles = articles.sort_values("발행 시각", ascending=False, ignore_index=True)
    return NewsResult(articles, now, window_start, config.NEWS_WINDOW_HOURS, per_query, calls)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    result = collect_news()
    print(f"수집 시각 {result.collected_at:%m-%d %H:%M}, 호출 {result.calls}회")
    print(f"목표 {result.target_hours}시간 → 실제 {result.covered_hours:.1f}시간 "
          f"({result.window_start:%m-%d %H:%M} ~ {result.collected_at:%H:%M})")
    print(pd.DataFrame(result.per_query).to_string(index=False))
    print(f"\n기간 안의 중복 제거 기사 {len(result.articles)}건, 최신 5건:")
    for _, row in result.articles.head(5).iterrows():
        print(f"  {row['발행 시각']:%H:%M} [{row['도메인']}] {row['제목']}")
