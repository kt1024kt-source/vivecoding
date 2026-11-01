"""로컬 서버: web/ 화면, AI 도우미 POST /api/chat, 관련 도서 POST /api/books (PRD FR-50, FR-31, FR-51, NFR-07, NFR-08).

run.bat이 build.py 다음에 띄운다. 127.0.0.1에서만 받는다. 배포 때는 같은 core/chat.py를 서버 함수가 부른다(페이즈 5).
실행: python serve.py  →  http://127.0.0.1:8000
"""
import json
import sys
import time
from collections import defaultdict, deque
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock

from core import chat, config, related_books

HOST, PORT = "127.0.0.1", 8000
MAX_BODY = 8192  # 질문 200자와 [관련 도서 찾기]에 함께 보내는 답(서버에서 800자로 자름)을 담기에 넉넉한 요청 크기

_recent = defaultdict(deque)  # IP → 최근 1분 질문 시각
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


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path not in ("/api/chat", "/api/books"):
            return self._json(404, {"error": "없는 주소입니다."})
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_BODY:
            return self._json(400, {"error": "질문이 너무 깁니다."})
        try:
            req = json.loads(self.rfile.read(length))
            question = req.get("question")
        except (ValueError, AttributeError):
            return self._json(400, {"error": "질문을 읽지 못했습니다."})
        if not allow(self.client_address[0]):  # 질문과 [관련 도서 찾기]를 합쳐 1분 한도
            return self._json(429, {"error": f"AI 도우미는 1분에 {config.CHAT_PER_MINUTE}번까지 쓸 수 있습니다. 잠시 뒤 다시 해 주세요."})
        try:
            # 모델과 생각 수준은 chat.ask·related_books가 허용 목록으로 걸러 낸다
            if self.path == "/api/chat":
                out = chat.ask(question, model=req.get("model"), thinking=req.get("thinking"))
            elif req.get("issue"):  # 이슈 상세: data.json에 있는 이슈만 받는다
                out = dict(related_books.for_issue(str(req["issue"]), model=req.get("model")))
            else:  # AI 도우미 답 아래
                out = related_books.for_answer(question, req.get("answer"), model=req.get("model"))
            reason = out.pop("fallback_reason", None)
            if reason:
                print(f"[AI 도우미] {out['model']}가 대신 답함 (기본 실패: {reason})", file=sys.stderr)
            if self.path == "/api/books":
                print(f"[관련 도서] 제안 {out.pop('suggested')}권 중 확인 {out.pop('checked')}권", file=sys.stderr)
            return self._json(200, out)
        except chat.ChatError as e:
            if e.__cause__:  # 원인은 터미널에만(키는 오류 메시지에 들어가지 않음)
                print(f"[AI 도우미] {e.__cause__}", file=sys.stderr)
            return self._json(503 if e.__cause__ else 400, {"error": str(e)})

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), partial(Handler, directory=str(config.WEB_DIR)))
    print(f"http://{HOST}:{PORT} 에서 화면과 AI 도우미를 엽니다. 끝내려면 Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
