from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from core.components import invalidate
from core.db import get_storage


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setenv("GYM_DB_PATH", str(tmp_path / "test.db"))
    invalidate()  # st.cache_data는 프로세스 전역이라 이전 테스트의 DB 내용이 남아 있을 수 있다
    yield get_storage()
    invalidate()


def test_record_page_survives_exercise_moved_to_other_part(storage):
    """B1: 기록 중인 운동의 부위를 운동 사전에서 바꿔도 기록 페이지가 멈추지 않아야 한다."""
    part = {p.name: p.id for p in storage.list_body_parts()}
    ex = {e.name: e.id for e in storage.list_exercises()}
    chest, back = part["가슴"], part["등"]

    at = AppTest.from_file("../views/1_운동_기록.py")
    # 가슴을 선택해 둔 상태에서 벤치프레스를 등으로 옮기고, 이어서 등을 선택한 상황
    # (등의 즐겨찾기에 옮겨진 벤치프레스가 따라 들어온다)
    storage.update_exercise(ex["벤치프레스"], body_part_id=back)
    invalidate()
    at.session_state["rec"] = {
        "date": date(2026, 10, 27),
        "parts": [chest, back],
        "items": {
            chest: [ex["벤치프레스"], ex["푸시업"], ex["딥스"]],
            back: [ex["랫풀다운"], ex["바벨로우"], ex["벤치프레스"]],
        },
        "unchecked": {ex["벤치프레스"]},
    }
    at.run(timeout=30)

    assert not at.exception
    labels = [c.label for c in at.checkbox]
    assert labels.count("벤치프레스") == 1
    rec = at.session_state["rec"]
    assert ex["벤치프레스"] not in rec["items"][chest]
    assert ex["벤치프레스"] in rec["items"][back]


def test_default_date_follows_today_in_long_session(storage, monkeypatch):
    """B6: 탭을 밤새 열어 둬도 기본 날짜가 '오늘'로 따라가야 한다."""
    from core import clock

    monkeypatch.setattr(clock, "today", lambda: date(2026, 10, 27))
    at = AppTest.from_file("../views/1_운동_기록.py")
    at.run(timeout=30)
    assert at.date_input[0].value == date(2026, 10, 27)

    monkeypatch.setattr(clock, "today", lambda: date(2026, 10, 28))  # 다음 날 같은 세션
    at.run(timeout=30)
    assert not at.exception
    assert at.date_input[0].value == date(2026, 10, 28)


def test_reselecting_part_restores_edited_list(storage):
    """I6: 부위를 해제했다가 다시 고르면 손본 목록(체크 해제, 추가한 운동)이 유지된다."""
    chest = {p.name: p.id for p in storage.list_body_parts()}["가슴"]
    ex = {e.name: e.id for e in storage.list_exercises()}

    at = AppTest.from_file("../views/1_운동_기록.py")
    at.run(timeout=30)
    at.pills(key="_rec_parts").set_value([chest]).run(timeout=30)
    at.checkbox(key=f"_rec_chk_{ex['딥스']}").uncheck().run(timeout=30)
    at.selectbox(key=f"_rec_add_{chest}").set_value(ex["덤벨 플라이"]).run(timeout=30)
    edited = at.session_state["rec"]["items"][chest]
    assert edited == [ex["벤치프레스"], ex["푸시업"], ex["딥스"], ex["덤벨 플라이"]]

    at.pills(key="_rec_parts").set_value([]).run(timeout=30)
    assert at.session_state["rec"]["items"] == {}
    at.pills(key="_rec_parts").set_value([chest]).run(timeout=30)

    assert not at.exception
    rec = at.session_state["rec"]
    assert rec["items"][chest] == edited
    assert ex["딥스"] in rec["unchecked"]
    assert [c.value for c in at.checkbox] == [True, True, False, True]
