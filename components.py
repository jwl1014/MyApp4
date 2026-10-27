"""여러 페이지에서 공통으로 쓰는 데이터 로더와 UI 컴포넌트."""

from __future__ import annotations

import html
import io
import re
from datetime import date
from urllib.parse import quote_plus

import streamlit as st

from core import clock
from core.db import ROOT_DIR, get_storage
from core.models import BodyPart, Exercise
from core.muscle_map import render_svg
from core.styles import part_badge, part_style

WEEKDAYS = "월화수목금토일"
EARLIEST_DATE = date(2000, 1, 1)

# 즐겨찾기 토글 후 상세 다이얼로그를 다시 열기 위한 session_state 키
_REOPEN_DETAIL_KEY = "_reopen_detail_exercise_id"


# ------------------------------------------------------------------ 데이터 로더
# 운동 사전·즐겨찾기·사진은 자주 읽고 드물게 바뀌므로 캐싱하고, 변경 후 invalidate()로 비운다.

@st.cache_data
def load_body_parts() -> list[BodyPart]:
    return get_storage().list_body_parts()


@st.cache_data
def load_exercises() -> list[Exercise]:
    return get_storage().list_exercises()


@st.cache_data
def load_favorites() -> list[Exercise]:
    return get_storage().list_favorites()


@st.cache_data
def load_image_keys() -> set[tuple[int, str]]:
    return get_storage().list_image_keys()


@st.cache_data(max_entries=200)
def load_image(exercise_id: int, kind: str) -> bytes | None:
    image = get_storage().get_exercise_image(exercise_id, kind)
    return image[1] if image else None


def invalidate() -> None:
    load_body_parts.clear()
    load_exercises.clear()
    load_favorites.clear()
    load_image_keys.clear()
    load_image.clear()


def exercises_of(body_part_id: int) -> list[Exercise]:
    return [e for e in load_exercises() if e.body_part_id == body_part_id]


def favorites_of(body_part_id: int) -> list[Exercise]:
    return [e for e in load_favorites() if e.body_part_id == body_part_id]


def favorite_ids() -> set[int]:
    return {e.id for e in load_favorites()}


def exercise_by_id(exercise_id: int) -> Exercise | None:
    return next((e for e in load_exercises() if e.id == exercise_id), None)


# ------------------------------------------------------------------ 포맷 도우미

_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~$:&])")


def md(text: str) -> str:
    """사용자가 입력한 글자를 Markdown으로 해석하지 않고 그대로 보이게 이스케이프한다.
    (링크·이미지·굵게, Streamlit의 :red[…] 색상 지시어, $수식$ 등)
    """
    return _MD_SPECIAL.sub(r"\\\1", text)


def format_date(d: date) -> str:
    return f"{d.isoformat()} ({WEEKDAYS[d.weekday()]})"


def days_ago(d: date | None, today: date | None = None) -> str:
    if d is None:
        return "기록 없음"
    diff = ((today or clock.today()) - d).days
    if diff == 0:
        return "오늘"
    if diff < 0:
        return f"{-diff}일 후"
    return f"{diff}일 전"


def workout_date_error(d: date) -> str | None:
    """운동 날짜로 쓸 수 없으면 한국어 안내 문구. 미래 날짜는 오입력으로 보고 막는다."""
    if d > clock.today():
        return "미래 날짜에는 기록할 수 없어요. 오늘 이전 날짜를 골라 주세요."
    if d < EARLIEST_DATE:
        return "2000년 1월 1일 이후 날짜만 기록할 수 있어요."
    return None


def youtube_search_url(exercise_name: str) -> str:
    return "https://www.youtube.com/results?search_query=" + quote_plus(f"{exercise_name} 자세")


# ------------------------------------------------------------------ 사진

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_SIDE = 1000


def process_image_upload(data: bytes) -> tuple[str, bytes]:
    """업로드한 사진을 확인하고 긴 변 1000px 이하 JPEG로 줄인다 (DB 용량 절약)."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("사진은 10MB 이하만 올릴 수 있어요.")
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)  # 휴대폰 사진의 회전 정보 반영
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError("사진 파일을 읽지 못했어요. JPG 또는 PNG 파일을 올려 주세요.") from e
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, "white")
        background.paste(img, mask=img.getchannel("A"))
        img = background
    else:
        img = img.convert("RGB")
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return "image/jpeg", out.getvalue()


# CSS가 늦게 붙어도 처음부터 제 모양으로 보이도록 핵심 스타일은 인라인으로 둔다 (styles.py 참고).
_THUMB_INLINE = (
    "display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.15rem;"
    "text-align:center;width:100%;aspect-ratio:4/3;border-radius:.5rem;padding:.5rem;"
    "border:1px dashed rgba(128,128,128,.35);overflow:hidden;"
)


def _placeholder(part_name: str, caption: str) -> None:
    style = part_style(part_name)
    # 운동 이름은 사용자가 입력할 수 있으므로 HTML에 넣기 전에 반드시 이스케이프한다.
    st.markdown(
        f"<div class='ex-thumb' style='{_THUMB_INLINE}background:{style.tint}'>"
        f"<span class='emoji'>{style.emoji}</span>"
        + (f"<span class='name'>{html.escape(caption)}</span>" if caption else "")
        + "<span class='sub'>사진 없음</span></div>",
        unsafe_allow_html=True,
    )


def exercise_image(ex: Exercise, kind: str, key: str, caption: str = "") -> None:
    """운동 사진을 표시한다. kind: "form"(운동 방법), "muscle"(자극 부위), "card"(사전 카드 썸네일).

    우선순위: 업로드한 사진 → assets/images 파일 → (자극 부위·카드) 근육 지도 그림 → 플레이스홀더.
    """
    kinds = ("form", "muscle") if kind == "card" else (kind,)
    for k in kinds:
        if (ex.id, k) in load_image_keys():
            with st.container(key=f"thumb_{key}"):
                st.image(load_image(ex.id, k), caption=caption or None, width="stretch")
            return
        path = ex.image_path if k == "form" else ex.muscle_image_path
        if path and (ROOT_DIR / path).is_file():
            with st.container(key=f"thumb_{key}"):
                st.image(str(ROOT_DIR / path), caption=caption or None, width="stretch")
            return
    if kind in ("muscle", "card"):
        style = part_style(ex.body_part_name)
        svg = render_svg(ex.primary_muscles, ex.secondary_muscles, style.color)
        if svg:
            with st.container(key=f"thumbmap_{key}"):
                st.image(svg, caption=caption or None, width="stretch")
            return
    with st.container(key=f"thumb_{key}"):
        _placeholder(ex.body_part_name, caption)


def empty_state(message: str, link_page: str | None = None, link_label: str = "") -> None:
    with st.container(border=True):
        st.markdown(f"<div style='text-align:center;padding:1.5rem 0'>{html.escape(message)}</div>",
                    unsafe_allow_html=True)
        if link_page:
            st.page_link(link_page, label=link_label, width="stretch")


# ------------------------------------------------------------------ 즐겨찾기 / 상세

def toggle_favorite(exercise_id: int) -> None:
    storage = get_storage()
    if exercise_id in favorite_ids():
        storage.remove_favorite(exercise_id)
    else:
        storage.add_favorite(exercise_id)
    invalidate()


def open_exercise_detail(exercise_id: int) -> None:
    """운동 상세 다이얼로그(F-3)를 연다. 제목에 운동명을 쓰기 위해 호출 시점에 데코레이터를 적용한다."""
    ex = exercise_by_id(exercise_id)
    if ex is None:
        st.error("운동 정보를 찾을 수 없습니다.")
        return
    st.dialog(md(ex.name), width="medium")(_render_exercise_detail)(ex)


def reopen_pending_detail() -> None:
    """즐겨찾기 토글로 rerun된 경우 다이얼로그를 다시 연다. 페이지 맨 끝에서 호출한다."""
    exercise_id = st.session_state.pop(_REOPEN_DETAIL_KEY, None)
    if exercise_id is not None:
        open_exercise_detail(exercise_id)


def _muscle_badges(label: str, muscles: str, color: str) -> None:
    names = [m.strip() for m in muscles.split(",") if m.strip()]
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.markdown(f"**{label}**", width="content")
        if not names:
            st.caption("-", width="content")
        for name in names:
            st.badge(md(name), color=color)


def _render_exercise_detail(ex: Exercise) -> None:
    is_fav = ex.id in favorite_ids()
    st.markdown(f"{part_badge(ex.body_part_name)} {'⭐ 즐겨찾기' if is_fav else ''}")

    # 넓은 화면에서는 나란히, 모바일(640px 이하)에서는 자동으로 세로 배치
    left, right = st.columns(2)
    with left:
        exercise_image(ex, "form", f"detail_form_{ex.id}", "운동 방법")
    with right:
        exercise_image(ex, "muscle", f"detail_muscle_{ex.id}", "자극 부위")

    _muscle_badges("주 자극", ex.primary_muscles, part_style(ex.body_part_name).color)
    _muscle_badges("보조 근육", ex.secondary_muscles, "gray")

    st.markdown("##### 💡 자세 팁")
    if ex.tips:
        st.markdown("\n\n".join(f"✅ {md(tip)}" for tip in ex.tips))
    else:
        st.caption("아직 등록된 팁이 없어요. 운동 사전에서 추가할 수 있어요.")
    for mistake in ex.mistakes:
        st.warning(f"**흔한 실수** · {md(mistake)}", icon="⚠️")

    with st.container(horizontal=True):
        if ex.video_url:
            st.link_button("참고 영상", ex.video_url, icon="🎬", width="stretch")
        else:
            # 등록된 영상이 없으면 유튜브 검색 결과로 안내한다 (특정 영상 주소를 임의로 넣지 않는다).
            st.link_button("자세 영상 찾기", youtube_search_url(ex.name), icon="🔎", width="stretch")
        label = "즐겨찾기 해제" if is_fav else "즐겨찾기 추가"
        # st.button의 icon은 이모지 한 글자 또는 :material/…: 아이콘만 허용한다 ("☆"는 오류).
        clicked = st.button(
            label, key=f"detail_fav_{ex.id}",
            icon=":material/star_border:" if is_fav else "⭐",
            type="secondary" if is_fav else "primary", width="stretch",
        )
    if clicked:
        toggle_favorite(ex.id)
        # 페이지 전체를 새로 그려 즐겨찾기 표시를 갱신한 뒤 다이얼로그를 다시 연다.
        st.session_state[_REOPEN_DETAIL_KEY] = ex.id
        st.rerun()
