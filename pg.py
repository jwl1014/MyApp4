"""PostgreSQL 테스트 도우미.

TEST_DATABASE_URL 환경변수에 테스트 전용 DB를 지정하면 저장소 테스트가 PostgreSQL에서도 실행된다.
매 테스트마다 모든 테이블을 지우므로 실제 데이터가 있는 DB(Supabase 등)를 넣으면 안 된다.
"""

import os

TABLES = ["exercise_images", "workout_logs", "favorites", "exercises", "body_parts", "app_meta"]


def pg_test_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")


def reset_postgres(url: str) -> None:
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS " + ", ".join(TABLES) + " CASCADE")
