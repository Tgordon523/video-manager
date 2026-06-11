from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, read from environment variables (or a local .env)."""

    # SQLAlchemy async URL, e.g. postgresql+asyncpg://user:pass@host:5432/db
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/videos"

    # rclone remote name (from `rclone config`) and the folder within it to watch.
    rclone_remote: str = ""
    rclone_drive_path: str = ""
    # Path to rclone.conf inside the container; passed to rclone via RCLONE_CONFIG.
    rclone_config: str = ""

    # Where downloaded mp4 files are stored locally.
    media_dir: str = "/data/videos"

    # How often the background scanner polls Drive.
    scan_interval_seconds: int = 300

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def drive_source(self) -> str:
        """The rclone path to scan, e.g. 'gdrive:Videos/ToEdit' or 'gdrive:'."""
        path = self.rclone_drive_path.strip().strip("/")
        return f"{self.rclone_remote}:{path}"


settings = Settings()
