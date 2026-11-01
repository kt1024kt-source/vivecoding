"""API 테스트 공용 도구. 표준 라이브러리만 쓴다(설치 불필요).

- .env는 실행할 때만 읽고, 키 값은 화면에 출력하지 않는다.
- 응답은 파일로 저장하지 않는다(YES24 축적 금지, 정보나루 표지 URL 저장 금지).
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# 한글 출력이 깨지지 않게 한다(Windows 콘솔)
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env(*names):
    """.env에서 필요한 키만 읽어 dict로 돌려준다. 값이 비어 있으면 종료한다."""
    if not ENV_PATH.exists():
        sys.exit(f"[중단] .env가 없습니다: {ENV_PATH}")
    values = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    missing = [n for n in names if not values.get(n)]
    if missing:
        filled = [n for n, v in values.items() if v]
        sys.exit(f"[중단] .env에 값이 비어 있습니다: {', '.join(missing)}\n"
                 f"       값이 있는 이름(값은 출력하지 않음): {', '.join(filled) or '없음'}")
    print(f"[확인] .env에서 {', '.join(names)} 읽음 (값은 출력하지 않음)")
    return {n: values[n] for n in names}


def get_json(base_url, params=None, headers=None, timeout=15, json_body=None):
    """요청을 보내 (HTTP 상태 코드, JSON 또는 원문 앞부분)을 돌려준다.

    json_body가 있으면 POST(JSON 본문), 없으면 GET으로 보낸다.
    URL에 키가 들어갈 수 있으므로 URL 전체는 출력하지 않는다.
    """
    url = base_url
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = dict(headers or {})
    data = None
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            status, body = res.status, res.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        sys.exit(f"[실패] 연결 오류: {e.reason}")
    print(f"[응답] HTTP {status}")
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, body[:500]


def find_key(obj, key):
    """응답 구조가 확인되기 전이므로, 중첩된 dict/list에서 key를 처음 찾은 값을 돌려준다."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        children = obj.values()
    elif isinstance(obj, list):
        children = obj
    else:
        return None
    for child in children:
        found = find_key(child, key)
        if found is not None:
            return found
    return None


def show_structure(obj, depth=0, max_depth=3):
    """값 없이 키 이름과 자료형만 보여 준다(응답 구조 확인용)."""
    pad = "  " * depth
    if depth > max_depth:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            print(f"{pad}{k}: {type(v).__name__}")
            show_structure(v, depth + 1, max_depth)
    elif isinstance(obj, list) and obj:
        print(f"{pad}[0] (총 {len(obj)}개)")
        show_structure(obj[0], depth + 1, max_depth)
