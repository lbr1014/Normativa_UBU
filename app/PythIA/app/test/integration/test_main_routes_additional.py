"""
Autora: Lydia Blanco Ruiz
Script con pruebas de integracion adicionales de las rutas principales de la aplicaicón (controllers.main.routes). Su objetivo es 
verificar escenarios menos frecuentes relacionados con la gestión de cuentas de usuario, la eliminación masiva de consultas, 
la visualización de imágenes de perfil y la validación de formularios de edición de usuario. 
Las pruebas cubren distintas situaciones de error, permisos y validaciones, reforzando la cobertura de las funcionalidades principales
accesibles para los usuarios autenticados.
"""

from unittest.mock import MagicMock, patch

from app.main.code.extensions import db
from app.main.code.model.consulta import Consulta
from app.test.support import BaseAppTestCase


class MainRoutesAdditionalCoverageIntegrationTest(BaseAppTestCase):
    def test_delete_own_account_invalid_form_and_missing_user(self):
        """
        Verifica el comportamiento de la eliminación de cuentas cuando el formulario es inválido o cuando el usuario asociado 
        ya no existe en el sistema.
        """
        user = self.create_user(email="del-own@example.com")
        self.login(user.email)

        bad_form = MagicMock()
        bad_form.validate_on_submit.return_value = False
        with patch("app.main.code.controllers.main.routes.EmptyForm", return_value=bad_form):
            res = self.client.post("/edit_user/delete")
        self.assertEqual(res.status_code, 400)

        ok_form = MagicMock()
        ok_form.validate_on_submit.return_value = True
        with patch("app.main.code.controllers.main.routes.EmptyForm", return_value=ok_form), patch(
            "app.main.code.controllers.main.routes.User.get_by_id", return_value=None
        ):
            res2 = self.client.post("/edit_user/delete")
        self.assertEqual(res2.status_code, 404)

    def test_bulk_delete_consultas_redirects_on_empty_and_403_on_missing_ids(self):
        """
        Comprueba las operaciones de eliminación masiva de consultas, validando escenarios con listas vacías, identificadores inexistentes,
        formularios inválidos y eliminaciones correctas.
        """
        user = self.create_user(email="bulk-del@example.com")
        self.login(user.email)
        consulta = self.create_consulta(user)

        ok_form = MagicMock()
        ok_form.validate_on_submit.return_value = True
        with patch("app.main.code.controllers.main.routes.EmptyForm", return_value=ok_form):
            empty = self.client.post("/history/delete", data={"selected_consulta_ids": []}, follow_redirects=False)
        self.assertEqual(empty.status_code, 302)

        with patch("app.main.code.controllers.main.routes.EmptyForm", return_value=ok_form):
            forbidden = self.client.post(
                "/history/delete",
                data={"selected_consulta_ids": [str(consulta.id), "999999"]},
                follow_redirects=False,
            )
        self.assertEqual(forbidden.status_code, 403)
        self.assertIsNotNone(db.session.get(Consulta, consulta.id))

        bad_form = MagicMock()
        bad_form.validate_on_submit.return_value = False
        with patch("app.main.code.controllers.main.routes.EmptyForm", return_value=bad_form):
            bad = self.client.post(
                "/history/delete",
                data={"selected_consulta_ids": [str(consulta.id)]},
                follow_redirects=False,
            )
        self.assertEqual(bad.status_code, 400)

        with patch("app.main.code.controllers.main.routes.EmptyForm", return_value=ok_form):
            ok = self.client.post(
                "/history/delete",
                data={"selected_consulta_ids": [str(consulta.id)]},
                follow_redirects=False,
            )
        self.assertEqual(ok.status_code, 302)
        self.assertIsNone(db.session.get(Consulta, consulta.id))

    def test_profile_image_route_uses_send_from_directory(self):
        """
        Verifica que las imágenes de perfil almacenadas en el sistema pueden recuperarse correctamente mediante la ruta 
        pública correspondiente.
        """
        user = self.create_user(email="profile-img@example.com")
        self.login(user.email)
        # Se reutiliza el upload folder temporal configurado por BaseAppTestCase.
        upload_dir = self.app.config["PROFILE_UPLOAD_FOLDER"]
        path = upload_dir / "x.png"
        path.write_bytes(b"img")
        res = self.client.get("/profile_image/x.png")
        self.assertEqual(res.status_code, 200)
        res.close()

    def test_edit_user_renders_when_apply_form_returns_false(self):
        """
        Comprueba que el formulario de edición de usuario vuelve a mostrarse correctamente cuando la aplicación de los cambios
        solicitados no puede completarse.
        """
        user = self.create_user(email="edit-user@example.com")
        self.login(user.email)

        with patch("app.main.code.controllers.main.routes.EditUserForm") as mock_form, patch(
            "app.main.code.controllers.main.routes._apply_edit_user_form",
            return_value=False,
        ):
            mock_form.return_value.validate_on_submit.return_value = True
            res = self.client.post("/edit_user", data={"email": "x@example.com"})

        self.assertEqual(res.status_code, 200)
