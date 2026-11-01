"""로컬 서버: web/ 화면, AI 도우미 POST /api/chat, 관련 도서 POST /api/books (PRD FR-50, FR-31, FR-51, NFR-07, NFR-08).

run.bat이 build.py 다음에 띄운다. 127.0.0.1에서만 받는다. 처리는 core/web_api.py에 있고, 배포 때는 같은 처리를 api/chat.py, api/books.py가 부른다.
실행: python serve.py  →  http://127.0.0.1:8000
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from core import config, web_api

HOST, PORT = "127.0.0.1", 8000


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        web_api.serve(self, self.path, self.client_address[0])


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), partial(Handler, directory=str(config.WEB_DIR)))
    print(f"http://{HOST}:{PORT} 에서 화면과 AI 도우미를 엽니다. 끝내려면 Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
