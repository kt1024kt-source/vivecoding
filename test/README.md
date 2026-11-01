# API 호출 테스트

키가 맞는지, 응답 구조가 어떤지 확인하는 최소 코드다. 표준 라이브러리만 써서 설치가 필요 없다(Python 3.11.9에서 작성).

| 파일 | API | 호출 수 | 근거 |
|---|---|---|---|
| `test_yes24.py` | YES24 카테고리 베스트셀러 | 1 | https://developers.yes24.com/api-doc/category-bestseller |
| `test_data4library.py` | 정보나루 인기대출도서, 이달의 키워드 | 2 | `../input/도서관정보나루_API_Manual.md` |
| `test_gemini.py` | Gemini 모델 목록 | 1 | https://ai.google.dev/api/models |
| `test_naver.py` | NAVER API HUB 뉴스 검색 | 1 | `../input/NAVER_API_HUB_Search_News_Manual.md` |
| `test_naver_trend.py` | 검색어 트렌드(`hub` 또는 `datalab`) | 1 | `../input/NAVER_API_HUB_Search_Trend_Manual.md`, `../input/네이버_데이터랩_통합검색어트렌드_API_매뉴얼.md` |

## 실행

이 폴더(`test/`)에서 실행한다.

```
python test_yes24.py
python test_data4library.py
python test_gemini.py
python test_naver.py [검색어]
python test_naver_trend.py [hub|datalab]
```

## 지키는 것

- 키는 `../.env`에서 실행할 때만 읽고 출력하지 않는다.
- 응답은 화면에만 보여 주고 파일로 저장하지 않는다.
- 호출 한도가 있으니 반복 실행하지 않는다.
