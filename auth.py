"""비밀번호(APP_PASSWORD) 설정 읽기.

secrets 파일이 아예 없으면 비밀번호 없이 쓰는 것으로 본다 (로컬 개발).
파일은 있는데 읽지 못하거나 값이 비어 있으면 설정 오류로 보고 앱을 열지 않는다.
Streamlit은 두 경우 모두 같은 예외(StreamlitSecretNotFoundError)를 내므로 error_id로 구분한다.
"""

import time
from collections.abc import Mapping
from typing import Any

NO_SECRETS_ERROR_ID = "no-secrets-found"


class SecretsConfigError(Exception):
    """secrets 설정이 잘못되어 비밀번호 사용 여부를 판단할 수 없음."""


def read_password(secrets: Mapping[str, Any]) -> str | None:
    try:
        value = secrets.get("APP_PASSWORD")
    except FileNotFoundError as e:  # StreamlitSecretNotFoundError는 FileNotFoundError의 하위 클래스
        if getattr(e, "error_id", None) == NO_SECRETS_ERROR_ID:
            return None
        raise SecretsConfigError(str(e)) from e
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SecretsConfigError("APP_PASSWORD는 비어 있지 않은 문자열이어야 해요.")
    return value


class LoginThrottle:
    """로그인 실패가 몰리면 잠시 잠근다.

    세션 단위 잠금은 새 세션(새로고침)으로 우회할 수 있으므로, 앱 전체(프로세스)의 최근 실패 수도 함께 본다.
    """

    def __init__(self, max_failures: int, window_seconds: float, lock_seconds: float, now=None):
        self.max_failures = max_failures
        self.window = window_seconds
        self.lock = lock_seconds
        self._now = now or time.monotonic
        self._failures: list[float] = []
        self._locked_until = 0.0

    def remaining_lock(self) -> float:
        """잠금이 풀리기까지 남은 초. 잠겨 있지 않으면 0."""
        return max(0.0, self._locked_until - self._now())

    def record_failure(self) -> None:
        now = self._now()
        self._failures = [t for t in self._failures if now - t < self.window] + [now]
        if len(self._failures) >= self.max_failures:
            self._locked_until = now + self.lock
            self._failures.clear()

    def record_success(self) -> None:
        self._failures.clear()
