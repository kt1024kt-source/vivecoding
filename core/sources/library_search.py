"""도서관 정보나루 질문 때 부르는 조회(AI 도우미, 이슈 관련 도서). pandas 없이 돈다(배포 서버 함수가 가볍게, 10-30).

근거: input/도서관정보나루_API_Manual.md (v20260620)
- srchBooks(49~51쪽): 제목 검색, 대출 많은 순(관련 도서 검증)
- loanItemSrch(9~12쪽): 조건별 인기 대출. 코드는 58~63쪽(성별, 연령, 지역, 대주제)
- libSrchByBook(38~39쪽): 책을 가진 도서관, region 필수
- bookImageURL은 AI 입력과 저장이 금지되어(12쪽) 받지도 담지도 않는다.
"""
import re
from datetime import date, timedelta

from core import config
from core.sources._http import ApiError, get_json

BASE = "https://data4library.kr/api/"
SKIP_READERS = "567"  # 부가기호 첫 자리: 5·6 학습참고서, 7 아동(매뉴얼 58~59쪽). 이슈 관련 책에서는 뺀다(10-30)

# 매뉴얼 58~63쪽 코드
GENDERS = {"0": "남성", "1": "여성"}
AGES = {"0": "영유아(0~5세)", "6": "유아(6~7세)", "8": "초등(8~13세)", "14": "청소년(14~19세)",
        "20": "20대", "30": "30대", "40": "40대", "50": "50대", "60": "60세 이상"}
REGIONS = {"11": "서울", "21": "부산", "22": "대구", "23": "인천", "24": "광주", "25": "대전", "26": "울산",
           "29": "세종", "31": "경기", "32": "강원", "33": "충북", "34": "충남", "35": "전북", "36": "전남",
           "37": "경북", "38": "경남", "39": "제주"}
KDCS = {"0": "총류", "1": "철학", "2": "종교", "3": "사회과학", "4": "자연과학", "5": "기술과학",
        "6": "예술", "7": "언어", "8": "문학", "9": "역사"}


def clean_title(name):
    """「안녕이라 그랬어 :김애란 소설 」 → 「안녕이라 그랬어」, 「듀얼 브레인 =AI 시대의…」 → 「듀얼 브레인」.
    부제(콜론 뒤)와 대등 서명(「 =」 뒤)을 떼고 공백을 정리한다."""
    return re.sub(r"\s+", " ", re.split(r":| =", name or "")[0]).strip()


def clean_authors(authors):
    """「지은이: 김애란」 → 「김애란」, 「원작: 흔한남매 ;그림: 유난희」 → 「흔한남매, 유난희」, 「설민석,그림: 정현희」 → 「설민석, 정현희」."""
    parts = [re.sub(r"^\s*[^:;,]{1,6}:\s*", "", p).strip() for p in re.split(r"[;,]", authors or "")]
    parts = [re.sub(r"\s*\((지은이|옮긴이|글|그림|엮은이)\)$", "", p) for p in parts]  # 「한로로 (HANRORO) (지은이)」
    return ", ".join(p for p in parts if p)


def _call(api, params):
    data = get_json("도서관 정보나루", BASE + api, params={
        "authKey": config.get_key("DATA4LIBRARY_API_KEY"), "format": "json", **params})
    body = data.get("response") or {}
    if "error" in body:
        raise ApiError("도서관 정보나루", 200, str(body["error"])[:200])
    return body


def _docs(body, key="docs", item="doc"):
    return [entry.get(item, entry) for entry in body.get(key) or []]


def _book(doc):
    return {
        "title": clean_title(doc.get("bookname")), "author": clean_authors(doc.get("authors")),
        "publisher": (doc.get("publisher") or "").strip(), "year": (doc.get("publication_year") or "").strip(),
        "loans": int(doc.get("loan_count") or 0), "isbn": (doc.get("isbn13") or "").strip(),
        "link": doc.get("bookDtlUrl"),
    }


def same_title(a, b):
    """부제·끝 괄호(「(큰글자책)」 등)를 떼고 공백·문장부호를 지운 제목이 같은가. 「총, 균, 쇠」 = 「총 균 쇠」."""
    def norm(t):
        return re.sub(r"[\W_]", "", re.sub(r"\s*\([^)]*\)\s*$", "", clean_title(t))).lower()
    return bool(norm(a)) and norm(a) == norm(b)


def same_author(suggested, found):
    """제안한 저자 이름의 낱말(2자 이상) 하나라도 실제 저자 칸에 있는가. 「재레드 다이아몬드」 ↔ 「재레드 다이아몬드 지음 ;김진준 옮김」."""
    found = re.sub(r"\s", "", found or "")
    return any(len(w) >= 2 and w in found for w in re.split(r"[\s,·;/]+", suggested or ""))


def find_book(title, author):
    """관련 도서 검증(PRD FR-31, FR-51, 10-31): 제목으로 찾아 제목·저자가 맞는 책 중 대출이 가장 많은 한 권. 없으면 None.
    아동·학습참고서는 뺀다(「(10대를 위한) 사피엔스」 같은 판은 제목이 달라 걸리지 않음)."""
    body = _call("srchBooks", {"title": clean_title(title), "pageSize": 20})
    for doc in _docs(body):  # 대출 많은 순
        if ((doc.get("addition_symbol") or " ")[0] not in SKIP_READERS
                and same_title(title, doc.get("bookname")) and same_author(author, doc.get("authors"))):
            return _book(doc)
    return None


def popular_loans(conditions, n):
    """조건별 인기 대출(PRD FR-52, 9~12쪽 loanItemSrch). conditions의 코드는 위 표에 있는 값만 쓰고 나머지는 버린다.
    돌려주는 값: (쓴 조건 {이름: 화면 글}, 기간 (시작, 끝), 책 목록). 같은 제목은 한 줄로."""
    used, params = {}, {}
    for name, table in (("gender", GENDERS), ("age", AGES), ("region", REGIONS), ("kdc", KDCS)):
        code = str(conditions.get(name) or "")
        if code in table:
            params[name], used[name] = code, table[code] + (" 도서관" if name == "region" else "")
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=config.LIBRARY_DAYS - 1)
    body = _call("loanItemSrch", {"startDt": start.isoformat(), "endDt": end.isoformat(), "pageSize": n * 3, **params})
    books, seen = [], set()
    for doc in _docs(body):
        book = _book(doc)
        if book["title"] in seen:
            continue
        seen.add(book["title"])
        books.append(book)
        if len(books) == n:
            break
    return used, (start.isoformat(), end.isoformat()), books


def libraries_with(isbn, region="21"):
    """책을 가진 도서관(PRD FR-33, 38~39쪽 libSrchByBook). 기본 부산(21). 돌려주는 값: (도서관 수, 이름 목록)."""
    body = _call("libSrchByBook", {"isbn": isbn, "region": region, "pageSize": 100})
    libs = _docs(body, "libs", "lib")
    return int(body.get("numFound") or len(libs)), [(lib.get("libName") or "").strip() for lib in libs]
