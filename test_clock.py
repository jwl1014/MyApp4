from datetime import datetime, timedelta, timezone

from core import clock


def test_today_is_korean_date():
    # 서버 시간대와 무관하게 UTC+9 기준 날짜여야 한다 (B4).
    expected = (datetime.now(timezone.utc) + timedelta(hours=9)).date()
    assert clock.today() == expected
    assert clock.now().utcoffset() == timedelta(hours=9)
