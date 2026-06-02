"""
Autora: Lydia Blanco Ruiz
Script con pruebas unitarias de formularios. Su objetivo es verificar la correcta validación de datos introducidos por los usuarios, 
la localización de etiquetas y mensajes de error, la gestión de formularios de autenticación, administración de usuarios, 
carga de documentos, consultas RAG y recuperación de contraseñas. Además, incluye pruebas relacionadas con la integración del servicio 
de validación de correos electrónicos mediante Emailable. Las pruebas garantizan que los formularios aplican correctamente las reglas de 
validación y presentan mensajes coherentes al usuario.
"""

import secrets
import string
from types import SimpleNamespace
from unittest.mock import patch

from wtforms.validators import ValidationError

from app.main.code.forms import (
    AdminCreateUserForm,
    EditUserForm,
    EmptyForm,
    ForgotPasswordForm,
    LanguageForm,
    LoginForm,
    PdfUploadForm,
    RAGDefaultQueryForm,
    RAGQueryForm,
    ResetPasswordForm,
    SignupForm,
    _validate_email_with_emailable,
)
from app.main.code.inetrnacionalizacion.tarduccion import t
from app.test.support import BaseAppTestCase


def _random_str(chars, length):
    return "".join(secrets.choice(chars) for _ in range(length))


def _strong_password():
    return "Aa1" + secrets.token_urlsafe(12)


def _weak_password_all_lowercase():
    return _random_str(string.ascii_lowercase, 16)


def _too_short_password():
    return _random_str(string.digits, 3)


class FormTestMixin:
    def _form(self, form_class, data=None):
        """
        Helper para crear formularios dentro del contexto de la aplicación.
        """
        with self.app.test_request_context("/", method="POST", data=data or {}):
            return form_class()

    def assert_form_valid(self, form_class, data=None):
        """
        Helper para verificar que un formulario es válido con los datos proporcionados.
        """
        with self.app.test_request_context("/", method="POST", data=data or {}):
            form = form_class()
            self.assertTrue(form.validate(), form.errors)
            return form

    def assert_form_invalid(self, form_class, data=None, field=None):
        """
        Helper para verificar que un formulario es inválido con los datos proporcionados.
        """
        with self.app.test_request_context("/", method="POST", data=data or {}):
            form = form_class()
            self.assertFalse(form.validate())
            if field:
                self.assertIn(field, form.errors)
            return form


class EmptyFormUnitTest(FormTestMixin, BaseAppTestCase):
    def test_empty_form_validates_without_fields(self):
        """
        Verifica que un formulario vacío puede validarse correctamente cuando no contiene campos propios.
        """
        form = self.assert_form_valid(EmptyForm)

        own_fields = [field for field in form if field.type != "CSRFTokenField"]
        self.assertEqual(own_fields, [])


class LanguageFormUnitTest(FormTestMixin, BaseAppTestCase):
    def test_language_form_requires_lang_and_accepts_next_url(self):
        """
        Comprueba que el formulario de selección de idioma exige un idioma válido y admite una URL de redirección posterior.
        """
        self.assert_form_invalid(LanguageForm, {"next": "/rag"}, "lang")

        form = self.assert_form_valid(LanguageForm, {"lang": "en", "next": "/rag"})
        self.assertEqual(form.lang.data, "en")
        self.assertEqual(form.next.data, "/rag")


class PdfUploadFormUnitTest(FormTestMixin, BaseAppTestCase):
    def test_pdf_upload_form_localizes_labels(self):
        """
        Verifica que las etiquetas del formulario de carga de documentos se traducen correctamente según el idioma activo.
        """
        form = self._form(PdfUploadForm)

        self.assertEqual(form.files.label.text, t("docs.upload_label"))
        self.assertEqual(form.submit.label.text, t("docs.upload_button"))

    def test_validate_files_requires_at_least_one_file(self):
        """
        Comprueba que es obligatorio seleccionar al menos un archivo para realizar una carga documental.
        """
        field = SimpleNamespace(data=[])

        with self.assertRaises(ValidationError) as raised:
            PdfUploadForm.validate_files(None, field)

        self.assertEqual(str(raised.exception), t("docs.upload_pdf_required"))

    def test_validate_files_rejects_non_pdf_files(self):
        """
        Verifica que se rechazan archivos que no tienen formato PDF.
        """
        field = SimpleNamespace(data=[SimpleNamespace(filename="notas.txt")])

        with self.assertRaises(ValidationError) as raised:
            PdfUploadForm.validate_files(None, field)

        self.assertEqual(str(raised.exception), t("docs.upload_pdf_invalid"))

    def test_validate_files_accepts_pdf_files_case_insensitively(self):
        """
        Comprueba que los archivos PDF son aceptados independientemente del uso de mayúsculas o minúsculas en la extensión.
        """
        field = SimpleNamespace(data=[SimpleNamespace(filename="contrato.PDF")])

        PdfUploadForm.validate_files(None, field)


class LoginFormUnitTest(FormTestMixin, BaseAppTestCase):
    def test_login_form_validates_credentials_shape_and_localizes_messages(self):
        """
        Verifica la validación de credenciales de acceso y la correcta traducción de etiquetas y mensajes de error.
        """
        self.assert_form_valid(LoginForm, {"email": "user@example.com", "password": _strong_password()})

        form = self.assert_form_invalid(LoginForm, {"email": "mal-email", "password": _too_short_password()}, "email")
        self.assertIn("password", form.errors)
        self.assertEqual(form.email.label.text, t("common.email"))
        self.assertEqual(form.password.label.text, t("common.password"))
        self.assertEqual(form.email.errors[0], t("validation.email"))
        self.assertEqual(form.password.errors[0], t("validation.min_length_6"))


class SignupFormUnitTest(FormTestMixin, BaseAppTestCase):
    def test_country_choices_follow_active_language(self):
        """
        Comprueba que la lista de países mostrada en el formulario se adapta al idioma seleccionado por el usuario.
        """
        with self.app.test_request_context("/", method="GET"):
            form = SignupForm()
            self.assertIn(("ES", "España"), form.country_code.choices)

        with self.app.test_request_context("/", method="GET"):
            from flask import session

            session["lang"] = "en"
            form = SignupForm()
            self.assertIn(("ES", "Spain"), form.country_code.choices)

    def test_signup_form_validates_secure_matching_passwords(self):
        """
        Verifica la validación de contraseñas seguras y la coincidencia entre contraseña y confirmación durante el registro.
        """
        password = _strong_password()
        form = self.assert_form_valid(
            SignupForm,
            {
                "nombre": "Lydia",
                "email": "lydiablanco71@gmail.com",
                "password": password,
                "confirm_password": password,
            },
        )
        self.assertEqual(form.country_code.data, "ES")

        mismatch = self.assert_form_invalid(
            SignupForm,
            {
                "nombre": "Lydia",
                "email": "lydiablanco71@gmail.com",
                "password": password,
                "confirm_password": _strong_password(),
            },
            "confirm_password",
        )
        self.assertEqual(mismatch.confirm_password.errors[0], t("auth.password_mismatch"))

        weak_password = _weak_password_all_lowercase()
        weak = self.assert_form_invalid(
            SignupForm,
            {
                "nombre": "Lydia",
                "email": "lydia@example.com",
                "password": weak_password,
                "confirm_password": weak_password,
            },
            "password",
        )
        self.assertIn(t("validation.password_security"), weak.password.errors)


class AdminCreateUserFormUnitTest(FormTestMixin, BaseAppTestCase):
    def test_admin_create_user_form_validates_user_data_and_admin_flag(self):
        """
        Comprueba la validación de los datos necesarios para crear usuarios desde el panel de administración y la correcta gestión del rol de administrador.
        """
        form = self.assert_form_valid(
            AdminCreateUserForm,
            {
                "nombre": "Admin",
                "email": "admin@example.com",
                "password": _strong_password(),
                "is_admin": "y",
            },
        )

        self.assertTrue(form.is_admin.data)
        self.assertEqual(form.country_code.data, "ES")
        self.assertEqual(form.is_admin.label.text, t("admin.is_admin"))

        invalid = self.assert_form_invalid(
            AdminCreateUserForm,
            {"nombre": "A", "email": "admin@example.com", "password": _weak_password_all_lowercase()},
        )
        self.assertIn("nombre", invalid.errors)
        self.assertIn("password", invalid.errors)


class EditUserFormUnitTest(FormTestMixin, BaseAppTestCase):
    def test_edit_user_form_accepts_empty_optional_fields_and_validates_values_when_present(self):
        """
        Verifica que los campos opcionales pueden dejarse vacíos y que los valores proporcionados se validan correctamente cuando existen.
        """
        form = self.assert_form_valid(EditUserForm, {})

        self.assertEqual(form.country_code.data, "ES")
        self.assertEqual(form.new_password.render_kw["placeholder"], t("user.leave_empty_password"))

        invalid = self.assert_form_invalid(
            EditUserForm,
            {"nombre": "A", "email": "mal-email", "new_password": _weak_password_all_lowercase()},
        )
        self.assertIn("nombre", invalid.errors)
        self.assertIn("email", invalid.errors)
        self.assertIn("new_password", invalid.errors)

    def test_edit_user_form_validate_email(self):
        """
        Comprueba que la validación del correo electrónico no genera errores cuando el campo se encuentra vacío.
        """
        with self.app.test_request_context("/", method="POST", data={}):
            form = EditUserForm()
            form.validate_email(SimpleNamespace(data=None))


class EmailableValidationUnitTest(BaseAppTestCase):
    def test_validate_email_with_emailable_returns_when_api_key_missing(self):
        """
        Verifica que la validación externa de correos se omite cuando no existe una clave de acceso configurada para Emailable.
        """
        with self.app.test_request_context("/", method="POST"):
            self.app.config["EMAILABLE_API_KEY"] = ""
            _validate_email_with_emailable(SimpleNamespace(data="user@example.com"))

    def test_validate_email_with_emailable_returns_when_email_empty(self):
        """
        Comprueba que no se realizan verificaciones externas cuando el campo de correo electrónico está vacío.
        """
        with self.app.test_request_context("/", method="POST"):
            self.app.config["EMAILABLE_API_KEY"] = "key"
            with patch("app.main.code.forms.verify_email") as mock_verify:
                _validate_email_with_emailable(SimpleNamespace(data=""))
        mock_verify.assert_not_called()


class RAGQueryFormUnitTest(FormTestMixin, BaseAppTestCase):
    def test_rag_query_form_requires_question_and_limits_length(self):
        """
        Verifica que las consultas RAG requieren una pregunta válida y respetan las restricciones de longitud definidas.
        """
        self.assert_form_valid(RAGQueryForm, {"question": "Que documentos hay disponibles?"})

        required = self.assert_form_invalid(RAGQueryForm, {"question": ""}, "question")
        self.assertEqual(required.question.errors[0], t("validation.required"))

        too_long = self.assert_form_invalid(RAGQueryForm, {"question": "a" * 2001}, "question")
        self.assertEqual(too_long.question.errors[0], t("validation.max_length_2000"))
        self.assertEqual(too_long.question.render_kw["placeholder"], t("rag.question_placeholder"))


class RAGDefaultQueryFormUnitTest(FormTestMixin, BaseAppTestCase):
    def test_rag_default_query_form_accepts_guided_fields_and_requires_built_question(self):
        """
        Comprueba la validación de consultas guiadas, incluyendo filtros documentales y tipos de preguntas predefinidos.
        """
        with self.app.test_request_context(
            "/",
            method="POST",
            data={
                "expediente": "",
                "doc_type": "administrativo",
                "question_kind": "amounts",
                "question": "Para los pliegos disponibles, extrae cantidades.",
            },
        ):
            valid = RAGDefaultQueryForm()
            valid.expediente.choices = [("", "General")]
            valid.doc_type.choices = [("", "Cualquiera"), ("administrativo", "Administrativo")]
            valid.question_kind.choices = [("amounts", "Cantidades")]
            valid.model.choices = []
            self.assertTrue(valid.validate(), valid.errors)

        self.assertEqual(valid.doc_type.data, "administrativo")
        self.assertEqual(valid.question_kind.data, "amounts")

        invalid = self.assert_form_invalid(RAGDefaultQueryForm, {"question": ""}, "question")
        self.assertEqual(invalid.question.errors[0], t("validation.required"))


class ForgotPasswordFormUnitTest(FormTestMixin, BaseAppTestCase):
    def test_forgot_password_form_validates_email(self):
        """
        Verifica la validación del correo electrónico utilizado para solicitar la recuperación de contraseña.
        """
        form = self.assert_form_valid(ForgotPasswordForm, {"email": "user@example.com"})
        self.assertEqual(form.submit.label.text, t("auth.forgot_password_submit"))

        invalid = self.assert_form_invalid(ForgotPasswordForm, {"email": "mal-email"}, "email")
        self.assertEqual(invalid.email.errors[0], t("validation.email"))


class ResetPasswordFormUnitTest(FormTestMixin, BaseAppTestCase):
    def test_reset_password_form_validates_security_and_confirmation(self):
        """
        Comprueba la validación de la nueva contraseña, incluyendo requisitos de seguridad y confirmación correcta de la misma.
        """
        password = _strong_password()
        self.assert_form_valid(ResetPasswordForm, {"password": password, "confirm_password": password})

        mismatch = self.assert_form_invalid(
            ResetPasswordForm,
            {"password": password, "confirm_password": _strong_password()},
            "confirm_password",
        )
        self.assertEqual(mismatch.confirm_password.errors[0], t("auth.password_mismatch"))

        weak_password = _weak_password_all_lowercase()
        weak = self.assert_form_invalid(ResetPasswordForm, {"password": weak_password, "confirm_password": weak_password}, "password")
        self.assertIn(t("validation.password_security"), weak.password.errors)
