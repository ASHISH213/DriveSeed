
# TASKS.md

Work one task at a time. For each task: ask the agent for a plan, approve it, let it implement, run it yourself, then commit. Tick the box only when the **Done when** line is true.

## How to prompt the agent (copy and adapt)
- Start of a session: "Read AGENTS.md, then ARCHITECTURE.md. We are working on task **M1.3** in TASKS.md. Give me a short plan first and wait for my go."
- After it finishes: "Run the tests and the app, show me the results, and list anything you did not finish."
- If something breaks: "Do not guess. Show the exact error, explain the likely cause, and propose one fix."

---

## M0: Project skeleton (about 1 week)
- [x] **M0.1 Repo and tooling.** Create the folder layout from `AGENTS.md`, `pyproject.toml` (ruff, mypy, pytest), `.gitignore`, `.env.example`, README with run instructions.
  *Done when:* `ruff check`, `mypy app` and `pytest` all run (even with one trivial test) and pass.
- [x] **M0.2 FastAPI app with health check.** `GET /healthz` returns `{"status":"ok"}`; config loaded from environment in `core/config.py` including `PROFILE`.
  *Done when:* the endpoint works and a test covers it.
- [x] **M0.3 Docker Compose.** Services `api`, `postgres`, `redis`; API connects to both.
  *Done when:* `docker compose up --build` starts everything and `/healthz` responds at `localhost:8000`.
- [x] **M0.4 Database and migrations.** SQLAlchemy base, Alembic set up, first migration creating `users` and `tasks` tables.
  *Done when:* `alembic upgrade head` creates the tables in the Compose database.
- [x] **M0.5 Interfaces.** Add the Protocols in `app/interfaces/` exactly as in `ARCHITECTURE.md` section 3, plus in-memory fake implementations for tests.
  *Done when:* fakes pass a small contract test for each interface.
- [x] **M0.6 Frontend skeleton.** Vite + React + TypeScript + Tailwind + shadcn/ui; tokens from `DESIGN.md` applied; dark/light toggle; FastAPI serves the built bundle.
  *Done when:* the built app loads at `localhost:8000` showing the styled empty `AppShell` in both themes.
- [x] **M0.7 CI.** GitHub Actions running backend lint, types, tests and frontend lint, typecheck, tests.
  *Done when:* a pull request shows all checks green.

## M1: Core pipeline (about 3 weeks)
- [x] **M1.1 Google OAuth login.** Login/callback/logout routes, `drive.file` scope only, session cookie, encrypted refresh token stored in `users`. (Needs a Google Cloud OAuth client in "Testing" mode with your account as a test user.)
  *Done when:* you can sign in with Google, see your email in the UI, and the token in the database is encrypted.
- [x] **M1.2 Drive storage backend.** `DriveApiStorage`: create root folder "DriveSeed", create folder, resumable upload with progress, MD5/size verification, list, delete, quota.
  *Done when:* a script uploads a 200 MB test file into your Drive and verification passes; unit tests use a fake Drive client.
- [x] **M1.3 Task model and API.** Tables for `tasks` and `task_files`; routes to create, list, pause, resume, cancel; state machine from `ARCHITECTURE.md` section 4 with tests for allowed and forbidden transitions.
  *Done when:* tests prove transitions; API returns tasks in JSON.
- [x] **M1.4 HTTP download engine.** `HttpEngine` with `httpx`, Range resume, SSRF guard (block private/loopback/link-local, check redirects), progress reporting.
  *Done when:* a URL download completes, resumes after being killed midway, and a request to `http://127.0.0.1` is rejected (tests for both).
- [x] **M1.5 Worker and pipeline.** `arq` worker runs: download → upload to Drive → verify → delete temp files → `completed`.
  *Done when:* adding a direct URL via the API ends with the file in your Drive and the temp folder empty.
- [x] **M1.6 Torrent engine.** `TorrentEngine` with `libtorrent`: fetch metadata (file list), selected-file download, pause/resume, progress. Disabled when `PROFILE=colab`.
  *Done when:* a legal test torrent (for example a Linux distribution ISO's official torrent) downloads and lands in Drive; a test proves the engine refuses to start under `PROFILE=colab`.
- [x] **M1.7 Live progress (SSE).** `GET /events` streams task updates (Redis pub/sub).
  *Done when:* `curl -N localhost:8000/events` shows live progress while a task runs.
- [x] **M1.8 Minimal dashboard.** AddBox, TaskCard with progress and controls, live updates over SSE.
  *Done when:* you can paste a magnet or URL in the browser, watch progress, and see it complete.

## M2: Library and streaming (about 2–3 weeks)
- [x] **M2.1 Library API and UI.** List/rename/move/delete, folder navigation, breadcrumbs, list and grid views, search by name.
- [x] **M2.2 Range streaming proxy.** `GET /stream/{file_id}` with correct `206`, `Content-Range`, `Accept-Ranges`; token refresh mid-stream.
  *Done when:* an MP4 in Drive plays in the browser and seeking works.
- [x] **M2.3 Player v1.** Vidstack/Video.js shell, resume position saved in `playback`, keyboard shortcuts.
- [x] **M2.4 Storage meter.** `GET /api/storage` and the `StorageRing` component.

## M3: Polish (about 2 weeks)
- [x] **M3.1 File selection modal** with checkboxes, total size, Drive free-space check and folder picker.
- [x] **M3.2 Error and edge states** from `DESIGN.md` section 8 (Drive full, disconnected, failed task with retry).
- [x] **M3.3 Rate limits and per-user caps** for tasks and streams.
- [x] **M3.4 Deploy** to a VPS or home server with Caddy and TLS; document in README.

## M3b: Design system, motion, and interaction
- [x] **M3b.1 Command Palette (`Ctrl/Cmd+K`).** Global keyboard shortcut modal to search files, filter tasks, trigger navigation and quick actions.
- [ ] **M3b.2 Signature animations.** Complete animations from `DESIGN.md` Section 6 (progress bar sheen, animated speed ticker, SVG path checkmark, shared layout transitions).
- [ ] **M3b.3 PWA and performance pass.** Web App manifest, service worker for offline shell/PWA installability, Lighthouse performance pass.

## Later phases (break these into small tasks when you reach them)
- **M4 Advanced streaming:** FFmpeg HLS transcoding, subtitles, stream-while-downloading.
- **M5 Automation:** API tokens, webhooks, RSS, Telegram bot.
- **M6 Colab Edition:** `colab` profile implementations (`MountedDriveStorage`, `InProcessQueue`, SQLite, single-user auth, `DriveHandoffStreamer`), notebook, `/api/capabilities`, acceptance criteria from PRD section 18.6.

## Notes for you (not the agent)
- Commit after every ticked box. If the agent goes off track, revert to the last commit instead of trying to patch a mess.
- Keep a short "what I learned / decisions" list at the bottom of this file so future sessions have context.

## Decisions log
- 2026-10-12: implemented custom frosted-glass PlayerShell with native HTML5 media engine, keyboard shortcuts, resume position tracking via `/api/playback/{file_id}`, and skip ripples (M2.3)
- 2026-10-12: implemented GET /api/storage endpoint and animated StorageRing component with adaptive color thresholds (<75% success, 75-90% warning, >=90% danger) and hover breakdown (M2.4)
- 2026-10-12: implemented POST /api/tasks/{task_id}/start with pre-flight Google Drive free-space check, FileTree with checkboxes and search, FolderPicker destination picker, and FileSelectionModal (M3.1)
- 2026-10-12: implemented POST /api/tasks/{task_id}/retry, TaskCard retry button, and SystemAlerts handling offline, Drive full (0 B free), almost full (>=90%), and Drive disconnected states (M3.2)
- 2026-10-12: implemented SlidingWindowRateLimiter (10 req/min for tasks, 20 req/min for auth), StreamConcurrencyLimiter (2 distinct files per user with connection pooling), and per-user active task limit (max 3 concurrent active tasks on create and retry) with HTTP 429 Retry-After responses (M3.3)
- 2026-10-12: implemented production deployment configuration with multi-stage Dockerfile (SPA build + runtime), Caddyfile with automatic TLS and unbuffered streaming (flush_interval -1), docker-compose with Caddy, API, worker, Postgres and Redis, and documented full VPS/home server setup in README (M3.4)
- 2026-10-12: implemented Command Palette modal with global Ctrl+K / Cmd+K shortcut, header trigger button with ⌘K badge, debounced Google Drive file search, task status filtering, quick actions (tab navigation, add download, theme toggle, sign in/out), and keyboard navigation with arrow keys and Enter (M3b.1)
