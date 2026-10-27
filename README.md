# 🏋️ 개인 헬스 기록

헬스장 운동 기록(날짜·부위·운동 방법)을 관리하는 Streamlit 웹 앱입니다.
- 요구사항: [PRD.md](PRD.md)
- 검토 결과: [REVIEW.md](REVIEW.md)

## 로컬 실행

Python 3.11 이상이 필요합니다.

```bash
# 1. 가상환경 생성
python -m venv .venv

# 2. 가상환경 활성화
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

# 3. 패키지 설치
pip install -r requirements.txt

# 4. 실행 → http://localhost:8501
streamlit run app.py
```

- **첫 실행**: `data/gym.db`(SQLite)가 생성되고 기본 운동 18개와 즐겨찾기가 등록됩니다.
- **다른 DB 파일 쓰기**: `GYM_DB_PATH` 환경변수를 지정합니다. 테스트할 때 실제 기록이 섞이지 않게 하려면 이렇게 하세요.

```bash
GYM_DB_PATH=test.db streamlit run app.py          # bash
$env:GYM_DB_PATH="test.db"; streamlit run app.py  # PowerShell
```

## 설정 (`.streamlit/secrets.toml` 또는 Streamlit Cloud의 Secrets)

```toml
APP_PASSWORD = "원하는 비밀번호"        # 없으면 비밀번호 없이 열림 (로컬 개발용)
DATABASE_URL = "postgresql://..."       # 없으면 SQLite 사용
```

- **`APP_PASSWORD`**
  - 형식이 틀리거나(따옴표 누락 등) 값이 비어 있으면 앱이 잠깁니다. 비밀번호 없이 열리지는 않습니다.
  - 로그인을 반복해서 틀리면 잠시 막힙니다. 한 세션에서 5번 틀리면 30초, 앱 전체에서 10분 동안 20번 틀리면 5분입니다.
- **`DATABASE_URL`**: 있으면 Supabase(PostgreSQL)에 저장합니다. Streamlit Cloud는 재시작할 때 로컬 파일을 지우므로 **배포할 때는 반드시 설정하세요.**
- **`secrets.toml`**: Git에 올리지 마세요. 이미 `.gitignore`에 들어 있습니다.

## Supabase 연결 방법

1. [supabase.com](https://supabase.com)에서 프로젝트를 만듭니다.
2. **Connect** 버튼 → **Connection string** → **Session pooler**의 URI를 복사합니다.
   - 형식: `postgresql://postgres.<프로젝트ID>:<DB비밀번호>@aws-0-<리전>.pooler.supabase.com:5432/postgres`
   - `<DB비밀번호>`는 프로젝트를 만들 때 정한 데이터베이스 비밀번호입니다.
3. 복사한 값을 Secrets의 `DATABASE_URL`에 넣습니다. 테이블과 기본 데이터는 앱이 처음 실행될 때 자동으로 만들어집니다.

## Streamlit Community Cloud 배포

1. GitHub 저장소에 코드를 올립니다. `.gitignore`가 DB 파일, 가상환경, `secrets.toml`을 제외합니다.
2. [share.streamlit.io](https://share.streamlit.io)에서 다음과 같이 설정합니다.
   - 저장소를 고르고 Main file path를 `app.py`로 지정합니다.
   - **Advanced settings**에서 Python 3.12 또는 3.13을 고릅니다.
   - Secrets에 `APP_PASSWORD`와 `DATABASE_URL`을 입력합니다.

## 테스트

```bash
pip install -r requirements-dev.txt
python -m pytest                                  # 전체 (PostgreSQL 테스트는 건너뜀)
python -m pytest tests/test_db.py -k favorite     # 일부만
```

- **PostgreSQL 테스트**: 저장소 테스트는 `TEST_DATABASE_URL`이 있으면 PostgreSQL에서도 실행됩니다.
- **주의**: 이 테스트는 매번 모든 테이블을 지웁니다. 반드시 테스트 전용 DB를 쓰고, 실제 Supabase DB 주소를 넣지 마세요.

```bash
TEST_DATABASE_URL=postgresql://postgres@localhost:5432/gym_test python -m pytest
```

## 폴더 구조

| 경로 | 역할 |
|---|---|
| `app.py` | 진입점: 비밀번호 확인, 페이지 네비게이션, CSS |
| `views/` | 운동 기록 / 운동 이력 / 운동 사전 / 즐겨찾기 페이지. `pages/`라는 이름은 쓰지 않습니다(Streamlit이 자동 인식해 로그인을 우회할 수 있음) |
| `core/db.py` | 저장소 (SQLite / PostgreSQL) |
| `core/components.py` | 공통 UI, 캐시 로더, 사진 처리, 운동 상세 다이얼로그 |
| `core/muscle_map.py` | 근육 정보로 자극 부위 그림(SVG) 생성 |
| `core/styles.py` | 부위별 색·이모지, 전역 CSS |
| `core/auth.py` | 비밀번호 설정 읽기, 로그인 시도 제한 |
| `core/clock.py` | 한국 시간 기준 날짜 |
| `core/export.py` | CSV 내보내기 도우미 |
| `core/models.py` | 데이터 클래스 |
| `data/exercises.json` | 기본 운동 방법·자세 팁·즐겨찾기 시드 데이터 |
| `assets/images/` | (선택) 파일로 두는 운동 사진 `{id}_form.png`, `{id}_muscle.png` |
| `tests/` | pytest + Streamlit AppTest |
