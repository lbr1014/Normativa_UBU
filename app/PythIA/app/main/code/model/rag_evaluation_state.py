"""
Autora: Lydia Blanco Ruiz
Entidad SQLAlchemy que registra el estado de evaluaciones del RAG.
"""

from __future__ import annotations

from app.main.code.extensions import db
from app.main.code.model.job_state import State


class RAGEvaluationState(State):
    """
    Estado persistido de una ejecucion de evaluacion del RAG.
    """

    __tablename__ = "rag_evaluation_state"

    message = db.Column(db.String(255), nullable=True)
    output_dir = db.Column(db.String(512), nullable=True)
    results_json_path = db.Column(db.String(512), nullable=True)
    row_results_json_path = db.Column(db.String(512), nullable=True)
    config_json_path = db.Column(db.String(512), nullable=True)
    ares_questions_json_path = db.Column(db.String(512), nullable=True)
    ares_dataset_json_path = db.Column(db.String(512), nullable=True)
    ares_dataset_tsv_path = db.Column(db.String(512), nullable=True)
