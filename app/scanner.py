"""Drive ingestion.

Two decoupled background tasks (both started from the FastAPI lifespan and held
by reference so they are never garbage-collected):

* ``scan_loop``        — periodically lists Drive and inserts rows for new mp4s.
* ``download_worker``   — drains any row still in ``pending``/``downloading`` and
                          downloads it. Because it works off DB state (not a
                          fire-and-forget hand-off), interrupted downloads — e.g.
                          an app restart mid-download — are retried automatically.
"""

import asyncio
import logging
import os
from datetime import datetime

from sqlalchemy import select

from . import media, rclone
from .config import settings
from .db import SessionLocal
from .models import ERROR, PENDING, BoardColumn, Video
from .ordering import next_video_position
from .repository import VideoRepository

logger = logging.getLogger("video_manager.scanner")

VIDEO_EXTS = (".mp4",)
IDLE_RECHECK_SECONDS = 30


def is_video(name: str) -> bool:
    return name.lower().endswith(VIDEO_EXTS)


def filter_videos(entries: list[dict]) -> list[dict]:
    """Keep only non-directory video files from an rclone lsjson listing."""
    return [e for e in entries if not e.get("IsDir") and is_video(e.get("Name", ""))]


def entry_file_id(entry: dict) -> str:
    """Stable identifier for a Drive entry (falls back to path/name)."""
    return entry.get("ID") or entry.get("Path") or entry.get("Name", "")


def _parse_modtime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class ScanCoordinator:
    """Encapsulates all Drive scanning state. One instance per app; one per test."""

    def __init__(self, adapter: rclone.DriveAdapter, repo: VideoRepository):
        self._lock = asyncio.Lock()
        self._ready = asyncio.Event()
        self._adapter = adapter
        self._repo = repo

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #
    async def discover(self) -> list[int]:
        """List Drive and insert rows for any new mp4s. Returns new video ids."""
        if not settings.rclone_remote:
            logger.warning("RCLONE_REMOTE is not set; skipping scan")
            return []
        if self._lock.locked():
            return []
        async with self._lock:
            new_ids = await self._run_discover()
        if new_ids:
            self._ready.set()
        return new_ids

    async def _run_discover(self) -> list[int]:
        source = settings.drive_source
        try:
            entries = await self._adapter.list_files(source)
        except rclone.RcloneError as exc:
            logger.error("rclone list failed: %s", exc)
            return []

        videos = filter_videos(entries)
        new_ids: list[int] = []

        async with SessionLocal() as session:
            first_col = (
                await session.execute(
                    select(BoardColumn).order_by(BoardColumn.position, BoardColumn.id)
                )
            ).scalars().first()
            if first_col is None:
                logger.warning("No board columns exist yet; skipping scan")
                return []

            existing = set(
                (await session.execute(select(Video.drive_file_id))).scalars().all()
            )
            next_pos = await next_video_position(session, first_col.id)

            for entry in videos:
                fid = entry_file_id(entry)
                if not fid or fid in existing:
                    continue
                video = Video(
                    drive_file_id=fid,
                    name=entry.get("Name", fid),
                    drive_path=entry.get("Path"),
                    size_bytes=entry.get("Size"),
                    drive_modified_at=_parse_modtime(entry.get("ModTime")),
                    column_id=first_col.id,
                    position=next_pos,
                    download_status=PENDING,
                )
                session.add(video)
                await session.flush()
                new_ids.append(video.id)
                existing.add(fid)
                next_pos += 1

            await session.commit()

        return new_ids

    # ------------------------------------------------------------------ #
    # Downloading
    # ------------------------------------------------------------------ #
    async def _download_video(self, video_id: int) -> None:
        result = await self._repo.get_for_download(video_id)
        if result is None:
            return
        name, rel_path = result

        os.makedirs(settings.media_dir, exist_ok=True)
        ext = os.path.splitext(name)[1] or ".mp4"
        dest = os.path.join(settings.media_dir, f"{video_id}{ext}")
        source_file = f"{settings.drive_source}/{rel_path}"

        try:
            await self._adapter.download(source_file, dest)
        except rclone.RcloneError as exc:
            logger.error("Download failed for %s: %s", name, exc)
            await self._repo.set_status(video_id, ERROR, str(exc))
            return

        duration = await media.probe_duration(dest)
        thumb_path = os.path.join(settings.media_dir, f"{video_id}.jpg")
        thumb_ok = await media.make_thumbnail(dest, thumb_path)

        await self._repo.mark_downloaded(
            video_id, dest, duration, thumb_path if thumb_ok else None,
        )
        logger.info("Downloaded %s -> %s", name, dest)

    # ------------------------------------------------------------------ #
    # Background tasks
    # ------------------------------------------------------------------ #
    async def download_worker(self) -> None:
        """Drain pending downloads, retrying interrupted ones across restarts."""
        logger.info("download worker started")
        count = await self._repo.reset_interrupted_downloads()
        if count:
            logger.info("Reset %s interrupted download(s) to pending", count)
        while True:
            # Clear before checking so a discovery that fires the event after our
            # query (but before we wait) is never missed.
            self._ready.clear()
            video_id = None
            try:
                video_id = await self._repo.next_pending_id()
                if video_id is None:
                    try:
                        await asyncio.wait_for(
                            self._ready.wait(), timeout=IDLE_RECHECK_SECONDS
                        )
                    except asyncio.TimeoutError:
                        pass
                    continue
                await self._download_video(video_id)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("download worker error")
                try:
                    if video_id is not None:
                        await self._repo.set_status(
                            video_id, ERROR, "unexpected error during download"
                        )
                except Exception:  # noqa: BLE001
                    logger.exception("failed to mark video errored")

    async def scan_loop(self) -> None:
        """Periodically discover new Drive files (downloads run in the worker)."""
        logger.info(
            "scanner started; interval=%ss source=%s",
            settings.scan_interval_seconds,
            settings.drive_source,
        )
        while True:
            try:
                new_ids = await self.discover()
                if new_ids:
                    logger.info("scan complete: %s new video(s)", len(new_ids))
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("scan loop error")
            await asyncio.sleep(settings.scan_interval_seconds)

    def background_tasks(self) -> list:
        """Return coroutines for both background tasks."""
        return [self.download_worker(), self.scan_loop()]


# --------------------------------------------------------------------------- #
# Module-level defaults — app uses these; tests instantiate ScanCoordinator
# directly with fake adapters instead of monkeypatching these globals.
# --------------------------------------------------------------------------- #
coordinator = ScanCoordinator(rclone.RcloneAdapter(), VideoRepository())


def get_coordinator() -> ScanCoordinator:
    """FastAPI dependency returning the active ScanCoordinator."""
    return coordinator


def background_tasks() -> list:
    return coordinator.background_tasks()
