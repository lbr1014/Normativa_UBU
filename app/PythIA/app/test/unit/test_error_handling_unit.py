"""
Autora: Lydia Blanco Ruiz
Script con pruebas unitarias de gestión de errores de la aplicación. Su objetivo es verificar el funcionamiento de 
los validadores de seguridad de contraseñas, la recopilación y formateo de errores de formularios, la detección del 
formato de respuesta solicitado por el cliente (HTML o JSON), la generación de respuestas de error y el registro de los 
manejadores globales de excepciones en Flask. Las pruebas garantizan que la aplicación proporciona mensajes de error consistentes 
y adecuados tanto para interfaces web como para llamadas API.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from wtforms.validators import ValidationError

from app.main.code.error_handling import (
    PasswordSecurity,
    collect_form_errors,
    register_error_handlers,
    render_error_response,
    wants_json_response,
)
from app.test.support import BaseAppTestCase


class PasswordSecurityUnitTest(BaseAppTestCase):
    def test_password_security_allows_empty_optional_values(self):
        """
        Verifica que el validador de seguridad de contraseñas permite valores vacíos cuando el campo es opcional.
        """
        validator = PasswordSecurity()

        validator(None, SimpleNamespace(data=""))

    def test_password_security_rejects_missing_required_character_classes(self):
        """
        Comprueba que se rechazan contraseñas que no cumplen los requisitos mínimos de seguridad definidos por 
        el validador, como la ausencia de mayúsculas, dígitos o caracteres especiales.
        """
        validator = PasswordSecurity(message="Password insegura")

        with self.assertRaises(ValidationError) as raised:
            validator(None, SimpleNamespace(data="sinmayusculas"))

        self.assertEqual(str(raised.exception), "Password insegura")

    def test_password_security_allows_custom_rules(self):
        """
        Verifica el funcionamiento del validador cuando se utilizan reglas de seguridad personalizadas.
        """
        validator = PasswordSecurity(require_upper=False, require_digit=False)

        validator(None, SimpleNamespace(data="minusculas"))


class FormErrorHandlingUnitTest(BaseAppTestCase):
    def test_collect_form_errors_skips_csrf_and_uses_label_text(self):
        """
        Comprueba que la recopilación de errores de formularios ignora los campos CSRF y utiliza etiquetas descriptivas 
        para presentar los errores al usuario.
        """
        csrf = SimpleNamespace(type="CSRFTokenField", errors=["csrf"], name="csrf", label=SimpleNamespace(text="CSRF"))
        email = SimpleNamespace(
            type="StringField",
            errors=["Email invalido"],
            name="email",
            label=SimpleNamespace(text="Correo"),
        )

        self.assertEqual(
            collect_form_errors([csrf, email]),
            [{"field": "Correo", "message": "Email invalido"}],
        )

    def test_collect_form_errors_handles_empty_form(self):
        """
        Verifica que la recopilación de errores funciona correctamente cuando el formulario está vacío o no existe.
        """
        self.assertEqual(collect_form_errors(None), [])


class ErrorResponseUnitTest(BaseAppTestCase):
    def test_wants_json_response_for_rag_json_and_accept_header(self):
        """
        Comprueba que el sistema detecta correctamente cuándo debe generar respuestas JSON en función de la ruta,
        el contenido de la petición o las cabeceras HTTP.
        """
        with self.app.test_request_context("/rag/ask"):
            self.assertTrue(wants_json_response())

        with self.app.test_request_context("/x", json={"a": 1}):
            self.assertTrue(wants_json_response())

        with self.app.test_request_context("/x", headers={"Accept": "application/json"}):
            self.assertTrue(wants_json_response())

    @patch("app.main.code.error_handling.render_template", return_value="<html>Error</html>")
    @patch("app.main.code.error_handling.t", side_effect=lambda key: key)
    def test_render_error_response_uses_template_for_html(self, _mock_t, mock_render):
        """
        Verifica que las respuestas de error se renderizan mediante plantillas HTML cuando el cliente solicita contenido web.
        """
        with self.app.test_request_context("/missing", headers={"Accept": "text/html"}):
            body, status = render_error_response(404, "title.key", "message.key")

        self.assertEqual(status, 404)
        self.assertEqual(body, "<html>Error</html>")
        mock_render.assert_called_once()

    @patch("app.main.code.error_handling.t", side_effect=lambda key: key)
    def test_render_error_response_uses_json_when_requested(self, _mock_t):
        """
        Comprueba que las respuestas de error se generan en formato JSON cuando el cliente realiza una petición orientada a API.
        """
        with self.app.test_request_context("/rag/status"):
            response, status = render_error_response(400, "title.key", "message.key")

        self.assertEqual(status, 400)
        self.assertEqual(response.get_json()["error"], "message.key")

    def test_register_error_handlers_registers_context_processor_and_handlers(self):
        """
        Verifica que los procesadores de contexto y manejadores globales de errores se registran correctamente durante la inicialización de la aplicación.
        """
        app = MagicMock()
        app.context_processor.side_effect = lambda func: func
        app.errorhandler.side_effect = lambda code: (lambda func: func)

        register_error_handlers(app)

        app.context_processor.assert_called_once()
        self.assertEqual(app.errorhandler.call_count, 4)
