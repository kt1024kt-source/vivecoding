"""형태소 분석과 불용어 (PRD 6.1의 4~5단계).

불용어 목록은 화면의 「선정 기준 보기」(FR-13)에 그대로 공개하므로 이 파일 한곳에서만 관리한다.
"""
from functools import lru_cache

from kiwipiepy import Kiwi

from core import config

# 명사(일반, 고유)와 영문 약어(예: AI, LG)만 키워드로 쓴다
NOUN_TAGS = {"NNG", "NNP"}
# 오늘의 이슈는 고유명사와 영문 약어만 쓴다(PRD 6.1, 10-28 결정)
PROPER_TAGS = {"NNP", "SL"}

# 형태소 분석기가 잘못 자르는 고유명사(예: 김건희 → 김건 + 희). 발견하면 더하고 날짜를 log.md에 남긴다
USER_WORDS = ["김건희"]

# 화면에 공개할 불용어. 실제 결과를 보며 늘리고, 늘린 날짜를 log.md에 남긴다
STOPWORD_GROUPS = {
    "수집 검색어": set(config.NEWS_QUERIES),
    "공통 상투어": {
        "사람", "자신", "시작", "필요", "시간", "가능", "대표", "특별", "최고", "이번", "최근",
        "오늘", "올해", "내년", "작년", "지난해", "오전", "오후", "대상", "관련", "통해", "위해",
    },
    "뉴스 상투어": {
        "속보", "단독", "종합", "기자", "사진", "영상", "포토", "뉴스", "인터뷰", "개최", "지원",
        "진행", "실시", "추진", "발표", "선정", "참여", "기념", "행사", "운영", "마련", "확대",
        "사설",  # 언론사 사설 머리표(10-28 추가)
    },
    "출판 상투어": {
        "독자", "작가", "저자", "출간", "출판", "수록", "작품", "베스트셀러", "이야기", "도서",
        "에디션", "개정", "번역", "신작", "장편", "소설", "시리즈", "페이지",
    },
    # 오늘의 이슈에서만 뺀다. 나라와 광역 지명이 이슈 자리를 차지해서(10-27 실험)
    "지명": {
        "한국", "대한민국", "코리아", "국내", "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
        "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주", "미국", "중국", "일본",
    },
}
NEWS_STOPWORDS = (STOPWORD_GROUPS["수집 검색어"] | STOPWORD_GROUPS["공통 상투어"]
                  | STOPWORD_GROUPS["뉴스 상투어"])
BOOK_STOPWORDS = STOPWORD_GROUPS["공통 상투어"] | STOPWORD_GROUPS["출판 상투어"]
PLACE_STOPWORDS = STOPWORD_GROUPS["지명"]


@lru_cache(maxsize=1)
def _kiwi():
    kiwi = Kiwi()
    for word in USER_WORDS:
        kiwi.add_user_word(word, "NNP")
    return kiwi


def nouns(text, stopwords=frozenset()):
    """한 문서의 키워드 집합. 한 문서에 여러 번 나와도 한 번으로 친다(문서 빈도용)."""
    return set(noun_tags(text, stopwords))


def noun_tags(text, stopwords=frozenset()):
    """한 문서의 키워드와 품사 {단어: 품사}. 오늘의 이슈에서 고유명사만 고를 때 품사를 쓴다."""
    if not text:
        return {}
    words = {}
    for token in _kiwi().tokenize(text):
        word = token.form
        if token.tag == "SL":
            # 영문은 대문자 약어만 남긴다(to, the 같은 일반 단어 제외)
            if not word.isupper():
                continue
        elif token.tag not in NOUN_TAGS:
            continue
        if len(word) < 2 or word in stopwords:
            continue
        words.setdefault(word, token.tag)
    return words
