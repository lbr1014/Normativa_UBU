"""create document operation state

Revision ID: d4c3b2a1f0e9
Revises: b7c8d9e0f1a2
Create Date: 2026-09-15 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "d4c3b2a1f0e9"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "document_operation_state",
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("message", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_operation_state_cancel_requested"), "document_operation_state", ["cancel_requested"], unique=False)
    op.create_index(op.f("ix_document_operation_state_created_at"), "document_operation_state", ["created_at"], unique=False)
    op.create_index(op.f("ix_document_operation_state_finished_at"), "document_operation_state", ["finished_at"], unique=False)
    op.create_index(op.f("ix_document_operation_state_operation"), "document_operation_state", ["operation"], unique=False)
    op.create_index(op.f("ix_document_operation_state_started_at"), "document_operation_state", ["started_at"], unique=False)
    op.create_index(op.f("ix_document_operation_state_status"), "document_operation_state", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_document_operation_state_status"), table_name="document_operation_state")
    op.drop_index(op.f("ix_document_operation_state_started_at"), table_name="document_operation_state")
    op.drop_index(op.f("ix_document_operation_state_operation"), table_name="document_operation_state")
    op.drop_index(op.f("ix_document_operation_state_finished_at"), table_name="document_operation_state")
    op.drop_index(op.f("ix_document_operation_state_created_at"), table_name="document_operation_state")
    op.drop_index(op.f("ix_document_operation_state_cancel_requested"), table_name="document_operation_state")
    op.drop_table("document_operation_state")
