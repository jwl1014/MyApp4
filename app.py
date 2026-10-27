"""앱 진입점: 페이지 설정, 비밀번호 확인, 네비게이션."""

import hmac
import logging
import time
from urllib.parse import urlparse

import streamlit as st

from core.auth import LoginThrottle, SecretsConfigError, read_password
from core.db import get_storage
from core.styles import inject_css

st.set_page_config(page_title="헬스 기록", page_icon="🏋️", layout="centered")
inject_css()

# (파일, 제목, 아이콘, URL 경로). 첫 항목이 기본 페이지다.
# 페이지 폴더 이름을 pages/로 하면 Streamlit이 자동 인식해, 서버 시작 직후 페이지 주소로 바로 들어올 때
# app.py(로그인·CSS)를 거치지 않고 실행된다. 그래서 views/를 쓴다.
PAGES = [
    ("views/1_운동_기록.py", "운동 기록", "📝", "운동_기록"),
    ("views/2_운동_이력.py", "운동 이력", "📅", "운동_이력"),
    ("views/3_운동_사전.py", "운동 사전", "📚", "운동_사전"),
    ("views/4_즐겨찾기.py", "즐겨찾기", "⭐", "즐겨찾기"),
]


def gate(page_fn, title: str, icon: str) -> None:
    """모든 URL을 page_fn 하나에 연결해 띄우고 스크립트를 멈춘다.
    st.navigation을 반드시 호출해야 페이지 주소로 바로 들어와도 다른 페이지가 열리지 않는다.
    """
    gate_pages = [
        st.Page(page_fn, title=title, icon=icon, url_path=url, default=i == 0)
        for i, (_, _, _, url) in enumerate(PAGES)
    ]
    st.navigation(gate_pages, position="hidden").run()
    st.stop()


def is_local_request() -> bool:
    host = urlparse(st.context.url or "").hostname or ""
    return host in ("localhost", "127.0.0.1", "::1")


# PRD 8장: secrets에 APP_PASSWORD가 있을 때만 비밀번호를 묻는다.
# secrets 형식이 틀리면 비밀번호 없이 열리지 않도록 앱을 잠근다.
def config_error_page() -> None:
    st.title("🔒 헬스 기록")
    st.error("비밀번호 설정(secrets)을 읽지 못해 앱을 잠갔어요. 관리자에게 알려주세요.", icon="🚫")
    # 오류 상세(파일 경로 등)는 방문자에게 보이지 않게 서버 로그에만 남긴다.
    st.caption("관리자용: secrets의 TOML 형식과 APP_PASSWORD 값을 확인하세요. 자세한 내용은 서버 로그에 있어요.")


try:
    password = read_password(st.secrets)
except SecretsConfigError as e:
    logging.getLogger(__name__).error("secrets 설정 오류로 앱을 잠금: %s", e)
    gate(config_error_page, "설정 오류", "🔒")


@st.cache_resource
def app_login_throttle() -> LoginThrottle:
    # 앱 전체(모든 세션)에서 10분 동안 20번 틀리면 5분간 로그인을 막는다.
    return LoginThrottle(max_failures=20, window_seconds=600, lock_seconds=300)


def login_page() -> None:
    st.title("🏋️ 헬스 기록")
    # 세션마다 5번 틀리면 30초간 막는다.
    session_throttle = st.session_state.setdefault(
        "_login_throttle", LoginThrottle(max_failures=5, window_seconds=300, lock_seconds=30)
    )
    throttles = (session_throttle, app_login_throttle())
    wait = max(t.remaining_lock() for t in throttles)
    with st.form("login"):
        entered = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("들어가기", type="primary", disabled=wait > 0)
    if wait > 0:
        st.warning(f"비밀번호를 여러 번 틀려 잠시 막았어요. {int(wait) + 1}초 후에 다시 시도해 주세요.", icon="⏳")
        return
    if submitted:
        if hmac.compare_digest(entered.encode(), password.encode()):
            for t in throttles:
                t.record_success()
            st.session_state["authenticated"] = True
            st.rerun()
        for t in throttles:
            t.record_failure()
        time.sleep(1)  # 연속 대입을 느리게 한다
        if max(t.remaining_lock() for t in throttles) > 0:
            st.rerun()
        st.error("비밀번호가 올바르지 않아요.")


# 로그인 전에는 모든 URL을 로그인 화면에 연결한다. 페이지 주소로 바로 들어와도 로그인 후 그 페이지가 열린다.
if password and not st.session_state.get("authenticated"):
    gate(login_page, "로그인", "🔒")

# 비밀번호 없이 PC 밖(휴대폰, 배포 URL 등)에서 접속하면 한 번 알려준다.
if password is None and not is_local_request() and not st.session_state.get("_no_password_warned"):
    st.session_state["_no_password_warned"] = True
    st.toast("비밀번호가 설정되지 않아 이 주소를 아는 누구나 접근할 수 있어요.", icon="⚠️", duration="long")

# 첫 실행 시 DB 생성 및 시드 적재
get_storage()

pages = [
    st.Page(path, title=title, icon=icon, url_path=url, default=i == 0)
    for i, (path, title, icon, url) in enumerate(PAGES)
]
# 상단 메뉴: 데스크톱에서는 사이드바 없이 본문을 넓게 쓰고, 모바일에서는 자동으로 접히는 메뉴가 된다.
st.navigation(pages, position="top").run()
