"""
Autora: Lydia Blanco Ruiz
Script con pruebas de integracion adicionales para cubrir la evaluación del sistema y la gestión de consultas activas. Su objetivo es 
verificar el funcionamiento de los endpoints encargados de recuperar evaluaciones recientes, consultar resultados detallados de 
evaluaciones finalizadas y detectar consultas RAG actualmente en ejecución. Las pruebas cubren distintos escenarios de éxito y error,
incluyendo ficheros inexistentes, rutas inválidas, resultados corruptos y evaluaciones incompletas.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.main.code.extensions import db
from app.main.code.model.rag_evaluation_state import RAGEvaluationState
from app.main.code.model.rag_query_state import RAGQueryState
from app.test.support import BaseAppTestCase


class RAGRoutesEvaluationAdditionalCoverageIntegrationTest(BaseAppTestCase):
    def setUp(self):
        """
        Inicializa el entorno de pruebas creando un usuario autenticado que será utilizado durante las pruebas de los endpoints 
        de evaluación RAG.
        """
        super().setUp()
        self.user = self.create_user(email="rag-eval@example.com")
        self.login(self.user.email)

    def test_rag_active_returns_none_and_active_job(self):
        """
        Verifica la consulta de trabajos RAG activos, comprobando tanto el caso en el que no existen tareas en ejecución como la 
        recuperación correcta de una consulta activa.
        """
        none = self.client.get("/rag/active", headers={"Accept": "application/json"})
        self.assertEqual(none.status_code, 200)
        self.assertEqual(none.get_json(), {"job_id": None})

        job = RAGQueryState(user_id=self.user.id, question="q", status="running", cancel_requested=False)
        db.session.add(job)
        db.session.commit()
        active = self.client.get("/rag/active", headers={"Accept": "application/json"})
        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.get_json()["job_id"], job.id)

    def test_latest_rag_evaluation_errors_and_success(self):
        """
        Comprueba la recuperación de la evaluación RAG más reciente, validando escenarios de éxito y distintos casos de error
        como resultados inexistentes, rutas fuera del directorio permitido, ficheros ausentes o resultados JSON inválidos.
        """
        with patch("app.main.code.controllers.rag.routes.t", side_effect=lambda key, **_k: key):
            missing = self.client.get("/rag/evaluation/latest", headers={"Accept": "application/json"})
        self.assertEqual(missing.status_code, 404)

        with tempfile.TemporaryDirectory() as tmpdir_s:
            tmpdir = Path(tmpdir_s)
            self.app.config["DATA_DIR"] = str(tmpdir)
            missing_file = tmpdir / "missing.json"
            out = tmpdir / "ragas_results.json"
            out.write_text(json.dumps({"final_metrics": {"a": 1}}), encoding="utf-8")
            job = RAGEvaluationState(status="done", progress=100, message="ok")
            job.results_json_path = str(out)
            db.session.add(job)
            db.session.commit()

            ok = self.client.get("/rag/evaluation/latest", headers={"Accept": "application/json"})
            self.assertEqual(ok.status_code, 200)
            self.assertEqual(ok.get_json()["final_metrics"], {"a": 1})

            # Sin archivo -> 404
            job.results_json_path = str(missing_file)
            db.session.commit()
            miss_file = self.client.get("/rag/evaluation/latest", headers={"Accept": "application/json"})
            self.assertEqual(miss_file.status_code, 404)

            # Path incorrecto -> 400
            job.results_json_path = str(tmpdir.parent / "escape.json")
            db.session.commit()
            bad = self.client.get("/rag/evaluation/latest", headers={"Accept": "application/json"})
            self.assertEqual(bad.status_code, 400)

            # JSON errone (incorrecto o no se puede leer) -> 500
            job.results_json_path = str(out)
            out.write_text("{", encoding="utf-8")
            db.session.commit()
            broken = self.client.get("/rag/evaluation/latest", headers={"Accept": "application/json"})
            self.assertEqual(broken.status_code, 500)

    def test_rag_evaluation_detail_404_and_success(self):
        """
        Verifica la visualización detallada de evaluaciones RAG, comprobando el comportamiento cuando la evaluación
        no ha finalizado, cuando todos los artefactos requeridos están disponibles y cuando faltan ficheros necesarios 
        para mostrar los resultados.
        """
        job = RAGEvaluationState(status="queued", progress=0, message="q")
        db.session.add(job)
        db.session.commit()
        not_done = self.client.get(f"/rag/evaluation/{job.id}")
        self.assertEqual(not_done.status_code, 404)

        with tempfile.TemporaryDirectory() as tmpdir_s:
            tmpdir = Path(tmpdir_s)
            self.app.config["DATA_DIR"] = str(tmpdir)
            results = tmpdir / "results.json"
            rows = tmpdir / "rows.json"
            cfg = tmpdir / "cfg.json"
            results.write_text(json.dumps({"final_metrics": {}}), encoding="utf-8")
            rows.write_text(json.dumps([]), encoding="utf-8")
            cfg.write_text(json.dumps({"x": 1}), encoding="utf-8")

            job2 = RAGEvaluationState(status="done", progress=100, message="ok")
            job2.results_json_path = str(results)
            job2.row_results_json_path = str(rows)
            job2.config_json_path = str(cfg)
            db.session.add(job2)
            db.session.commit()

            ok = self.client.get(f"/rag/evaluation/{job2.id}")
            self.assertEqual(ok.status_code, 200)

            # faltan filas -> aborta(404)
            rows.unlink()
            missing_rows = self.client.get(f"/rag/evaluation/{job2.id}")
            self.assertEqual(missing_rows.status_code, 404)
