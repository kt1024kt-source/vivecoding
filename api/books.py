"""배포 서버 함수: 관련 도서 POST /api/books (PRD FR-31, FR-51). 처리는 core/web_api.py로 로컬 serve.py와 같다."""
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 배포 폴더 맨 위의 core/를 찾게 한다

from core import web_api  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        web_api.serve(self, "/api/books", web_api.forwarded_ip(self))
