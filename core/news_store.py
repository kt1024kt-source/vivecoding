"""뉴스 누적 보관 (PRD 6.1, 10-27 결정: 한 번에 1,000건 한계로 낮에는 1시간 남짓만 덮으므로 빌드마다 쌓는다).

- 빌드마다 받은 기사(그때 모든 검색어가 덮은 구간 안의 것)를 원문 링크로 합치고, 최근 N시간보다 오래된 것은 지운다.
- 보관 항목: 제목, 원문 링크, 네이버 링크, 발행 시각, 도메인, 검색어. 요약은 분석에 쓰지 않으므로 보관하지 않는다.
- 빌드마다 덮은 구간도 남겨, N시간 중 실제로 덮은 시간과 빈 구간을 화면에 그대로 보인다.
- 파일(store/news_store.json)은 Git에 올리지 않는다. 자동 빌드에서는 Actions 캐시에 둔다(페이즈 4).

터미널 확인: python -m core.news_store
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pandas as pd

from core import config

KST = timezone(timedelta(hours=9))
COLUMNS = ["제목", "원문 링크", "네이버 링크", "발행 시각", "도메인", "검색어"]


@dataclass
class StoreResult:
    articles: pd.DataFrame        # 누적된 기사, 최신순
    now: datetime
    window_start: datetime        # now - N시간
    covered: list = field(default_factory=list)  # 덮은 구간 [(시작, 끝)], 겹침 합침
    gaps: list = field(default_factory=list)     # N시간 중 덮지 못한 구간
    builds: int = 0               # 기간 안에 남은 빌드 수

    @property
    def covered_hours(self):
        return sum((e - s).total_seconds() for s, e in self.covered) / 3600


def _load():
    if not config.NEWS_STORE.exists():
        return [], []
    raw = json.loads(config.NEWS_STORE.read_text(encoding="utf-8"))
    intervals = [(datetime.fromisoformat(s), datetime.fromisoformat(e)) for s, e in raw["intervals"]]
    articles = [{**a, "발행 시각": datetime.fromisoformat(a["발행 시각"])} for a in raw["articles"]]
    return intervals, articles


def _save(intervals, articles):
    config.NEWS_STORE.parent.mkdir(exist_ok=True)
    raw = {
        "intervals": [[s.isoformat(), e.isoformat()] for s, e in intervals],
        "articles": [{**a, "발행 시각": a["발행 시각"].isoformat()} for a in articles],
    }
    config.NEWS_STORE.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")


def _merge(intervals):
    merged = []
    for s, e in sorted(intervals):
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def update(news=None, now=None):
    """news(NewsResult)를 쌓고 N시간이 지난 것을 지운 뒤 누적 결과를 돌려준다. news가 없으면(수집 실패) 쌓인 것만 쓴다."""
    now = now or (news.collected_at if news else datetime.now(KST))
    window_start = now - timedelta(hours=config.NEWS_WINDOW_HOURS)
    intervals, stored = _load()

    rows = {a["원문 링크"]: a for a in stored}
    if news is not None:
        intervals.append((news.window_start, news.collected_at))
        for a in news.articles[COLUMNS].to_dict(orient="records"):
            a["발행 시각"] = a["발행 시각"].to_pydatetime()
            old = rows.get(a["원문 링크"])
            if old:
                old["검색어"] = sorted(set(old["검색어"]) | set(a["검색어"]))
            else:
                rows[a["원문 링크"]] = a

    intervals = [(s, e) for s, e in intervals if e > window_start]
    articles = [a for a in rows.values() if a["발행 시각"] >= window_start]
    _save(intervals, articles)

    covered = [(max(s, window_start), min(e, now)) for s, e in _merge(intervals)]
    gaps, cursor = [], window_start
    for s, e in covered:
        if s > cursor:
            gaps.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < now:
        gaps.append((cursor, now))

    df = pd.DataFrame(articles, columns=COLUMNS)
    if not df.empty:
        df = df.sort_values("발행 시각", ascending=False, ignore_index=True)
    return StoreResult(df, now, window_start, covered, gaps, len(intervals))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    r = update()
    print(f"누적 기사 {len(r.articles)}건, 빌드 {r.builds}회, 최근 {config.NEWS_WINDOW_HOURS}시간 중 {r.covered_hours:.1f}시간 덮음")
    for s, e in r.gaps:
        print(f"  빈 구간 {s:%m-%d %H:%M} ~ {e:%H:%M}")
