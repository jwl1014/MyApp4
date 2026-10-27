"""운동의 근육 정보로 앞·뒤 인체 근육 지도(SVG)를 그린다.

사진이 없어도 "자극 부위"를 보여주기 위한 것이다. 주 자극 근육은 부위 색으로 진하게,
보조 근육은 연하게 칠한다. 근육 이름은 data/exercises.json과 사용자가 입력한 한국어 문자열을
키워드로 찾으므로, 새로 추가한 운동에도 그대로 적용된다.
"""

from __future__ import annotations

# 키워드 → 근육 영역. 위에서부터 먼저 맞는 규칙을 쓴다 (예: "후면 삼각근"이 "삼각근"보다 먼저).
_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("전면 삼각근", ("front_delts",)),
    ("후면 삼각근", ("rear_delts",)),
    ("삼각근", ("front_delts", "rear_delts")),
    ("어깨", ("front_delts", "rear_delts")),
    ("대흉근", ("chest",)),
    ("가슴", ("chest",)),
    ("삼두", ("triceps",)),
    ("이두", ("biceps",)),
    ("전완", ("forearms",)),
    ("복근", ("abs",)),
    ("복직근", ("abs",)),
    ("코어", ("abs",)),
    ("척추기립근", ("erectors",)),
    ("기립근", ("erectors",)),
    ("둔근", ("glutes",)),
    ("엉덩이", ("glutes",)),
    ("햄스트링", ("hamstrings",)),
    ("광배", ("lats",)),
    ("대원근", ("teres",)),
    ("능형근", ("rhomboids",)),
    ("승모", ("traps",)),
    ("대퇴사두", ("quads",)),
    ("허벅지 앞", ("quads",)),
    ("내전근", ("adductors",)),
    ("비복근", ("calves",)),
    ("종아리", ("calves",)),
    ("가자미근", ("calves",)),
]

# 영역별 SVG 도형. 좌표는 폭 100의 인체 기준이며, 뒤쪽 그림은 x+110으로 옮겨 그린다.
_FRONT: dict[str, list[str]] = {
    "front_delts": ['<ellipse cx="27" cy="43" rx="7" ry="7"/>', '<ellipse cx="73" cy="43" rx="7" ry="7"/>'],
    "chest": ['<ellipse cx="41" cy="53" rx="10" ry="8"/>', '<ellipse cx="59" cy="53" rx="10" ry="8"/>'],
    "biceps": ['<ellipse cx="21" cy="63" rx="4.5" ry="11"/>', '<ellipse cx="79" cy="63" rx="4.5" ry="11"/>'],
    "forearms": ['<ellipse cx="17" cy="100" rx="4.5" ry="14"/>', '<ellipse cx="83" cy="100" rx="4.5" ry="14"/>'],
    "abs": ['<rect x="43" y="63" width="14" height="34" rx="4"/>'],
    "quads": ['<ellipse cx="41" cy="135" rx="7" ry="19"/>', '<ellipse cx="59" cy="135" rx="7" ry="19"/>'],
    "adductors": ['<ellipse cx="47.5" cy="125" rx="2.8" ry="10"/>', '<ellipse cx="52.5" cy="125" rx="2.8" ry="10"/>'],
}
_BACK: dict[str, list[str]] = {
    "traps": ['<polygon points="50,29 65,41 50,64 35,41"/>'],
    "rear_delts": ['<ellipse cx="27" cy="43" rx="7" ry="7"/>', '<ellipse cx="73" cy="43" rx="7" ry="7"/>'],
    "rhomboids": ['<ellipse cx="45.5" cy="50" rx="3.5" ry="7"/>', '<ellipse cx="54.5" cy="50" rx="3.5" ry="7"/>'],
    "teres": ['<ellipse cx="34" cy="52" rx="3" ry="4"/>', '<ellipse cx="66" cy="52" rx="3" ry="4"/>'],
    "lats": ['<polygon points="34,55 44,62 44,90 37,82"/>', '<polygon points="66,55 56,62 56,90 63,82"/>'],
    "triceps": ['<ellipse cx="21" cy="63" rx="4.5" ry="11"/>', '<ellipse cx="79" cy="63" rx="4.5" ry="11"/>'],
    "forearms": ['<ellipse cx="17" cy="100" rx="4.5" ry="14"/>', '<ellipse cx="83" cy="100" rx="4.5" ry="14"/>'],
    "erectors": ['<rect x="45" y="66" width="4" height="32" rx="2"/>', '<rect x="51" y="66" width="4" height="32" rx="2"/>'],
    "glutes": ['<ellipse cx="42" cy="113" rx="9" ry="8"/>', '<ellipse cx="58" cy="113" rx="9" ry="8"/>'],
    "hamstrings": ['<ellipse cx="41" cy="141" rx="7" ry="17"/>', '<ellipse cx="59" cy="141" rx="7" ry="17"/>'],
    "calves": ['<ellipse cx="41" cy="174" rx="5.5" ry="11"/>', '<ellipse cx="59" cy="174" rx="5.5" ry="11"/>'],
}

# 머리·몸통·팔·다리 실루엣 (앞뒤 공통)
_BODY = """
<circle cx="50" cy="17" r="11"/>
<rect x="45" y="26" width="10" height="9" rx="3"/>
<path d="M28 36 Q50 31 72 36 L70 64 Q67 84 67 100 L68 114 L32 114 L33 100 Q33 84 30 64 Z"/>
<path d="M20 38 Q27 34 31 40 L27 86 L15 86 Z"/>
<path d="M80 38 Q73 34 69 40 L73 86 L85 86 Z"/>
<path d="M14 86 L27 86 L23 124 L12 124 Z"/>
<path d="M86 86 L73 86 L77 124 L88 124 Z"/>
<path d="M32 112 L49.5 112 L48 160 L46 196 L36 196 L34 160 Z"/>
<path d="M68 112 L50.5 112 L52 160 L54 196 L64 196 L66 160 Z"/>
"""

# 부위 배지 색 이름 → SVG 색 (Streamlit 기본 팔레트와 같은 계열)
_COLORS = {
    "red": "#FF4B4B", "blue": "#1C83E1", "green": "#21C354",
    "violet": "#803DF5", "orange": "#FF8700", "gray": "#808495",
}


def regions_for(muscles: str) -> set[str]:
    """"대퇴사두근, 둔근" 같은 문자열에서 근육 영역 이름을 찾는다."""
    found: set[str] = set()
    for name in (m.strip() for m in muscles.split(",")):
        for keyword, regions in _KEYWORDS:
            if keyword in name:
                found.update(regions)
                break
    return found


def _layer(shapes: dict[str, list[str]], regions: set[str], dx: int, attrs: str) -> str:
    body = "".join(s for r in regions if r in shapes for s in shapes[r])
    return f'<g transform="translate({dx} 0)" {attrs}>{body}</g>' if body else ""


def render_svg(primary: str, secondary: str, color: str = "red") -> str | None:
    """근육 지도 SVG 문자열. 알아볼 수 있는 근육이 하나도 없으면 None."""
    main = regions_for(primary)
    sub = regions_for(secondary) - main
    if not main and not sub:
        return None
    fill = _COLORS.get(color, _COLORS["red"])
    all_regions = set(_FRONT) | set(_BACK)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 210 214" font-family="sans-serif">',
        # 실루엣과 근육 윤곽은 반투명 회색이라 라이트·다크 배경 모두에서 보인다.
        f'<g fill="#9AA0A6" fill-opacity="0.22">{_BODY}</g>',
        f'<g transform="translate(110 0)" fill="#9AA0A6" fill-opacity="0.22">{_BODY}</g>',
        _layer(_FRONT, all_regions, 0, 'fill="#9AA0A6" fill-opacity="0.18"'),
        _layer(_BACK, all_regions, 110, 'fill="#9AA0A6" fill-opacity="0.18"'),
        _layer(_FRONT, sub, 0, f'fill="{fill}" fill-opacity="0.38"'),
        _layer(_BACK, sub, 110, f'fill="{fill}" fill-opacity="0.38"'),
        _layer(_FRONT, main, 0, f'fill="{fill}" fill-opacity="0.95"'),
        _layer(_BACK, main, 110, f'fill="{fill}" fill-opacity="0.95"'),
        '<g fill="#808495" font-size="10" text-anchor="middle">'
        '<text x="50" y="210">앞</text><text x="160" y="210">뒤</text></g>',
        "</svg>",
    ]
    return "".join(parts)
