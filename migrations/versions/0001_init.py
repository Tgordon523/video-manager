"""initial schema: columns, videos, notes

Revision ID: 0001
Revises:
Create Date: 2026-06-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "columns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("drive_file_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("drive_path", sa.String(length=1024), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("drive_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("local_path", sa.String(length=1024), nullable=True),
        sa.Column(
            "download_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("download_error", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("thumbnail_path", sa.String(length=1024), nullable=True),
        sa.Column(
            "column_id",
            sa.Integer(),
            sa.ForeignKey("columns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_videos_drive_file_id", "videos", ["drive_file_id"], unique=True
    )
    op.create_index("ix_videos_column_id", "videos", ["column_id"])

    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "video_id",
            sa.Integer(),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_notes_video_id", "notes", ["video_id"])


def downgrade() -> None:
    op.drop_index("ix_notes_video_id", table_name="notes")
    op.drop_table("notes")
    op.drop_index("ix_videos_column_id", table_name="videos")
    op.drop_index("ix_videos_drive_file_id", table_name="videos")
    op.drop_table("videos")
    op.drop_table("columns")
