"""
Autora: Lydia Blanco Ruiz
Script con la entidad SQLAlchemy que registra el estado de conversiones a Markdown.
"""

from __future__ import annotations

from app.main.code.extensions import db
from app.main.code.model.job_state import State


class MarkdownConversionState(State):
    """
    Estado persistido de un proceso de conversion a Markdown.
    """

    __tablename__ = "markdown_conversion_state"

    message = db.Column(db.String(255), nullable=True)
