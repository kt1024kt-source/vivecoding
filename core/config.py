"""키 읽기와 설정값.

키는 환경 변수(자동 빌드의 GitHub Actions Secrets) → .env(로컬) 순서로 찾는다.
값은 화면, 로그, data.json에 넣지 않는다(PRD NFR-01). 브라우저 쪽(web/)에는 키가 가지 않는다.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
WEB_DIR = ROOT / "web"
DATA_JSON = WEB_DIR / "data.json"   # build.py가 만들고 web/index.html이 읽는다

# 뉴스 수집 (PRD 6.1)
NEWS_QUERIES = ["정치", "경제", "사회", "문화", "국제", "IT", "과학"]  # IT·과학은 일치 기사가 적어 둘로 나눔(10-27)
NEWS_WINDOW_HOURS = 12
NEWS_PAGE_SIZE = 100      # display 최대값
NEWS_MAX_START = 1000     # start 최대값
NEWS_STORE = ROOT / "store" / "news_store.json"  # 빌드마다 쌓는 최근 N시간 기사(Git 제외, 10-27 누적 방식)

# 도서 (PRD 6.2)
YES24_CATEGORY_ID = "001"
YES24_TOP_N = 100         # pageSize 최대값
YES24_CACHE = ROOT / "store" / "yes24_today.json"  # 하루 1회 받은 결과(책 소개 포함, 하루치만 덮어씀, Git 제외)
BOOK_EXCLUDE_SORTS = ("국내도서-수험서 자격증",)  # 도서 키워드에서 뺄 분류(10-26 결정), 목록에는 그대로 보인다

# 도서관 인기 대출 (PRD FR-41, 10-29): 전국·전체 대상, 같은 제목 여러 권은 한 줄로
LIBRARY_DAYS = 30         # 어제까지 최근 30일 대출
LIBRARY_FETCH_N = 300     # 한 번에 받을 권 수(묶기 전)
LIBRARY_TOP_N = 100       # 묶은 뒤 남길 줄 수
LIBRARY_CACHE = ROOT / "store" / "library_today.json"  # 하루 1회 받은 결과(하루치만 덮어씀, Git 제외)

# 관련 도서 (PRD FR-31~33, FR-51, 10-31 작업자 결정): [관련 도서 찾기]를 누를 때만 Gemini가 제목·저자를 제안하고
# 정보나루 → 예스24 제목 검색으로 실제 있는 책인지 확인한다. 화면 값은 API 결과만
RELATED_SUGGEST_N = 10    # Gemini에 제안받을 권 수. 지어낸 책이 많아(10-31 시험: 확인 비율 low 4/21, medium 5/10) 넉넉히 받는다
RELATED_THINKING = "medium"  # 책 제안은 생각 수준 고정(low는 없는 책을 더 많이 냄). 모델은 화면에서 고른 것을 쓴다
RELATED_SHOW_N = 3        # 확인된 책 중 보여 줄 권 수
BUSAN_REGION = "21"       # 정보나루 지역 코드(매뉴얼 62쪽), 책마다 부산 소장 도서관

# 분석과 화면(data.json에 담는 양)
ISSUE_TOP_N = 10

# 이슈와 뉴스 워드클라우드 점수 (PRD 6.1, 10-28 결정): 언론사 수 × log10(IDF_N / 네이버 뉴스 전체 건수)
IDF_N = 1_000_000_000         # 네이버 뉴스 전체 기사 수의 근사 상수
GENERIC_TOTAL = 10_000_000    # 전체 건수가 이 이상이면 평소에 흔한 일반 단어로 보고 뺀다
RESCUE_LIFT = 3.0             # 일반 단어라도 평소 대비 배율이 이 이상이면 건져 올린다(10-28, 12시간치로 재확인 예정)
ISSUE_POOL = 60               # 이슈 점수를 매길 후보(언론사 수 상위) 수
ISSUE_MIN_OUTLETS = 5         # 이보다 적은 언론사만 쓴 단어는 이슈에서 뺀다(데이터가 적을 때의 우연 방지)
CLOUD_POOL = 200              # 워드클라우드 점수를 매길 후보 수
WORD_TOTALS_CACHE = ROOT / "store" / "word_totals.json"  # 단어별 전체 건수, 그날 조회분만 보관
CLOUD_TOP_N = 100         # 워드클라우드마다 담을 키워드 수
ISSUE_ARTICLES_N = 20     # 이슈마다 담을 관련 기사 수

# AI 도우미 (PRD FR-50, NFR-08, 10-30)
# 버전 고정 이름(-latest 별칭은 시연 직전에 바뀔 수 있어 쓰지 않음, PRD 5.5). 10-30 시험: 2.5-flash는 새 사용자에게 막힘(404),
# 3.8·3.7-flash는 수요 과다로 40초 초과·503, 3.5-flash는 생각 수준 low로 2~3초
GEMINI_MODEL = "gemini-3.5-flash"  # 기본값
GEMINI_THINKING = "low"
# 화면에서 고를 수 있는 값(10-30 작업자 요청). 서버는 이 목록에 있는 값만 받고 나머지는 기본값으로 바꾼다
CHAT_MODELS = {"gemini-3.5-flash": "3.5 Flash", "gemini-3.7-flash": "3.7 Flash", "gemini-3.8-flash": "3.8 Flash"}
CHAT_THINKING = {"low": "낮음", "medium": "중간"}
GEMINI_FALLBACK = "gemini-3.5-flash-lite"  # 수요 과다(503)·시간 초과 때 한 번만 대신 부름(10-30 시험: 3.1-flash-lite는 1~24초로 들쭉날쭉해 바꿈)
GEMINI_FALLBACK_THINKING = "medium"  # 대체 모델은 생각 수준 고정. low는 「가장 큰 이슈」를 근거 부족으로 잘못 답함(10-30 시험), medium은 4~6초
CHAT_MAX_CHARS = 200      # 질문 길이 한도
CHAT_PER_MINUTE = 5       # 한 사람(IP)이 1분에 보낼 수 있는 질문 수
CHAT_BOOKS_N = 50         # Gemini에 넘길 예스24·도서관 목록 각각의 권 수
CHAT_SOURCES_N = 5        # 답에 붙일 근거 기사 수
CHAT_LOANS_N = 5          # 도서관 조건 질문(FR-52)에 붙일 책 수


def _read_env_file():
    values = {}
    if not ENV_PATH.exists():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def get_key(name):
    """키 값을 돌려준다. 없으면 이름만 담아 KeyError를 낸다."""
    for source in (os.environ, _read_env_file()):
        if source.get(name):
            return source[name]
    raise KeyError(f"키가 없습니다: {name}")


def key_status(*names):
    """키가 있는지 여부만 돌려준다(값은 돌려주지 않음)."""
    status = {}
    for name in names:
        try:
            get_key(name)
            status[name] = True
        except KeyError:
            status[name] = False
    return status
