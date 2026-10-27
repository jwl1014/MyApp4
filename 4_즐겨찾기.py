"""즐겨찾기 관리 페이지 (F-2)."""

import streamlit as st

from core.components import (
    empty_state,
    exercise_by_id,
    exercises_of,
    favorites_of,
    invalidate,
    load_body_parts,
    md,
    open_exercise_detail,
    reopen_pending_detail,
)
from core.db import get_storage
from core.styles import part_label

storage = get_storage()


UNDO_KEY = "_fav_undo"


def move(ex_id: int, direction: int) -> None:
    st.session_state.pop(UNDO_KEY, None)
    storage.move_favorite(ex_id, direction)
    invalidate()


def remove(ex_id: int) -> None:
    # 🗑️는 확인 없이 바로 지우므로, 원래 자리로 되돌릴 수 있게 순서를 기억해 둔다.
    st.session_state[UNDO_KEY] = (ex_id, storage.favorite_sort_order(ex_id))
    storage.remove_favorite(ex_id)
    invalidate()


def undo_remove() -> None:
    ex_id, sort_order = st.session_state.pop(UNDO_KEY)
    storage.add_favorite(ex_id, sort_order=sort_order)
    invalidate()


def add(part_id: int) -> None:
    st.session_state.pop(UNDO_KEY, None)
    key = f"_fav_add_{part_id}"
    ex_id = st.session_state[key]
    if ex_id is not None:
        storage.add_favorite(ex_id)
        invalidate()
    st.session_state[key] = None


st.title("⭐ 즐겨찾기")
st.caption("운동 기록에서 부위를 선택하면 여기 순서대로 운동이 자동으로 채워져요.")

if undo := st.session_state.get(UNDO_KEY):
    removed = exercise_by_id(undo[0])
    with st.container(border=True, horizontal=True, vertical_alignment="center"):
        st.markdown(f"🗑️ **{md(removed.name) if removed else '운동'}**을(를) 즐겨찾기에서 뺐어요.", width="stretch")
        st.button("되돌리기", icon="↩️", on_click=undo_remove, key="_fav_undo_btn")
        st.button("✖️", help="닫기", type="tertiary", key="_fav_undo_close",
                  on_click=lambda: st.session_state.pop(UNDO_KEY, None))

body_parts = load_body_parts()
for tab, part in zip(st.tabs([part_label(p.name) for p in body_parts]), body_parts):
    with tab:
        favorites = favorites_of(part.id)
        if not favorites:
            empty_state(f"{part.name} 즐겨찾기가 없어요. 아래에서 자주 하는 운동을 추가해 보세요.")

        for i, ex in enumerate(favorites):
            # 가로 컨테이너: 모바일에서도 이름과 버튼이 한 줄에 유지된다.
            with st.container(border=True, horizontal=True, vertical_alignment="center", gap="small"):
                st.markdown(f"**{i + 1}.** {md(ex.name)}", width="stretch")
                st.button(
                    "⬆️", key=f"_fav_up_{ex.id}", help="위로", disabled=i == 0, type="tertiary",
                    on_click=move, args=(ex.id, -1),
                )
                st.button(
                    "⬇️", key=f"_fav_down_{ex.id}", help="아래로", disabled=i == len(favorites) - 1,
                    type="tertiary", on_click=move, args=(ex.id, 1),
                )
                if st.button("ℹ️", key=f"_fav_info_{ex.id}", help="운동 방법 보기", type="tertiary"):
                    open_exercise_detail(ex.id)
                st.button(
                    "🗑️", key=f"_fav_del_{ex.id}", help="즐겨찾기에서 삭제", type="tertiary",
                    on_click=remove, args=(ex.id,),
                )

        fav_ids = {e.id for e in favorites}
        candidates = [e.id for e in exercises_of(part.id) if e.id not in fav_ids]
        if candidates:
            st.selectbox(
                "즐겨찾기 추가",
                options=candidates,
                index=None,
                format_func=lambda i: exercise_by_id(i).name,
                key=f"_fav_add_{part.id}",
                on_change=add,
                args=(part.id,),
                placeholder="➕ 즐겨찾기에 추가할 운동 선택",
                label_visibility="collapsed",
            )
        else:
            st.caption("이 부위의 모든 운동이 즐겨찾기에 있어요.")

reopen_pending_detail()
