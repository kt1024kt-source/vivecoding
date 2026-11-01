"""네이버 검색어 트렌드 API 호출 테스트 (1회 호출).

같은 데이터(네이버 데이터랩 검색어 트렌드)를 두 경로로 제공한다. 경로마다 키와 헤더가 다르다.
- hub: NAVER API HUB, POST https://naverapihub.apigw.ntruss.com/search-trend/v1/search
       헤더 X-NCP-APIGW-API-KEY-ID / X-NCP-APIGW-API-KEY
       근거: ../input/NAVER_API_HUB_Search_Trend_Manual.md
- datalab: 네이버 개발자센터, POST https://openapi.naver.com/v1/datalab/search
       헤더 X-Naver-Client-Id / X-Naver-Client-Secret, 하루 1,000회
       근거: ../input/네이버_데이터랩_통합검색어트렌드_API_매뉴얼.md
두 경로 모두 .env의 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET을 쓴다.

요청: 최근 7일 + 오늘, 일간. 오늘 값이 나오는지도 함께 확인한다.
응답 ratio는 실제 검색 횟수가 아니라 요청 결과 안의 최댓값을 100으로 둔 상대값이다.

실행: python test_naver_trend.py [hub|datalab]
"""
import sys
from datetime import date, timedelta

from _common import get_json, load_env, show_structure

ROUTES = {
    "hub": ("https://naverapihub.apigw.ntruss.com/search-trend/v1/search",
            "X-NCP-APIGW-API-KEY-ID", "X-NCP-APIGW-API-KEY"),
    "datalab": ("https://openapi.naver.com/v1/datalab/search",
                "X-Naver-Client-Id", "X-Naver-Client-Secret"),
}

route = sys.argv[1] if len(sys.argv) > 1 else "hub"
if route not in ROUTES:
    sys.exit(f"[중단] 경로는 {', '.join(ROUTES)} 중 하나")
url, id_header, secret_header = ROUTES[route]

env = load_env("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET")
today = date.today()
body = {
    "startDate": (today - timedelta(days=7)).isoformat(),
    "endDate": today.isoformat(),
    "timeUnit": "date",
    "keywordGroups": [
        {"groupName": "날씨", "keywords": ["날씨"]},
        {"groupName": "금리", "keywords": ["금리", "기준금리"]},
        {"groupName": "도서관", "keywords": ["도서관", "공공도서관"]},
    ],
}

print(f"=== 검색어 트렌드 ({route}) {body['startDate']} ~ {body['endDate']} ===")
status, data = get_json(url, json_body=body, headers={
    id_header: env["NAVER_CLIENT_ID"],
    secret_header: env["NAVER_CLIENT_SECRET"],
})

if not isinstance(data, dict):
    sys.exit(f"[실패] JSON이 아닌 응답: {data}")
if status != 200:
    sys.exit(f"[실패] 오류 응답: {data}")

print("[응답 구조]")
show_structure(data)
for result in data.get("results", []):
    points = result.get("data", [])
    last = points[-1]["period"] if points else "없음"
    series = ", ".join(f"{p['period'][5:]}={p['ratio']:.1f}" for p in points)
    print(f"  {result.get('title')} (마지막 날짜 {last}): {series}")
print(f"\n[성공] 검색어 트렌드({route}) 호출 확인, 오늘({today}) 값 포함 여부는 위 마지막 날짜로 판단")
