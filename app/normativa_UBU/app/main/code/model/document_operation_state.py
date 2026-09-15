"""
Autora: Lydia Blanco Ruiz
Estado persistido de operaciones asíncronas sobre documentos.
"""

from __future__ import annotations

from app.main.code.extensions import db
from app.main.code.model.job_state import State


class DocumentOperationState(State):
    """
    Estado de una operación de carga o borrado de documentos.
    """

    __tablename__ = "document_operation_state"

    operation = db.Column(db.String(20), nullable=False, index=True)
    message = db.Column(db.String(255), nullable=True)
