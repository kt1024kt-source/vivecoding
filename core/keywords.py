"""키워드 분석 (PRD 6.1~6.3, FR-12, FR-20~FR-23).

- 뉴스 점수: 키워드를 제목에 쓴 언론사 수 × log10(N / 네이버 뉴스 전체 건수). 평소에 흔한 단어(전체 건수가 기준 이상)는 뺀다
  - 단, 흔한 단어라도 평소보다 눈에 띄게 많이 나왔으면(배율이 기준 이상) 건져 올려 점수를 매긴다
  - 오늘의 이슈: 고유명사와 영문 약어만(지명 제외), 언론사 수가 기준 미만이면 뺀다. 상위 N개
  - 뉴스 워드클라우드: 명사 전체
- 도서 키워드: 제목과 책 소개에서 뽑은 키워드가 나온 책 수
- 종합 점수: 출처별 최댓값으로 나눠 0~1로 맞춘 뒤 합산
- 공통 키워드: 뉴스와 도서 양쪽 상위 목록에 모두 나온 키워드

터미널 확인: python -m core.keywords   (누적 뉴스와 그날 YES24 보관분을 읽고, 새 단어의 전체 건수만 조회)
"""
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from core import config
from core.sources.naver_news import word_totals
from core.text import BOOK_STOPWORDS, NEWS_STOPWORDS, PROPER_TAGS, nouns, noun_tags

COMMON_POOL = 200  # 공통 키워드를 찾을 때 볼 출처별 상위 키워드 수


def doc_freq(texts, stopwords):
    counts = Counter()
    for text in texts:
        counts.update(nouns(text, stopwords))
    return counts


def title_nouns(articles):
    """기사 제목마다 {키워드: 품사}. 점수 계산과 이슈별 기사 찾기에 함께 쓰려고 한 번만 분석한다."""
    return [noun_tags(title, NEWS_STOPWORDS) for title in articles["제목"]] if not articles.empty else []


def outlet_counts(articles, nouns_per_title, proper_only=False, drop=frozenset()):
    """키워드마다 제목에 그 키워드를 쓴 언론사(도메인) 수. 한 언론사가 여러 번 써도 한 번으로 친다."""
    outlets = defaultdict(set)
    for words, domain in zip(nouns_per_title, articles["도메인"]):
        for word, tag in words.items():
            if (proper_only and tag not in PROPER_TAGS) or word in drop:
                continue
            outlets[word].add(domain)
    return Counter({word: len(domains) for word, domains in outlets.items()})


@dataclass
class Scored:
    scores: Counter
    totals: dict
    generic: list                                 # 일반 단어로 뺀 것
    rescued: dict = field(default_factory=dict)   # 일반 단어지만 건져 올린 것 {단어: 배율}
    baseline: float = 0.0                         # 일반 단어의 (언론사 수 ÷ 전체 건수) 중앙값
    calls: int = 0


def rarity_scores(counts, pool, min_outlets=1, baseline=None):
    """언론사 수 상위 pool개를 후보로 점수를 매긴다.

    배율 = (언론사 수 ÷ 전체 건수) ÷ baseline. baseline은 일반 단어들의 같은 값의 중앙값이라 평소만큼 나온 일반 단어는 1 근처다.
    이슈처럼 후보에 일반 단어가 적으면 중앙값이 흔들리므로, 명사 전체로 구한 baseline을 넘겨받아 쓴다.
    """
    candidates = [w for w, c in counts.most_common(pool) if c >= min_outlets]
    totals, calls = word_totals(candidates)
    ratio = {w: counts[w] / totals[w] for w in candidates}
    if baseline is None:
        generic_ratios = sorted(ratio[w] for w in candidates if totals[w] >= config.GENERIC_TOTAL)
        baseline = generic_ratios[len(generic_ratios) // 2] if generic_ratios else 0.0
    result = Scored(Counter(), totals, [], {}, baseline, calls)
    for word in candidates:
        if totals[word] >= config.GENERIC_TOTAL:
            lift = ratio[word] / baseline if baseline else 0.0
            if lift < config.RESCUE_LIFT:
                result.generic.append(word)
                continue
            result.rescued[word] = lift
        result.scores[word] = counts[word] * math.log10(config.IDF_N / totals[word])
    return result


def articles_with(articles, nouns_per_title, word, n=None):
    """키워드가 제목에 들어간 기사(최신순 그대로) 상위 n건 (FR-30)."""
    rows = [i for i, words in enumerate(nouns_per_title) if word in words]
    return articles.iloc[rows[:n] if n else rows]


def book_keywords(books, use_intro=True, exclude_sorts=()):
    """exclude_sorts: 빼고 셀 YES24 분류(예: 「국내도서-수험서 자격증」)."""
    if exclude_sorts:
        books = books[~books["분류"].isin(exclude_sorts)]
    if books.empty:
        return Counter()
    texts = books["제목"] + " " + books["책 소개"] if use_intro else books["제목"]
    return doc_freq(texts, BOOK_STOPWORDS)


def normalize(counts):
    top = max(counts.values(), default=0)
    return {word: count / top for word, count in counts.items()} if top else {}


def combined(news_counts, book_counts):
    scores = Counter(normalize(news_counts))
    scores.update(normalize(book_counts))
    return scores


def common(news_counts, book_counts, pool=COMMON_POOL):
    news_top = {w for w, _ in news_counts.most_common(pool)}
    book_top = {w for w, _ in book_counts.most_common(pool)}
    scores = combined(news_counts, book_counts)
    return sorted(news_top & book_top, key=lambda w: scores[w], reverse=True)


if __name__ == "__main__":
    import sys
    from core import news_store
    from core.sources.yes24 import collect_bestsellers_daily
    from core.text import PLACE_STOPWORDS

    sys.stdout.reconfigure(encoding="utf-8")
    store = news_store.update()
    arts = store.articles
    books = collect_bestsellers_daily()
    print(f"누적 뉴스 {len(arts)}건(최근 {config.NEWS_WINDOW_HOURS}시간 중 {store.covered_hours:.1f}시간), 도서 {len(books.books)}권\n")

    per_title = title_nouns(arts)
    every = outlet_counts(arts, per_title)
    cloud_r = rarity_scores(every, config.CLOUD_POOL)
    proper = outlet_counts(arts, per_title, proper_only=True, drop=PLACE_STOPWORDS)
    issue_r = rarity_scores(proper, config.ISSUE_POOL, config.ISSUE_MIN_OUTLETS, baseline=cloud_r.baseline)
    cloud = cloud_r.scores
    print("[오늘의 이슈] 키워드(언론사 수, 전체 건수)")
    print("  " + ", ".join(f"{w}({proper[w]}곳, {issue_r.totals[w]:,})"
                           for w, _ in issue_r.scores.most_common(config.ISSUE_TOP_N)))
    print("\n[뉴스 워드클라우드 상위 30] 점수")
    print("  " + ", ".join(f"{w}({s:.0f})" for w, s in cloud.most_common(30)))
    print(f"\n[일반 단어로 뺀 것] {', '.join(sorted(set(issue_r.generic) | set(cloud_r.generic)))}")
    rescued = {**cloud_r.rescued, **issue_r.rescued}
    print(f"[건져 올린 일반 단어(배율 {config.RESCUE_LIFT} 이상)] "
          + ", ".join(f"{w}({x:.1f}배)" for w, x in sorted(rescued.items(), key=lambda t: -t[1])))
    print(f"(전체 건수 새로 조회 {cloud_r.calls + issue_r.calls}회)")

    book_counts = book_keywords(books.books, exclude_sorts=config.BOOK_EXCLUDE_SORTS)
    print("\n[도서 키워드 상위 20] 제목 + 책 소개, 수험서 제외 (책 수)")
    print("  " + ", ".join(f"{w}({c})" for w, c in book_counts.most_common(20)))
    print("\n[종합 상위 20]")
    print("  " + ", ".join(f"{w}({s:.2f})" for w, s in combined(cloud, book_counts).most_common(20)))
    print(f"\n[공통 키워드] 뉴스와 도서 각 상위 {COMMON_POOL}개에 모두 있는 것")
    print("  " + ", ".join(common(cloud, book_counts)[:30]))
