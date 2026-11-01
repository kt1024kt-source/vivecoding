"""도서관 정보나루 API 호출 테스트 (2회 호출).

근거: ../input/도서관정보나루_API_Manual.md (v20260620)
- 3. 인기대출도서 조회 loanItemSrch (매뉴얼 9~12쪽)
- 17. 이달의 키워드 monthlyKeywords (매뉴얼 52~53쪽)
- format=json으로 요청한다. JSON의 바깥 구조는 매뉴얼에 없어서 실제 응답으로 확인한다.
- bookImageURL은 화면 표시만 허용, 저장과 AI 입력 금지이므로 출력하지 않는다.
- 매뉴얼의 호출 URL은 http다(키가 암호화되지 않은 채 전송됨).

실행: python test_data4library.py
"""
from datetime import date, timedelta

from _common import find_key, get_json, load_env, show_structure

BASE = "http://data4library.kr/api"

key = load_env("DATA4LIBRARY_API_KEY")["DATA4LIBRARY_API_KEY"]

# 1) 인기대출도서: 최근 30일, 5건
end = date.today() - timedelta(days=1)
start = end - timedelta(days=29)
print(f"\n=== 인기대출도서 loanItemSrch ({start} ~ {end}) ===")
status, data = get_json(f"{BASE}/loanItemSrch", params={
    "authKey": key, "startDt": start.isoformat(), "endDt": end.isoformat(),
    "pageNo": 1, "pageSize": 5, "format": "json",
})
if isinstance(data, dict):
    print("[응답 구조]")
    show_structure(data)
    print(f"numFound={find_key(data, 'numFound')} resultNum={find_key(data, 'resultNum')}")
    for entry in find_key(data, "docs") or []:
        doc = entry.get("doc", entry)
        print(f"  {doc.get('ranking')}. {doc.get('bookname')} / {doc.get('authors')} / "
              f"대출 {doc.get('loan_count')} / ISBN {doc.get('isbn13')}")
else:
    print(f"[실패] JSON이 아닌 응답: {data}")

# 2) 이달의 키워드: month 생략 시 직전 달
print("\n=== 이달의 키워드 monthlyKeywords (직전 달) ===")
status, data = get_json(f"{BASE}/monthlyKeywords", params={"authKey": key, "format": "json"})
if isinstance(data, dict):
    print("[응답 구조]")
    show_structure(data)
    keywords = find_key(data, "keywords") or []
    print(f"키워드 수={len(keywords)} (매뉴얼: 100건 제공)")
    for entry in keywords[:10]:
        kw = entry.get("keyword", entry)
        print(f"  {kw.get('word')} ({kw.get('weight')})")
else:
    print(f"[실패] JSON이 아닌 응답: {data}")
