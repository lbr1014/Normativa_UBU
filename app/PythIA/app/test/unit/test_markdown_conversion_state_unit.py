"""
Autora: Lydia Blanco Ruiz
Script con pruebas unitarias relacionadas con las notificaciones de finalización de tareas de conversión 
de documentos a Markdown. Su objetivo es verificar que los correos electrónicos enviados al finalizar una 
conversión contienen correctamente la información relevante del proceso, incluyendo el resultado de la ejecución, 
métricas de conversión y enlaces de acceso a los documentos procesados.
"""

from unittest.mock import patch

from app.main.code.services.markdown_conversion_state import (
    send_markdown_finished_email,
)
from app.test.support import BaseAppTestCase


class MarkdownConversionStateNotificationUnitTest(BaseAppTestCase):
    @patch("app.main.code.services.markdown_conversion_state.mail.send")
    def test_send_markdown_finished_email_includes_metrics_and_url(self, mock_send):
        """
        Verifica que el correo electrónico enviado tras finalizar una conversión Markdown incluye correctamente 
        el destinatario, el asunto, las métricas de conversión obtenidas y la URL de acceso a los documentos 
        procesados.
        """
        send_markdown_finished_email(
            "user@example.com",
            ok=True,
            message="Markdown listo",
            job_id=7,
            docs_url="http://localhost/admin/documents/list",
            converted_docs=2,
            skipped_docs=1,
        )

        msg = mock_send.call_args.args[0]
        self.assertEqual(msg.recipients, ["user@example.com"])
        self.assertIn("Conversi", msg.subject)
        self.assertIn("Documentos convertidos: 2", msg.body)
        self.assertIn("http://localhost/admin/documents/list", msg.body)
