"""Thin async wrappers around the rclone CLI."""

import asyncio
import json
import os
from typing import Protocol

from .config import settings


class RcloneError(Exception):
    pass


class DriveAdapter(Protocol):
    async def list_files(self, source: str) -> list[dict]: ...
    async def download(self, source_file: str, dest: str) -> None: ...


def _env() -> dict[str, str]:
    env = os.environ.copy()
    if settings.rclone_config:
        env["RCLONE_CONFIG"] = settings.rclone_config
    return env


async def _run(*args: str) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        "rclone",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_env(),
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RcloneError(stderr.decode(errors="replace").strip() or "rclone failed")
    return stdout


async def list_files(source: str) -> list[dict]:
    """Return rclone lsjson entries (files only) for the given remote:path."""
    out = await _run("lsjson", source, "--files-only")
    return json.loads(out.decode() or "[]")


async def download(source_file: str, dest: str) -> None:
    """Download a single remote file to a local destination path."""
    await _run("copyto", source_file, dest)


class RcloneAdapter:
    """Wraps the module-level rclone functions behind the DriveAdapter protocol."""

    async def list_files(self, source: str) -> list[dict]:
        return await list_files(source)

    async def download(self, source_file: str, dest: str) -> None:
        await download(source_file, dest)
