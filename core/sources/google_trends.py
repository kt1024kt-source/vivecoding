"""Google 트렌드 한국 인기 급상승 검색어 (11-08 작업자 결정: 별도 탭으로만, AI 도우미 자료와 워드클라우드에는 넣지 않음).

근거: https://trends.google.com/trending/rss?geo=KR (키 없는 RSS, 2026-11-08 호출로 구조 확인)
- 항목: title(검색어), ht:approx_traffic(대략 검색량, 예: 10000+), pubDate(시작 시각), ht:news_item(관련 기사 제목·주소·언론사)
- 공식 API가 아니라 주소나 형식이 예고 없이 바뀔 수 있다. 실패해도 빌드는 계속된다(build.py).
- 이미지(ht:picture, ht:news_item_picture)는 받지도 담지도 않는다.
- 이슈 아닌 검색어(스포츠, 연예 등)도 거르지 않고 그대로 보인다(작업자 결정: 거르는 기준이 또 하나의 필터가 됨).
"""
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

from core.sources._http import TIMEOUT_SECONDS, ApiError

URL = "https://trends.google.com/trending/rss"
NS = {"ht": "https://trends.google.com/trending/rss"}
NEWS_PER_TERM = 3


def _traffic(text):
    """「10000+」 → 10000(정렬용). 숫자가 없으면 0."""
    digits = re.sub(r"[^0-9]", "", text or "")
    return int(digits) if digits else 0


def collect(geo="KR"):
    """돌려주는 값: 검색어 목록 [{term, traffic, started, news[{title, link, source}]}], 대략 검색량 많은 순."""
    try:
        res = requests.get(URL, params={"geo": geo}, headers={"User-Agent": "Mozilla/5.0 (trandeer)"}, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as e:
        raise ApiError("Google 트렌드", "연결 실패", type(e).__name__) from None
    if res.status_code != 200:
        raise ApiError("Google 트렌드", res.status_code, res.text[:200])
    try:
        root = ET.fromstring(res.content)
    except ET.ParseError:
        raise ApiError("Google 트렌드", res.status_code, "RSS가 아닌 응답") from None
    terms = []
    for item in root.iter("item"):
        term = (item.findtext("title") or "").strip()
        if not term:
            continue
        try:
            started = parsedate_to_datetime(item.findtext("pubDate")).isoformat()
        except (TypeError, ValueError):
            started = None
        news = []
        for n in item.findall("ht:news_item", NS)[:NEWS_PER_TERM]:
            link = (n.findtext("ht:news_item_url", namespaces=NS) or "").strip()
            if link.startswith(("http://", "https://")):
                news.append({"title": (n.findtext("ht:news_item_title", namespaces=NS) or "").strip(),
                             "link": link, "source": (n.findtext("ht:news_item_source", namespaces=NS) or "").strip()})
        terms.append({"term": term, "traffic": (item.findtext("ht:approx_traffic", namespaces=NS) or "").strip(),
                      "started": started, "news": news})
    if not terms:
        raise ApiError("Google 트렌드", res.status_code, "검색어가 없는 응답")
    # RSS는 시작 시각 순이다. 대략 검색량 많은 순으로, 같으면 RSS 순서(최근 것 먼저) 그대로
    return sorted(terms, key=lambda t: -_traffic(t["traffic"]))
