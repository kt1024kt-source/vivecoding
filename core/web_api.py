"""AI 도우미 POST /api/chat, 관련 도서 POST /api/books의 처리 (PRD FR-50, FR-31, FR-51, NFR-07, NFR-08).

로컬 서버(serve.py)와 배포 서버 함수(api/chat.py, api/books.py)가 같이 쓴다.
pandas·kiwipiepy 없이 돈다(배포 함수에는 requests만 설치, DEPLOY_PLAN 2.2).
"""
import json
import sys
import time
from collections import defaultdict, deque
from threading import Lock

from core import chat, config, related_books

PATHS = ("/api/chat", "/api/books")
MAX_BODY = 8192  # 질문 200자, [관련 도서 찾기]의 이슈 낱말이나 검색어 3개를 담기에 넉넉한 요청 크기

_recent = defaultdict(deque)  # IP → 최근 1분 질문 시각. 배포에서는 함수 인스턴스마다 따로 센다(DEPLOY_PLAN 4.2)
_lock = Lock()


def allow(ip):
    """IP마다 1분에 config.CHAT_PER_MINUTE번까지(NFR-08)."""
    now = time.monotonic()
    with _lock:
        q = _recent[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= config.CHAT_PER_MINUTE:
            return False
        q.append(now)
        return True


def answer(path, req, ip):
    """요청 하나를 처리해 (상태 코드, 응답 dict)를 돌려준다."""
    if not allow(ip):  # 질문과 [관련 도서 찾기]를 합쳐 1분 한도
        return 429, {"error": f"AI 도우미는 1분에 {config.CHAT_PER_MINUTE}번까지 쓸 수 있습니다. 잠시 뒤 다시 해 주세요."}
    try:
        # 모델과 생각 수준은 chat.ask·related_books가 허용 목록으로 걸러 낸다
        if path == "/api/chat":
            out = chat.ask(req.get("question"), model=req.get("model"), thinking=req.get("thinking"))
        elif req.get("issue"):  # 이슈 상세: data.json에 있는 이슈만 받는다
            out = dict(related_books.for_issue(str(req["issue"]), model=req.get("model")))
        else:  # AI 도우미 답 아래: 답과 함께 받은 검색어로 정보나루만 찾는다(11-08)
            out = related_books.for_keywords(req.get("keywords"))
        reason = out.pop("fallback_reason", None)
        if reason:
            print(f"[AI 도우미] {out['model']}가 대신 답함 (기본 실패: {reason})", file=sys.stderr)
        if "suggested" in out:
            print(f"[관련 도서] 제안 {out.pop('suggested')}권 중 확인 {out.pop('checked')}권", file=sys.stderr)
        return 200, out
    except chat.ChatError as e:
        if e.__cause__:  # 원인은 서버 기록에만(키는 오류 메시지에 들어가지 않음)
            print(f"[AI 도우미] {e.__cause__}", file=sys.stderr)
        return (503 if e.__cause__ else 400), {"error": str(e)}


def serve(handler, path, ip):
    """BaseHTTPRequestHandler의 POST 하나를 읽고 JSON으로 답한다."""
    if path not in PATHS:
        return send_json(handler, 404, {"error": "없는 주소입니다."})
    length = int(handler.headers.get("Content-Length") or 0)
    if not 0 < length <= MAX_BODY:
        return send_json(handler, 400, {"error": "질문이 너무 깁니다."})
    try:
        req = json.loads(handler.rfile.read(length))
    except ValueError:
        req = None
    if not isinstance(req, dict):
        return send_json(handler, 400, {"error": "질문을 읽지 못했습니다."})
    send_json(handler, *answer(path, req, ip))


def forwarded_ip(handler):
    """배포 함수에서 요청한 사람의 IP. Vercel이 X-Forwarded-For에 넣어 준다."""
    fwd = handler.headers.get("X-Forwarded-For") or ""
    return fwd.split(",")[0].strip() or handler.client_address[0]


def send_json(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)
