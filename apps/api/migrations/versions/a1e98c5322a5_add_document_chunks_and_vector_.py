"""Add document chunks and vector embeddings.

Revision ID: a1e98c5322a5
Revises: 73489dd9db67
Create Date: 2026-07-22 07:43:07.832099
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects import postgresql


# Revision identifiers used by Alembic.
revision: str = "a1e98c5322a5"
down_revision: Union[str, Sequence[str], None] = (
    "73489dd9db67"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create document chunk and vector-search storage."""

    # The PostgreSQL image includes pgvector, but every database
    # must enable the extension before VECTOR columns are created.
    op.execute(
        "CREATE EXTENSION IF NOT EXISTS vector"
    )

    op.create_table(
        "document_chunks",
        sa.Column(
            "workspace_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "processing_run_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "document_page_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "chunk_index",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "page_number",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "start_character",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "end_character",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "text_content",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "character_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "word_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "content_sha256",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "embedding",
            VECTOR(384),
            nullable=True,
        ),
        sa.Column(
            "embedding_provider",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "embedding_model",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "embedding_dimensions",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "embedded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "extra_metadata",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            server_default=sa.text(
                "'{}'::jsonb"
            ),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "status IN "
                "('pending', 'embedding', "
                "'ready', 'failed')"
            ),
            name=op.f(
                "ck_document_chunks_status_valid"
            ),
        ),
        sa.CheckConstraint(
            "character_count >= 0",
            name=op.f(
                "ck_document_chunks_"
                "character_count_non_negative"
            ),
        ),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name=op.f(
                "ck_document_chunks_"
                "chunk_index_non_negative"
            ),
        ),
        sa.CheckConstraint(
            (
                "embedding_dimensions IS NULL "
                "OR embedding_dimensions > 0"
            ),
            name=op.f(
                "ck_document_chunks_"
                "embedding_dimensions_positive"
            ),
        ),
        sa.CheckConstraint(
            "end_character >= start_character",
            name=op.f(
                "ck_document_chunks_"
                "character_range_valid"
            ),
        ),
        sa.CheckConstraint(
            "page_number >= 1",
            name=op.f(
                "ck_document_chunks_"
                "page_number_positive"
            ),
        ),
        sa.CheckConstraint(
            "start_character >= 0",
            name=op.f(
                "ck_document_chunks_"
                "start_character_non_negative"
            ),
        ),
        sa.CheckConstraint(
            "word_count >= 0",
            name=op.f(
                "ck_document_chunks_"
                "word_count_non_negative"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f(
                "fk_document_chunks_"
                "document_id_documents"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_page_id"],
            ["document_pages.id"],
            name=op.f(
                "fk_document_chunks_"
                "document_page_id_document_pages"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["document_processing_runs.id"],
            name=op.f(
                "fk_document_chunks_"
                "processing_run_id_"
                "document_processing_runs"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f(
                "fk_document_chunks_"
                "workspace_id_workspaces"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f(
                "pk_document_chunks"
            ),
        ),
        sa.UniqueConstraint(
            "processing_run_id",
            "chunk_index",
            name=(
                "processing_run_"
                "chunk_index_unique"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_document_chunks_content_sha256"
        ),
        "document_chunks",
        ["content_sha256"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_document_chunks_document_id"
        ),
        "document_chunks",
        ["document_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_document_chunks_document_page_id"
        ),
        "document_chunks",
        ["document_page_id"],
        unique=False,
    )

    op.create_index(
        "ix_document_chunks_document_run",
        "document_chunks",
        [
            "document_id",
            "processing_run_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_document_chunks_page_order",
        "document_chunks",
        [
            "document_page_id",
            "chunk_index",
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_document_chunks_processing_run_id"
        ),
        "document_chunks",
        ["processing_run_id"],
        unique=False,
    )

    op.create_index(
        "ix_document_chunks_workspace_document",
        "document_chunks",
        [
            "workspace_id",
            "document_id",
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_document_chunks_workspace_id"
        ),
        "document_chunks",
        ["workspace_id"],
        unique=False,
    )

    op.create_index(
        "ix_document_chunks_workspace_status",
        "document_chunks",
        [
            "workspace_id",
            "status",
        ],
        unique=False,
    )

    # HNSW approximate-nearest-neighbor index for cosine search.
    op.create_index(
        "ix_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={
            "m": 16,
            "ef_construction": 64,
        },
        postgresql_ops={
            "embedding": "vector_cosine_ops",
        },
    )


def downgrade() -> None:
    """Remove document chunk and vector-search storage."""

    op.drop_index(
        "ix_document_chunks_embedding_hnsw",
        table_name="document_chunks",
    )

    op.drop_index(
        "ix_document_chunks_workspace_status",
        table_name="document_chunks",
    )

    op.drop_index(
        op.f(
            "ix_document_chunks_workspace_id"
        ),
        table_name="document_chunks",
    )

    op.drop_index(
        "ix_document_chunks_workspace_document",
        table_name="document_chunks",
    )

    op.drop_index(
        op.f(
            "ix_document_chunks_processing_run_id"
        ),
        table_name="document_chunks",
    )

    op.drop_index(
        "ix_document_chunks_page_order",
        table_name="document_chunks",
    )

    op.drop_index(
        "ix_document_chunks_document_run",
        table_name="document_chunks",
    )

    op.drop_index(
        op.f(
            "ix_document_chunks_document_page_id"
        ),
        table_name="document_chunks",
    )

    op.drop_index(
        op.f(
            "ix_document_chunks_document_id"
        ),
        table_name="document_chunks",
    )

    op.drop_index(
        op.f(
            "ix_document_chunks_content_sha256"
        ),
        table_name="document_chunks",
    )

    op.drop_table(
        "document_chunks"
    )

    # Do not drop the vector extension. Other tables or future
    # migrations may depend on it.