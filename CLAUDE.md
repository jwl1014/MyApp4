# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Built in stages defined in `PROMPTS.md`: 1) skeleton, 2) features, 3) UI, 4) Playwright review → `REVIEW.md`, 5) deployment. **Stages 1–4 are done.**
- After the review, every finding was fixed. `REVIEW.md` §8 covers B1, B2 and B4; §9 covers B3, B5–B9, the Info items and the six partial requirements.
- What's left:
  - I7 is a Streamlit-internal console warning.
  - I5's ~0.6 s CSS delay is mitigated, not removed.
  - Stage 5 needs the user's own Supabase project. The Postgres backend was verified against a local PostgreSQL 16, not against Supabase itself.
- Record any new fixes in `REVIEW.md`.

- `PRD.md` (v1.1) reflects the implementation and is the source of truth. Requirement IDs (`F-1-1` … `F-5-3`) are referenced by the prompts and `REVIEW.md`; keep them stable.
- The user communicates in Korean; UI text, seed data, error messages, and docs are in Korean.

## Commands

```bash
.venv/Scripts/python -m streamlit run app.py      # http://localhost:8501
.venv/Scripts/python -m pytest                    # all tests (PostgreSQL cases skip)
.venv/Scripts/python -m pytest tests/test_db.py -k move_favorite   # single test
TEST_DATABASE_URL=postgresql://postgres@localhost:54329/gym_test .venv/Scripts/python -m pytest   # + PostgreSQL
```

- **Storage selection**:
  - `DATABASE_URL` selects the PostgreSQL backend. Otherwise SQLite is used: `data/gym.db`, or the file named by `GYM_DB_PATH`.
  - `data/gym.db` is the user's real log; never use it for tests.
  - `TEST_DATABASE_URL` makes `tests/test_db.py` run every storage test on PostgreSQL too. **It drops all tables each test**, so it must never point at real data.
- **No system PostgreSQL is installed.** To test against PostgreSQL, install one into the session scratchpad (check first whether `<scratchpad>/pgenv` already exists): `conda create -p <scratchpad>/pgenv -c conda-forge postgresql=16`, then run `initdb` and `pg_ctl` from `pgenv/Library/bin`. `pg_ctl start` keeps the shell pipe open, so expect the tool call to be backgrounded.
- **Servers**:
  - For Playwright, run a separate server on another port (8502+) and stop only the servers you started for testing.
  - The user usually has their own server on 8501. **Ask before stopping or restarting it.** It keeps already-imported `core/` modules, so after code changes tell the user it needs a restart to pick them up.
  - Likewise, ask before deleting tooling you set up in the scratchpad (e.g. a local PostgreSQL install).
  - Test the password gate with `--secrets.files <tmp>/secrets.toml`. Never create `.streamlit/secrets.toml`, because hot-reloaded secrets would lock the user's running app.
- **Page-level tests** use `streamlit.testing.v1.AppTest` (`tests/test_record_page.py`).
  - Paths are relative to the test file (`../views/...`).
  - Set `GYM_DB_PATH` to a tmp file and call `core.components.invalidate()` before and after, because `st.cache_data` is process-global.
  - `at.pills(key=...)`, `at.checkbox(key=...)` and `at.selectbox(key=...)` drive the record page.
  - When adding a regression test, confirm it fails with the fix disabled.

Playwright notes for this Streamlit version (1.66):
- **Checkboxes**: the row's label stretches to full width via CSS, so clicking anywhere on the row toggles it. Clicking the text is still the most robust choice.
- **Body-part pills**: the emoji is `aria-hidden`, so select by text: `locator('[data-testid="stButtonGroup"]').first().getByRole('button', {name: '등', exact: true})`. The selected state is `aria-pressed`.
- **Duplicate key elements**: buttons with `help=` appear twice under `.st-key-<key> button` because of the tooltip wrapper; use `.first()`.
- **Selectboxes**:
  - Click, wait about 500 ms, then click the option with `exact: true`; names like 벤치프레스 / 인클라인 벤치프레스 overlap.
  - Typing plus `Enter` works, except inside popover forms.
  - Body-part options carry an emoji (`🔵 등`).
- **Dates**: `st.date_input` renders contenteditable spinbuttons (`getByRole('spinbutton', {name: /day, 운동 날짜/})`). A typed value commits when focus leaves the widget; calendar picks (`stDateInputCalendarButton`) commit immediately. The range has no clear button.
- **File uploads**: `locator('[data-testid="stFileUploader"] input[type=file]').setInputFiles(path)`.
- **Mobile**: use a context with `isMobile: true, hasTouch: true` and an iPhone user agent; resizing the viewport alone keeps desktop behaviour. Navigation is `position="top"`, which becomes a drawer (`stExpandSidebarButton`) on mobile; on desktop, links are `header a`.
- **Sessions**: `page.goto` starts a new session and loses session state. Navigate through in-app links to test persistence.
- **Timing**: injected CSS lands about 0.6 s after the first render, so wait about 2 s before screenshots. After editing anything under `core/`, restart the test server; imported modules aren't reliably reloaded.
- **Harmless noise**:
  - Console 404s on `<page>/_stcore/health` and `/_stcore/host-config` after a deep-link reload.
  - An occasional `Multiple different fragmentIds` warning.

## Architecture

The app is a single-user Streamlit app. Selecting a body part auto-populates that part's **favorite** exercises, in favorite order, as a pre-checked list the user trims or extends. Clicking an exercise opens a detail dialog with a photo or a generated muscle map, plus posture tips.

- **`app.py`**:
  - Reads secrets, gates access, injects CSS, and routes with `st.navigation` from the `PAGES` table. Add new pages there.
  - Page scripts live in `views/`, deliberately not `pages/`. Streamlit auto-discovers `pages/`, so a deep link right after server start would skip `app.py`.
  - `gate()` maps every URL to one page (login or config error), so deep links never reach real pages before authentication.
- **`core/auth.py`**:
  - `read_password(st.secrets)` returns `None` only when no secrets file exists (`error_id == "no-secrets-found"`). Parse errors and an empty or non-string `APP_PASSWORD` raise `SecretsConfigError`, and the app locks (fail closed, details only in the server log).
  - `LoginThrottle` takes an injectable clock. Login uses a per-session throttle (5 failures → 30 s) plus an app-wide `st.cache_resource` one (20 in 10 min → 5 min).
- **`core/clock.py`** is the only source of "today" (`clock.today()`, KST = UTC+9, fixed offset because Windows lacks tzdata). Never call `date.today()` or `datetime.now()` directly.
- **`core/db.py`**:
  - `Storage` holds all queries. `SQLiteBackend` and `PostgresBackend` own only the DB-specific parts: DDL, connections, schema-version storage (`PRAGMA user_version` vs the `app_meta` table), sequence fixup after seeding, and unique-violation detection.
  - Write SQL in the shared dialect: `?` placeholders (`_PgConnection` rewrites them to `%s`, so don't use a literal `?` or `%`), `ON CONFLICT`, `RETURNING`, and full `GROUP BY` lists.
  - `SQLiteStorage(path)` and `PostgresStorage(url)` are factory functions. `get_storage()` picks the backend and is `lru_cache`d.
  - The Postgres backend uses a `psycopg_pool` with `prepare_threshold=None`, which Supabase's pooler needs, and an advisory lock around schema creation and seeding.
- **`core/components.py`**:
  - Holds the `st.cache_data` loaders (exercises, favorites, body parts, image keys, image bytes). Call `invalidate()` after any write to exercises, favorites or images. Workout logs are not cached.
  - Also holds `md()`, `workout_date_error()`, `process_image_upload()`, `exercise_image()`, `toggle_favorite()` and the detail dialog.
- **`core/muscle_map.py`** maps Korean muscle names to body regions by keyword (first match wins, so "후면 삼각근" comes before "삼각근") and renders a front/back SVG. New muscle names need a keyword there; `tests/test_components.py` checks that every seed name maps to a region.
- **`core/styles.py`** holds the per-part emoji and badge color and the global CSS (`st.html`). Theme colors live in `.streamlit/config.toml` under `[theme.light]` and `[theme.dark]`.
- **`core/export.py`** holds the CSV helpers: formula neutralizing and the file name.
- **Detail dialog**: `open_exercise_detail(id)` applies `st.dialog(md(ex.name))` at call time. Toggling a favorite inside it stores the id in session state and reruns, so pages that open the dialog must end with `reopen_pending_detail()`.

Data rules worth knowing:
- `exercises.mistakes` ("흔한 실수") is rendered separately from `tips`. Exercise names are unique per body part and limited to 50 characters.
- `workout_logs` is unique on `(workout_date, exercise_id)`. `save_workout(mode="merge"|"overwrite")` implements F-1-8.
- `created_at` is always written in KST by the app.
- Workout dates must not be in the future or before 2000-01-01 (`workout_date_error`). `last_workout_dates()` ignores future rows.
- A log's body part is derived through its exercise. Moving an exercise to another part changes the part shown on its past logs.
- Favorite `sort_order` is global, but `move_favorite` swaps only within a body part. `add_favorite(id, sort_order=...)` restores a removed favorite to its old slot (undo).
- **Images**:
  - Uploads are stored in the `exercise_images` table (BLOB/BYTEA, JPEG ≤1000px), so they survive Cloud restarts.
  - Display priority: uploaded image → `assets/images/{id}_form.png` / `_muscle.png` file → muscle-map SVG (muscle and card views) → placeholder.
  - Never add third-party exercise photos or invented video URLs. Without a `video_url`, the dialog links to a YouTube search.

Streamlit patterns used here. Keep them when changing the UI:
- **Record page state**: the source of truth is `st.session_state["rec"]` = `date` (`None` means today), `parts`, `items`, `unchecked`, and `stash` (lists of deselected parts, restored on reselect).
  - Each run copies `rec` into the `_rec_*` widget keys before rendering, and `on_change` callbacks write back.
  - `prune_items()` runs every render and on save. It drops ids whose exercise moved to another part, and duplicates across parts and the stash; a duplicate key would crash the page.
- **User text in Markdown** (names, memos, tips, badges, toasts, dialog titles) goes through `md()`. Raw HTML with `unsafe_allow_html` uses `html.escape`.
- **Flash messages**: page results go through a `*_flash` session key, `(kind, msg)`. Success is a toast; errors are `st.error`.
- **Closing the history edit popover**: it has a key and `on_change="rerun"`. After a save, the page sets `_hist_close_popover`, and the next run sets that key to `False` before rendering.
- **Widget `icon=`** accepts only one emoji or `:material/…:` ("☆" raises). Use "☆" as a label instead.
- **Row layouts** use `st.container(horizontal=True)`; `st.columns` stacks below 640px.
- **Icon buttons** are `type="tertiary"`; CSS gives them a 44×44px minimum.
- **Expanders need a `key`** so layout shifts don't collapse them.
- **No `clear_on_submit`**: forms embed a version counter in their key and bump it only on success.
- **Placeholders** carry inline styles, because global CSS arrives late.
- The primary target is a mobile browser; check layouts at 375px with a mobile context.

## Deployment (GitHub → Streamlit Community Cloud)

- **What gets committed**: `.gitignore` already excludes `.venv/`, caches, `*.db` (including the real `data/gym.db`), `.streamlit/secrets.toml` and `.playwright-mcp/`.
  - The deploy needs `app.py`, `views/`, `core/`, `data/exercises.json`, `requirements.txt`, `.streamlit/config.toml` and `assets/images/.gitkeep`.
  - Docs, `tests/` and `review/` are optional extras for the submission.
  - The directory is not a git repo yet. Ask before `git init`, committing or pushing.
- **Cloud settings**:
  - Main file `app.py`.
  - Python 3.12 or 3.13: streamlit 1.66.1 and pandas 3.1.0 need ≥3.11, and whether Cloud offers 3.14 is unverified.
  - Secrets: `APP_PASSWORD` and `DATABASE_URL`. Use Supabase's Session pooler URI; the README has the steps. If Secrets is left empty, the app opens without a password (warning toast only) and uses ephemeral SQLite.
