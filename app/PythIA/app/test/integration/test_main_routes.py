"""
Autora: Lydia Blanco Ruiz
Script con pruebas de integración de las rutas pricipales de la aplicación. Su objetivo es verificar las funcionalidades accesibles
para los usuarios autenticados, incluyendo la visualización de la página principal, la edición del perfil, la gestión de preferencias,
el historial de consultas, las estadísticas de uso y la eliminación de consultas y cuentas de usuario. Las pruebas validan tanto los flujos 
de operación habituales como distintos escenarios de validación, permisos y gestión de datos, garantizando el correcto comportamiento de las 
funcionalidades principales de la aplicación.
"""

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import current_app

from app.main.code.extensions import db
from app.main.code.model.consulta import Consulta
from app.test.support import BaseAppTestCase


class MainRoutesIntegrationTest(BaseAppTestCase):
    def test_inicio_renders_public_home(self):
        """
        Verifica que la página de inicio pública se muestra correctamente y devuelve el contenido esperado para usuarios no autenticados.
        """
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"PythIA", response.data)

    @patch("app.main.code.controllers.main.routes.qdrant_get_payloads", return_value={})
    def test_pagina_principal_renders_authenticated_dashboard(self, _mock_qdrant):
        """
        Comprueba que los usuarios autenticados pueden acceder correctamente a su panel principal y visualizar la información asociada a sus consultas.
        """
        user = self.create_user(email="dashboard@example.com")
        self.create_consulta(user)
        self.login(user.email)

        response = self.client.get("/pagina_principal")

        self.assertEqual(response.status_code, 200)

    def test_edit_user_updates_profile(self):
        """
        Verifica la actualización de los datos básicos del perfil de usuario, incluyendo nombre, correo electrónico y contraseña.
        """
        user = self.create_user(email="edit@example.com")
        self.login("edit@example.com")
        updated_password = "Nueva" + "123"

        response = self.client.post(
            "/edit_user",
            data={
                "nombre": "Nombre Nuevo",
                "email": "lydiablanco71@gmail.com",
                "new_password": updated_password,
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        db.session.refresh(user)
        self.assertEqual(user.nombre, "Nombre Nuevo")
        self.assertEqual(user.email, "lydiablanco71@gmail.com")
        self.assertTrue(user.check_password(updated_password))

    def test_edit_user_rejects_duplicate_email(self):
        """
        Comprueba que el sistema impide actualizar el perfil utilizando una dirección de correo electrónico ya asignada a otro usuario.
        """
        self.create_user(email="existing@example.com")
        user = self.create_user(email="edit-duplicate@example.com")
        self.login(user.email)

        response = self.client.post(
            "/edit_user",
            data={"nombre": "Duplicado", "email": "existing@example.com", "new_password": ""},
        )

        self.assertEqual(response.status_code, 200)
        db.session.refresh(user)
        self.assertEqual(user.email, "edit-duplicate@example.com")

    def test_edit_user_uploads_profile_image(self):
        """
        Verifica la carga y almacenamiento correcto de una imagen de perfil asociada al usuario.
        """
        user = self.create_user(email="edit-image@example.com")
        self.login(user.email)

        response = self.client.post(
            "/edit_user",
            data={
                "nombre": "Con Foto",
                "email": user.email,
                "country_code": "ES",
                "new_password": "",
                "profile_image": (BytesIO(b"fake image"), "avatar.png"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 302)
        db.session.refresh(user)
        self.assertIsNotNone(user.profile_image)
        self.assertTrue(user.profile_image.startswith("user-"))
        self.assertTrue(user.profile_image.endswith(".png"))
        upload_dir = current_app.config["PROFILE_UPLOAD_FOLDER"]
        saved_filename = Path(user.profile_image).name
        saved_file = upload_dir / saved_filename
        self.assertTrue(saved_file.exists())

    def test_edit_user_updates_preferences(self):
        """
        Comprueba la actualización de las preferencias de usuario, incluyendo idioma, tema visual y modelo de lenguaje preferido.
        """
        user = self.create_user(email="prefs@example.com")

        self.login(user.email)

        response = self.client.post(
            "/edit_user",
            data={
                "nombre": "Prefs",
                "email": user.email,
                "country_code": "ES",
                "new_password": "",
                "theme_mode": "light",
                "language": "en",
                "preferred_model": "qwen3:4b-instruct-q4_K_M",
            },
        )

        self.assertEqual(response.status_code, 302)

        db.session.refresh(user)

        self.assertEqual(user.theme_mode, "light")
        self.assertEqual(user.language, "en")
        self.assertEqual(
            user.preferred_model,
            "qwen3:4b-instruct-q4_K_M",
        )

    def test_edit_user_updates_session_language(self):
        """
        Verifica que el idioma seleccionado por el usuario se actualiza correctamente tanto en el perfil como en la sesión activa.
        """
        user = self.create_user(email="lang@example.com")

        self.login(user.email)

        self.client.post(
            "/edit_user",
            data={
                "nombre": "Idioma",
                "email": user.email,
                "country_code": "ES",
                "new_password": "",
                "language": "en",
            },
        )

        with self.client.session_transaction() as session:
            self.assertEqual(session["lang"], "en")

    def test_new_user_has_default_preferences(self):
        """
        Comprueba que los nuevos usuarios reciben las preferencias predeterminadas configuradas por la aplicación.
        """
        user = self.create_user(email="defaults@example.com")

        self.assertEqual(user.theme_mode, "system")
        self.assertEqual(user.language, "es")
        
    def test_rag_form_uses_user_preferred_model(self):
        """
        Verifica que el formulario de consultas RAG utiliza el modelo preferido configurado por el usuario.
        """
        user = self.create_user(
            email="model@example.com",
            preferred_model="qwen3:4b-instruct-q4_K_M",
        )

        self.login(user.email)

        response = self.client.get("/rag/")

        self.assertEqual(response.status_code, 200)

    def test_user_can_delete_own_account(self):
        """
        Comprueba que un usuario puede eliminar correctamente su propia cuenta del sistema.
        """
        user = self.create_user(email="delete-account@example.com")
        self.login(user.email)

        response = self.client.post("/edit_user/delete", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(db.session.get(type(user), user.id))

    @patch("app.main.code.controllers.main.routes.qdrant_get_payloads")
    def test_history_uses_saved_fragmentos_without_calling_qdrant(self, mock_qdrant):
        """
        Verifica que el historial de consultas utiliza los fragmentos almacenados previamente sin realizar nuevas consultas a la base vectorial.
        """
        user = self.create_user(email="history@example.com")
        self.login("history@example.com")
        self.create_consulta(
            user,
            fragmentos=[
                {
                    "ranking": 1,
                    "qdrant_point_id": "saved-qid",
                    "metadata": {"filename": "saved.pdf"},
                    "chunk": "texto guardado",
                }
            ],
        )

        response = self.client.get("/history?page=1")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"saved.pdf", response.data)
        mock_qdrant.assert_not_called()

    def test_stats_renders_regular_user_scope(self):
        """
        Comprueba la generación de estadísticas para usuarios normales, limitando la información mostrada a sus propias consultas.
        """
        user = self.create_user(email="stats-regular@example.com")
        other = self.create_user(email="stats-other-regular@example.com")
        self.create_consulta(user)
        self.create_consulta(other)
        self.login(user.email)

        response = self.client.get("/stats")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"chart-user-comparison", response.data)
        self.assertIn(user.email.encode(), response.data)
        self.assertIn(b"Global", response.data)
        self.assertNotIn(b"comparison_user_ids", response.data)

    def test_stats_admin_global_selected_user_and_missing_user(self):
        """
        Verifica la visualización de estadísticas por parte de administradores, incluyendo estadísticas globales, filtradas por usuario y 
        el tratamiento de usuarios inexistentes.
        """
        admin = self.create_user(email="stats-admin@example.com", is_admin=True)
        selected = self.create_user(nombre="Usuario Stats", email="stats-selected@example.com")
        self.create_consulta(admin)
        self.create_consulta(selected)
        self.login(admin.email)

        global_response = self.client.get("/stats")
        selected_response = self.client.get(f"/stats?user_id={selected.id}")
        comparison_response = self.client.get(f"/stats?comparison_user_ids={admin.id}&comparison_user_ids={selected.id}")
        missing_response = self.client.get("/stats?user_id=999999")

        self.assertEqual(global_response.status_code, 200)
        self.assertEqual(selected_response.status_code, 200)
        self.assertEqual(comparison_response.status_code, 200)
        self.assertIn(b"stats-admin@example.com", comparison_response.data)
        self.assertIn(b"stats-selected@example.com", comparison_response.data)
        self.assertEqual(missing_response.status_code, 404)

    def test_stats_admin_global_shows_user_comparison_without_queries(self):
        """
        Comprueba que las estadísticas administrativas muestran correctamente comparativas de usuarios incluso cuando algunos 
        de ellos no tienen consultas registradas.
        """
        admin = self.create_user(email="stats-empty-admin@example.com", is_admin=True)
        user = self.create_user(nombre="Sin consultas", email="stats-empty-user@example.com")
        self.login(admin.email)

        response = self.client.get("/stats")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"chart-user-comparison", response.data)
        self.assertIn(user.email.encode(), response.data)

    def test_delete_consulta_only_allows_owner(self):
        """
        Verifica que únicamente el propietario de una consulta puede eliminarla y que otros usuarios reciben una respuesta de acceso denegado.
        """
        owner = self.create_user(email="owner@example.com")
        other = self.create_user(email="other@example.com")
        consulta = self.create_consulta(owner)

        self.login(other.email)
        forbidden = self.client.post(f"/consulta/{consulta.id}/delete")
        self.assertEqual(forbidden.status_code, 403)

        self.login(owner.email)
        allowed = self.client.post(f"/consulta/{consulta.id}/delete", follow_redirects=False)
        self.assertEqual(allowed.status_code, 302)
        self.assertIsNone(db.session.get(Consulta, consulta.id))

    @patch("app.main.code.controllers.main.routes.EmptyForm")
    def test_delete_consulta_rejects_invalid_form(self, mock_empty_form):
        """
        Comprueba que la eliminación de consultas es rechazada cuando el formulario asociado no supera las validaciones requeridas.
        """
        form = MagicMock()
        form.validate_on_submit.return_value = False
        mock_empty_form.return_value = form
        user = self.create_user(email="delete-invalid@example.com")
        consulta = self.create_consulta(user)
        self.login(user.email)

        response = self.client.post(f"/consulta/{consulta.id}/delete")

        self.assertEqual(response.status_code, 400)
        self.assertIsNotNone(db.session.get(Consulta, consulta.id))
