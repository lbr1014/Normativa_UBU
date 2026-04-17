"""
Autora: Lydia Blanco Ruiz
Script de migracion de Alembic para evolucionar el esquema de la base de datos.
"""

"""add model name to rag query state

Revision ID: 2b7c9e1f4a20
Revises: a7d9e4c2b1f0
Create Date: 2026-04-16 18:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2b7c9e1f4a20"
down_revision = "a7d9e4c2b1f0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("rag_query_state", schema=None) as batch_op:
        batch_op.add_column(sa.Column("model_name", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("rag_query_state", schema=None) as batch_op:
        batch_op.drop_column("model_name")
