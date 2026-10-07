# TECH_STACK.md

Rule: choose from this list. Anything new needs approval (see `AGENTS.md`). Versions: use the current stable release at project start, then **pin exact versions** in `pyproject.toml`/`package.json` and commit the lockfiles. Do not upgrade major versions mid-milestone.

## Backend
| Area | Choice | Why | Not chosen |
|---|---|---|---|
| Language | Python 3.12 | Your main stack; best libtorrent bindings | n/a |
| Web framework | FastAPI + Uvicorn | Async, typed, automatic API docs | Flask (less async), Django (heavier) |
| Validation | Pydantic v2 | Built into FastAPI | n/a |
| Torrent engine | `libtorrent` (Python bindings, pip package) | Mature, supports sequential download and piece priorities | Writing a client from scratch, qBittorrent API (extra moving part) |
| HTTP downloads | `httpx` (async, Range support) | Resumable downloads | requests (sync) |
| Job queue | `arq` + Redis | Light, async-native | Celery (heavier, more setup) |
| Database | PostgreSQL + SQLAlchemy 2 + Alembic | Reliable, migrations | SQLite (only for the Colab profile) |
| Cache / pub-sub | Redis | Queue plus live progress events | n/a |
| Google APIs | `google-api-python-client`, `google-auth`, `google-auth-oauthlib` | Official; resumable uploads | Third-party Drive wrappers |
| Token encryption | `cryptography` (Fernet) | Simple and safe for stored refresh tokens | Storing tokens in plain text (never) |
| Media | FFmpeg (system binary) | HLS transcoding | n/a |
| Testing | pytest, pytest-asyncio, respx (HTTP mocks) | Standard | n/a |
| Quality | ruff (lint + format), mypy | Fast and strict | black + flake8 combo |

## Frontend
| Area | Choice | Why |
|---|---|---|
| Framework | React + Vite + TypeScript (strict) | Large animation ecosystem; static build served by FastAPI |
| Styling | Tailwind CSS + CSS variable tokens | Fast theming; tokens in `DESIGN.md` |
| Components | shadcn/ui (Radix) | Accessible primitives you own in the repo |
| Animation | Framer Motion (`motion`), Lottie for illustrations | Springs, layout animations, shared-element transitions |
| Server state | TanStack Query | Caching, optimistic updates |
| UI state | Zustand | Tiny and simple |
| Live updates | Server-Sent Events (SSE) first; WebSocket only if needed | Simpler than WebSockets for one-way progress |
| Player | Vidstack (or Video.js) + hls.js | Themeable, HLS |
| Icons / fonts | Lucide; Inter and JetBrains Mono | Consistent look |
| Testing | Vitest + Testing Library; Playwright for key flows (later) | Standard |

## Infrastructure
- Docker + Docker Compose (services: `api`, `worker`, `redis`, `postgres`, optional `caddy`).
- Reverse proxy: Caddy (automatic TLS) with response buffering off on `/stream` and `/events`.
- CI: GitHub Actions running lint, type check and tests.
- Hosting: any VPS or home server that **allows torrent traffic**. Check the provider's policy first.

## Do-not-use list
- No ORM-less raw SQL for app logic (migrations excepted).
- No Celery, no Flask, no Django, no jQuery.
- No CSS-in-JS libraries; no UI kits other than shadcn/ui.
- No service-account-based Drive storage (it has no personal quota).
- No full `drive` scope; no `localStorage` for tokens.
- No scraping libraries or torrent-search integrations.
