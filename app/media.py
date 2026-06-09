"""Best-effort media metadata via ffprobe / ffmpeg. Failures never block ingestion."""

import asyncio
import logging

logger = logging.getLogger("video_manager.media")


async def _run(*args: str) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return proc.returncode or 0, out, err


async def probe_duration(path: str) -> float | None:
    """Return the video duration in seconds, or None if it can't be read."""
    try:
        code, out, _ = await _run(
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        )
        if code == 0 and out.strip():
            return float(out.strip())
    except (OSError, ValueError):
        logger.warning("ffprobe failed for %s", path, exc_info=True)
    return None


async def make_thumbnail(video_path: str, thumb_path: str) -> bool:
    """Grab a single frame as a thumbnail. Returns True on success."""
    try:
        code, _, _ = await _run(
            "ffmpeg",
            "-y",
            "-ss",
            "1",
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-vf",
            "scale=480:-2",
            thumb_path,
        )
        return code == 0
    except OSError:
        logger.warning("ffmpeg thumbnail failed for %s", video_path, exc_info=True)
        return False
