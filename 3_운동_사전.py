"""운동 사전 페이지 (F-5)."""

import streamlit as st

from core.components import (
    empty_state,
    exercise_by_id,
    exercise_image,
    exercises_of,
    favorite_ids,
    invalidate,
    load_body_parts,
    load_exercises,
    load_image_keys,
    md,
    open_exercise_detail,
    process_image_upload,
    reopen_pending_detail,
    toggle_favorite,
)
from core.db import get_storage
from core.models import Exercise
from core.styles import part_label

COLUMNS = 3
PHOTO_TYPES = ["jpg", "jpeg", "png", "webp"]
PHOTO_LABELS = {"form": "운동 방법 사진", "muscle": "자극 부위 사진"}

body_parts = load_body_parts()
parts = {p.id: p.name for p in body_parts}


def lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def exercise_form(ex: Exercise | None) -> None:
    """운동 추가(ex=None) 또는 수정 폼. 수정 대상이 바뀌면 폼 키가 바뀌어 기본값이 다시 채워진다.

    clear_on_submit은 검증 실패 때도 입력을 지우므로 쓰지 않고, 추가에 성공하면
    폼 버전을 올려 새 폼으로 바꾸는 방식으로 입력을 비운다.
    """
    version = st.session_state.get("_lib_new_form_ver", 0)
    form_key = f"_lib_form_{ex.id}" if ex else f"_lib_form_new_{version}"
    with st.form(form_key, border=False):
        name = st.text_input("운동 이름 *", value=ex.name if ex else "", max_chars=50)
        part_ids = list(parts)
        part_id = st.selectbox(
            "부위 *",
            options=part_ids,
            index=part_ids.index(ex.body_part_id) if ex else 0,
            format_func=lambda pid: part_label(parts[pid]),
        )
        primary = st.text_input("주 자극 근육", value=ex.primary_muscles if ex else "")
        secondary = st.text_input("보조 근육", value=ex.secondary_muscles if ex else "")
        tips = st.text_area(
            "자세 팁 (한 줄에 하나씩)", value="\n".join(ex.tips) if ex else "", height=120
        )
        mistakes = st.text_area(
            "흔한 실수 (한 줄에 하나씩)", value="\n".join(ex.mistakes) if ex else "", height=80
        )
        video_url = st.text_input("참고 영상 URL", value=(ex.video_url or "") if ex else "")

        # F-5-3 사진: DB에 저장하므로 Streamlit Cloud가 재시작해도 남는다.
        uploads, removals = {}, set()
        image_keys = load_image_keys()
        for kind, label in PHOTO_LABELS.items():
            uploads[kind] = st.file_uploader(label, type=PHOTO_TYPES, key=f"{form_key}_{kind}")
            if ex and (ex.id, kind) in image_keys:
                if st.checkbox(f"{label} 삭제", key=f"{form_key}_{kind}_remove"):
                    removals.add(kind)
        st.caption("자극 부위 사진이 없으면 근육 정보로 그린 그림이 대신 표시돼요.")

        if not st.form_submit_button("저장" if ex else "운동 추가", type="primary", width="stretch"):
            return
        video_url = video_url.strip() or None
        if video_url and not video_url.startswith(("http://", "https://")):
            st.error("영상 URL은 http:// 또는 https://로 시작해야 해요.", icon="🚫")
            return
        try:
            # 운동을 저장하기 전에 사진부터 확인해, 사진 오류로 일부만 저장되는 일이 없게 한다.
            photos = {k: process_image_upload(f.getvalue()) for k, f in uploads.items() if f is not None}
        except ValueError as e:
            st.error(str(e), icon="🚫")
            return
        fields = dict(
            primary_muscles=primary.strip(),
            secondary_muscles=secondary.strip(),
            tips=lines(tips),
            mistakes=lines(mistakes),
            video_url=video_url,
        )
        storage = get_storage()
        try:
            if ex:
                storage.update_exercise(ex.id, name=name, body_part_id=part_id, **fields)
                exercise_id = ex.id
            else:
                exercise_id = storage.add_exercise(name, part_id, **fields)
        except ValueError as e:
            st.error(str(e), icon="🚫")
            return
        for kind in removals - photos.keys():
            storage.delete_exercise_image(exercise_id, kind)
        for kind, (mime, data) in photos.items():
            storage.set_exercise_image(exercise_id, kind, mime, data)
        invalidate()
        if ex is None:
            st.session_state["_lib_new_form_ver"] = version + 1
        st.session_state["lib_flash"] = f"'{md(' '.join(name.split()))}' 운동을 {'수정' if ex else '추가'}했어요."
        st.rerun()


st.title("📚 운동 사전")
st.caption("운동을 눌러 자세와 자극 부위를 확인하세요. ⭐는 즐겨찾기 운동이에요.")

flash = st.session_state.pop("lib_flash", None)
if flash:
    st.toast(flash, icon="✅")

favs = favorite_ids()

# F-5-1, F-5-2 부위별 카드 그리드 (640px 이하에서는 st.columns가 자동으로 한 줄씩 쌓인다)
for tab, part in zip(st.tabs([part_label(p.name) for p in body_parts]), body_parts):
    with tab:
        exercises = exercises_of(part.id)
        if not exercises:
            empty_state("등록된 운동이 없어요. 아래 '새 운동 추가'에서 등록해 보세요.")
        for row_start in range(0, len(exercises), COLUMNS):
            cols = st.columns(COLUMNS)
            for col, ex in zip(cols, exercises[row_start:row_start + COLUMNS]):
                with col.container(border=True, height="stretch"):
                    exercise_image(ex, "card", f"lib_{ex.id}")
                    is_fav = ex.id in favs
                    st.markdown(f"**{'⭐ ' if is_fav else ''}{md(ex.name)}**")
                    st.caption(md(ex.primary_muscles) or "자극 부위 정보 없음")
                    st.space("stretch")
                    with st.container(horizontal=True, gap="small"):
                        if st.button("자세히", key=f"_lib_open_{ex.id}", width="stretch", icon="🔍"):
                            open_exercise_detail(ex.id)
                        # F-2-2: 카드에서 바로 즐겨찾기 토글 ("☆"는 icon이 아닌 label이라 사용 가능)
                        st.button(
                            "⭐" if is_fav else "☆", key=f"_lib_fav_{ex.id}",
                            help="즐겨찾기 해제" if is_fav else "즐겨찾기 추가",
                            on_click=toggle_favorite, args=(ex.id,),
                        )

st.divider()

# F-5-3 운동 추가/수정
# key를 지정해야 상단 메시지 표시 등으로 레이아웃이 바뀌어도 펼침 상태가 유지된다.
with st.expander("➕ 새 운동 추가", key="_lib_add_expander"):
    exercise_form(None)

with st.expander("✏️ 운동 정보 수정", key="_lib_edit_expander"):
    all_ids = [e.id for e in load_exercises()]
    target_id = st.selectbox(
        "수정할 운동",
        options=all_ids,
        index=None,
        format_func=lambda i: f"{exercise_by_id(i).body_part_name} · {exercise_by_id(i).name}",
        placeholder="운동을 선택하세요",
        key="_lib_edit_target",
    )
    if target_id is not None:
        exercise_form(exercise_by_id(target_id))

reopen_pending_detail()
