"""외부 API 요청 공용 함수. 오류 메시지에 키나 키가 든 URL을 넣지 않는다."""
import requests

TIMEOUT_SECONDS = 15


class ApiError(Exception):
    """API 호출 실패. 화면에 그대로 보여도 되는 정보만 담는다."""

    def __init__(self, source, status, detail):
        self.source, self.status, self.detail = source, status, detail
        super().__init__(f"[{source}] HTTP {status}: {detail}")


def get_json(source, url, params=None, headers=None):
    try:
        res = requests.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as e:
        raise ApiError(source, "연결 실패", type(e).__name__) from None
    try:
        data = res.json()
    except ValueError:
        raise ApiError(source, res.status_code, "JSON이 아닌 응답") from None
    if res.status_code != 200:
        raise ApiError(source, res.status_code, str(data)[:200])
    return data


def post_json(source, url, body, headers=None, timeout=TIMEOUT_SECONDS):
    try:
        res = requests.post(url, json=body, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise ApiError(source, "연결 실패", type(e).__name__) from None
    try:
        data = res.json()
    except ValueError:
        raise ApiError(source, res.status_code, "JSON이 아닌 응답") from None
    if res.status_code != 200:
        message = (data.get("error") or {}).get("message") if isinstance(data, dict) else None
        raise ApiError(source, res.status_code, str(message or data)[:200])
    return data
