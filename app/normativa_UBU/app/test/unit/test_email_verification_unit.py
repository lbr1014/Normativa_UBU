"""
Autora: Lydia Blanco Ruiz
Script con pruebas unitarias del servicio de verificación de direcciones de correo electrónico basado en la API de Emailable. 
Su objetivo es verificar el comportamiento del sistema ante distintas situaciones relacionadas con la validación de correos, 
incluyendo la ausencia de configuración de la API, errores de comunicación con el servicio externo y
respuestas inválidas recibidas desde la plataforma de verificación. 
Las pruebas garantizan que el servicio gestiona adecuadamente los errores y devuelve estados consistentes para su posterior 
tratamiento en la aplicación.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests
from flask import Flask

from app.main.code.services.email_verification import verify_email


class EmailVerificationUnitTest(unittest.TestCase):
    def test_verify_email_skips_when_api_key_missing(self):
        """
        Verifica que la validación de correos se omite correctamente cuando no existe una clave de acceso configurada para la API de Emailable.
        """
        app = Flask(__name__)
        app.config["EMAILABLE_API_KEY"] = ""
        with app.app_context():
            self.assertEqual(
                verify_email("user@example.com"),
                {"state": "skipped", "reason": "missing_api_key"},
            )

    def test_verify_email_returns_error_on_request_exception(self):
        """
        Comprueba que el servicio devuelve un estado de error cuando se produce una excepción 
        durante la comunicación con la API externa de verificación.
        """
        app = Flask(__name__)
        app.config["EMAILABLE_API_KEY"] = "key"
        with app.app_context(), patch(
            "app.main.code.services.email_verification.requests.get",
            side_effect=requests.RequestException("network"),
        ):
            out = verify_email("user@example.com")

        self.assertEqual(out["state"], "error")

    def test_verify_email_returns_error_when_payload_is_not_dict(self):
        """
        Verifica que se detectan respuestas con formatos inválidos y se devuelve el estado de error correspondiente cuando los datos 
        recibidos no tienen la estructura esperada.
        """
        app = Flask(__name__)
        app.config["EMAILABLE_API_KEY"] = "key"
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = ["not-a-dict"]
        with app.app_context(), patch(
            "app.main.code.services.email_verification.requests.get",
            return_value=resp,
        ):
            out = verify_email("user@example.com")

        self.assertEqual(out["state"], "error")
