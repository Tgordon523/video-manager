from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# Default board columns, seeded on first run if the table is empty.
DEFAULT_COLUMNS = ["Backlog", "Editing", "Review", "Published"]

# download_status values
PENDING = "pending"
DOWNLOADING = "downloading"
DOWNLOADED = "downloaded"
ERROR = "error"


class BoardColumn(Base):
    __tablename__ = "columns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    videos: Mapped[list["Video"]] = relationship(
        back_populates="column",
        order_by="Video.position",
        cascade="all, delete-orphan",
    )


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Google Drive's stable file ID — our dedup key.
    drive_file_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    drive_path: Mapped[str | None] = mapped_column(String(1024))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    drive_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    local_path: Mapped[str | None] = mapped_column(String(1024))
    download_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PENDING
    )
    download_error: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024))

    column_id: Mapped[int] = mapped_column(
        ForeignKey("columns.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    column: Mapped["BoardColumn"] = relationship(back_populates="videos")
    notes: Mapped[list["Note"]] = relationship(
        back_populates="video",
        order_by="Note.created_at.desc()",
        cascade="all, delete-orphan",
    )


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    video: Mapped["Video"] = relationship(back_populates="notes")
