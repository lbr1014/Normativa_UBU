"""
Autora: Lydia Blanco Ruiz
Script con pruebas unitarias adicionales para cubrir los casos menos frecuentes de los métodos de administración. Estas pruebas complementan las ya existentes en test_admin_unit.py, 
centrandose en aspectos como la detección de tareas obsoletas, manejo de errores en procesos externos, validación de rutas para descargas seguras, y comportamiento de los endpoints bajo 
condiciones límite. El objetivo es asegurar una cobertura exhaustiva de los servicios administrativos, garantizando su correcto funcionamiento incluso en situaciones atípicas o de fallo.
"""

import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.main.code.controllers.admin import routes as admin_routes
from app.main.code.extensions import db
from app.main.code.model.markdown_conversion_state import MarkdownConversionState
from app.main.code.model.rag_evaluation_state import RAGEvaluationState
from app.main.code.model.vector_update_state import VectorUpdateState
from app.main.code.model.web_scraping_state import WebScrapingSate
from app.test.support import BaseAppTestCase


class AdminRoutesAdditionalCoverageUnitTest(BaseAppTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(email="admin2@example.com", is_admin=True)
        self.login(self.admin.email)

    def test_datetime_and_stale_job_helpers(self):
        """
        Comprueba el funcionamiento de las funciones auxiliares encargadas de normalizar fechas y detectar tareas obsoletas (stale jobs) en función del momento de arranque de la aplicación.
        """
        aware = datetime(2026, 5, 31, 10, 0, tzinfo=timezone.utc)
        naive = datetime(2026, 5, 31, 10, 0)

        self.assertEqual(admin_routes._normalize_dt_for_compare(None, reference=naive), None)
        self.assertEqual(admin_routes._normalize_dt_for_compare(aware, reference=aware), aware)
        self.assertEqual(admin_routes._normalize_dt_for_compare(aware, reference=naive).tzinfo, None)

        boot_at = datetime(2026, 5, 31, 10, 0)
        job = SimpleNamespace(status="queued", created_at=boot_at - timedelta(seconds=1), started_at=None)
        self.assertTrue(admin_routes._job_is_stale_since_boot(job, boot_at=boot_at))

        job2 = SimpleNamespace(status="done", created_at=boot_at - timedelta(days=1), started_at=None)
        self.assertFalse(admin_routes._job_is_stale_since_boot(job2, boot_at=boot_at))

        job3 = SimpleNamespace(status="queued", created_at=boot_at, started_at=boot_at - timedelta(seconds=1))
        self.assertTrue(admin_routes._job_is_stale_since_boot(job3, boot_at=boot_at))

        job4 = SimpleNamespace(status="queued", created_at=boot_at, started_at=boot_at)
        self.assertFalse(admin_routes._job_is_stale_since_boot(job4, boot_at=None))

    def test_mark_job_as_stale_uses_fallback_when_mark_failed_missing(self):
        """
        Verifica que una tarea obsoleta se marca correctamente como fallida tanto cuando dispone del método mark_failed() como cuando debe utilizarse el mecanismo alternativo de actualización manual.
        """
        job = SimpleNamespace(status="queued", error=None, finished_at=None)
        admin_routes._mark_job_as_stale(job)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.error, admin_routes.STALE_JOB_MESSAGE)
        self.assertIsNotNone(job.finished_at)

        class JobWithMarkFailed:
            def __init__(self):
                self.called = False

            def mark_failed(self, *_a, **_k):
                self.called = True

        job2 = JobWithMarkFailed()
        admin_routes._mark_job_as_stale(job2)
        self.assertTrue(job2.called)

    def test_upload_documents_wraps_single_file(self):
        """
        Comprueba que la subida de un único archivo se adapta correctamente al formato esperado por el servicio de almacenamiento de documentos.
        """
        fake_form = MagicMock()
        fake_form.validate_on_submit.return_value = True
        fake_form.files.data = MagicMock(filename="one.pdf")
        fake_service = MagicMock()
        fake_service.save_uploads.return_value = 1
        with patch("app.main.code.controllers.admin.routes.PdfUploadForm", return_value=fake_form), patch(
            "app.main.code.controllers.admin.routes.documentos_service", return_value=fake_service
        ):
            resp = self.client.post("/admin/documents/upload", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        args, _kwargs = fake_service.save_uploads.call_args
        self.assertEqual(len(args[0]), 1)

    def test_status_endpoints_mark_jobs_stale(self):
        """
        Verifica que los endpoints de consulta de estado detectan tareas bloqueadas o abandonadas y las marcan automáticamente como fallidas.
        """
        boot_at = datetime(2026, 5, 31, 10, 0)
        self.app.config["APP_BOOT_AT"] = boot_at

        mk = MarkdownConversionState(status="running", progress=0, message="m", cancel_requested=False)
        mk.created_at = boot_at - timedelta(hours=1)
        db.session.add(mk)
        db.session.commit()
        res = self.client.get(f"/admin/documents/markdown/status/{mk.id}", headers={"Accept": "application/json"})
        self.assertEqual(res.status_code, 200)
        db.session.refresh(mk)
        self.assertEqual(mk.status, "failed")

        vec = VectorUpdateState(status="running", progress=0, cancel_requested=False)
        vec.created_at = boot_at - timedelta(hours=1)
        db.session.add(vec)
        db.session.commit()
        res2 = self.client.get(f"/admin/vector-db/status/{vec.id}", headers={"Accept": "application/json"})
        self.assertEqual(res2.status_code, 200)
        db.session.refresh(vec)
        self.assertEqual(vec.status, "failed")

        rag = RAGEvaluationState(status="running", progress=0, message="r", cancel_requested=False)
        rag.created_at = boot_at - timedelta(hours=1)
        db.session.add(rag)
        db.session.commit()
        res3 = self.client.get(f"/admin/rag/evaluation/status/{rag.id}", headers={"Accept": "application/json"})
        self.assertEqual(res3.status_code, 200)
        db.session.refresh(rag)
        self.assertEqual(rag.status, "failed")

    def test_view_document_markdown_render_html_with_and_without_markdown_lib(self):
        """
        Comprueba la visualización de documentos Markdown tanto cuando la librería de conversión a HTML está disponible como cuando no lo está.
        """
        doc = self.create_document(nombre="doc.pdf")
        doc.markdown_content = "# Titulo"
        db.session.commit()

        # Sin libreria markdown -> devuelve markdown raw
        with patch("importlib.import_module", side_effect=ModuleNotFoundError()):
            raw = self.client.get(f"/admin/documents/{doc.id}/view?format=markdown&render=html")
        self.assertEqual(raw.status_code, 200)
        self.assertEqual(raw.mimetype, "text/markdown")

        fake_md = SimpleNamespace(markdown=lambda text, **_k: f"<h1>{text}</h1>")
        with patch("importlib.import_module", return_value=fake_md):
            rendered = self.client.get(f"/admin/documents/{doc.id}/view?format=markdown&render=html")
        self.assertEqual(rendered.status_code, 200)
        self.assertIn(b"<h1>", rendered.data)

    def test_download_rag_evaluation_artifact_rejects_path_traversal_and_missing(self):
        """
        Verifica que la descarga de artefactos de evaluación RAG rechaza rutas fuera del directorio permitido y archivos inexistentes.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            self.app.config["DATA_DIR"] = str(base)

            job = RAGEvaluationState(status="done", progress=100, message="ok")
            job.results_json_path = str(base / "out.json")
            db.session.add(job)
            db.session.commit()

            missing = self.client.get(
                f"/admin/rag/evaluation/download/{job.id}/results",
                headers={"Accept": "application/json"},
            )
            self.assertEqual(missing.status_code, 404)

            # Ruta fuera de DATA_DIR -> 400
            job.results_json_path = str(Path(tmpdir).parent / "escape.json")
            db.session.commit()
            bad = self.client.get(
                f"/admin/rag/evaluation/download/{job.id}/results",
                headers={"Accept": "application/json"},
            )
            self.assertEqual(bad.status_code, 400)

    def test_rag_evaluation_async_success_and_failure(self):
        """
        Comprueba que la ejecución asíncrona de evaluaciones RAG actualiza correctamente el estado del trabajo tanto en casos de éxito como de error.
        """
        job = RAGEvaluationState(status="queued", progress=0, message="q")
        db.session.add(job)
        db.session.commit()

        artifacts = SimpleNamespace(
            output_dir=Path("."),
            results_json_path=Path("results.json"),
            row_results_json_path=Path("rows.json"),
            config_json_path=Path("cfg.json"),
            ares_questions_json_path=Path("q.json"),
            ares_dataset_json_path=Path("d.json"),
            ares_dataset_tsv_path=Path("d.tsv"),
        )

        with patch("app.main.code.controllers.admin.routes.run_rag_evaluation", return_value=artifacts), patch(
            "app.main.code.controllers.admin.routes.translate_for", side_effect=lambda _l, key, **_k: key
        ):
            admin_routes.rag_evaluation_async(app=self.app, job_id=job.id, lang="es")
        db.session.refresh(job)
        self.assertEqual(job.status, "done")
        self.assertEqual(job.progress, 100)

        failing = RAGEvaluationState(status="queued", progress=0, message="q")
        db.session.add(failing)
        db.session.commit()
        with patch("app.main.code.controllers.admin.routes.run_rag_evaluation", side_effect=RuntimeError("boom")), patch.object(
            self.app.logger, "exception"
        ):
            admin_routes.rag_evaluation_async(app=self.app, job_id=failing.id, lang="es")
        db.session.expire_all()
        refreshed = db.session.get(RAGEvaluationState, failing.id)
        self.assertEqual(refreshed.status, "failed")

    def test_documents_list_page_filters_use_query_paginate(self):
        """
        Verifica que la página de listado de documentos aplica correctamente los filtros de búsqueda y paginación.
        """
        doc = self.create_document(nombre="filtro.pdf")
        doc.status = "indexed"
        doc.tipo_documento = "tipo"
        db.session.commit()

        response = self.client.get("/admin/documents/list?name=filtro&type=tipo&status=indexed&markdown=no&page=1")
        self.assertEqual(response.status_code, 200)

    def test_bulk_delete_documents_handles_error(self):
        """
        Comprueba que los errores producidos durante la eliminación masiva de documentos son gestionados adecuadamente.
        """
        with patch("app.main.code.controllers.admin.routes.documentos_service") as mock_svc, patch.object(
            self.app.logger, "exception"
        ):
            mock_svc.return_value.delete_document.side_effect = RuntimeError("boom")
            resp = self.client.post("/admin/documents/bulk-delete", data={"selected_doc_ids": ["1", "1"]})
        self.assertEqual(resp.status_code, 500)

    def test_handle_scraping_exception_adds_calledprocess_details(self):
        """
        Verifica que las excepciones producidas por procesos externos de scraping almacenan información detallada del error generado.
        """
        job = WebScrapingSate(status="running", progress=0, message="x", cancel_requested=False)
        db.session.add(job)
        db.session.commit()

        exc = subprocess.CalledProcessError(1, ["cmd"], output="OUT", stderr="ERR")
        with patch("app.main.code.controllers.admin.routes.translate_for", return_value="msg"), patch(
            "app.main.code.controllers.admin.routes.send_scraping_finished_email"
        ), patch("app.main.code.controllers.admin.routes._send_email_safe"):
            admin_routes._handle_scraping_exception(
                self.app,
                job.id,
                "admin@example.com",
                "http://docs.local",
                "es",
                exc,
            )
        db.session.refresh(job)
        self.assertEqual(job.status, "failed")
        self.assertIn("ERR", job.error)

    def test_scraping_async_calledprocesserror_continues_when_results_exist(self):
        """
        Comprueba que una tarea de scraping puede finalizar correctamente aunque uno de los procesos externos falle, siempre que existan resultados válidos generados previamente.
        """
        job = WebScrapingSate(status="queued", progress=0, cancel_requested=False)
        db.session.add(job)
        db.session.commit()

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            resultados_json = base / "resultados.json"
            resultados_json.write_text("{}", encoding="utf-8")
            pliegos_json = base / "pliegos.json"
            pliegos_json.write_text("{}", encoding="utf-8")

            def run_script(job, script, cwd, env, should_cancel, lang, **kwargs):
                if "script_1" in str(kwargs.get("message", "")) or script.name == "one.py":
                    raise subprocess.CalledProcessError(1, ["cmd"], stderr="ERR")

            with patch(
                "app.main.code.controllers.admin.routes._build_scraping_context",
                return_value=(base, base, Path("one.py"), Path("two.py"), base, {}, resultados_json, pliegos_json),
            ), patch("app.main.code.controllers.admin.routes._run_scraping_script", side_effect=run_script), patch(
                "app.main.code.controllers.admin.routes._sync_scraping_results", return_value=(0, 0)
            ), patch(
                "app.main.code.controllers.admin.routes.send_scraping_finished_email"
            ), patch("app.main.code.controllers.admin.routes._send_email_safe"):
                admin_routes.scraping_async(self.app, job.id, "admin@example.com", "http://docs.local")

        db.session.expire_all()
        self.assertEqual(db.session.get(WebScrapingSate, job.id).status, "done")
