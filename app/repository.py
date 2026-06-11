from sqlalchemy import select, update

from .db import SessionLocal
from .models import DOWNLOADED, DOWNLOADING, PENDING, Video


class VideoRepository:
    def __init__(self, session_factory=None):
        self._sf = session_factory or SessionLocal

    async def next_pending_id(self) -> int | None:
        async with self._sf() as session:
            return (
                await session.execute(
                    select(Video.id)
                    .where(Video.download_status == PENDING)
                    .order_by(Video.id)
                    .limit(1)
                )
            ).scalar_one_or_none()

    async def reset_interrupted_downloads(self) -> int:
        async with self._sf() as session:
            result = await session.execute(
                update(Video)
                .where(Video.download_status == DOWNLOADING)
                .values(download_status=PENDING)
            )
            await session.commit()
        return result.rowcount

    async def set_status(
        self, video_id: int, status: str, error: str | None = None
    ) -> None:
        async with self._sf() as session:
            video = await session.get(Video, video_id)
            if video is None:
                return
            video.download_status = status
            if error is not None:
                video.download_error = error[:2000]
            await session.commit()

    async def get_for_download(self, video_id: int) -> tuple[str, str] | None:
        """Mark video as downloading; return (name, rel_path) or None if missing."""
        async with self._sf() as session:
            video = await session.get(Video, video_id)
            if video is None:
                return None
            video.download_status = DOWNLOADING
            await session.commit()
            return video.name, video.drive_path or video.name

    async def mark_downloaded(
        self,
        video_id: int,
        local_path: str,
        duration: float | None,
        thumbnail_path: str | None,
    ) -> None:
        async with self._sf() as session:
            video = await session.get(Video, video_id)
            if video is None:
                return
            video.local_path = local_path
            video.download_status = DOWNLOADED
            video.download_error = None
            video.duration_seconds = duration
            video.thumbnail_path = thumbnail_path
            await session.commit()
