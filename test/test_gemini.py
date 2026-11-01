"""Gemini API 키 확인 테스트 (모델 목록 조회 1회, 텍스트 생성 없음).

근거: https://ai.google.dev/api/models (2026-10-26 확인)
- GET https://generativelanguage.googleapis.com/v1beta/models?key=...
- 응답: models[].name, displayName, supportedGenerationMethods
- 어떤 데이터도 Gemini에 보내지 않는다. 쓸 모델 이름을 이 목록에서 고른다.

실행: python test_gemini.py
"""
import sys

from _common import get_json, load_env

URL = "https://generativelanguage.googleapis.com/v1beta/models"

key = load_env("GOOGLE_API_KEY")["GOOGLE_API_KEY"]
status, data = get_json(URL, params={"key": key, "pageSize": 100})

if not isinstance(data, dict):
    sys.exit(f"[실패] JSON이 아닌 응답: {data}")
if status != 200:
    error = data.get("error", {})
    sys.exit(f"[실패] {error.get('status')}: {error.get('message')}")

models = data.get("models", [])
usable = [m for m in models if "generateContent" in m.get("supportedGenerationMethods", [])]
print(f"[결과] 모델 {len(models)}개 중 generateContent 지원 {len(usable)}개")
for m in usable:
    print(f"  {m.get('name')}  ({m.get('displayName')})")
print("\n[성공] Gemini API 키 확인")
