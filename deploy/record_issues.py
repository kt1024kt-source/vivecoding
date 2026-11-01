"""오늘의 이슈 기록: 09시·21시(KST)가 지난 뒤 첫 빌드에서 data.json의 이슈를 history/issues.csv에 한 번 더한다 (DEPLOY_PLAN 3장).

10-31 작업자 결정: 기록은 오늘의 이슈만, 저장소의 CSV에. 직접 계산한 낱말·점수·건수만 남기고 기사 제목과 링크는 넣지 않는다.
예약 실행이 늦거나 빠져도 그 회차를 아직 적지 않았으면 다음 빌드가 적는다. GitHub Actions가 빌드 뒤에 부르고 커밋한다.
실행: python deploy/record_issues.py
"""
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "history" / "issues.csv"
COLUMNS = ["slot", "generated_at", "rank", "word", "score", "outlet_count", "article_count"]
SLOT_HOURS = (9, 21)
KST = timezone(timedelta(hours=9))


def current_slot(now):
    """지금 시각이 속한 회차. 09시 전이면 전날 21시 회차."""
    passed = [h for h in SLOT_HOURS if now.hour >= h]
    day = now if passed else now - timedelta(days=1)
    hour = passed[-1] if passed else SLOT_HOURS[-1]
    return f"{day:%Y-%m-%d} {hour:02d}"


def main():
    data = json.loads((ROOT / "web" / "data.json").read_text(encoding="utf-8"))
    if not data.get("issues"):
        print("[건너뜀] 오늘의 이슈가 비어 있다")
        return
    slot = current_slot(datetime.fromisoformat(data["generated_at"]).astimezone(KST))
    if HISTORY.exists():
        with HISTORY.open(encoding="utf-8", newline="") as f:
            if any(row["slot"] == slot for row in csv.DictReader(f)):
                print(f"[건너뜀] {slot}시 회차는 이미 기록함")
                return
    new = not HISTORY.exists()
    HISTORY.parent.mkdir(exist_ok=True)
    with HISTORY.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(COLUMNS)
        for rank, issue in enumerate(data["issues"], 1):
            w.writerow([slot, data["generated_at"], rank, issue["word"], issue["score"],
                        issue["outlet_count"], issue["article_count"]])
    print(f"[기록] {slot}시 회차 이슈 {len(data['issues'])}개 → {HISTORY.parent.name}/{HISTORY.name}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
