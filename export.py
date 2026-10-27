"""CSV 내보내기 도우미 (F-4-5)."""

from datetime import date


def csv_safe(value: str) -> str:
    """Excel이 수식으로 실행하지 않도록 =, +, -, @ 등으로 시작하는 값 앞에 '를 붙인다."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def csv_file_name(start: date | None, end: date | None) -> str:
    if start is None:
        return "운동기록_전체.csv"
    if start == end:
        return f"운동기록_{start}.csv"
    return f"운동기록_{start}_{end}.csv"
