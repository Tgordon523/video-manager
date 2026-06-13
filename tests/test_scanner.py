import asyncio
import contextlib

from sqlalchemy import func, select

from app import scanner
from app.models import BoardColumn, Video
from app.repository import VideoRepository
from app.scanner import ScanCoordinator


# --------------------------------------------------------------------------- #
# Pure-function tests — no DB, no coordinator needed
# --------------------------------------------------------------------------- #

def test_filter_videos_keeps_only_mp4_files():
    entries = [
        {"Name": "a.mp4", "IsDir": False},
        {"Name": "b.MP4", "IsDir": False},
        {"Name": "c.txt", "IsDir": False},
        {"Name": "subdir", "IsDir": True},
    ]
    names = {e["Name"] for e in scanner.filter_videos(entries)}
    assert names == {"a.mp4", "b.MP4"}


def test_entry_file_id_prefers_drive_id():
    assert scanner.entry_file_id({"ID": "abc", "Name": "x.mp4"}) == "abc"
    assert scanner.entry_file_id({"Name": "x.mp4"}) == "x.mp4"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

class FakeAdapter:
    """Fake DriveAdapter — no rclone, no network."""

    def __init__(self, listing=None):
        self.listing = listing or []
        self.downloads: list[tuple[str, str]] = []

    async def list_files(self, source: str) -> list[dict]:
        return self.listing

    async def download(self, source_file: str, dest: str) -> None:
        self.downloads.append((source_file, dest))


# --------------------------------------------------------------------------- #
# Coordinator-based tests — each test gets its own isolated ScanCoordinator
# --------------------------------------------------------------------------- #

async def test_discover_inserts_and_dedups(db, monkeypatch):
    monkeypatch.setattr(scanner.settings, "rclone_remote", "gdrive")
    listing = [
        {"ID": "1", "Name": "intro.mp4", "Size": 100, "IsDir": False,
         "ModTime": "2024-01-01T00:00:00Z"},
        {"ID": "2", "Name": "b-roll.mp4", "Size": 200, "IsDir": False},
        {"ID": "3", "Name": "notes.txt", "Size": 5, "IsDir": False},
    ]

    sc = ScanCoordinator(FakeAdapter(listing), VideoRepository())

    new_ids = await sc.discover()
    assert len(new_ids) == 2  # the .txt is ignored

    # Re-running discovers nothing new (deduped by Drive file ID).
    assert await sc.discover() == []

    async with db() as session:
        count = (await session.execute(select(func.count(Video.id)))).scalar()
        assert count == 2
        statuses = (
            await session.execute(select(Video.download_status))
        ).scalars().all()
        assert all(status == "pending" for status in statuses)


async def test_worker_drains_pending_and_recovers_interrupted(db, monkeypatch):
    async with db() as session:
        col = (
            await session.execute(select(BoardColumn).order_by(BoardColumn.position))
        ).scalars().first()
        session.add_all([
            Video(drive_file_id="p", name="p.mp4", column_id=col.id, position=1,
                  download_status="pending"),
            # A row stuck in 'downloading' simulates an interrupted previous run.
            Video(drive_file_id="d", name="d.mp4", column_id=col.id, position=2,
                  download_status="downloading"),
        ])
        await session.commit()

    sc = ScanCoordinator(FakeAdapter(), VideoRepository())
    downloaded: list[int] = []

    async def fake_download_video(video_id: int) -> None:
        downloaded.append(video_id)
        await sc._repo.set_status(video_id, "downloaded")

    sc._download_video = fake_download_video

    task = asyncio.create_task(sc.download_worker())
    try:
        for _ in range(100):
            async with db() as session:
                remaining = (
                    await session.execute(
                        select(func.count(Video.id)).where(
                            Video.download_status.in_(["pending", "downloading"])
                        )
                    )
                ).scalar()
            if remaining == 0:
                break
            await asyncio.sleep(0.02)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    # Both the pending row and the recovered (was 'downloading') row downloaded.
    assert len(downloaded) == 2
    async with db() as session:
        statuses = (
            await session.execute(select(Video.download_status))
        ).scalars().all()
        assert all(status == "downloaded" for status in statuses)
