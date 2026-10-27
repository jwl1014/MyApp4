"""부위별 색상·이모지와 앱 전역 CSS.

색상은 st.badge / Markdown 배지가 지원하는 이름(red, blue, green …)만 사용해
라이트·다크 테마 모두에서 Streamlit이 대비를 맞추게 한다.
"""

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class PartStyle:
    emoji: str
    color: str  # st.badge color 이름
    tint: str   # 플레이스홀더 배경용 반투명 색 (라이트·다크 공용)


PART_STYLES = {
    "가슴": PartStyle("🔴", "red", "rgba(255, 75, 75, 0.12)"),
    "등": PartStyle("🔵", "blue", "rgba(28, 131, 225, 0.12)"),
    "다리": PartStyle("🟢", "green", "rgba(33, 195, 84, 0.12)"),
}
# PRD 범위 밖의 부위(어깨, 팔 등)를 추가했을 때 순서대로 사용
_FALLBACK_STYLES = [
    PartStyle("🟣", "violet", "rgba(128, 61, 245, 0.12)"),
    PartStyle("🟠", "orange", "rgba(255, 164, 33, 0.12)"),
    PartStyle("⚪", "gray", "rgba(128, 128, 128, 0.12)"),
]


def part_style(name: str) -> PartStyle:
    if name in PART_STYLES:
        return PART_STYLES[name]
    return _FALLBACK_STYLES[sum(map(ord, name)) % len(_FALLBACK_STYLES)]


def part_label(name: str) -> str:
    """위젯 라벨용 "🔴 가슴"."""
    return f"{part_style(name).emoji} {name}"


def part_badge(name: str) -> str:
    """Markdown 안에 넣는 부위 배지."""
    return f":{part_style(name).color}-badge[{name}]"


_CSS = """
<style>
/* 운동 사진/플레이스홀더 비율 통일 */
.ex-thumb, [class*="st-key-thumb"] img {
    aspect-ratio: 4 / 3;
    width: 100%;
    object-fit: cover;
    border-radius: 0.5rem;
}
.ex-thumb {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.15rem;
    text-align: center;
    border: 1px dashed rgba(128, 128, 128, 0.35);
    padding: 0.5rem;
    overflow: hidden;
}
.ex-thumb .emoji { font-size: 1.8rem; line-height: 1; }
.ex-thumb .name { font-weight: 600; word-break: keep-all; }
.ex-thumb .sub { font-size: 0.75rem; opacity: 0.6; }
/* 근육 지도 그림은 잘리지 않게 비율을 유지한다 (st-key-thumbmap_*) */
[class*="st-key-thumbmap"] img { object-fit: contain; }
/* 상세 다이얼로그의 사진은 화면을 다 차지하지 않도록 높이 제한 */
[class*="st-key-thumb"][class*="_detail"] .ex-thumb,
[class*="st-key-thumb"][class*="_detail"] img { max-height: 220px; }

/* 모바일 터치 영역: 아이콘 버튼(ℹ️ ✖️ ⬆️ ⬇️ 🗑️ ✏️)을 최소 44px로 */
[data-testid="stMain"] button[kind="tertiary"],
[data-testid="stMain"] [data-testid="stPopover"] button {
    min-width: 44px;
    min-height: 44px;
}
/* 체크박스는 이름 글자뿐 아니라 행 전체를 눌러도 체크되게 */
[data-testid="stCheckbox"] label { width: 100%; }

/* 모바일: 상단 여백을 줄여 첫 화면에 입력 영역이 더 보이게 */
@media (max-width: 640px) {
    [data-testid="stMainBlockContainer"] { padding-top: 3rem; padding-left: 1rem; padding-right: 1rem; }
    h1 { font-size: 1.75rem !important; }
    /* 한 줄에 카드 하나씩 쌓이므로 사진을 납작하게 해서 스크롤을 줄인다 */
    [class*="st-key-thumb"][class*="_lib_"] .ex-thumb,
    [class*="st-key-thumb"][class*="_lib_"] img { aspect-ratio: 16 / 9 !important; }
    [class*="st-key-thumb"][class*="_detail"] .ex-thumb,
    [class*="st-key-thumb"][class*="_detail"] img { max-height: 160px; }
}
</style>
"""


def inject_css() -> None:
    # 스타일은 첫 화면보다 약 0.6초 늦게 적용된다 (Streamlit 렌더링 구조상 st.markdown도 같고,
    # st.markdown은 제목 위에 빈 줄까지 생긴다). 그래서 눈에 잘 띄는 플레이스홀더는 인라인 스타일로도 그린다.
    st.html(_CSS)
