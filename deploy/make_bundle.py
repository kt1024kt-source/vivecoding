"""배포 폴더 만들기: build.py가 만든 web/data.json과 화면, 서버 함수를 deploy_out/trandeer/에 모은다 (DEPLOY_PLAN 작업 3).

GitHub Actions가 빌드 뒤에 부르고, 그 폴더를 Vercel CLI로 올린다. data.json은 Git에 커밋하지 않고 여기에만 담는다(NFR-03).
- 화면: web/ → 배포 폴더의 web/ (vercel.json의 outputDirectory라 주소 맨 위에 보인다)
- 함수: api/ 와 함수가 쓰는 core 파일만. requirements.txt에는 requests만(Vercel은 적힌 패키지를 함수에 담는다)
- 오늘의 이슈가 비면 배포하지 않고 실패로 끝낸다. 이전 배포가 그대로 남는다(10-31 작업자 결정 D4, FR-03)
실행: python deploy/make_bundle.py
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deploy_out" / "trandeer"  # 폴더 이름이 Vercel 프로젝트 이름이 된다(첫 배포 때)

# 서버 함수가 부르는 모듈(pandas·kiwipiepy를 쓰는 build 쪽 모듈은 넣지 않는다)
CORE_FILES = [
    "core/__init__.py", "core/config.py", "core/chat.py", "core/related_books.py", "core/web_api.py",
    "core/sources/__init__.py", "core/sources/_http.py", "core/sources/library_search.py",
]
WEB_SKIP = ("*.pyc",)


def requests_line():
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("requests=="):
            return line
    sys.exit("[중단] requirements.txt에 requests 줄이 없다")


def main():
    data_json = ROOT / "web" / "data.json"
    if not data_json.exists():
        sys.exit("[중단] web/data.json이 없어 배포하지 않는다")
    data = json.loads(data_json.read_text(encoding="utf-8"))
    if not data.get("issues"):
        errors = "\n  ".join(data.get("errors") or ["(실패 기록 없음)"])
        sys.exit(f"[중단] 오늘의 이슈가 비어 배포하지 않는다. 이전 배포가 그대로 남는다:\n  {errors}")

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "web", OUT / "web", ignore=shutil.ignore_patterns(*WEB_SKIP))
    shutil.copytree(ROOT / "api", OUT / "api", ignore=shutil.ignore_patterns("__pycache__"))
    for rel in CORE_FILES:
        (OUT / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, OUT / rel)
    shutil.copy2(ROOT / "deploy" / "vercel.json", OUT / "vercel.json")
    (OUT / "requirements.txt").write_text(requests_line() + "\n", encoding="utf-8")

    files = sorted(p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file())
    print(f"[완료] {OUT.relative_to(ROOT).as_posix()}/ 파일 {len(files)}개, 이슈 {len(data['issues'])}개, "
          f"data.json {data.get('generated_at')}")
    for f in files:
        print(f"  {f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
