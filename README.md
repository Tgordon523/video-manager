# Video Manager

A local-first **kanban board** for tracking videos you're working on. New `.mp4` files dropped into
a **Google Drive** folder are auto-discovered, downloaded locally, and added as cards. Move cards
between status columns and keep a **notes log** on each video to track progress and ideas. All state
lives in **Postgres**; everything runs via **Docker Compose**.

- **Discovery + download** from Google Drive via `rclone` (no Google Cloud project needed)
- **Drag-and-drop kanban** — default columns: Backlog → Editing → Review → Published (editable in-app)
- **Per-video notes log** with add / edit / delete
- **In-app video preview** with seeking (HTTP Range support)
- Single Python service (FastAPI + HTMX) + Postgres

## Requirements

- Docker + Docker Compose (tested with OrbStack on macOS)
- [rclone](https://rclone.org/downloads/) installed on your machine (one-time config only)

## Setup

### 1. Authorise Google Drive with rclone

```bash
rclone config
```

- `n` for a new remote — choose any name (e.g. **`drive`**)
- Storage type: **Google Drive** (`drive`)
- Leave `client_id`/`client_secret` blank to use rclone's built-in credentials
- Scope: `drive` (full) or `drive.readonly` if you only need read access
- Complete the browser auth flow; say **no** to "edit advanced config"

Verify it works:

```bash
rclone lsd drive:
```

### 2. Configure the app

```bash
cp .env.example .env
```

Edit `.env` — the key fields:

| Variable | Example | Notes |
|---|---|---|
| `RCLONE_REMOTE` | `drive` | The remote name you chose in step 1 |
| `RCLONE_DRIVE_PATH` | `Videos/ToEdit` | Folder inside the remote to watch (blank = root) |
| `RCLONE_CONFIG_DIR` | `/Users/you/.config/rclone` | **Absolute** path to the dir holding `rclone.conf` — find it with `rclone config file`. No `~` shortcuts. |
| `SCAN_INTERVAL_SECONDS` | `300` | How often (seconds) to poll Drive |

### 3. Run

```bash
docker compose up --build
```

Open **http://localhost:8000** in your browser.

> **OrbStack users:** OrbStack displays the bind address as `http://0.0.0.0:8000` in its UI — that
> is not browseable. The correct URL is always **http://localhost:8000**.

The app applies DB migrations, seeds the default columns, and starts the background scanner
automatically on first boot.

## Usage

| Action | How |
|---|---|
| Discover new Drive files immediately | Click **Scan now** — downloads run in the background; cards self-update `pending → downloading → downloaded` |
| Reorder or move a card | Drag it within or between columns |
| View / note a video | Click a card to open the detail page: watch, seek, add/edit/delete notes |
| Add a column | Click **+ Column** at the right edge |
| Delete a column | Click the `×` on its header (only allowed when the column is empty) |

## How it works

```
Google Drive
    │  rclone lsjson (every SCAN_INTERVAL_SECONDS)
    ▼
ScanCoordinator.discover()   ← inserts new Video rows (status: pending)
    │
    ▼
ScanCoordinator.download_worker()   ← drains pending rows one at a time
    │  rclone copyto → /data/videos/<id>.mp4
    │  ffprobe → duration   ffmpeg → thumbnail.jpg
    ▼
Video row (status: downloaded) → served via FileResponse with Range support
```

Because the worker reads from DB state rather than an in-memory queue, interrupted downloads
(e.g. app restart mid-download) are retried automatically on the next boot.

## Module layout

| Module | Responsibility |
|---|---|
| `app/scanner.py` | `ScanCoordinator` — Drive polling loop, download worker, injectable adapter + repo |
| `app/repository.py` | `VideoRepository` — all scanner-side DB reads/writes |
| `app/rclone.py` | `DriveAdapter` protocol + `RcloneAdapter` wrapping the rclone CLI |
| `app/ordering.py` | Position arithmetic for columns and video cards |
| `app/deps.py` | `get_or_404` — generic fetch-or-404 used by all route handlers |
| `app/routes/` | Route handlers split by resource: `board`, `videos`, `columns`, `notes` |
| `app/web.py` | Jinja2 env, template filters (`duration`, `filesize`), `load_board` |

## Data & persistence

- Postgres data lives in the `pgdata` Docker volume; downloaded videos in `media`.
- **Reset everything** (DB + downloaded files): `docker compose down -v`

## Security note

This tool has **no authentication** and binds to `127.0.0.1:8000` only. Do not expose it to a
public network without adding auth in front of it.

## Development

Run the tests (no Docker needed — uses a temporary SQLite DB):

```bash
uv sync
uv run pytest
```

`VideoRepository` and `DriveAdapter` are injectable, so scanner tests use a `FakeAdapter` and a
fresh `ScanCoordinator` per test — no real Drive credentials or monkeypatching needed.
