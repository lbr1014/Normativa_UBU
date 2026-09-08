"""drop legacy tender metadata

Revision ID: b7c8d9e0f1a2
Revises: a1c2d3e4f5b6
Create Date: 2026-09-08 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b7c8d9e0f1a2"
down_revision = "a1c2d3e4f5b6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("chunks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_chunks_numero_expediente"))
        batch_op.drop_index(batch_op.f("ix_chunks_tipo_documento"))
        batch_op.drop_column("numero_expediente")
        batch_op.drop_column("tipo_documento")

    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_documents_numero_expediente"))
        batch_op.drop_index(batch_op.f("ix_documents_tipo_documento"))
        batch_op.drop_column("numero_expediente")
        batch_op.drop_column("tipo_documento")


def downgrade():
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tipo_documento", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("numero_expediente", sa.String(length=255), nullable=True))
        batch_op.create_index(batch_op.f("ix_documents_tipo_documento"), ["tipo_documento"], unique=False)
        batch_op.create_index(batch_op.f("ix_documents_numero_expediente"), ["numero_expediente"], unique=False)

    with op.batch_alter_table("chunks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tipo_documento", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("numero_expediente", sa.String(length=255), nullable=True))
        batch_op.create_index(batch_op.f("ix_chunks_tipo_documento"), ["tipo_documento"], unique=False)
        batch_op.create_index(batch_op.f("ix_chunks_numero_expediente"), ["numero_expediente"], unique=False)
