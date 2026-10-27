import pytest
from streamlit.errors import StreamlitSecretNotFoundError

from core.auth import SecretsConfigError, read_password


class FakeSecrets(dict):
    """st.secrets처럼 접근할 때 예외를 낼 수 있는 대역."""

    def __init__(self, error=None, **values):
        super().__init__(**values)
        self.error = error

    def get(self, key, default=None):
        if self.error:
            raise self.error
        return super().get(key, default)


def secrets_error(error_id):
    return StreamlitSecretNotFoundError("secrets error", error_id=error_id)


def test_password_from_secrets():
    assert read_password(FakeSecrets(APP_PASSWORD="pw")) == "pw"


def test_no_password_key_means_open():
    assert read_password(FakeSecrets(OTHER="x")) is None


def test_missing_secrets_file_means_open():
    assert read_password(FakeSecrets(error=secrets_error("no-secrets-found"))) is None


def test_malformed_secrets_file_locks_app():
    # B2: TOML 문법 오류(따옴표 누락 등)가 "비밀번호 없음"으로 처리되면 안 된다.
    with pytest.raises(SecretsConfigError):
        read_password(FakeSecrets(error=secrets_error("failed-parsing-secrets-file")))


@pytest.mark.parametrize("value", ["", "   ", 1234, ["pw"]])
def test_empty_or_non_string_password_locks_app(value):
    with pytest.raises(SecretsConfigError):
        read_password(FakeSecrets(APP_PASSWORD=value))


def test_login_throttle_locks_after_repeated_failures():
    from core.auth import LoginThrottle

    t = [0.0]
    throttle = LoginThrottle(max_failures=3, window_seconds=60, lock_seconds=30, now=lambda: t[0])
    for _ in range(2):
        throttle.record_failure()
    assert throttle.remaining_lock() == 0
    throttle.record_failure()
    assert throttle.remaining_lock() == 30
    t[0] = 29
    assert throttle.remaining_lock() == 1
    t[0] = 30
    assert throttle.remaining_lock() == 0


def test_login_throttle_forgets_old_failures():
    from core.auth import LoginThrottle

    t = [0.0]
    throttle = LoginThrottle(max_failures=3, window_seconds=60, lock_seconds=30, now=lambda: t[0])
    throttle.record_failure()
    throttle.record_failure()
    t[0] = 61  # 앞의 두 번은 창 밖으로 밀려난다
    throttle.record_failure()
    assert throttle.remaining_lock() == 0
