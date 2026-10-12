# DriveSeed

DriveSeed is a modern, high-performance web application that downloads files on a server (via direct HTTP/HTTPS URLs and torrents), automatically saves them directly into the user's personal Google Drive, and provides instant in-browser browsing and media streaming with a responsive animated UI.

---

## Architecture

- **Backend:** Python 3.12+ / FastAPI (REST API, Server-Sent Events, RFC 7233 Range streaming proxy)
- **Engines:** `libtorrent` (BitTorrent engine) and `httpx` (resumable HTTP downloads with SSRF guard)
- **Background Workers:** `arq` + Redis
- **Database:** PostgreSQL (SQLAlchemy 2 async ORM, Alembic migrations)
- **Storage:** Google Drive API v3 (strictly scoped to `drive.file`)
- **Reverse Proxy:** Caddy 2 (automated Let's Encrypt / ZeroSSL TLS, unbuffered streaming)
- **Frontend:** React + Vite + TypeScript + Tailwind CSS + shadcn/ui + Framer Motion

For technical architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md). For detailed product specs, see [DriveSeed_PRD.md](DriveSeed_PRD.md).

---

## Production Deployment (VPS or Home Server)

DriveSeed is fully containerized with Docker Compose and includes Caddy as an automated TLS reverse proxy.

### 1. Server Requirements

- **Operating System:** Linux (Ubuntu 22.04 / 24.04 LTS, Debian 12, or similar)
- **Hardware:** 1+ vCPU, 2+ GB RAM, and sufficient scratch disk for concurrent downloads (downloads are deleted locally once uploaded to Google Drive).
- **Hosting Policy:** Ensure your VPS provider or ISP **allows torrent traffic** (e.g., Hetzner, BuyVM, OVH, Netcup, or home servers). Check the provider's Terms of Service.
- **Firewall / Open Ports:** Open ports `80/tcp`, `443/tcp`, and `443/udp` (for HTTP/3 QUIC).

### 2. DNS Configuration

Point your domain or subdomain to your server's public IP address:
- **A Record:** `driveseed.yourdomain.com` -> `<Server IPv4>`
- **AAAA Record:** `driveseed.yourdomain.com` -> `<Server IPv6>` (optional)

### 3. Google OAuth 2.0 Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project and navigate to **APIs & Services > Library**.
3. Enable the **Google Drive API**.
4. Configure the **OAuth Consent Screen** (User Type: External) and add the `.../auth/drive.file` scope.
5. Navigate to **APIs & Services > Credentials** and click **Create Credentials > OAuth client ID** (Web application).
6. Configure the URIs:
   - **Authorized JavaScript origins:** `https://driveseed.yourdomain.com`
   - **Authorized redirect URIs:** `https://driveseed.yourdomain.com/api/auth/callback`
7. Copy your **Client ID** and **Client Secret**.

### 4. Server Configuration

Clone the repository and copy `.env.example`:

```bash
git clone https://github.com/your-username/pyTorrent.git /opt/driveseed
cd /opt/driveseed
cp .env.example .env
```

Generate secure production secrets:

```bash
# Generate SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate FERNET_KEY (for encrypting Google Drive refresh tokens at rest)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Edit `.env` with your domain and credentials:

```bash
DOMAIN=driveseed.yourdomain.com
ACME_EMAIL=admin@yourdomain.com

SECRET_KEY=your-generated-secret-key
FERNET_KEY=your-generated-fernet-key

GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://driveseed.yourdomain.com/api/auth/callback
CORS_ORIGINS=https://driveseed.yourdomain.com

DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/driveseed
POSTGRES_PASSWORD=choose-a-strong-db-password
REDIS_URL=redis://redis:6379/0
```

### 5. Launch with Docker Compose

Build and launch the full stack in detached mode:

```bash
docker compose up -d --build
```

The stack launches 5 orchestrated services:
1. `caddy`: Front-facing reverse proxy with automatic Let's Encrypt / ZeroSSL TLS certificate issuance.
2. `api`: FastAPI backend and pre-built React frontend SPA.
3. `worker`: `arq` background queue processing torrent and direct URL downloads and Drive uploads.
4. `postgres`: PostgreSQL 16 database.
5. `redis`: Redis 7 job queue and SSE broadcaster.

### 6. Verify Deployment

- **Check container status:**
  ```bash
  docker compose ps
  ```
- **Inspect service logs:**
  ```bash
  docker compose logs -f caddy api worker
  ```
- **Verify healthcheck:**
  Visit `https://driveseed.yourdomain.com/healthz?check_services=true` in your browser or curl:
  ```bash
  curl -s https://driveseed.yourdomain.com/healthz?check_services=true
  # Returns: {"status":"ok","database":"connected","redis":"connected"}
  ```

### 7. How Caddy Handles Reverse Proxying & Streaming

In [Caddyfile](Caddyfile):
- Automatic TLS certificate issuance and renewal via ACME.
- Response buffering is explicitly disabled (`flush_interval -1`) on `/stream/*`, `/api/stream/*`, and `/api/events`. This ensures real-time Server-Sent Events progress events and media byte-range seeking are streamed with zero proxy buffering latency.
- Non-streaming responses are compressed using modern Zstandard and Gzip.

---

## Local Development

### Prerequisites
- Python 3.12+
- Node.js 18+ and npm
- PostgreSQL and Redis (or run via `docker compose up -d postgres redis`)

### Backend Setup
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -e backend/
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## Standard Commands

Reference commands from `AGENTS.md`:

- **Run all backend tests:**
  ```bash
  cd backend && pytest -q
  ```
- **Backend lint and format checks:**
  ```bash
  cd backend && ruff check . && ruff format --check .
  ```
- **Backend static type checking:**
  ```bash
  cd backend && mypy app
  ```
- **Frontend test suite:**
  ```bash
  cd frontend && npm test
  ```
- **Frontend lint and typecheck:**
  ```bash
  cd frontend && npm run lint && npm run typecheck
  ```
- **Build production frontend:**
  ```bash
  cd frontend && npm run build
  ```
- **Generate and apply database migrations:**
  ```bash
  cd backend && alembic revision --autogenerate -m "migration_description" && alembic upgrade head
  ```
