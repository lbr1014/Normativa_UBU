from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.extensions import db


class MarkdownConversionState(db.Model):
    __tablename__ = "markdown_conversion_state"

    id = db.Column(db.Integer, primary_key=True)

    status = db.Column(db.String(20), nullable=False, default="queued", index=True)
    progress = db.Column(db.Integer, nullable=False, default=0)
    message = db.Column(db.String(255), nullable=True)
    cancel_requested = db.Column(db.Boolean, nullable=False, default=False, index=True)
    error = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.created_at:
            self.created_at = datetime.now(ZoneInfo("Europe/Madrid"))
