"""
Autora: Lydia Blanco Ruiz
Script con pruebas de integracion de las rutas RAG. Su objetivo es verificar el funcionamiento completo del sistema de consultas 
basadas en Retrieval-Augmented Generation, incluyendo la visualización de formularios, la creación y reutilización de tareas asíncronas, 
la construcción de preguntas guiadas, la validación de consultas, la comparación de modelos, la consulta de estados y la cancelación de trabajos.
Las pruebas cubren tanto escenarios de uso normales como situaciones de error, permisos y cancelaciones, garantizando el correcto comportamiento 
del flujo de consulta RAG de extremo a extremo.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from flask_login import login_user

from app.main.code.extensions import db
from app.main.code.model.rag_query_state import RAGQueryState
from app.test.support import BaseAppTestCase


class RAGRoutesIntegrationTest(BaseAppTestCase):
    def setUp(self):
        """
        Inicializa el entorno de pruebas creando un usuario autenticado que será utilizado durante la ejecución de las pruebas de las rutas RAG.
        """
        super().setUp()
        self.user = self.create_user(email="rag@example.com")
        self.login(self.user.email)

    def test_rag_page_requires_login_and_renders_for_authenticated_user(self):
        """
        Verifica que la página principal de consultas RAG está disponible para usuarios autenticados y muestra correctamente el formulario de consulta.
        """
        response = self.client.get("/rag/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<form", response.data)

    def test_model_comparison_page_renders_with_user_scope_stats(self):
        """
        Comprueba que la página de comparación de modelos muestra correctamente estadísticas asociadas a las consultas realizadas por el usuario.
        """
        job = RAGQueryState(
            user_id=self.user.id,
            question="Pregunta con tokens",
            model_name="modelo-a",
            status="done",
            result_payload={"answer": "Respuesta", "execution_device": "GPU", "total_tokens": 12},
        )
        db.session.add(job)
        db.session.commit()

        response = self.client.get("/rag/modelos")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"modelo-a", response.data)

    def test_model_comparison_payload_aggregates_admin_and_fallback_values(self):
        """
        Verifica la generación de estadísticas agregadas de modelos para administradores, incluyendo tiempos de respuesta, dispositivos de
        ejecución y consumo de tokens.
        """
        from app.main.code.controllers.rag import routes as rag_routes

        admin = self.create_user(email="admin-rag@example.com", is_admin=True)
        other = self.create_user(email="other-rag@example.com")
        base = RAGQueryState(
            user_id=self.user.id,
            question="Una pregunta",
            model_name=None,
            status="done",
            result_payload={"model": "modelo-b", "answer": "Dos palabras", "execution_device": "CPU"},
        )
        base.finished_at = base.created_at + timedelta(seconds=4)
        usage = RAGQueryState(
            user_id=other.id,
            question="Otra",
            model_name="modelo-c",
            status="done",
            result_payload={"usage": {"total_tokens": 7}, "execution_device": "desconocido"},
        )
        usage.started_at = usage.created_at + timedelta(seconds=1)
        usage.finished_at = usage.started_at + timedelta(seconds=3)
        db.session.add_all([base, usage])
        db.session.commit()

        with self.app.test_request_context("/rag/modelos"):
            login_user(admin)
            payload = rag_routes.build_model_comparison_payload()

        self.assertEqual(payload["scope"], "global")
        self.assertEqual(payload["summary"]["models"], 2)
        by_model = {item["model"]: item for item in payload["models"]}
        self.assertEqual(by_model["modelo-b"]["cpu"], 1)
        self.assertEqual(by_model["modelo-b"]["avg_time"], 4.0)
        self.assertGreater(by_model["modelo-b"]["tokens"], 0)
        self.assertEqual(by_model["modelo-c"]["unknown_device"], 1)
        self.assertEqual(by_model["modelo-c"]["tokens"], 7)

    def test_model_comparison_payload_handles_empty_user_scope_and_token_keys(self):
        """
        Comprueba la generación de estadísticas cuando no existen consultas registradas y valida los mecanismos auxiliares de extracción 
        de tokens y tiempos de respuesta.
        """
        from app.main.code.controllers.rag import routes as rag_routes

        self.assertEqual(rag_routes.extract_token_count(RAGQueryState(user_id=1, question=""), {"tokens": 3}), 3)
        self.assertEqual(rag_routes.extract_token_count(RAGQueryState(user_id=1, question=""), {"eval_count": 4}), 4)
        self.assertEqual(rag_routes.extract_response_time(RAGQueryState(user_id=1, question=""), {"elapsed_s": 1.5}), 1.5)
        self.assertEqual(rag_routes.extract_response_time(RAGQueryState(user_id=1, question=""), {}), None)

        with self.app.test_request_context("/rag/modelos"):
            login_user(self.user)
            payload = rag_routes.build_model_comparison_payload()

        self.assertEqual(payload["scope"], "global")
        self.assertEqual(payload["summary"]["models"], 0)
        self.assertEqual(payload["models"], [])

    def test_rag_json_routes_return_json_when_unauthenticated(self):
        """
        Verifica que las rutas JSON del sistema RAG devuelven respuestas de error estructuradas cuando el usuario no está autenticado.
        """
        self.client.post("/logout")

        response = self.client.post(
            "/rag/ask",
            data={"question": "Que dice el pliego?"},
            headers={"Accept": "application/json"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content_type, "application/json")
        self.assertIn("error", response.get_json())

    @patch("app.main.code.controllers.rag.routes.executor.submit")
    def test_rag_ask_creates_queued_job(self, mock_submit):
        """
        Comprueba que una nueva consulta RAG genera correctamente una tarea asíncrona en estado de cola.
        """
        response = self.client.post("/rag/ask", data={"question": "Que dice el pliego?"})

        self.assertEqual(response.status_code, 202)
        job_id = response.get_json()["job_id"]
        job = db.session.get(RAGQueryState, job_id)
        self.assertEqual(job.user_id, self.user.id)
        self.assertEqual(job.status, "queued")
        mock_submit.assert_called_once()

    @patch("app.main.code.controllers.rag.routes.executor.submit")
    def test_rag_ask_builds_guided_question_on_server(self, mock_submit):
        """
        Verifica la construcción automática de preguntas guiadas a partir de los parámetros seleccionados por el usuario.
        """
        self.create_document(numero_expediente="EXP-55")

        response = self.client.post(
            "/rag/ask",
            data={
                "question": "",
                "expediente": "EXP-55",
                "doc_type": "tecnico",
                "question_kind": "amounts",
                "model": "fake-model",
            },
        )

        self.assertEqual(response.status_code, 202)
        job = db.session.get(RAGQueryState, response.get_json()["job_id"])
        self.assertIn("expediente EXP-55", job.question)
        self.assertIn("doc_type=tecnico", job.question)
        self.assertIn("cantidades economicas", job.question)
        self.assertEqual(job.model_name, "fake-model")
        mock_submit.assert_called_once()

    @patch("app.main.code.controllers.rag.routes.executor.submit")
    def test_rag_ask_builds_summary_guided_question_and_ignores_locked_fields(self, mock_submit):
        """
        Comprueba la generación de preguntas orientadas a resúmenes generales y el tratamiento adecuado de parámetros incompatibles o bloqueados.
        """
        self.create_document(numero_expediente="EXP-77")

        response = self.client.post(
            "/rag/ask",
            data={
                "question": "",
                "expediente": "EXP-77",
                "summary": "y",
                "model": "fake-model",
            },
        )

        self.assertEqual(response.status_code, 202)
        job = db.session.get(RAGQueryState, response.get_json()["job_id"])
        self.assertIn("expediente EXP-77", job.question)
        self.assertIn("resumen general y detallado", job.question)
        self.assertNotIn("pliego tecnico", job.question)
        mock_submit.assert_called_once()

    def test_rag_ask_rejects_invalid_form(self):
        """
        Verifica que las consultas con formularios inválidos son rechazadas antes de iniciar el procesamiento RAG.
        """
        response = self.client.post("/rag/ask", data={"question": ""})

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    @patch("app.main.code.controllers.rag.routes.validate_question", return_value={"answer": "Pregunta no valida"})
    def test_rag_ask_rejects_service_validation_error(self, _mock_validate_question):
        """
        Comprueba que los errores de validación generados por el servicio RAG son devueltos correctamente al usuario.
        """
        response = self.client.post("/rag/ask", data={"question": "Pregunta formalmente valida"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Pregunta no valida")

    @patch("app.main.code.controllers.rag.routes.executor.submit")
    def test_rag_ask_reuses_active_job_for_same_user(self, mock_submit):
        """
        Verifica que el sistema reutiliza una tarea activa existente cuando el usuario ya tiene una consulta en ejecución.
        """
        active_job = RAGQueryState(user_id=self.user.id, question="Anterior", status="running")
        db.session.add(active_job)
        db.session.commit()

        response = self.client.post("/rag/ask", data={"question": "Nueva pregunta"})

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()["job_id"], active_job.id)
        self.assertTrue(response.get_json()["reused"])
        mock_submit.assert_not_called()

    @patch("app.main.code.controllers.rag.routes.executor.submit")
    def test_rag_ask_does_not_reuse_active_job_when_cancel_requested(self, mock_submit):
        """
        Comprueba que las tareas marcadas para cancelación no son reutilizadas y se crea una nueva consulta independiente.
        """
        active_job = RAGQueryState(
            user_id=self.user.id,
            question="Anterior",
            status="running",
            cancel_requested=True,
        )
        db.session.add(active_job)
        db.session.commit()

        response = self.client.post("/rag/ask", data={"question": "Nueva pregunta"})

        self.assertEqual(response.status_code, 202)
        self.assertNotEqual(response.get_json()["job_id"], active_job.id)
        self.assertNotIn("reused", response.get_json())
        mock_submit.assert_called_once()

    def test_rag_status_only_allows_owner(self):
        """
        Verifica que únicamente el propietario de una consulta puede acceder a la información de estado y resultados asociados.
        """
        owner = self.create_user(email="owner-rag@example.com")
        job = RAGQueryState(
            user_id=owner.id,
            question="Privada",
            status="done",
            message="Lista",
            result_payload={"answer": "ok"},
        )
        db.session.add(job)
        db.session.commit()

        forbidden = self.client.get(f"/rag/status/{job.id}")
        self.assertEqual(forbidden.status_code, 404)

        self.login(owner.email)
        allowed = self.client.get(f"/rag/status/{job.id}")
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.get_json()["result"], {"answer": "ok"})

    def test_rag_cancel_marks_queued_job_as_cancelled(self):
        """
        Comprueba que la cancelación de tareas en cola actualiza correctamente su estado y registra la finalización de la operación.
        """
        job = RAGQueryState(user_id=self.user.id, question="Cancelar", status="queued", message="En cola")
        db.session.add(job)
        db.session.commit()

        response = self.client.post(f"/rag/cancel/{job.id}")

        self.assertEqual(response.status_code, 202)
        db.session.refresh(job)
        self.assertTrue(job.cancel_requested)
        self.assertEqual(job.status, "cancelled")
        self.assertIsNotNone(job.finished_at)

    @patch("app.main.code.controllers.rag.routes.EmptyForm")
    def test_rag_cancel_rejects_invalid_form(self, mock_empty_form):
        """
        Verifica que las solicitudes de cancelación son rechazadas cuando el formulario asociado no supera las validaciones requeridas.
        """
        form = MagicMock()
        form.validate_on_submit.return_value = False
        mock_empty_form.return_value = form
        job = RAGQueryState(user_id=self.user.id, question="Cancelar", status="queued", message="En cola")
        db.session.add(job)
        db.session.commit()

        response = self.client.post(f"/rag/cancel/{job.id}")

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_rag_cancel_running_job_keeps_running_and_requests_cancel(self):
        """
        Comprueba que las tareas en ejecución permanecen activas mientras se marca correctamente la solicitud de cancelación pendiente.
        """
        job = RAGQueryState(user_id=self.user.id, question="Cancelar", status="running", message="Procesando")
        db.session.add(job)
        db.session.commit()

        response = self.client.post(f"/rag/cancel/{job.id}")

        self.assertEqual(response.status_code, 202)
        db.session.refresh(job)
        self.assertTrue(job.cancel_requested)
        self.assertEqual(job.status, "running")
        self.assertIsNone(job.finished_at)

    def test_rag_cancel_finished_job_is_idempotent(self):
        """
        Verifica que la cancelación de tareas ya finalizadas no modifica su estado y devuelve una respuesta consistente.
        """
        job = RAGQueryState(user_id=self.user.id, question="Hecha", status="done", message="Lista")
        db.session.add(job)
        db.session.commit()

        response = self.client.post(f"/rag/cancel/{job.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "done")
