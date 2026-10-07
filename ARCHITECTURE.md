# ARCHITECTURE.md

Short technical blueprint. Product reasoning lives in `DriveSeed_PRD.md`. If code and this file disagree, ask which is right and update the file.

## 1. Big picture
```
Browser (React app)
   │  HTTPS, SSE (/events)
   ▼
FastAPI  ──── enqueue ───►  Redis  ───►  Worker(s)
   │  ▲                                   │  libtorrent / httpx download
   │  │ Range stream                      │  → local temp dir
   ▼  │                                   │  → upload to Drive (resumable)
PostgreSQL                                ▼
                                   Google Drive (user's own)
```
- **API process:** auth, REST, SSE progress feed, streaming proxy.
- **Worker process:** downloads, uploads, transcoding. Runs separately so heavy work never blocks the API.
- **Drive is the source of truth for file content.** The database stores only metadata and Drive file IDs.
- **Temp disk is disposable.** Anything in the temp dir can be lost; tasks must be resumable.

## 2. Profiles
Behaviour is selected by `PROFILE` (env var): `server` (default) or `colab` (Phase 2).

| Interface | `server` | `colab` |
|---|---|---|
| `StorageBackend` | `DriveApiStorage` (OAuth, resumable upload) | `MountedDriveStorage` (mounted path) |
| `DownloadEngine` | `HttpEngine` + `TorrentEngine` | `HttpEngine` only |
| `TaskQueue` | `ArqQueue` (Redis) | `InProcessQueue` (asyncio) |
| Database | PostgreSQL | SQLite file on Drive |
| `Auth` | Google OAuth, multi-user | single-user session token |
| `Streamer` | `ProxyStreamer` (Range, HLS) | `DriveHandoffStreamer` (link to Drive viewer) |

Build every `server` implementation behind these interfaces from the start, so the Colab profile is only new implementations plus config.

## 3. Interfaces (`backend/app/interfaces/`)
```python
class StorageBackend(Protocol):
    async def ensure_root(self, user: User) -> str: ...                  # returns root folder id
    async def create_folder(self, user: User, parent_id: str, name: str) -> str: ...
    async def upload_file(self, user: User, parent_id: str, local_path: Path,
                          on_progress: Callable[[int, int], None]) -> StoredFile: ...  # verifies size + md5
    async def list_folder(self, user: User, folder_id: str) -> list[StoredFile]: ...
    async def open_range(self, user: User, file_id: str, start: int, end: int | None) -> AsyncIterator[bytes]: ...
    async def rename(self, user: User, file_id: str, new_name: str) -> StoredFile: ...
    async def move(self, user: User, file_id: str, new_parent_id: str) -> StoredFile: ...
    async def delete(self, user: User, file_id: str) -> None: ...
    async def quota(self, user: User) -> StorageQuota: ...

class DownloadEngine(Protocol):
    async def fetch_metadata(self, source: str) -> TaskMetadata: ...      # file list + sizes
    async def start(self, task: Task, selected: list[int], dest: Path) -> AsyncIterator[Progress]: ...
    async def pause(self, task_id: str) -> None: ...
    async def resume(self, task_id: str) -> None: ...
    async def cancel(self, task_id: str) -> None: ...

class TaskQueue(Protocol):
    async def enqueue(self, name: str, **kwargs) -> str: ...

class Streamer(Protocol):
    async def stream(self, user: User, file_id: str, range_header: str | None) -> StreamResponse: ...
```

## 4. Task state machine
```
queued → fetching_metadata → awaiting_selection → downloading → uploading → completed
                 │                                    │            │
                 └────────────── failed ◄─────────────┴────────────┘
 downloading ⇄ paused        any state → cancelled
```
Rules:
- Every state change is saved to the DB, then published as an SSE event.
- On worker restart, tasks in `downloading` or `uploading` are resumed from the last good state.
- `completed` is set only after Drive upload is verified (size and MD5) and temp files are deleted.
- Retries: up to 3 with exponential backoff for network and Drive 5xx/rate-limit errors; permanent errors go to `failed` with a readable message.

## 5. Key flows

**Add and store**
1. `POST /api/tasks` (magnet, URL or `.torrent`) → create task `queued`, enqueue metadata job.
2. Worker fetches metadata → task `awaiting_selection`, event sent with the file list.
3. `POST /api/tasks/{id}/start` with selected files and destination → pre-flight check of Drive free space → `downloading`.
4. As each file completes, upload it to Drive (resumable, 8–32 MB chunks) → record in `files` → delete local copy.
5. When all selected files are stored → `completed`.

**Stream**
1. Player requests `GET /stream/{file_id}` with `Range`.
2. API verifies session and ownership, gets a fresh Drive access token, requests the same range from Drive, and returns `206 Partial Content` with correct headers.
3. If the format is not browser-playable, the player requests `/hls/{file_id}/index.m3u8`; a worker transcodes on demand with FFmpeg and caches segments briefly.

## 6. Data model
- `users(id, google_sub, email, drive_refresh_token_enc, drive_root_folder_id, created_at)`
- `tasks(id, user_id, source_type, source_uri, info_hash, name, state, progress, size_bytes, error, created_at, completed_at)`
- `task_files(id, task_id, path, size_bytes, selected, state, drive_file_id)`
- `files(id, user_id, drive_file_id, name, parent_folder_id, mime_type, size_bytes, md5, created_at)`
- `playback(user_id, file_id, position_seconds, updated_at)`
- `api_tokens(id, user_id, token_hash, label, last_used_at)`
- `audit_log(id, user_id, action, target, created_at)`

All tables use UUID primary keys and `created_at`. Change the schema only through Alembic migrations.

## 7. API (v1)
| Method | Path | Purpose |
|---|---|---|
| GET | `/auth/google/login`, `/auth/google/callback`, POST `/auth/logout` | Google sign-in |
| POST | `/api/tasks` | Add magnet, URL or `.torrent` |
| GET | `/api/tasks` | List tasks |
| POST | `/api/tasks/{id}/start` | Start with selected files |
| POST | `/api/tasks/{id}/pause` · `/resume` · `/cancel` | Control |
| GET | `/api/files?folder=` | List library |
| PATCH / DELETE | `/api/files/{id}` | Rename, move, delete |
| GET | `/api/storage` | Drive quota |
| GET | `/api/capabilities` | What this profile supports, e.g. `{ "torrents": true, "streaming": "proxy", "multiUser": true }`; the frontend hides unsupported features |
| GET | `/events` | SSE progress stream |
| GET | `/stream/{file_id}` | Range streaming |
| GET | `/hls/{file_id}/index.m3u8` | Transcoded stream |
| GET | `/healthz` | Health check |

Error format: `{ "error": { "code": "TASK_NOT_FOUND", "message": "..." } }`.

## 8. Google Drive specifics
- OAuth authorization-code flow, offline access, scope `https://www.googleapis.com/auth/drive.file` only.
- Create one root folder "DriveSeed" per user; keep its ID in `users`.
- Refresh access tokens on demand; handle expiry during long streams and uploads.
- Resumable upload with chunk size a multiple of 256 KB; verify `md5Checksum` after upload.
- Surface quota and rate-limit errors as clear task errors, never silent retries forever.

## 9. Security checklist
- HTTPS only; secure, HttpOnly, SameSite cookies; CSRF protection on state-changing routes.
- Encrypt refresh tokens (Fernet; key from environment).
- SSRF guard on URL downloads: resolve DNS, block private ranges, re-check after every redirect.
- Rate limit add-task and auth endpoints; cap concurrent tasks and streams per user.
- Never expose Drive tokens to the browser; the API fetches from Drive on the user's behalf.
- Validate and sanitize file names (no path traversal when writing temp files).

## 10. Observability
Structured JSON logs with task and user IDs (no secrets), `/healthz`, basic Prometheus metrics (tasks by state, upload bytes, stream count), Sentry for exceptions (optional).

## 11. Colab profile notes (Phase 2)
Full rules in PRD section 18. In short: torrent engine disabled and tested, no media proxying, SQLite state on Drive, single-user token, scratch downloads on local disk then large sequential copies to Drive with checksum verification, resumable HTTP downloads.
