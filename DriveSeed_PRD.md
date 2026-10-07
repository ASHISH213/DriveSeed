# Product Requirements Document: DriveSeed

**Working title:** DriveSeed (an improved, Google Drive–backed alternative to Seedr)
**Stack:** Python (FastAPI, libtorrent, Celery/arq, PostgreSQL, Redis)
**Version:** 1.1 draft  |  **Date:** 7 Oct 2026  |  **Owner:** Ashish
**Changes in 1.1:** modern, animation-rich UI/UX spec (sections 6.2, 6.4, 6.5); new Phase 2 "Colab Edition" (section 18) with a compliance review that changes its scope.

---

## 1. Summary

DriveSeed is a web app that fetches torrents and direct links on cloud servers, saves the finished files into the **user's own Google Drive**, and lets them **stream or download** those files from the browser. The user's device never connects to a torrent swarm, and storage is not capped by the service's own disks.

The core product bet: Seedr charges for hosted storage. If the user's Drive is the storage layer, the service's cost drops sharply, and users get far more space than a 2 GB free tier.

## 2. Analysis of Seedr (baseline)

> **Source note:** the Seedr site blocks automated page fetching, so the UI notes below come from public reviews and directory listings plus general knowledge of the product, not a pixel-level inspection. Verify against screenshots before finalising the design.

### 2.1 What Seedr does
- Add a torrent via magnet link, `.torrent` file, or URL; Seedr downloads it on its servers.
- Files land in a private cloud storage area, shown in a file-explorer-style view.
- Browser streaming of video and audio without downloading first.
- Normal HTTP download of finished files to the user's device.
- Freemium: small free storage (reported as 2 GB), paid tiers for more space, speed and extra access methods.
- Privacy angle: the user's machine only talks to Seedr's servers, not to peers.

### 2.2 UI/UX observations
- Simple, single-purpose dashboard: an "add" input at the top, a task list, then folders and files.
- Low learning curve, which is the main reason reviewers like it.
- Light on power-user tools: limited search, bulk actions, previews and organisation.

### 2.3 Strengths to keep
1. Dead-simple add-and-stream flow.
2. Zero client software.
3. Folder browsing that feels like a normal file manager.
4. Privacy from the swarm.

### 2.4 Gaps to fix (our opportunities)
| Gap in Seedr | DriveSeed improvement |
|---|---|
| Small free storage; paid for real capacity | Storage is the user's Google Drive (15 GB free, upgradeable via Google One) |
| Storage tied to one vendor's servers | Files live in a place the user already owns and controls |
| Basic player | Rich player: subtitles, resume, speed control, audio tracks, transcoding fallback |
| Must finish before reliable streaming | Optional "stream while downloading" with sequential piece mode |
| Limited organisation | Search, tags, bulk actions, auto-sort into Movies/TV/Music/Other |
| Little transparency on tasks | Live progress, peers, speed, ETA, per-file selection before download |
| Limited automation | RSS auto-download, API tokens, webhooks, Telegram bot (later phase) |

## 3. Goals and non-goals

### Goals
- G1: From pasting a magnet link to a file in Drive with no manual steps.
- G2: Smooth in-browser streaming of Drive-stored media, including seeking.
- G3: Self-hostable and cheap to run (single VPS to start).
- G4: A modern, polished, animation-rich UI that feels like a premium product, stays fast (60 fps) and works on mobile.
- G5 (Phase 2): A Google Colab + Drive edition that reuses the same UI/UX and shared code, within Colab's usage rules (see section 18).

### Non-goals (v1)
- Hosting or indexing any content, or running a torrent search engine.
- Public file sharing or a public link marketplace.
- Native mobile apps (responsive web only).
- Storage backends other than Google Drive (designed so they can be added later).

## 4. Target users
- **Primary:** individuals who want to download large legal files (Linux ISOs, open datasets, public-domain media, personal archives) without exposing their IP or using local disk.
- **Secondary:** developers and homelab users who want a self-hosted, scriptable version.

## 5. Functional requirements

Priority: **P0** = MVP, **P1** = v1.1, **P2** = later.

### 5.1 Authentication and accounts
- P0: Google sign-in (OAuth 2.0). One identity gives login and Drive authorisation.
- P0: Request the narrow `drive.file` scope so the app only touches files it creates; create a root folder "DriveSeed" on first login.
- P0: Revoke access / disconnect Drive and delete account data.
- P1: Optional email login plus separate Drive connect step.

### 5.2 Adding downloads
- P0: Add by magnet link, `.torrent` upload, or direct HTTP(S) URL.
- P0: After metadata is fetched, show the file list with sizes so the user picks which files to keep and the target folder.
- P0: Pre-flight check of Drive free space against selected size; clear warning if insufficient.
- P1: Bulk add (paste many links).
- P2: RSS feed auto-add with filters.

### 5.3 Download engine and task management
- P0: Task states: `queued → fetching metadata → downloading → uploading to Drive → completed | failed | paused`.
- P0: Pause, resume, cancel, retry; per-user concurrent task limit.
- P0: Live progress (percent, speed, peers, ETA) pushed over WebSocket/SSE.
- P0: Auto-cleanup of local temp files once upload to Drive is verified.
- P1: Seed-ratio/time limits, bandwidth caps per user.
- P1: Duplicate detection by info-hash.

### 5.4 Google Drive storage
- P0: Upload each finished file via the Drive **resumable upload** API in chunks, preserving folder structure.
- P0: Store Drive file IDs and metadata (name, size, MIME type, checksum) in the DB; Drive stays the source of truth for content.
- P0: Verify upload with size and MD5 from the Drive API before deleting local data.
- P1: Upload files as they complete instead of waiting for the whole torrent.
- P1: Trash/delete from the app removes from Drive (with confirmation).
- P2: Support Shared Drives.

### 5.5 Streaming
- P0: A backend streaming endpoint proxies Drive content with full **HTTP Range** support, so the browser `<video>`/`<audio>` element can seek.
- P0: Direct-play for browser-friendly formats (MP4/H.264/AAC, WebM, MP3, AAC, FLAC).
- P1: On-demand **FFmpeg transcoding to HLS** for MKV, HEVC, AC3/DTS and other unsupported formats.
- P1: Subtitle support (sidecar `.srt`/`.vtt` auto-detected, embedded tracks extracted); remember playback position per file.
- P1: Stream-while-downloading using libtorrent sequential mode for the file being watched.
- P2: Chromecast, audio-only mode, thumbnails/scrub preview.

### 5.6 File manager
- P0: Folder tree, list/grid toggle, rename, move, delete, download, multi-select.
- P0: Search by name; sort by name/size/date/type.
- P1: Tags, favourites, "continue watching" row, auto-sort rules.
- P1: Image and PDF preview; ZIP-on-the-fly for folder download.

### 5.7 Settings and API
- P1: Personal API tokens and a REST API (add task, list tasks, list files, stream URL).
- P1: Webhooks on task completion.
- P2: Telegram bot to add magnets and receive notifications.

## 6. UX and UI specification

**Design principles:** one primary action on the home screen, instant feedback, dark mode first, keyboard friendly.

### 6.1 Screens
1. **Landing/login:** one headline, one "Continue with Google" button, short explanation of how Drive is used and what access is requested.
2. **Dashboard (home):**
   - Top: large "Paste magnet link or drop .torrent" input.
   - Middle: active tasks cards (name, progress bar, speed, peers, ETA, pause/cancel).
   - Bottom: "Continue watching" and recently completed.
   - Header: Drive storage meter (used / total) with a warning colour near full.
3. **File selection modal:** tree with checkboxes, total size, Drive free space check, destination folder picker, "Start" button.
4. **Library:** file manager (see 5.6) with breadcrumb, search bar, and bulk toolbar.
5. **Player:** full-width player, subtitle/audio/quality menu, resume prompt, next-episode button for folders.
6. **Settings:** Drive connection, limits, API tokens, theme, delete account.

### 6.2 UI stack (updated for a rich, animated UI)
The backend stays 100% Python. The rich animation requirements push the frontend to a component-based SPA, which replaces the earlier HTMX plan.

| Layer | Choice | Why |
|---|---|---|
| Framework | **React + Vite + TypeScript** | Mature animation ecosystem; builds to a static bundle |
| Styling | **Tailwind CSS** + CSS variables as design tokens | Fast theming (dark/light/accent) |
| Components | **shadcn/ui (Radix primitives)** | Accessible dialogs, menus, tabs, command palette |
| Animation | **Framer Motion** (springs, layout animations, `AnimatePresence`), **Lottie** for illustrations, CSS/View Transitions for simple cases | Smooth shared-element and list animations |
| Data | **TanStack Query** + SSE/WebSocket subscription, **Zustand** for UI state | Live task updates, optimistic UI |
| Player | **Vidstack** or **Video.js** + **hls.js**, custom skin | Themeable, HLS support, subtitle and track menus |
| Icons/fonts | Lucide icons; Inter (UI) and JetBrains Mono (numbers) | Clean and consistent |
| Delivery | `vite build` output served as static files by FastAPI | Node is needed only at build time; one Python process serves everything |

The same built bundle is reused unchanged in the Colab Edition (section 18).

### 6.3 UX requirements
- Responsive down to 360 px width.
- First meaningful paint under 2 s on a typical connection; initial JS under 250 KB gzipped, with the player and Lottie files lazy-loaded.
- All animations run at 60 fps by animating only `transform` and `opacity`, and honour `prefers-reduced-motion` (fall back to simple fades).
- Empty, loading, error and "Drive full" states designed for every screen.
- Accessible: keyboard controls for the player, labelled controls, sufficient contrast.

### 6.4 Visual design language and motion

**Look and feel**
- Dark-first theme with a polished light theme; user-selectable accent colour.
- Violet-to-cyan gradient accent, used for progress, focus rings and primary buttons.
- Frosted-glass surfaces (translucent cards with backdrop blur) used sparingly for the header, modals and player controls.
- 12–16 px corner radius, soft layered shadows and subtle glow on active elements; 4 px spacing grid.
- Tabular, monospaced numerals for speeds, sizes and ETAs so values do not jitter.
- A design-token file and a Storybook of all components, so the Colab Edition and main app stay visually identical.

**Motion principles**
- Purposeful: every animation explains a state change (added, progressing, finished, moved).
- Timing: micro-interactions 120–200 ms, element transitions 250–400 ms, page transitions up to 450 ms; spring physics for natural feel.
- Never block input; animations are interruptible.

**Signature animations**
| Moment | Animation |
|---|---|
| Paste magnet link | Input glows, the link "morphs" into a new task card that slides into the list |
| Fetching metadata | Skeleton shimmer, then file tree expands with staggered row reveals |
| Downloading | Gradient progress bar with moving sheen, animated number ticker for speed and ETA, live speed sparkline |
| Uploading to Drive | Small "cloud → Drive" flow animation along a path while the upload progress runs |
| Task complete | Checkmark draws itself, soft confetti burst, card settles into the library |
| Library | Shared-layout animation between list and grid views; staggered entrance; hover lift with soft shadow |
| Open file | Poster/thumbnail expands into the player (shared-element transition) |
| Player | Controls fade in/out, scrub-bar thumbnail preview, double-tap/double-click skip ripple, ambient backdrop tinted from the poster's dominant colour |
| Storage meter | Animated radial ring that shifts colour as Drive fills |
| Toasts and undo | Slide-in/out with a countdown ring on "Undo" |
| Empty and error states | Lottie illustrations with a gentle idle loop |

### 6.5 Rich UX features
- P0: skeleton loading everywhere, optimistic updates, undo for delete/move, drag-and-drop for both adding torrents and moving files.
- P1: **command palette** (Ctrl/Cmd+K), full keyboard shortcuts, right-click context menus, marquee multi-select.
- P1: installable **PWA**, browser notifications when a task finishes, theme and accent picker.
- P2: onboarding tour with animated hints, poster and metadata enrichment for media, picture-in-picture and mini-player that persists across pages.

## 7. System architecture

```
Browser (HTMX/Alpine, Video.js/hls.js)
        │  HTTPS, WebSocket/SSE
        ▼
 FastAPI app (auth, REST API, streaming proxy)
        │                    │
        │ enqueue jobs       │ Range requests
        ▼                    ▼
 Redis (queue, pub/sub)   Google Drive API v3
        │                    ▲
        ▼                    │ resumable upload
 Worker(s): libtorrent engine + uploader + FFmpeg
        │
        ▼
 Ephemeral local disk (temp download area)

 PostgreSQL: users, tasks, files, tokens, playback state
```

### 7.1 Components
| Component | Technology | Notes |
|---|---|---|
| Web/API | FastAPI + Uvicorn | async, OpenAPI docs for free |
| Torrent engine | `python-libtorrent` (libtorrent-rasterbar) | sessions, sequential download, piece priorities |
| Job queue | Celery or arq with Redis | arq is lighter and async-native |
| Database | PostgreSQL + SQLAlchemy + Alembic | SQLite acceptable for single-user self-host |
| Cache/pubsub | Redis | task progress fan-out to WebSocket/SSE |
| Drive client | `google-api-python-client` + `google-auth-oauthlib` | resumable uploads, Range reads |
| Transcoding | FFmpeg subprocess | HLS segments cached short-term |
| Reverse proxy | Caddy or Nginx | TLS, buffering off for streams |
| Packaging | Docker Compose | one command local/VPS deploy |

### 7.2 Key flows

**Add and store**
1. User submits magnet → API creates `task`, enqueues job.
2. Worker fetches metadata, returns file list → user selects files.
3. libtorrent downloads to the temp directory.
4. Per completed file, the uploader streams it to Drive in chunks (resumable), verifies size/MD5, records the Drive file ID.
5. Local temp file is deleted; task marked completed; UI updated live.

**Stream**
1. Player requests `/stream/{file_id}` with a `Range` header.
2. API checks the user's session, loads the user's Drive credentials (refreshing the token if needed).
3. API calls Drive `files.get?alt=media` with the same Range and pipes bytes back with `206 Partial Content`.
4. If the codec is unsupported, API returns an HLS playlist; a worker transcodes from the Drive stream on demand.

### 7.3 Why a proxy, not direct Drive links
Drive links need the user's OAuth token and are not reliably embeddable in `<video>`. The proxy keeps tokens server-side, supports Range, and allows transcoding and access control. Cost: bandwidth passes through the server, so the VPS needs adequate egress.

## 8. Data model (core tables)

- `users`: id, google_sub, email, drive_refresh_token (encrypted), drive_root_folder_id, created_at
- `tasks`: id, user_id, source_type, source_uri, info_hash, name, state, progress, size_bytes, error, created_at, completed_at
- `task_files`: id, task_id, path, size_bytes, selected, state, drive_file_id
- `files`: id, user_id, drive_file_id, name, parent_folder_id, mime_type, size_bytes, md5, created_at
- `playback`: user_id, file_id, position_seconds, updated_at
- `api_tokens`: id, user_id, token_hash, label, last_used_at
- `audit_log`: user_id, action, target, created_at

## 9. API surface (v1 sketch)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/tasks` | add magnet / URL / .torrent |
| GET | `/api/tasks` | list tasks with live state |
| POST | `/api/tasks/{id}/start` | begin with selected files |
| POST | `/api/tasks/{id}/pause` `/resume` `/cancel` | control |
| GET | `/api/files?folder=` | list library |
| PATCH/DELETE | `/api/files/{id}` | rename, move, delete |
| GET | `/stream/{file_id}` | Range-capable stream |
| GET | `/hls/{file_id}/index.m3u8` | transcoded stream |
| GET | `/api/storage` | Drive quota used/total |
| GET | `/events` | SSE/WebSocket progress feed |

## 10. Google Drive integration details

- **Auth:** OAuth 2.0 authorisation-code flow with offline access to obtain a refresh token; store it encrypted (e.g. Fernet with a key from the environment/secret manager).
- **Scope:** prefer `https://www.googleapis.com/auth/drive.file`. The full `drive` scope is a restricted scope and triggers extra Google verification, so avoid it unless a feature truly needs it.
- **Service accounts are not suitable** as the storage layer: they have no personal storage quota. Use each user's own Drive via OAuth.
- **Uploads:** resumable protocol, chunk size a multiple of 256 KB (e.g. 8–32 MB), retry with exponential backoff on 5xx and rate-limit errors.
- **Limits to design around:** Drive API request quotas, a daily per-account upload cap, per-file size limit, and the user's own free space. Surface these as clear in-app messages.
- **Streaming reads:** pass through Range, handle token refresh mid-stream, and set `Accept-Ranges: bytes`, `Content-Range`, and correct `Content-Type`.
- **Consent screen:** if the app is public, Google OAuth verification is required. For personal or small-circle use, "Testing" mode with listed test users works.

## 11. Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | Stream start under 3 s from click; seek under 2 s; API p95 under 300 ms (non-stream) |
| Capacity (MVP) | 20 concurrent active tasks and 20 concurrent streams on a 4 vCPU / 8 GB VPS |
| Reliability | Resumable uploads; tasks survive worker restarts; no orphaned temp files after 24 h |
| Security | HTTPS only, encrypted tokens, CSRF protection, rate limiting, per-user isolation, SSRF filtering on URL downloads (block private IP ranges) |
| Privacy | No content logging beyond task metadata; one-click account and data deletion |
| Observability | Structured logs, Prometheus metrics, health endpoint, Sentry for errors |
| Compatibility | Latest Chrome, Edge, Firefox, Safari; Android and iOS browsers |

## 12. Legal, compliance and safety

- Torrenting technology is lawful, but much content shared that way is copyrighted. The product must be positioned for lawful use and carry clear Terms of Service and an acceptable-use policy.
- Provide a **DMCA/abuse contact and takedown process**, and a way to disable accounts that abuse the service. Consider ISP and hosting-provider policies when picking where to host; many providers prohibit torrent traffic.
- The service stores nothing itself: content goes to the user's own Drive, which is also subject to Google's terms and automated abuse scanning. Say this plainly in onboarding.
- Do not ship a built-in search engine or tracker index of copyrighted material.
- Local laws vary; if you plan to offer this publicly, get legal advice for your jurisdiction.

## 13. Milestones

| Phase | Scope | Rough effort |
|---|---|---|
| **M0 Setup** | Repo, Docker Compose, FastAPI skeleton, Postgres, CI | 1 week |
| **M1 Core pipeline** | Google OAuth, add magnet, libtorrent download, Drive upload, task list with live progress | 3 weeks |
| **M2 Library and streaming** | File manager, Range streaming proxy, basic player, resume position | 2–3 weeks |
| **M3 Polish** | File selection modal, search, error states, storage meter, rate limits, deploy to VPS | 2 weeks |
| **M3b Design system and motion** | Tokens, Storybook, signature animations (6.4), command palette, PWA, performance pass | 2–3 weeks |
| **M4 Advanced streaming** | HLS transcoding, subtitles, stream-while-downloading | 3 weeks |
| **M5 Automation** | API tokens, webhooks, RSS, Telegram bot | 2–3 weeks |
| **M6 Colab Edition (Phase 2)** | Compliant Colab profile of the same app (section 18) | 2–3 weeks |

MVP (M0–M3) is roughly 8–9 weeks of part-time solo work; adding the motion and design-system work (M3b) brings the polished v1 to roughly 11–12 weeks, assuming no major Drive quota surprises.

**Important:** the abstraction layers listed in section 18.3 should be built from M0. Retrofitting them at M6 would cost far more than doing them up front.

## 14. Success metrics

- Time from pasting a magnet to first byte in Drive (median).
- Percentage of tasks completing without manual retry (target 95%+).
- Stream start time and rebuffer ratio.
- Activation: share of new users who complete one download and one playback in their first session.
- 7-day and 30-day retention.

## 15. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Drive API quotas or upload caps hit | Failed or delayed uploads | Backoff and queueing, clear user messaging, per-user throttles |
| Hosting provider bans torrent traffic | Service shut down | Choose a torrent-tolerant provider; keep deploy portable via Docker |
| Streaming bandwidth cost through the proxy | Runaway egress bills | Per-user bandwidth caps, direct-play where possible, cache HLS briefly |
| Local disk fills during big downloads | Stalled tasks | Pre-flight size checks, per-user temp quotas, upload-as-you-go |
| Abuse or copyright complaints | Legal exposure | ToS, takedown process, rate limits, account suspension tools |
| Google OAuth verification friction | Blocks public launch | Start with test-user mode, use narrow scope |
| Transcoding CPU load | Slow streams | Limit concurrent transcodes, direct-play first, optional GPU later |
| Heavy animations hurt low-end devices | Janky UI | Animate only transform/opacity, performance budget, reduced-motion mode, test on a mid-range Android phone |
| Colab rules prohibit torrenting and media serving | Runtime terminated or account restricted | Colab Edition ships with the torrent engine disabled and no media proxying (section 18.2) |
| Colab runtimes are ephemeral (12 h max, idle timeouts) | Interrupted tasks | Resumable HTTP downloads and state stored on Drive (section 18.4) |

## 16. Open questions

1. Single-user self-hosted tool, or multi-user hosted service? (changes auth, quotas, and legal posture)
2. Is "stream while downloading" required at launch, or can it wait for M4?
3. Hosting target: home server, VPS, or cloud (and what egress budget)?
4. Free tier limits (tasks, bandwidth) if this becomes a hosted product?
5. Should other storage backends (S3, OneDrive) be planned for the data model now?
6. Colab Edition: is a compliant, reduced version (URL downloads, Drive-native playback) acceptable, or is the full torrent-and-stream experience required? If the latter, the answer is a self-hosted deployment instead of Colab (see 18.2 and 18.7).
7. Colab Edition: will you use a paid Colab plan with a positive compute-unit balance? That changes which UI options are allowed (18.2).

## 18. Phase 2: Colab Edition (Google Colab + Drive only)

### 18.1 Intent
After the main product is complete, port it to run entirely from a Google Colab notebook with Google Drive as the only storage, **reusing the same frontend bundle so the UI/UX is identical** and the backend code shared.

### 18.2 Compliance review (this changes the scope)
Google's Colab FAQ ("Which activities are restricted in Colab?", checked 7 Oct 2026) lists the following as disallowed on **all** managed runtimes:
- downloading torrents or engaging in peer-to-peer file-sharing;
- file hosting, media serving, or other web service offerings not related to interactive compute with Colab.

It also lists, for free-tier runtimes (no positive compute-unit balance), that these may be terminated without warning:
- bypassing the notebook UI to interact primarily via a web UI.

Other facts from the same FAQ that shape the design: free runtimes last at most about 12 hours and are deleted when idle; limits are unpublished and fluctuate; Drive mounting can return I/O errors when quotas or folder-size limits are hit; interrupted moves on a mounted Drive can lose data in transit.

**What this means for the original request:**

| Requested capability | Colab verdict | Decision in this PRD |
|---|---|---|
| Torrent downloading | Disallowed on all tiers | **Not included** in the Colab Edition (engine disabled by profile) |
| Streaming media from the runtime | Falls under "media serving" | **Not included**; playback hands off to Drive's own viewer instead |
| Same web UI served from the runtime | Restricted on free tier; gray area on paid | **Option B** below, user decides |
| Direct HTTP(S) URL downloads into Drive | Allowed interactive compute use | **Included** |

This PRD does not include keep-alive tricks, disguised tunnels, or other ways to avoid Colab's abuse detection. They would put the user's Google account at risk and are outside what the product should do.

**UI delivery options for the Colab Edition**
- **Option A (lowest risk):** a notebook-native interface built with `ipywidgets` that mirrors the layout and flows (add URL, task list, library, storage meter). Fully inside the notebook UI, but it cannot reproduce the full animation-rich design.
- **Option B (identical UI/UX):** run the shared FastAPI app in the notebook and show the same React bundle in a notebook output frame. Gives the original look and animations, but it is a web UI served from the runtime. Use only on a paid plan with a positive compute-unit balance, with the notebook open and being actively used, and re-read Colab's terms first.
- **Recommended:** build the shared core so both are possible; ship Option B behind a clearly labelled setting and Option A as the safe default.

### 18.3 Architecture: interfaces that make the port a configuration change
Build these abstractions from M0 and choose implementations with a `PROFILE` setting (`server` or `colab`).

| Interface | `server` profile | `colab` profile |
|---|---|---|
| `StorageBackend` | Google Drive API (OAuth, resumable upload) | Mounted Drive path (`/content/drive/MyDrive/DriveSeed`); write to a temp name, then rename after checksum check |
| `DownloadEngine` | HTTP + libtorrent | HTTP only (torrent engine disabled) |
| `TaskQueue` | Redis + arq/Celery | In-process `asyncio` queue |
| `Database` | PostgreSQL | SQLite file kept on Drive so state survives runtime resets |
| `Auth` | Google OAuth, multi-user | Single-user session token shown in the notebook output |
| `Streamer` | Range-capable proxy, optional HLS | Hand-off to Drive's native preview/download (no media proxying) |
| `Frontend` | React bundle served by FastAPI | **Same bundle** (Option B) or ipywidgets view (Option A) |

### 18.4 Colab runtime design
- **Notebook cells:** (1) mount Drive and set paths, (2) `pip install` dependencies, (3) start the app with a single "Run" cell, (4) display the UI and show status and logs.
- **Local scratch first:** download to the VM's local disk, then copy completed files to Drive in large sequential writes (avoids many small Drive I/O calls); verify size/checksum, then delete scratch files.
- **Resumability:** all task state is persisted in the SQLite file on Drive; on restart the app reconciles unfinished tasks and resumes HTTP downloads with `Range` where the server supports it. A banner explains when a runtime was recycled.
- **Drive limits:** keep folders under ~10,000 items (auto-shard into subfolders), back off and show a clear message on `Input/output error` or quota notifications.
- **Session awareness:** show remaining-time guidance and warn before large jobs that may not finish within a session. No artificial activity to keep the session alive.
- **Packaging:** one notebook file plus a pinned `requirements-colab.txt`; the frontend bundle is downloaded from a release asset at startup.

### 18.5 Feature parity matrix
| Feature | Main app | Colab Edition |
|---|---|---|
| Add direct URL download | Yes | Yes |
| Add magnet / .torrent | Yes | No (disabled) |
| Google Drive as storage | API, any user | Mounted Drive of the signed-in notebook user |
| Library (browse, rename, move, delete, search) | Yes | Yes |
| In-browser streaming through the app | Yes (Range proxy, HLS) | No; opens in Drive's own player/preview |
| Subtitles, resume position, HLS | Yes | Only in Drive's viewer where supported |
| Multi-user accounts | Yes | No (single user) |
| API tokens, webhooks, Telegram bot | Yes | Not applicable |
| Animated UI (6.4) | Yes | Yes with Option B; reduced with Option A |

### 18.6 Acceptance criteria
- Cold start: from opening the notebook to a working UI in under 3 minutes.
- A 5 GB direct-URL download lands on Drive with a verified checksum, and resumes after a simulated runtime restart.
- No code path in the `colab` profile can start a torrent session (covered by an automated test).
- Library, task list and storage meter look and behave identically to the main app when using Option B.
- Clear in-app messages for Drive quota errors and approaching session limits.

### 18.7 Alternative for the full experience
If torrenting plus in-app streaming is the real goal, run the **same shared stack** where those uses are permitted: your own machine, a home server, or a VPS from a provider that allows torrent traffic, deployed with the Docker Compose setup from M0. That keeps the full UI/UX and Drive storage, without Colab's restrictions.

## 19. Suggested repository layout

```
driveseed/
├── app/
│   ├── main.py            # FastAPI entry
│   ├── api/               # routers: tasks, files, stream, auth
│   ├── core/              # config, security, db
│   ├── services/
│   │   ├── torrent.py     # libtorrent wrapper
│   │   ├── drive.py       # Drive upload/read, token refresh
│   │   └── transcode.py   # FFmpeg/HLS
│   ├── workers/           # arq/Celery tasks
│   ├── templates/         # Jinja2 + HTMX
│   └── static/
├── migrations/            # Alembic
├── docker-compose.yml
├── Dockerfile
└── tests/
```
