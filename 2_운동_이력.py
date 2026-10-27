"""운동 이력 페이지 (F-4)."""

from datetime import date, timedelta
from itertools import groupby

import pandas as pd
import streamlit as st

from core import clock
from core.components import (
    days_ago,
    empty_state,
    exercises_of,
    format_date,
    load_body_parts,
    md,
    workout_date_error,
)
from core.db import get_storage
from core.export import csv_file_name, csv_safe
from core.models import WorkoutLog
from core.styles import part_badge, part_label

RECORD_PAGE = "views/1_운동_기록.py"

storage = get_storage()
body_parts = load_body_parts()
parts = {p.id: p.name for p in body_parts}


@st.dialog("기록 삭제")
def confirm_delete(target: WorkoutLog | date) -> None:
    if isinstance(target, date):
        st.write(f"**{format_date(target)}** 기록을 모두 삭제할까요?")
    else:
        st.write(f"**{format_date(target.workout_date)} · {md(target.exercise_name)}** 기록을 삭제할까요?")
    st.caption("삭제한 기록은 되돌릴 수 없어요.")
    with st.container(horizontal=True):
        if st.button("취소", width="stretch"):
            st.rerun()
        if st.button("삭제", type="primary", icon="🗑️", width="stretch"):
            if isinstance(target, date):
                storage.delete_workout_day(target)
            else:
                storage.delete_workout_log(target.id)
            st.session_state["hist_flash"] = ("success", "기록을 삭제했어요.")
            st.rerun()


def popover_key(log: WorkoutLog) -> str:
    return f"_hist_pop_{log.id}"


def edit_form(log: WorkoutLog) -> None:
    with st.form(f"_hist_edit_{log.id}", border=False):
        new_date = st.date_input(
            "날짜", value=log.workout_date, format="YYYY-MM-DD",
            # 범위 검사는 저장할 때 한국어로 안내한다 (Streamlit 기본 오류는 영어).
            min_value=date(1900, 1, 1), max_value=date(2100, 12, 31),
        )
        options = exercises_of(log.body_part_id)
        new_ex = st.selectbox(
            "운동",
            options=[e.id for e in options],
            index=[e.id for e in options].index(log.exercise_id),
            format_func={e.id: e.name for e in options}.get,
        )
        new_memo = st.text_input("메모", value=log.memo, max_chars=100, placeholder="예: 60kg × 10회")
        if st.form_submit_button("저장", type="primary", width="stretch"):
            try:
                if error := workout_date_error(new_date):
                    raise ValueError(error)
                storage.update_workout_log(
                    log.id, workout_date=new_date, exercise_id=new_ex, memo=new_memo.strip()
                )
            except ValueError as e:
                # 팝오버는 아래에서 닫으므로 결과 메시지는 페이지 상단에 표시한다.
                st.session_state["hist_flash"] = ("error", f"수정하지 못했어요: {e}")
            else:
                st.session_state["hist_flash"] = ("success", "기록을 수정했어요.")
            # 위젯 상태는 생성된 뒤에 바꿀 수 없으므로, 다음 실행에서 팝오버를 그리기 전에 닫는다.
            st.session_state["_hist_close_popover"] = popover_key(log)
            st.rerun()


st.title("📅 운동 이력")

if close_key := st.session_state.pop("_hist_close_popover", None):
    st.session_state[close_key] = False

flash = st.session_state.pop("hist_flash", None)
if flash:
    kind, msg = flash
    if kind == "success":
        st.toast(msg, icon="✅")
    else:
        st.error(msg, icon="🚫")

# 요약 지표: 이번 주 운동일 수 + F-4-4 부위별 마지막 운동일
today = clock.today()
week_start = today - timedelta(days=today.weekday())
week_days = {l.workout_date for l in storage.list_workout_logs(start=week_start, end=week_start + timedelta(days=6))}
last_dates = storage.last_workout_dates()

with st.container(horizontal=True, gap="small"):
    st.metric("이번 주 운동", f"{len(week_days)}일", border=True, width="stretch")
    for name, last in last_dates.items():
        st.metric(
            part_label(name), days_ago(last), border=True, width="stretch",
            help=f"마지막 운동: {last.isoformat()}" if last else None,
        )

if not any(last_dates.values()):
    empty_state("아직 기록이 없어요. 첫 운동을 기록해 보세요!", RECORD_PAGE, "📝 운동 기록하러 가기")
    st.stop()

# F-4-2 필터
with st.container(border=True):
    period = st.date_input(
        "기간",
        value=(today - timedelta(days=30), today),
        min_value=date(1900, 1, 1),
        max_value=date(2100, 12, 31),
        format="YYYY-MM-DD",
        key="hist_period",
    )
    selected_parts = st.pills(
        "부위",
        options=list(parts),
        selection_mode="multi",
        default=list(parts),
        format_func=lambda pid: part_label(parts[pid]),
        key="hist_parts",
    )

# 기간 선택 도중(시작일만 고른 상태)에는 시작일 하루만 조회한다.
start, end = (period[0], period[-1]) if period else (None, None)
logs = storage.list_workout_logs(start=start, end=end, body_part_ids=selected_parts)

if not logs:
    empty_state("조건에 맞는 기록이 없어요. 기간이나 부위를 바꿔 보세요.")
    st.stop()

# F-4-5 CSV 다운로드
df = pd.DataFrame(
    [
        {
            "날짜": l.workout_date.isoformat(),
            "부위": l.body_part_name,
            "운동": csv_safe(l.exercise_name),
            "메모": csv_safe(l.memo),
        }
        for l in logs
    ]
)
with st.container(horizontal=True, vertical_alignment="center"):
    st.caption(f"{df['날짜'].nunique()}일 · {len(logs)}개 운동", width="stretch")
    st.download_button(
        "CSV 다운로드",
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name=csv_file_name(start, end),
        mime="text/csv",
        icon="⬇️",
        help="현재 조건의 기록을 CSV로 다운로드",
    )

# F-4-1, F-4-3 날짜별 타임라인 카드와 수정/삭제
for day, day_logs in groupby(logs, key=lambda l: l.workout_date):
    day_logs = list(day_logs)
    part_names = list(dict.fromkeys(l.body_part_name for l in day_logs))
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            badges = " ".join(part_badge(n) for n in part_names)
            st.markdown(f"**{format_date(day)}** &nbsp; {badges}", width="stretch")
            st.caption(days_ago(day), width="content")
            if st.button("🗑️", key=f"_hist_del_day_{day}", help="이 날 기록 전체 삭제", type="tertiary"):
                confirm_delete(day)

        for log in day_logs:
            with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                with st.container(gap=None):
                    st.markdown(f"{part_badge(log.body_part_name)} {md(log.exercise_name)}")
                    if log.memo:
                        st.caption(md(log.memo))
                with st.popover("✏️", help="수정", type="tertiary", key=popover_key(log), on_change="rerun"):
                    edit_form(log)
                if st.button("✖️", key=f"_hist_del_{log.id}", help="삭제", type="tertiary"):
                    confirm_delete(log)
