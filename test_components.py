import io
from datetime import timedelta

import pytest
from PIL import Image

from core import clock
from core.components import md, process_image_upload, workout_date_error, youtube_search_url
from core.muscle_map import regions_for, render_svg


def test_md_escapes_markdown_and_streamlit_directives():
    assert md("**굵게**") == r"\*\*굵게\*\*"
    assert md(":red[빨강]") == r"\:red\[빨강\]"
    assert md("[링크](http://x)") == r"\[링크\]\(http\:\/\/x\)".replace(r"\/", "/")
    assert md("벤치프레스") == "벤치프레스"


def test_workout_date_error():
    today = clock.today()
    assert workout_date_error(today) is None
    assert workout_date_error(today + timedelta(days=1))  # 미래 날짜 (B5)
    assert workout_date_error(today.replace(year=1999))  # 너무 오래된 날짜


def test_youtube_search_url_is_encoded():
    assert youtube_search_url("벤치 프레스&") .startswith("https://www.youtube.com/results?search_query=")
    assert "&" not in youtube_search_url("a&b").split("?", 1)[1].replace("search_query=", "")


def _image_bytes(fmt: str, size=(2400, 1200), mode="RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, (255, 0, 0, 128) if mode == "RGBA" else (255, 0, 0)).save(buf, format=fmt)
    return buf.getvalue()


@pytest.mark.parametrize("fmt,mode", [("PNG", "RGBA"), ("JPEG", "RGB"), ("WEBP", "RGB")])
def test_process_image_upload_resizes_to_jpeg(fmt, mode):
    mime, data = process_image_upload(_image_bytes(fmt, mode=mode))
    assert mime == "image/jpeg"
    img = Image.open(io.BytesIO(data))
    assert img.format == "JPEG" and max(img.size) == 1000


def test_process_image_upload_rejects_non_images():
    with pytest.raises(ValueError):
        process_image_upload(b"not an image")


def test_muscle_map_regions():
    assert regions_for("대퇴사두근, 둔근") == {"quads", "glutes"}
    assert regions_for("후면 삼각근") == {"rear_delts"}
    assert regions_for("알 수 없는 근육") == set()
    assert render_svg("알 수 없음", "") is None
    svg = render_svg("대흉근", "삼두근", "red")
    assert svg.startswith("<svg") and "#FF4B4B" in svg


def test_csv_safe_neutralizes_formulas():
    from core.export import csv_safe

    assert csv_safe('=HYPERLINK("x")') == "'=HYPERLINK(\"x\")"
    assert csv_safe("+1") == "'+1" and csv_safe("@SUM") == "'@SUM" and csv_safe("-2") == "'-2"
    assert csv_safe("60kg x 10") == "60kg x 10" and csv_safe("") == ""


def test_csv_file_name():
    from datetime import date

    from core.export import csv_file_name

    assert csv_file_name(None, None) == "운동기록_전체.csv"  # B9
    assert csv_file_name(date(2026, 10, 1), date(2026, 10, 1)) == "운동기록_2026-10-01.csv"
    assert csv_file_name(date(2026, 10, 1), date(2026, 10, 27)) == "운동기록_2026-10-01_2026-10-27.csv"
