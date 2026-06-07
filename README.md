# Video Manager

A local-first **kanban board** for tracking videos you're working on. New `.mp4` files dropped into
a **Google Drive** folder are auto-discovered, downloaded locally, and added as cards. Move cards
between status columns and keep a **notes log** on each video to track progress and ideas. All state
lives in **Postgres**; everything runs via **Docker Compose**.

- **Discovery + download** from Google Drive via `rclone` (no Google Cloud project needed)
- **Drag-and-drop kanban** — default columns: Backlog → Editing → Review → Published (editable in-app)
- **Per-video notes log** with add / edit / delete
- **In-app preview** of downloaded videos (with seeking)
- Single Python service (FastAPI + HTMX) + Postgres

## Requirements

- Docker + Docker Compose
- [rclone](https://rclone.org/downloads/) installed on your machine (only for the one-time config)

## Setup

### 1. Authorize Google Drive with rclone

```bash
rclone config
```

- `n` for a new remote, name it **`gdrive`**
- storage type: **Google Drive** (`drive`)
- accept the defaults; leave client_id/secret blank to use rclone's built-in client
- scope: `drive` (or `drive.readonly` if you only want read access)
- complete the browser auth flow; say **no** to "edit advanced config" and **yes** to "use auto config"

Verify it works:

```bash
rclone lsd gdrive:
```

### 2. Configure the app

```bash
cp .env.example .env
```

Edit `.env`:

- `RCLONE_REMOTE=gdrive` — the remote name from step 1
- `RCLONE_DRIVE_PATH=Videos/ToEdit` — the folder to watch (blank = Drive root)
- `RCLONE_CONFIG_DIR=/Users/you/.config/rclone` — **absolute** path to the dir holding
  `rclone.conf` (find it with `rclone config file`). No `~` shortcuts.
- `SCAN_INTERVAL_SECONDS=300` — how often to poll Drive

### 3. Run

```bash
docker compose up --build
```

Open **http://localhost:8000**. The app applies migrations, seeds the default columns, and starts
the background scanner automatically.

## Usage

- **Scan now** — discover new Drive files immediately (downloads run in the background; cards show
  `pending → downloading → downloaded` and self-update).
- **Drag a card** between/within columns to change its status; the position persists.
- **Click a card** to open it: watch the video, and add/edit/delete notes.
- **+ Column** to add a status; the `×` on a column deletes it (only when empty).

## How it works

- A background task polls `rclone lsjson <remote>:<folder>` for `.mp4` files. New ones (deduped by
  Drive file ID) are inserted into Postgres and downloaded with `rclone copyto` into the `media`
  volume. `ffprobe`/`ffmpeg` add duration + a thumbnail (best-effort).
- The web layer is server-rendered FastAPI + Jinja with HTMX for partial updates and SortableJS for
  drag-and-drop. Video is served via `FileResponse` with HTTP Range support so you can seek.

## Data & persistence

- Postgres data → `pgdata` volume; downloaded videos → `media` volume.
- Reset everything (including the DB and downloaded files): `docker compose down -v`.

## Security note

This tool has **no authentication** and binds to `127.0.0.1` only. Do not expose it to a public
network without adding auth in front of it.

## Development

Run the tests (no Docker needed; uses an in-memory SQLite DB):

```bash
uv sync
uv run pytest
```
