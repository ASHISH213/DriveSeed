# 🌱 DriveSeed

<p align="center">
  <img src="https://raw.githubusercontent.com/ASHISH213/pyTorrent/master/frontend/public/icon-512.png" alt="DriveSeed Logo" width="120" height="120" style="border-radius: 24px; box-shadow: 0 8px 32px rgba(0,0,0,0.3);" />
</p>

<p align="center">
  <strong>High-Performance Cloud Seedbox, Download Manager & Media Streamer for Google Drive</strong>
</p>

<p align="center">
  <a href="#features"><img src="https://img.shields.io/badge/Status-Production%20Ready-emerald?style=for-the-badge" alt="Status" /></a>
  <a href="#tech-stack"><img src="https://img.shields.io/badge/Python-3.12%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="#tech-stack"><img src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" /></a>
  <a href="#tech-stack"><img src="https://img.shields.io/badge/React-18%20%2B%20Vite-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React 18" /></a>
  <a href="#tech-stack"><img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Compose" /></a>
  <a href="#license"><img src="https://img.shields.io/badge/License-MIT-purple?style=for-the-badge" alt="License" /></a>
</p>

---

## 📖 Table of Contents

1. [Overview](#-overview)
2. [Key Features](#-key-features)
3. [Architecture & Tech Stack](#-architecture--tech-stack)
4. [Deployment Options](#-deployment-options)
   - [A. Production VPS Deployment (Docker Compose + Caddy)](#a-production-vps-deployment-docker-compose--caddy)
   - [B. Local Development (Windows / Linux / macOS)](#b-local-development-windows--linux--macos)
   - [C. Google Colab Edition (Zero Server, Drive-Mounted)](#c-google-colab-edition-zero-server-drive-mounted)
5. [Google Cloud Console Setup (OAuth 2.0)](#-google-cloud-console-setup-oauth-20)
6. [Integrations & Automation](#-integrations--automation)
   - [Telegram Bot Integration](#telegram-bot-integration)
   - [RSS Feed Auto-Downloader](#rss-feed-auto-downloader)
   - [Webhook Lifecycle Events](#webhook-lifecycle-events)
   - [Personal API Tokens (`ds_...`)](#personal-api-tokens-ds_)
7. [REST API Reference](#-rest-api-reference)
8. [Testing & Quality Verification](#-testing--quality-verification)
9. [Security & Compliance](#-security--compliance)
10. [License](#-license)

---

## 🌟 Overview

**DriveSeed** is a self-hosted cloud download orchestrator and media center designed to bridge fast internet connections with Google Drive. Instead of keeping gigabytes of downloaded files on local drives or VPS storage, DriveSeed downloads files on a server (via direct HTTP/HTTPS URLs or BitTorrent magnets) and automatically streams completed payloads straight into your personal Google Drive account.

Once uploaded to Drive, local scratch files are instantly deleted to keep your disk usage minimal. You can browse your Drive library, view folders, search items, manage files, and stream video/audio files directly inside a modern, glassmorphic web UI complete with subtitles, resume points, and keyboard navigation.

---

## ⚡ Key Features

- **🚀 Dual Download Engines**:
  - **BitTorrent / Magnet Engine**: Powered by `python-libtorrent` 2.x with sequential piece prioritization for instant streaming pre-allocation, file selection trees, and fine-grained bandwidth control.
  - **HTTP/HTTPS Direct Engine**: Resumable multi-threaded chunk downloads via `httpx` with SSRF protection against private/loopback address spoofing.
- **☁️ Zero-Footprint Google Drive Sync**:
  - Sequential 16 MB chunk uploads directly to Google Drive API v3 (strictly restricted to `drive.file` scope).
  - Checksum validation (MD5) and automatic scratch file purging upon upload verification.
- **🎬 Frosted-Glass Media Center**:
  - HTML5 media player (`PlayerShell`) with keyboard shortcuts (Space, J/L, Arrows, F, M, C), skip ripples, and progress bar hover previews.
  - Dynamic resume playback tracking via `/api/playback/{file_id}`.
  - Sidecar `.srt` and `.vtt` subtitle auto-discovery with on-the-fly SubRip-to-WebVTT conversion.
  - On-demand FFmpeg HLS transcoding fallback for non-native video formats (`.mkv`, HEVC, etc.).
  - Stream-while-downloading: watch active torrent downloads before the payload completes.
- **🤖 Power Integrations**:
  - **Telegram Bot**: Link your Telegram account with a one-time code to send magnet links or URLs (`/add <link>`), check real-time speeds (`/status`), browse files (`/library`), and receive push notifications on task completion.
  - **RSS Feed Auto-Downloader**: Poll periodic RSS 2.0 and Atom XML feeds with customizable regex filtering and GUID deduplication.
  - **HMAC Webhooks**: Register endpoints with `X-DriveSeed-Signature` headers to receive lifecycle webhook events (`task.completed`, `task.failed`).
  - **Personal API Tokens**: Generate Bearer tokens prefixed with `ds_...` (SHA-256 encrypted at rest) for custom automation scripts.
- **✨ Signature UI/UX & PWA**:
  - Framer Motion signature micro-animations: 45-degree diagonal progress bar sheen, cloud-to-drive upload particles, SVG self-drawing checkmarks, celebratory confetti bursts, and layout morphing.
  - Animated radial SVG storage ring (`StorageRing`) with adaptive thresholds (<75% green, 75-90% amber, ≥90% red).
  - Global Command Palette (`Ctrl+K` / `⌘K`) for rapid navigation, file search, and task filtering.
  - Full Progressive Web App (PWA) with service worker offline shell caching.
- **🔬 Google Colab Edition**:
  - Dedicated `colab` runtime profile that runs within Google Colab notebooks.
  - Mounts Google Drive (`/content/drive/MyDrive/DriveSeed`), uses in-process `asyncio` task queues, persistent SQLite DB, single-user owner authentication, and Google Drive native playback handoff (ensuring 100% compliance with Colab Terms of Service).

---

## 🏗 Architecture & Tech Stack

```mermaid
graph TD
    Client[Browser / PWA / Telegram Bot] -->|HTTPS / WSS / SSE| Caddy[Caddy 2 Reverse Proxy]
    Caddy -->|Static Assets| SPA[React 18 + Vite SPA]
    Caddy -->|REST API / SSE| API[FastAPI Backend]
    
    API -->|Authenticate / Tokens| DB[(PostgreSQL / SQLite)]
    API -->|Dispatch Jobs| Redis[(Redis 7)]
    Redis -->|Consume Tasks| Worker[arq Background Worker]
    
    Worker -->|Torrent Engine| Libtorrent[libtorrent Engine]
    Worker -->|Direct Engine| Httpx[httpx Download Engine]
    
    Libtorrent -->|Local Scratch| Scratch[(Temp Disk)]
    Httpx -->|Local Scratch| Scratch
    
    Scratch -->|Chunked Upload & Verify| GDrive[Google Drive API v3 / Mounted Drive]
    Scratch -.->|Auto-Delete on Complete| Scratch
    
    API -->|RFC 7233 Range Proxy / HLS| GDrive
    API -->|Live Task Events| Broadcaster[SSE Event Broadcaster]
    Broadcaster -->|Server-Sent Events| Client
```

| Layer | Technologies | Role / Notes |
|---|---|---|
| **Frontend** | React 18, Vite, TypeScript, Tailwind CSS, shadcn/ui, Framer Motion, Lucide Icons | Responsive glassmorphic UI, PWA, 60fps animations, Command Palette |
| **Backend API** | Python 3.12+, FastAPI, Pydantic v2, uvicorn | Async REST endpoints, SSE stream, Range byte seeking, OAuth & token security |
| **Worker & Queue** | `arq`, Redis 7, `asyncio` | High-throughput concurrent background task orchestration and retry handling |
| **Download Engines** | `python-libtorrent` 2.x, `httpx` | Sequential torrent streaming piece priority, HTTP range resume, SSRF protection |
| **Database** | PostgreSQL 16 (Server) / SQLite (Colab), SQLAlchemy 2 Async, Alembic | User profiles, tasks, files, playback timestamps, webhooks, RSS subscriptions |
| **Storage** | Google Drive API v3 (`drive.file`) or Mounted Drive | Resumable chunked upload, MD5 validation, atomic file replacement |
| **Proxy & TLS** | Caddy 2 | Automated ACME TLS, HTTP/3 (QUIC), unbuffered streaming (`flush_interval -1`) |

---

## 🚀 Deployment Options

### A. Production VPS Deployment (Docker Compose + Caddy)

This is the recommended production deployment for running DriveSeed on a dedicated VPS or home server.

#### 1. Server Prerequisites
- **OS**: Ubuntu 22.04 / 24.04 LTS, Debian 12, or Arch Linux.
- **Specs**: 1+ vCPU, 2+ GB RAM, and sufficient scratch disk (e.g. 20–50 GB SSD).
- **Network / Hosting Policy**: Ensure your VPS hosting provider permits BitTorrent traffic (e.g. Hetzner, OVH, BuyVM, Netcup, or residential home servers).
- **Ports**: Open ports `80/tcp`, `443/tcp`, and `443/udp` (for HTTP/3).

#### 2. DNS Configuration
Point an A / AAAA record to your server's public IP address:
```text
A     driveseed.yourdomain.com   ->  <Server IPv4 Address>
AAAA  driveseed.yourdomain.com   ->  <Server IPv6 Address> (Optional)
```

#### 3. Clone Repository & Setup Environment
```bash
git clone https://github.com/ASHISH213/pyTorrent.git /opt/driveseed
cd /opt/driveseed
cp .env.example .env
```

Generate secure cryptographic keys:
```bash
# Generate SECRET_KEY (session signature)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate FERNET_KEY (AES-128-CBC encryption of Drive refresh tokens at rest)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Configure your `.env` file:
```env
PROFILE=server
DOMAIN=driveseed.yourdomain.com
ACME_EMAIL=admin@yourdomain.com

SECRET_KEY=your-generated-secret-key
FERNET_KEY=your-generated-fernet-key

# Google OAuth Credentials (see Google Cloud Setup section below)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://driveseed.yourdomain.com/api/auth/callback
CORS_ORIGINS=https://driveseed.yourdomain.com

# PostgreSQL & Redis
POSTGRES_PASSWORD=your-secure-postgres-password
DATABASE_URL=postgresql+asyncpg://postgres:your-secure-postgres-password@postgres:5432/driveseed
REDIS_URL=redis://redis:6379/0

# Optional Telegram Bot Integration
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
```

#### 4. Launch Stack
```bash
docker compose up -d --build
```

This launches five orchestrated containers:
1. `caddy`: Handles automatic HTTPS certificates via Let's Encrypt / ZeroSSL and routes traffic with zero-buffer streaming.
2. `api`: FastAPI backend container serving the REST API and bundled frontend.
3. `worker`: Background download and upload pipeline processor.
4. `postgres`: PostgreSQL 16 database storing persistent relational state.
5. `redis`: Redis 7 instance managing job queues and live event channels.

#### 5. Verify Health & Logs
```bash
# Check running status
docker compose ps

# View service logs
docker compose logs -f caddy api worker

# Verify API healthcheck
curl -s https://driveseed.yourdomain.com/healthz?check_services=true
# Returns: {"status":"ok","database":"connected","redis":"connected"}
```

---

### B. Local Development (Windows / Linux / macOS)

#### Prerequisites
- **Python**: 3.12+
- **Node.js**: 18+ and `npm`
- **PostgreSQL & Redis**: Run locally or via Docker:
  ```bash
  docker run -d --name ds-postgres -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16-alpine
  docker run -d --name ds-redis -p 6379:6379 redis:7-alpine
  ```

#### Backend Setup
```bash
# 1. Create and activate Python virtual environment
python -m venv .venv

# On Windows PowerShell:
.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate

# 2. Install backend in editable mode with development dependencies
pip install -e "backend[dev]"

# 3. Configure local environment
cp .env.example .env
# Set DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/driveseed
# Set REDIS_URL=redis://localhost:6379/0

# 4. Run database migrations
cd backend
alembic upgrade head

# 5. Start the FastAPI development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

#### Running the Background Worker
In a second terminal window (with `.venv` active):
```bash
cd backend
python -m arq app.workers.pipeline.WorkerSettings
```

#### Frontend Setup
In a third terminal window:
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser. The Vite dev server proxies API calls to `http://localhost:8000`.

---

### C. Google Colab Edition (Zero Server, Drive-Mounted)

DriveSeed includes a fully compliant, zero-cost Google Colab edition that requires no server infrastructure.

> **Colab Terms of Service Compliance Guarantee**:
> In accordance with Google Colab's usage restrictions, the Colab profile:
> - **Strictly disables torrenting** (`TorrentEngine` throws `RuntimeError`, magnets are rejected).
> - **Disables media proxying** (media files are handed off to Google Drive's native viewer).
> - **Employs no keep-alive tricks or tunnels**.

#### How to Run on Google Colab:
1. Open the [driveseed_colab.ipynb](driveseed_colab.ipynb) notebook in Google Colab.
2. Select **Runtime > Run all** (or execute cells sequentially):
   - **Step 1**: Mounts your Google Drive (`/content/drive/MyDrive/DriveSeed`).
   - **Step 2**: Installs lightweight pinned dependencies (`pip install -r backend/requirements-colab.txt`).
   - **Step 3**: Sets `PROFILE=colab` and points database to SQLite on Google Drive (`.driveseed.db`).
   - **Step 4**: Initializes database tables and launches the FastAPI background server.
   - **Step 5**: Renders the complete DriveSeed web interface inside a Colab output iframe via `google.colab.output.serve_kernel_port_as_iframe(8000)`.

3. **Persistent State**:
   Because SQLite and all downloaded files are kept in `/content/drive/MyDrive/DriveSeed`, your task history, file library, and downloads survive Google Colab runtime disconnections and resets.

---

## 🔑 Google Cloud Console Setup (OAuth 2.0)

DriveSeed uses Google Drive API v3 with the minimal scope `https://www.googleapis.com/auth/drive.file`, which grants access only to files and folders created by DriveSeed itself.

1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., `DriveSeed`).
3. Enable APIs:
   - Go to **APIs & Services > Library**.
   - Search for **Google Drive API** and click **Enable**.
4. Configure OAuth Consent Screen:
   - Go to **APIs & Services > OAuth consent screen**.
   - Select **External** and fill in app details.
   - Under **Scopes**, add `.../auth/drive.file`.
   - Add your personal Gmail account to **Test users**.
5. Create OAuth Credentials:
   - Go to **APIs & Services > Credentials > Create Credentials > OAuth client ID**.
   - Application type: **Web application**.
   - Name: `DriveSeed Web Client`.
   - **Authorized JavaScript origins**:
     - Local: `http://localhost:5173` and `http://localhost:8000`
     - Production: `https://driveseed.yourdomain.com`
   - **Authorized redirect URIs**:
     - Local: `http://localhost:8000/api/auth/callback`
     - Production: `https://driveseed.yourdomain.com/api/auth/callback`
6. Copy the generated **Client ID** and **Client Secret** into your `.env` file.

---

## 🤖 Integrations & Automation

### Telegram Bot Integration

DriveSeed features a complete Telegram bot integration allowing remote management from your phone.

1. Create a bot using [@BotFather](https://t.me/BotFather) on Telegram and obtain your bot token.
2. Add `TELEGRAM_BOT_TOKEN=<your-token>` to your `.env` file.
3. Open DriveSeed Settings, navigate to **Telegram Bot**, and click **Connect Telegram Account** to generate a 6-digit one-time code.
4. Send `/start <code>` to your bot in Telegram to link your account.

**Available Bot Commands**:
- `/add <magnet|url>`: Enqueue a download task directly from Telegram.
- `/status`: View active tasks, speeds, percentages, and ETA tickers.
- `/library`: Browse recently uploaded files in Google Drive.
- `/unlink`: Disconnect your Telegram account from DriveSeed.
- **Push Notifications**: Receive instant Telegram messages when a download completes or fails.

---

### RSS Feed Auto-Downloader

Automate downloads from trackers or direct content feeds:
- Add RSS 2.0 (with enclosures or magnets) and Atom XML feeds.
- Configure regex match and exclude patterns (e.g., filter `1080p` while excluding `HDRip`).
- Automatic background polling every 15 minutes with duplicate filtering against seen GUIDs.

---

### Webhook Lifecycle Events

Register webhook endpoints in the Settings page to trigger external automation (e.g., n8n, Zapier, Discord, or Home Assistant):
- Events supported: `task.completed`, `task.failed`.
- Payloads are signed with an HMAC-SHA256 signature passed in the `X-DriveSeed-Signature: sha256=...` header.
- Includes automatic retry with exponential backoff on network failures.

---

### Personal API Tokens (`ds_...`)

Generate programmatic API tokens for shell scripts, CLI tools, or external services:
- Token format: `ds_<64-character-urlsafe-secret>`.
- Cryptographically hashed with SHA-256 before database storage.
- Pass in HTTP requests as: `Authorization: Bearer ds_...`.

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/capabilities` | Return runtime profile, storage backend, limits, and feature flags |
| `GET` | `/healthz` | Health check (`?check_services=true` validates DB and Redis) |
| `GET` | `/api/auth/login` | Return Google OAuth 2.0 authorization URL |
| `GET` | `/api/auth/callback` | Exchange OAuth code for encrypted session cookie |
| `GET` | `/api/auth/me` | Fetch authenticated user profile and Drive connection status |
| `POST` | `/api/tasks` | Create a new download task (`source_uri`, optional `name`) |
| `GET` | `/api/tasks` | List all tasks for authenticated user |
| `GET` | `/api/tasks/{id}` | Get detailed task progress, speeds, and file lists |
| `POST` | `/api/tasks/{id}/start` | Apply file selection and trigger upload/download pipeline |
| `POST` | `/api/tasks/{id}/pause` | Pause active downloading task |
| `POST` | `/api/tasks/{id}/resume` | Resume paused task |
| `POST` | `/api/tasks/{id}/retry` | Retry failed task with clean state |
| `DELETE` | `/api/tasks/{id}` | Cancel and remove task |
| `GET` | `/api/events` | Server-Sent Events (SSE) real-time task progress stream |
| `GET` | `/api/files` | Browse Google Drive files and folders (`?folder=<id>&search=<query>`) |
| `POST` | `/api/files/folder` | Create new folder in Google Drive |
| `PATCH` | `/api/files/{id}` | Rename or move a file/folder in Google Drive |
| `DELETE` | `/api/files/{id}` | Permanently delete file from Google Drive |
| `GET` | `/api/storage` | Fetch used, free, and total Google Drive quota |
| `GET` | `/stream/{file_id}` | RFC 7233 byte-range streaming proxy for audio and video |
| `GET` | `/stream/{file_id}/handoff` | 303 Redirect to Google Drive native viewer (Colab compliant) |
| `GET` | `/hls/{id}/index.m3u8` | On-demand FFmpeg HLS transcode master playlist |
| `GET` | `/api/files/{id}/subtitles` | List sidecar subtitle tracks for media file |
| `GET` | `/api/tokens` | List active personal API tokens |
| `POST` | `/api/tokens` | Create and reveal personal API token |
| `POST` | `/api/webhooks` | Register new webhook endpoint |
| `POST` | `/api/rss` | Create RSS auto-download subscription |

---

## 🧪 Testing & Quality Verification

DriveSeed maintains strict test coverage, static analysis, and type safety standards:

```bash
# 1. Run backend test suite (156 passing tests)
cd backend && pytest -q

# 2. Check code formatting & linting with Ruff
cd backend && ruff check . && ruff format --check .

# 3. Static type analysis with mypy strict mode
cd backend && mypy app

# 4. Run frontend test suite (72 passing Vitest tests)
cd frontend && npm test -- --run

# 5. Frontend TypeScript type checking & ESLint
cd frontend && npm run typecheck && npm run lint
```

---

## 🛡️ Security & Compliance

- **OAuth Scope Limitation**: DriveSeed exclusively requests `https://www.googleapis.com/auth/drive.file`. It can never read, modify, or list files not created by DriveSeed.
- **SSRF Hardening**: All direct URL requests validate DNS resolutions against private, loopback, and link-local IP blocks (RFC 1918, RFC 3927) on initial request and subsequent redirects.
- **Tokens Encrypted at Rest**: Google Drive refresh tokens are encrypted using AES-128-CBC (`Fernet`) before database insertion and decrypted in-memory only when initiating Google API client sessions.
- **Rate & Concurrency Limiting**: Includes sliding-window API rate limiters (`SlidingWindowRateLimiter`), active concurrent task caps per user, and media stream concurrency bounds (`StreamConcurrencyLimiter`).
- **Google Colab Compliance**: In the `colab` profile, torrent engines are disabled by profile configuration, and media proxying is replaced by Drive-native handoff links.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<p align="center">
  Crafted with modern engineering principles for fast, private, and elegant cloud file management.
</p>
