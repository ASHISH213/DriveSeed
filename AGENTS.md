# AGENTS.md: Project rules for DriveSeed

Read this file first in every session. Then read `ARCHITECTURE.md`, `TECH_STACK.md`, `DESIGN.md` and `TASKS.md` when relevant. The full product spec is `DriveSeed_PRD.md` (read only the section you need).

## What this project is
DriveSeed is a web app that downloads files on a server (direct URLs and torrents), saves them into the user's own Google Drive, and lets the user browse and stream them in a modern, animated UI. A later "Colab profile" runs a reduced version inside Google Colab.

## Stack (one line)
Python 3.12 + FastAPI + python `libtorrent` + arq (Redis) + PostgreSQL (SQLAlchemy, Alembic) + Google Drive API v3; frontend React + Vite + TypeScript + Tailwind + shadcn/ui + Framer Motion. Details in `TECH_STACK.md`.

## Repository layout
```
backend/
  app/
    main.py              FastAPI entry
    api/                 routers (auth, tasks, files, stream, events)
    core/                config, security, db, logging
    interfaces/          Protocols: StorageBackend, DownloadEngine, TaskQueue, Streamer
    services/            drive.py, torrent.py, http_download.py, transcode.py
    workers/             background jobs
    models/              SQLAlchemy models
    schemas/             Pydantic schemas
  migrations/            Alembic
  tests/
frontend/
  src/ (components, pages, hooks, styles, lib)
docs/                    extra notes
docker-compose.yml
.env.example
```
Do not invent new top-level folders without asking.

## Commands (keep this section up to date)
- Start everything: `docker compose up --build`
- Backend tests: `cd backend && pytest -q`
- Backend lint/format: `cd backend && ruff check . && ruff format .`
- Type check: `cd backend && mypy app`
- Frontend dev: `cd frontend && npm run dev`
- Frontend checks: `cd frontend && npm run lint && npm run typecheck && npm test`
- DB migration: `cd backend && alembic revision --autogenerate -m "msg" && alembic upgrade head`

If a command here does not work yet, say so and fix this section when it does.

## How to work (important)
1. **One task at a time.** Work only on the task I name from `TASKS.md`. Do not start the next one.
2. **Plan first.** Before writing code, give a short plan: files to create or change, and how you will verify it. Wait for my "go" unless the task is trivial.
3. **Small steps.** Prefer small, reviewable changes. Commit after each working step with a clear message (`feat:`, `fix:`, `chore:`, `docs:`).
4. **Verify.** After changes, run the relevant tests and the app. Report what you ran and the result. Never claim something works without running it.
5. **Tests.** Every new backend function with logic gets a test. Use fakes for Drive and libtorrent in tests; never hit real Google APIs in automated tests.
6. **Ask before** adding a dependency, changing the database schema outside a migration, changing a public API route, or deviating from `ARCHITECTURE.md`.
7. **Update docs.** If you change behaviour, update the matching `.md` file in the same change.
8. If you are blocked or unsure, stop and ask a specific question instead of guessing.

## Code conventions
- Python: type hints everywhere, `async` for I/O, Pydantic models for request/response, no business logic in routers (put it in `services/`).
- Use the interfaces in `app/interfaces/`. Code outside `services/` must not import Google or libtorrent libraries directly.
- Configuration only through `app/core/config.py` (environment variables). No hard-coded secrets, URLs or paths.
- Errors: raise typed exceptions, return consistent JSON errors `{ "error": { "code": "...", "message": "..." } }`.
- Logging: structured logs. Never log tokens, magnet links with private trackers, or full file contents.
- Frontend: TypeScript strict mode, small components, styling through Tailwind classes and the tokens in `DESIGN.md`, animations through the motion presets (no random one-off timings).
- Keep functions short and names descriptive. No dead code or commented-out blocks.

## Hard rules (never break)
- **Secrets:** never commit `.env`, tokens or credentials. Only `.env.example` with placeholder values.
- **Drive tokens** are encrypted at rest and never sent to the browser.
- **URL downloads** must block private/loopback/link-local IP ranges (SSRF protection), including after redirects.
- **Scope:** request only the Google Drive scope `drive.file`.
- **No content search or indexing:** do not add any search engine, tracker list, or index of copyrighted content.
- **Colab profile (`PROFILE=colab`):** the torrent engine must be disabled and no media proxying is allowed. There must be a test proving this. Do not add keep-alive tricks, tunnels or anything that evades Colab's usage rules.
- **Local temp files** are always deleted after a verified upload to Drive.
- Do not delete or overwrite user files in Drive without an explicit user action in the UI.

## Definition of done (for any task)
- Code runs; relevant tests pass; lint and type checks pass.
- The behaviour in the task's "Done when" line is demonstrated.
- Docs updated if needed; changes committed.
- A short summary is given: what changed, what was run, anything left over.
