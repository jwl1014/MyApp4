from datetime import date

import pytest

from core.db import PostgresStorage, SQLiteStorage
from tests.pg import reset_postgres, pg_test_url


@pytest.fixture(params=["sqlite", "postgres"])
def make_storage(request, tmp_path):
    """같은 DB를 가리키는 새 Storage를 만드는 함수 (앱 재시작 흉내).

    postgres는 TEST_DATABASE_URL이 있을 때만 실행한다 (tests/pg.py 참고).
    """
    if request.param == "sqlite":
        path = tmp_path / "test.db"
        return lambda: SQLiteStorage(path)
    url = pg_test_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL이 없어 PostgreSQL 테스트를 건너뜀")
    reset_postgres(url)
    return lambda: PostgresStorage(url)


@pytest.fixture
def storage(make_storage):
    return make_storage()


def part_id(storage, name):
    return next(p.id for p in storage.list_body_parts() if p.name == name)


def exercise_id(storage, name):
    return next(e.id for e in storage.list_exercises() if e.name == name)


# ------------------------------------------------------------------ 시드

def test_seed_loads_body_parts_and_exercises(storage):
    assert [p.name for p in storage.list_body_parts()] == ["가슴", "등", "다리"]
    exercises = storage.list_exercises()
    assert len(exercises) == 18
    for ex in exercises:
        assert ex.tips and ex.mistakes and ex.primary_muscles
        assert ex.image_path == f"assets/images/{ex.id}_form.png"
        assert ex.muscle_image_path == f"assets/images/{ex.id}_muscle.png"


def test_seed_default_favorites_in_order(storage):
    names = [e.name for e in storage.list_favorites(part_id(storage, "가슴"))]
    assert names == ["벤치프레스", "푸시업", "딥스"]
    assert [e.name for e in storage.list_favorites(part_id(storage, "다리"))] == ["스쿼트", "레그프레스"]


def test_seed_is_idempotent_and_respects_user_changes(make_storage):
    first = make_storage()
    first.remove_favorite(exercise_id(first, "벤치프레스"))

    second = make_storage()  # 앱 재시작
    assert len(second.list_exercises()) == 18
    assert "벤치프레스" not in [e.name for e in second.list_favorites()]


# ------------------------------------------------------------ 운동 방법

def test_add_exercise_trims_and_rejects_duplicates(storage):
    chest = part_id(storage, "가슴")
    new_id = storage.add_exercise("  펙 덱   플라이 ", chest, tips=["팁"])
    ex = storage.get_exercise(new_id)
    assert ex.name == "펙 덱 플라이"
    assert ex.tips == ["팁"]
    assert ex.image_path == f"assets/images/{new_id}_form.png"
    assert ex.muscle_image_path == f"assets/images/{new_id}_muscle.png"

    with pytest.raises(ValueError):
        storage.add_exercise("펙 덱 플라이", chest)
    with pytest.raises(ValueError):
        storage.add_exercise("   ", chest)
    with pytest.raises(ValueError):
        storage.add_exercise("가" * 51, chest)


def test_same_name_allowed_in_different_body_part(storage):
    storage.add_exercise("벤치프레스", part_id(storage, "등"))


def test_update_exercise(storage):
    ex_id = exercise_id(storage, "푸시업")
    storage.update_exercise(ex_id, tips=["새 팁"], video_url="https://example.com")
    ex = storage.get_exercise(ex_id)
    assert ex.tips == ["새 팁"]
    assert ex.video_url == "https://example.com"

    with pytest.raises(ValueError):
        storage.update_exercise(ex_id, name="벤치프레스")
    with pytest.raises(ValueError):
        storage.update_exercise(ex_id, **{"id; DROP TABLE exercises": 1})


def test_special_characters_are_stored_safely(storage):
    name = "로우'); DROP TABLE exercises;--"
    ex_id = storage.add_exercise(name, part_id(storage, "등"))
    assert storage.get_exercise(ex_id).name == name
    assert len(storage.list_exercises()) == 19


# -------------------------------------------------------------- 즐겨찾기

def test_add_and_remove_favorite(storage):
    ex_id = exercise_id(storage, "덤벨 플라이")
    storage.add_favorite(ex_id)
    storage.add_favorite(ex_id)  # 중복 추가는 무시
    names = [e.name for e in storage.list_favorites(part_id(storage, "가슴"))]
    assert names == ["벤치프레스", "푸시업", "딥스", "덤벨 플라이"]
    assert storage.is_favorite(ex_id)

    storage.remove_favorite(ex_id)
    assert not storage.is_favorite(ex_id)


def test_move_favorite_within_body_part(storage):
    chest = part_id(storage, "가슴")
    storage.move_favorite(exercise_id(storage, "딥스"), -1)
    assert [e.name for e in storage.list_favorites(chest)] == ["벤치프레스", "딥스", "푸시업"]

    # 맨 위에서 위로, 맨 아래에서 아래로는 변화 없음 (다른 부위와 섞이지 않음)
    storage.move_favorite(exercise_id(storage, "벤치프레스"), -1)
    storage.move_favorite(exercise_id(storage, "푸시업"), 1)
    assert [e.name for e in storage.list_favorites(chest)] == ["벤치프레스", "딥스", "푸시업"]
    assert [e.name for e in storage.list_favorites(part_id(storage, "등"))] == ["랫풀다운", "바벨로우"]


# -------------------------------------------------------------- 운동 기록

def test_save_and_list_workout(storage):
    day = date(2026, 10, 27)
    ids = [exercise_id(storage, n) for n in ("벤치프레스", "푸시업")]
    assert storage.save_workout(day, ids) == 2
    assert storage.has_workout_on(day)

    logs = storage.list_workout_logs()
    assert {l.exercise_name for l in logs} == {"벤치프레스", "푸시업"}
    assert all(l.workout_date == day and l.body_part_name == "가슴" for l in logs)


def test_save_workout_merge_and_overwrite(storage):
    day = date(2026, 10, 27)
    bench, pushup, dips = (exercise_id(storage, n) for n in ("벤치프레스", "푸시업", "딥스"))
    storage.save_workout(day, [bench, pushup])

    assert storage.save_workout(day, [pushup, dips], mode="merge") == 1
    assert {l.exercise_name for l in storage.list_workout_logs()} == {"벤치프레스", "푸시업", "딥스"}

    storage.save_workout(day, [dips], mode="overwrite")
    assert [l.exercise_name for l in storage.list_workout_logs()] == ["딥스"]


def test_save_workout_requires_exercises(storage):
    with pytest.raises(ValueError):
        storage.save_workout(date(2026, 10, 27), [])


def test_list_workout_logs_filters(storage):
    storage.save_workout(date(2026, 10, 20), [exercise_id(storage, "스쿼트")])
    storage.save_workout(date(2026, 10, 25), [exercise_id(storage, "랫풀다운")])
    storage.save_workout(date(2026, 10, 27), [exercise_id(storage, "벤치프레스")])

    logs = storage.list_workout_logs()
    assert [l.workout_date.day for l in logs] == [27, 25, 20]

    ranged = storage.list_workout_logs(start=date(2026, 10, 21), end=date(2026, 10, 26))
    assert [l.exercise_name for l in ranged] == ["랫풀다운"]

    legs = storage.list_workout_logs(body_part_ids=[part_id(storage, "다리")])
    assert [l.exercise_name for l in legs] == ["스쿼트"]
    assert storage.list_workout_logs(body_part_ids=[]) == []


def test_update_and_delete_workout_log(storage):
    day = date(2026, 10, 27)
    storage.save_workout(day, [exercise_id(storage, "벤치프레스"), exercise_id(storage, "딥스")])
    bench_log, dips_log = storage.list_workout_logs()

    storage.update_workout_log(bench_log.id, memo="60kg")
    assert storage.list_workout_logs()[0].memo == "60kg"

    with pytest.raises(ValueError):
        storage.update_workout_log(bench_log.id, exercise_id=dips_log.exercise_id)

    storage.delete_workout_log(bench_log.id)
    assert [l.exercise_name for l in storage.list_workout_logs()] == ["딥스"]

    storage.delete_workout_day(day)
    assert storage.list_workout_logs() == []
    assert not storage.has_workout_on(day)


def test_last_workout_dates(storage):
    storage.save_workout(date(2026, 10, 20), [exercise_id(storage, "스쿼트")])
    storage.save_workout(date(2026, 10, 23), [exercise_id(storage, "레그 컬")])
    assert storage.last_workout_dates() == {
        "가슴": None,
        "등": None,
        "다리": date(2026, 10, 23),
    }


def test_last_workout_dates_ignores_future(storage):
    # B5: 잘못 입력한 미래 날짜가 "N일 후"로 표시되지 않아야 한다.
    storage.save_workout(date(2026, 10, 20), [exercise_id(storage, "랫풀다운")])
    storage.save_workout(date(2030, 1, 15), [exercise_id(storage, "바벨로우")])
    assert storage.last_workout_dates(until=date(2026, 10, 27))["등"] == date(2026, 10, 20)


def test_new_exercise_ids_continue_after_seed(storage):
    # PostgreSQL은 시드가 id를 직접 넣으므로 시퀀스가 뒤로 옮겨져 있어야 한다.
    new_id = storage.add_exercise("펙덱 플라이", part_id(storage, "가슴"))
    assert new_id > 18
    storage.add_favorite(new_id)
    assert storage.is_favorite(new_id)


def test_update_exercise_error_messages(storage):
    # B7: 중복 이름과 그 밖의 오류를 구분해 안내한다.
    ex_id = exercise_id(storage, "푸시업")
    with pytest.raises(ValueError, match="같은 이름"):
        storage.update_exercise(ex_id, name="벤치프레스")
    with pytest.raises(ValueError, match="존재하지 않는 부위"):
        storage.update_exercise(ex_id, body_part_id=9999)
    with pytest.raises(ValueError, match="존재하지 않는 부위"):
        storage.add_exercise("새 운동", 9999)


def test_restore_favorite_to_original_position(storage):
    chest = part_id(storage, "가슴")
    pushup = exercise_id(storage, "푸시업")
    order = storage.favorite_sort_order(pushup)
    storage.remove_favorite(pushup)
    storage.add_favorite(pushup, sort_order=order)
    assert [e.name for e in storage.list_favorites(chest)] == ["벤치프레스", "푸시업", "딥스"]


def test_exercise_images(storage):
    ex_id = exercise_id(storage, "스쿼트")
    assert storage.get_exercise_image(ex_id, "form") is None
    storage.set_exercise_image(ex_id, "form", "image/jpeg", b"jpeg-data-1")
    storage.set_exercise_image(ex_id, "form", "image/png", b"png-data-2")  # 덮어쓰기
    assert storage.get_exercise_image(ex_id, "form") == ("image/png", b"png-data-2")
    assert storage.list_image_keys() == {(ex_id, "form")}
    storage.delete_exercise_image(ex_id, "form")
    assert storage.list_image_keys() == set()
    with pytest.raises(ValueError):
        storage.set_exercise_image(ex_id, "other", "image/png", b"x")


def test_created_at_is_kst(storage, monkeypatch):
    from datetime import datetime
    from core import clock, db
    fixed = datetime(2026, 10, 27, 7, 30, tzinfo=clock.KST)  # 한국 오전 7:30 = UTC 전날 22:30
    monkeypatch.setattr(db.clock, "now", lambda: fixed)
    storage.save_workout(date(2026, 10, 27), [exercise_id(storage, "스쿼트")])
    assert storage.list_workout_logs()[0].created_at == datetime(2026, 10, 27, 7, 30)
