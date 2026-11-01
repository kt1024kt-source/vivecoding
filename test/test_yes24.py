"""YES24 카테고리 베스트셀러 API 호출 테스트 (1회 호출, 5건).

근거: https://developers.yes24.com/api-doc/category-bestseller (2026-10-26 확인)
- GET https://apis.yes24.com/v1/category/bestseller, 인증 헤더 X-Api-Key
- 필수 파라미터 categoryId (문서 curl 예시 값 001, 어떤 분류인지는 문서에 설명 없음)
- 오류 코드: AUTH_001/002(401), PARAM_001/006(400), BEST_001(404)
- 일일 호출 한도는 계정 단위로 누적되므로 반복 실행을 피한다(FAQ).

실행: python test_yes24.py [categoryId]
"""
import sys

from _common import get_json, load_env, show_structure

URL = "https://apis.yes24.com/v1/category/bestseller"

key = load_env("YES24_API_KEY")["YES24_API_KEY"]
category_id = sys.argv[1] if len(sys.argv) > 1 else "001"

status, data = get_json(
    URL,
    params={"categoryId": category_id, "pageSize": 5},
    headers={"X-Api-Key": key},
)

if not isinstance(data, dict):
    sys.exit(f"[실패] JSON이 아닌 응답: {data}")

print(f"success={data.get('success')} errorCode={data.get('errorCode')} message={data.get('message')}")
if status != 200 or not data.get("success"):
    sys.exit("[실패] 위 오류 코드를 문서의 오류 표와 대조한다.")

print("\n[응답 구조]")
show_structure(data)

body = data.get("data") or {}
items = body.get("items") or []
print(f"\n[결과] totalCount={body.get('totalCount')} 받은 건수={len(items)}")
print(f"기준 시각(meta.pubDate)={(body.get('meta') or {}).get('pubDate')}")
for item in items:
    print(f"  {item.get('sortOrder')}. {item.get('title')} / {item.get('author')} / "
          f"{item.get('publisher')} / ISBN {item.get('isbn13')}")
print("\n[성공] YES24 API 호출 확인")
