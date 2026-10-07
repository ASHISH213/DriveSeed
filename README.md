# DriveSeed

DriveSeed is a web application that downloads files on a server (via direct HTTP URLs and torrents), saves them directly into the user's personal Google Drive, and enables streaming and browsing via a modern, animated UI.

## Architecture

- **Backend:** Python 3.12+ / FastAPI (REST, SSE, Range streaming proxy)
- **Engines:** `libtorrent` (torrent) and `httpx` (HTTP downloads)
- **Background Jobs:** `arq` + Redis
- **Database:** PostgreSQL (SQLAlchemy 2, Alembic migrations)
- **Storage:** Google Drive API v3 (scoped to `drive.file`)
- **Frontend:** React + Vite + TypeScript + Tailwind CSS + shadcn/ui + Framer Motion

For technical architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md). For detailed product specs, see [DriveSeed_PRD.md](DriveSeed_PRD.md).

---

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 18+ and npm
- Docker & Docker Compose
- Google Cloud project with OAuth credentials (`drive.file` scope)

### Backend Setup
1. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -e backend/
   ```
3. Copy environment configuration:
   ```bash
   cp .env.example .env
   ```

### Frontend Setup
```bash
cd frontend
npm install
```

---

## Standard Commands

Reference commands from `AGENTS.md`:

- **Start everything (Docker Compose):**
  ```bash
  docker compose up --build
  ```
- **Backend tests:**
  ```bash
  cd backend && pytest -q
  ```
- **Backend lint & format:**
  ```bash
  cd backend && ruff check . && ruff format .
  ```
- **Backend type check:**
  ```bash
  cd backend && mypy app
  ```
- **Frontend dev server:**
  ```bash
  cd frontend && npm run dev
  ```
- **Frontend checks:**
  ```bash
  cd frontend && npm run lint && npm run typecheck && npm test
  ```
- **Database migrations:**
  ```bash
  cd backend && alembic revision --autogenerate -m "migration_message" && alembic upgrade head
  ```
