"""한국 시간 기준 날짜/시각.

Streamlit Community Cloud 서버는 UTC로 동작하므로 date.today()를 쓰면 한국 오전 0~9시에
날짜가 하루 밀린다. 앱의 "오늘"은 항상 이 모듈을 통해 구한다.
한국은 서머타임이 없어 고정 오프셋을 쓴다 (ZoneInfo는 Windows에서 tzdata 패키지가 필요).
"""

from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9), "KST")


def now() -> datetime:
    return datetime.now(KST)


def today() -> date:
    return now().date()
