"""add structural chunk metadata

Revision ID: a1c2d3e4f5b6
Revises: f3a8c9d2e1b4
Create Date: 2026-09-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a1c2d3e4f5b6"
down_revision = "f3a8c9d2e1b4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("chunks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("structure_type", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("page", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("level", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("bbox", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("structural_metadata", sa.JSON(), nullable=True))
        batch_op.create_index(batch_op.f("ix_chunks_structure_type"), ["structure_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_chunks_page"), ["page"], unique=False)
        batch_op.create_index(batch_op.f("ix_chunks_level"), ["level"], unique=False)


def downgrade():
    with op.batch_alter_table("chunks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_chunks_level"))
        batch_op.drop_index(batch_op.f("ix_chunks_page"))
        batch_op.drop_index(batch_op.f("ix_chunks_structure_type"))
        batch_op.drop_column("structural_metadata")
        batch_op.drop_column("bbox")
        batch_op.drop_column("level")
        batch_op.drop_column("page")
        batch_op.drop_column("structure_type")
