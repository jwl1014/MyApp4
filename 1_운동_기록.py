"""운동 기록 페이지 (F-1).

입력 상태는 위젯 키가 아닌 st.session_state["rec"]에 보관한다. 위젯 상태는 다른 페이지로
이동하면 Streamlit이 지워버리므로, 매 실행마다 "rec"에서 위젯 키(_rec_*)로 값을 복원하고
on_change 콜백에서 다시 "rec"로 반영한다.
"""

from datetime import date

import streamlit as st

from core import clock
from core.components import (
    empty_state,
    exercise_by_id,
    exercises_of,
    favorites_of,
    format_date,
    invalidate,
    load_body_parts,
    md,
    open_exercise_detail,
    reopen_pending_detail,
    workout_date_error,
)
from core.db import get_storage
from core.styles import part_label

MODES = {"merge": "기존 기록에 추가 (병합)", "overwrite": "기존 기록 지우고 덮어쓰기"}


def new_state() -> dict:
    # date: None이면 "오늘" (탭을 밤새 열어 둬도 다음 날 기본값이 어제로 남지 않게 매번 계산)
    # items: 부위 id → 화면에 표시할 운동 id 목록 (즐겨찾기 순서 + 추가한 순서)
    # stash: 선택 해제한 부위의 items/unchecked. 같은 부위를 다시 고르면 손본 목록을 되살린다.
    return {"date": None, "parts": [], "items": {}, "unchecked": set(), "stash": {}}


rec: dict = st.session_state.setdefault("rec", new_state())
rec.setdefault("stash", {})  # 이전 버전 세션 호환
storage = get_storage()
parts = {p.id: p.name for p in load_body_parts()}


def record_date() -> date:
    return rec["date"] or clock.today()


# ------------------------------------------------------------------ 콜백

def on_date_change() -> None:
    chosen = st.session_state["_rec_date"]
    rec["date"] = None if chosen == clock.today() else chosen


def on_parts_change() -> None:
    selected = st.session_state["_rec_parts"]
    rec["parts"] = selected
    for pid in list(rec["items"]):
        if pid not in selected:
            ex_ids = rec["items"].pop(pid)
            rec["stash"][pid] = (ex_ids, {i for i in ex_ids if i in rec["unchecked"]})
            rec["unchecked"] -= set(ex_ids)
    for pid in selected:
        if pid not in rec["items"]:
            if pid in rec["stash"]:
                ex_ids, unchecked = rec["stash"].pop(pid)
                rec["items"][pid] = ex_ids
                rec["unchecked"] |= unchecked
            else:
                # F-1-3: 부위를 선택하면 즐겨찾기 운동을 체크된 상태로 자동 추가
                rec["items"][pid] = [e.id for e in favorites_of(pid)]


def on_check_change(ex_id: int) -> None:
    if st.session_state[f"_rec_chk_{ex_id}"]:
        rec["unchecked"].discard(ex_id)
    else:
        rec["unchecked"].add(ex_id)


def on_add_exercise(pid: int) -> None:
    key = f"_rec_add_{pid}"
    ex_id = st.session_state[key]
    if ex_id is not None and ex_id not in rec["items"][pid]:
        rec["items"][pid].append(ex_id)
        rec["unchecked"].discard(ex_id)
    st.session_state[key] = None


def on_remove_exercise(pid: int, ex_id: int) -> None:
    rec["items"][pid].remove(ex_id)
    rec["unchecked"].discard(ex_id)


def prune_items() -> None:
    """다른 페이지에서 운동의 부위를 바꾸면 rec에 옛 부위로 남은 id가 생긴다.
    같은 id가 두 부위에 있으면 체크박스 키가 중복돼 페이지가 멈추므로, 부위가 맞지 않거나
    이미 나온 id는 매 실행마다 걸러낸다.
    """
    seen: set[int] = set()
    for pid, ex_ids in rec["items"].items():
        kept = []
        for ex_id in ex_ids:
            ex = exercise_by_id(ex_id)
            if ex is not None and ex.body_part_id == pid and ex_id not in seen:
                kept.append(ex_id)
                seen.add(ex_id)
        ex_ids[:] = kept
    rec["unchecked"] &= seen
    # 선택 해제해 둔 부위의 목록도 같은 기준으로 정리한다 (다시 선택할 때 중복이 생기지 않게).
    for pid, (ex_ids, unchecked) in list(rec["stash"].items()):
        kept = [
            i for i in ex_ids
            if (ex := exercise_by_id(i)) is not None and ex.body_part_id == pid and i not in seen
        ]
        rec["stash"][pid] = (kept, unchecked & set(kept))


def checked_ids() -> list[int]:
    return [
        ex_id
        for pid in rec["parts"]
        for ex_id in rec["items"].get(pid, [])
        if ex_id not in rec["unchecked"]
    ]


def on_save(mode: str) -> None:
    prune_items()
    ids = checked_ids()
    day = record_date()
    if error := workout_date_error(day):
        st.session_state["rec_flash"] = ("error", error)
        return
    try:
        added = storage.save_workout(day, ids, mode=mode)
    except ValueError as e:
        st.session_state["rec_flash"] = ("error", str(e))
        return
    names = ", ".join(md(exercise_by_id(i).name) for i in ids)
    msg = f"{format_date(day)} 운동을 저장했어요: {names}"
    if mode == "merge" and added < len(ids):
        msg += f" (이미 기록된 {len(ids) - added}개는 제외)"
    st.session_state["rec_flash"] = ("success", msg)
    st.session_state["rec"] = new_state()


# ------------------------------------------------------------------ 화면

prune_items()

st.title("📝 운동 기록")
st.caption("오늘 한 운동을 체크하고 저장하세요.")

flash = st.session_state.pop("rec_flash", None)
if flash:
    kind, msg = flash
    if kind == "success":
        st.toast(msg, icon="✅", duration="long")
    else:
        st.error(msg, icon="🚫")

# F-1-1 날짜. 범위 제한은 Streamlit 기본(영어) 오류 대신 아래에서 한국어로 안내한다.
day = record_date()
st.session_state["_rec_date"] = day
st.date_input(
    "운동 날짜",
    key="_rec_date",
    on_change=on_date_change,
    min_value=date(1900, 1, 1),
    max_value=date(2100, 12, 31),
    format="YYYY-MM-DD",
)
date_error = workout_date_error(day)
if date_error:
    st.error(date_error, icon="📅")

existing = [] if date_error else storage.list_workout_logs(start=day, end=day)
if existing:
    st.info(
        f"이 날짜에 이미 기록이 있어요: {', '.join(md(l.exercise_name) for l in existing)}",
        icon="📌",
    )

# F-1-2 부위 (터치하기 쉬운 큰 토글 버튼)
st.session_state["_rec_parts"] = rec["parts"]
st.pills(
    "운동 부위",
    options=list(parts),
    selection_mode="multi",
    format_func=lambda pid: part_label(parts[pid]),
    key="_rec_parts",
    on_change=on_parts_change,
    width="stretch",
)

if not rec["parts"]:
    empty_state("운동한 부위를 선택하면 즐겨찾기 운동이 자동으로 채워져요.")

for pid in rec["parts"]:
    item_ids = rec["items"].get(pid, [])
    checked_count = sum(1 for i in item_ids if i not in rec["unchecked"])
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"#### {part_label(parts[pid])}", width="stretch")
            st.caption(f"{checked_count} / {len(item_ids)}개 선택", width="content")
        if not item_ids:
            st.caption("즐겨찾기 운동이 없어요. 아래에서 운동을 추가하세요.")

        # F-1-4 체크 해제/삭제, ℹ️ 상세 보기
        # 가로 컨테이너는 모바일에서도 세로로 쌓이지 않아 체크박스와 버튼이 한 줄에 유지된다.
        for ex_id in item_ids:
            ex = exercise_by_id(ex_id)
            if ex is None:
                continue
            with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                st.session_state[f"_rec_chk_{ex_id}"] = ex_id not in rec["unchecked"]
                st.checkbox(
                    md(ex.name), key=f"_rec_chk_{ex_id}", on_change=on_check_change, args=(ex_id,),
                    width="stretch",
                )
                if st.button("ℹ️", key=f"_rec_info_{ex_id}", help="운동 방법 보기", type="tertiary"):
                    open_exercise_detail(ex_id)
                st.button(
                    "✖️", key=f"_rec_del_{ex_id}", help="목록에서 빼기", type="tertiary",
                    on_click=on_remove_exercise, args=(pid, ex_id),
                )

        # F-1-5 즐겨찾기 외 운동 추가
        candidates = [e.id for e in exercises_of(pid) if e.id not in item_ids]
        if candidates:
            st.selectbox(
                "운동 추가",
                options=candidates,
                index=None,
                format_func=lambda i: exercise_by_id(i).name,
                key=f"_rec_add_{pid}",
                on_change=on_add_exercise,
                args=(pid,),
                placeholder="➕ 다른 운동 추가",
                label_visibility="collapsed",
            )

        # F-1-6 새 운동 직접 입력
        with st.expander("목록에 없는 운동 직접 입력", key=f"_rec_new_expander_{pid}", icon="✍️"):
            # 등록에 성공했을 때만 입력을 비우도록 폼 버전을 키에 넣는다 (clear_on_submit은 실패해도 지움).
            form_ver = st.session_state.get(f"_rec_new_ver_{pid}", 0)
            with st.form(f"_rec_new_{pid}_{form_ver}", border=False):
                new_name = st.text_input("운동 이름", max_chars=50, placeholder="예: 펙덱 플라이")
                if st.form_submit_button("새 운동 등록 후 추가", width="stretch"):
                    try:
                        new_id = storage.add_exercise(new_name, pid)
                    except ValueError as e:
                        st.error(str(e), icon="🚫")
                    else:
                        invalidate()
                        rec["items"][pid].append(new_id)
                        st.session_state[f"_rec_new_ver_{pid}"] = form_ver + 1
                        st.rerun()

# F-1-7, F-1-8 저장
ids = checked_ids()
mode = "merge"
if existing and ids:
    mode = st.radio(
        "같은 날짜에 기록이 있어요. 어떻게 저장할까요?",
        options=list(MODES),
        format_func=MODES.get,
        key="_rec_mode",
    )

if rec["parts"] and not ids:
    st.caption("저장할 운동을 하나 이상 체크하세요.")

st.button(
    f"저장하기 · {len(ids)}개 운동" if ids else "저장하기",
    type="primary",
    icon="💾",
    width="stretch",
    disabled=not ids or bool(date_error),
    on_click=on_save,
    args=(mode,),
)

reopen_pending_detail()
