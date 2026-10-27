"""앱 전반에서 사용하는 데이터 클래스."""

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class BodyPart:
    id: int
    name: str


@dataclass(frozen=True)
class Exercise:
    id: int
    name: str
    body_part_id: int
    body_part_name: str
    image_path: str | None = None
    muscle_image_path: str | None = None
    primary_muscles: str = ""
    secondary_muscles: str = ""
    tips: list[str] = field(default_factory=list)
    mistakes: list[str] = field(default_factory=list)
    video_url: str | None = None


@dataclass(frozen=True)
class WorkoutLog:
    id: int
    workout_date: date
    exercise_id: int
    exercise_name: str
    body_part_id: int
    body_part_name: str
    memo: str = ""
    created_at: datetime | None = None
