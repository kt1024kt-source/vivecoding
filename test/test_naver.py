"""NAVER API HUB 뉴스 검색 API 호출 테스트 (1회 호출, 5건).

근거: ../input/NAVER_API_HUB_Search_News_Manual.md (공식 문서 확인일 2026-10-27)
- GET https://naverapihub.apigw.ntruss.com/search/v1/news
- 헤더 X-NCP-APIGW-API-KEY-ID(Client ID), X-NCP-APIGW-API-KEY(Client Secret)
- query 필수, display 1~100, start 1~1000, sort sim/date
- 오류: SE01~SE06(400), SE05(404), SE99(500), 공통 401/403/429
- 일일 호출 한도 25,000회

실행: python test_naver.py [검색어]
"""
import sys

from _common import get_json, load_env, show_structure

URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"

env = load_env("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET")
query = sys.argv[1] if len(sys.argv) > 1 else "사회"

status, data = get_json(
    URL,
    params={"query": query, "display": 5, "start": 1, "sort": "date", "format": "json"},
    headers={
        "X-NCP-APIGW-API-KEY-ID": env["NAVER_CLIENT_ID"],
        "X-NCP-APIGW-API-KEY": env["NAVER_CLIENT_SECRET"],
    },
)

if not isinstance(data, dict):
    sys.exit(f"[실패] JSON이 아닌 응답: {data}")
if status != 200:
    sys.exit(f"[실패] 오류 응답: {data}")

print("\n[응답 구조]")
show_structure(data)

items = data.get("items", [])
print(f"\n[결과] 검색어={query} total={data.get('total')} 받은 건수={len(items)} "
      f"lastBuildDate={data.get('lastBuildDate')}")
for item in items:
    print(f"  {item.get('pubDate')} | {item.get('title')}")
    print(f"    원문 {item.get('originallink')}")
print("\n[성공] 네이버 뉴스 검색 API 호출 확인")
