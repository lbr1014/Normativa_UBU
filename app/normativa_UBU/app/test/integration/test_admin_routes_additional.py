"""
Autora: Lydia Blanco Ruiz
Script con pruebas de integracion adicionales para las rutas de administarción de la aplicación. Su objetivo es verificar 
escenarios poco frecuentes y ramas adicionales relacionadas con la gestión de usuarios, documentos, evaluaciones RAG y 
tareas asíncronas de mantenimiento. Las pruebas cubren la detección de trabajos obsoletos, filtros avanzados de administración,
operaciones masivas, descargas de artefactos de evaluación y validación de distintos 
estados de las tareas en segundo plano. 
"""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.main.code.extensions import db
from app.main.code.model.markdown_conversion_state import MarkdownConversionState
from app.main.code.model.rag_evaluation_state import RAGEvaluationState
from app.main.code.model.vector_update_state import VectorUpdateState
from app.test.support import BaseAppTestCase


class AdminRoutesAdditionalCoverageIntegrationTest(BaseAppTestCase):
    def setUp(self):
        """
        Inicializa el entorno de pruebas creando un usuario administrador autenticado para ejecutar las operaciones administrativas 
        cubiertas por las pruebas.
        """
        super().setUp()
        self.admin = self.create_user(email="admin-extra@example.com", is_admin=True)
        self.login(self.admin.email)

    def test_active_jobs_status_marks_stale_and_returns_payload(self):
        """
        Verifica que las tareas en ejecución consideradas obsoletas son marcadas como fallidas y que el sistema devuelve correctamente el 
        estado actualizado de los trabajos activos.
        """
        boot_at = datetime(2026, 5, 31, 10, 0, tzinfo=timezone.utc)
        self.app.config["APP_BOOT_AT"] = boot_at

        mk = MarkdownConversionState(status="running", progress=0, message="m", cancel_requested=False)
        mk.created_at = boot_at - timedelta(hours=1)
        db.session.add(mk)
        db.session.commit()

        response = self.client.get("/admin/jobs/active", headers={"Accept": "application/json"})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNone(payload["markdown"])
        db.session.refresh(mk)
        self.assertEqual(mk.status, "failed")

        vec = VectorUpdateState(status="running", progress=0, cancel_requested=False)
        db.session.add(vec)
        db.session.commit()
        response2 = self.client.get("/admin/jobs/active", headers={"Accept": "application/json"})
        self.assertEqual(response2.status_code, 200)
        self.assertIsNotNone(response2.get_json()["vector"])

    def test_users_filters_role_user(self):
        """
        Comprueba el filtrado de usuarios por rol dentro del panel de administración.
        """
        self.create_user(email="u1@example.com", is_admin=False)
        self.create_user(email="u2@example.com", is_admin=True)
        page = self.client.get("/admin/users?role=user")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"u1@example.com", page.data)
        self.assertNotIn(b"u2@example.com", page.data)

    def test_bulk_users_invalid_action_redirects_and_missing_user_404(self):
        """
        Verifica el comportamiento de las operaciones masivas cuando se solicita una acción inválida o se incluyen usuarios inexistentes.
        """
        user = self.create_user(email="bulk-x@example.com", is_admin=False)
        invalid = self.client.post(
            "/admin/users/bulk",
            data={
                "bulk_action": "nope",
                "selected_user_ids": [str(user.id)],
                "filter_country": "ES",
            },
            follow_redirects=False,
        )
        self.assertEqual(invalid.status_code, 302)

        missing = self.client.post(
            "/admin/users/bulk",
            data={"bulk_action": "toggle", "selected_user_ids": ["999999"]},
            headers={"Accept": "application/json"},
        )
        self.assertEqual(missing.status_code, 404)

    def test_documents_list_filters_unknown_type_and_markdown_yes(self):
        """
        Comprueba los filtros del listado documental para documentos sin tipo asignado y documentos que disponen de contenido Markdown 
        generado.
        """
        doc = self.create_document(nombre="md.pdf")
        doc.tipo_documento = None
        doc.markdown_content = "# ok"
        db.session.commit()

        response = self.client.get("/admin/documents/list?type=unknown&markdown=yes&page=1")
        self.assertEqual(response.status_code, 200)

    def test_rag_evaluation_run_invalid_post_returns_400_json_and_html_redirect(self):
        """
        Verifica la validación de solicitudes de evaluación RAG, comprobando tanto las respuestas JSON de error como las redirecciones 
        HTML cuando la solicitud es válida.
        """
        fake_form = MagicMock()
        fake_form.validate_on_submit.return_value = False
        with patch("app.main.code.controllers.admin.routes.EmptyForm", return_value=fake_form), patch(
            "app.main.code.controllers.admin.routes.t", return_value="bad request"
        ):
            bad = self.client.post("/admin/rag/evaluation/run", headers={"Accept": "application/json"})
        self.assertEqual(bad.status_code, 400)

        # En HTML (sin JSON) debe redirigir con flash
        ok_form = MagicMock()
        ok_form.validate_on_submit.return_value = True
        with patch("app.main.code.controllers.admin.routes.EmptyForm", return_value=ok_form), patch(
            "app.main.code.controllers.admin.routes.submit_tracked"
        ):
            html = self.client.post("/admin/rag/evaluation/run", follow_redirects=False)
        self.assertEqual(html.status_code, 302)

    def test_rag_evaluation_status_missing_returns_404(self):
        """
        Comprueba que la consulta del estado de una evaluación inexistente devuelve correctamente un error de recurso no encontrado.
        """
        missing = self.client.get("/admin/rag/evaluation/status/999999", headers={"Accept": "application/json"})
        self.assertEqual(missing.status_code, 404)

    def test_download_rag_evaluation_invalid_artifact_404_and_success_download(self):
        """
        Verifica la descarga de artefactos de evaluación RAG, incluyendo tanto escenarios de error por artefactos inexistentes 
        como descargas correctas de resultados disponibles.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            self.app.config["DATA_DIR"] = str(base)
            f = base / "out.json"
            f.write_text("{}", encoding="utf-8")

            job = RAGEvaluationState(status="done", progress=100, message="ok")
            job.results_json_path = str(f)
            db.session.add(job)
            db.session.commit()

            invalid = self.client.get(
                f"/admin/rag/evaluation/download/{job.id}/nope",
                headers={"Accept": "application/json"},
            )
            self.assertEqual(invalid.status_code, 404)

            ok = self.client.get(
                f"/admin/rag/evaluation/download/{job.id}/results",
                headers={"Accept": "application/json"},
            )
            self.assertEqual(ok.status_code, 200)
            ok.close()

    def test_rag_evaluation_async_returns_when_job_missing(self):
        """
        Comprueba que el procesamiento asíncrono de evaluaciones finaliza de forma segura cuando el trabajo solicitado no existe.
        """
        from app.main.code.controllers.admin import routes as admin_routes

        admin_routes.rag_evaluation_async(app=self.app, job_id=999999, lang="es")

    def test_bulk_delete_documents_redirects_when_empty_and_success_when_ids(self):
        """
        Verifica las operaciones masivas de eliminación documental, tanto cuando no se seleccionan documentos como cuando se eliminan 
        correctamente los elementos indicados.
        """
        empty = self.client.post("/admin/documents/bulk-delete", data={"selected_doc_ids": []}, follow_redirects=False)
        self.assertEqual(empty.status_code, 302)

        fake_service = MagicMock()
        with patch("app.main.code.controllers.admin.routes.documentos_service", return_value=fake_service):
            ok = self.client.post("/admin/documents/bulk-delete", data={"selected_doc_ids": ["1", "1"]}, follow_redirects=False)
        self.assertEqual(ok.status_code, 302)
        fake_service.delete_document.assert_called_once_with(1)

