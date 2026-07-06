"""
Autora: Lydia Blanco Ruiz
Script de pruebas unitarias para funcionalidades adicionales del módulo de documentos, enfocadas en cubrir rutas de ejecución
excepcionales y casos límite que no están contemplados en las pruebas principales. 
Las pruebas verifican la inferencia de metadatos documentales, la validación de archivos PDF, la gestión de errores durante la 
lectura de flujos de datos, el cálculo de páginas de documentos y el comportamiento de los procesos de indexación vectorial ante cancelaciones 
y situaciones anómalas.
"""

import builtins
import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from werkzeug.datastructures import FileStorage

from app.main.code.model.documento import Documento
from app.main.code.services.documentos import (
    DocumentosService,
    JobCancelledError,
    infer_document_metadata_from_filename,
)
from app.test.support import BaseAppTestCase


class _BadTellStream(io.BytesIO):
    def tell(self):
        """
        Simula un flujo que lanza una excepción al intentar obtener la posición actual.
        """
        raise OSError("nope")


class _BadSeekStream(io.BytesIO):
    def seek(self, *_a, **_k):
        """
        Simula un flujo que lanza una excepción al intentar desplazarse a una posición específica.
        """
        raise OSError("nope")


class _StringReadStream(io.BytesIO):
    def read(self, size=-1):
        """
        Simula un flujo que devuelve datos como cadena en lugar de bytes, lo que puede ocurrir si el stream no es binario o 
        si hay un error en la lectura.
        """
        return b"%PDF-"[:size].decode("utf-8")


class DocumentosAdditionalCoverageUnitTest(BaseAppTestCase):
    def _service(self) -> DocumentosService:
        """
        Crea una instancia del servicio de documentos con dependencias simuladas para pruebas unitarias.
        """
        return DocumentosService(
            self._docs_dir,
            index_pliegos_dir=lambda _path: {},
            delete_chunks=MagicMock(),
            markdown_converter=MagicMock(),
        )

    def test_infer_document_metadata_handles_len_one_and_more_than_two(self):
        """
        Verifica que la inferencia de metadatos documentales gestiona correctamente resultados incompletos, excesivos o inválidos 
        devueltos durante el análisis del nombre del archivo.
        """
        with patch.object(Documento, "infer_metadata_from_filename", return_value=("EXP-1",)):
            self.assertEqual(infer_document_metadata_from_filename("x.pdf"), ("EXP-1", None))
        with patch.object(Documento, "infer_metadata_from_filename", return_value=("EXP-1", "administrativo", "extra")):
            self.assertEqual(infer_document_metadata_from_filename("x.pdf"), ("EXP-1", "administrativo"))
        with patch.object(Documento, "infer_metadata_from_filename", return_value=None):
            self.assertEqual(infer_document_metadata_from_filename("x.pdf"), (None, None))
        with patch.object(Documento, "infer_metadata_from_filename", return_value="not-a-tuple"):
            self.assertEqual(infer_document_metadata_from_filename("x.pdf"), (None, None))

    def test_read_stream_window_handles_tell_read_and_restore_errors_and_str_data(self):
        """
        Comprueba la lectura parcial de flujos de datos gestionando correctamente errores de posicionamiento, restauración de punteros y
        conversiones de datos en formato texto a binario.
        """
        service = self._service()
        storage = SimpleNamespace(filename="archivo.pdf")

        data = service._read_stream_window(_BadTellStream(b"abc"), storage, 2)
        self.assertEqual(data, b"ab")

        data2 = service._read_stream_window(_BadSeekStream(b"abc"), storage, 2)
        self.assertEqual(data2, b"")

        data3 = service._read_stream_window(_StringReadStream(b""), storage, 8)
        self.assertTrue(data3.startswith(b"%PDF-"))

    def test_is_pdf_upload_warns_on_missing_signature_but_returns_true(self):
        """
        Verifica el comportamiento de la validación de archivos PDF cuando no se detecta la firma característica del formato, 
        manteniendo la compatibilidad con determinados escenarios de carga.
        """
        service = self._service()
        stream = io.BytesIO(b"NOTPDF")
        stream.seek(1)
        fs = FileStorage(stream=stream, filename="doc.pdf", content_type="text/plain")
        self.assertTrue(service._is_pdf_upload(fs))

    def test_is_pdf_upload_handles_tell_and_restore_exceptions(self):
        """
        Comprueba que la validación de documentos PDF continúa funcionando correctamente cuando se producen excepciones durante la 
        lectura o reposicionamiento del flujo de datos.
        """
        service = self._service()
        bad_tell = _BadTellStream(b"%PDF-1.4")
        fs = FileStorage(stream=bad_tell, filename="doc.pdf")
        self.assertTrue(service._is_pdf_upload(fs))

        class _RestoreFail(io.BytesIO):
            def __init__(self, data):
                """
                Simula un flujo que falla al intentar restaurar la posición después de una lectura, permitiendo probar la gestión de 
                excepciones en ese escenario.
                """
                super().__init__(data)
                self._restore = False

            def seek(self, pos, whence=0):
                """
                Falla la restauración solo en el primer intento de seek que no sea al inicio, para simular un error de restauración.
                """
                if pos != 0 and not self._restore:
                    self._restore = True
                    raise OSError("restore fail")
                return super().seek(pos, whence)

        fs2 = FileStorage(stream=_RestoreFail(b"%PDF-1.4"), filename="doc.pdf")
        self.assertTrue(service._is_pdf_upload(fs2))

        class _RestoreAlways(io.BytesIO):
            def seek(self, pos, whence=0):
                """
                Simula un flujo que siempre falla al intentar restaurar la posición, para cubrir el manejo de excepciones en ambos 
                intentos de seek.
                """
                if pos != 0:
                    raise OSError("restore fail")
                return super().seek(pos, whence)

        s = _RestoreAlways(b"XXXXXNOTPDFDATA")
        s.read(3)
        fs3 = FileStorage(stream=s, filename="doc.pdf", content_type="application/pdf")
        self.assertTrue(service._is_pdf_upload(fs3))

        class _ProbeStringStream(io.BytesIO):
            def __init__(self, data):
                """
                Simula un flujo que devuelve datos como cadena en lugar de bytes en la primera lectura, 
                para probar la ruta de codificación de cadenas.
                """
                super().__init__(data)
                self._call = 0

            def read(self, size=-1):
                """
                Devuelve datos como cadena en lugar de bytes en la primera lectura, luego devuelve otra cadena para simular un flujo no binario.
                """
                self._call += 1
                if self._call == 1:
                    return "NOPE"  
                return "still nope"  

        s2 = _ProbeStringStream(b"")
        s2.read(2)
        fs4 = FileStorage(stream=s2, filename="doc.pdf", content_type="text/plain")
        self.assertTrue(service._is_pdf_upload(fs4))

    def test_page_count_exceptions_importerror_fallback_and_sort_empty(self):
        """
        Verifica la gestión de errores producidos por dependencias externas relacionadas con el recuento de páginas y 
        comprueba el comportamiento de la ordenación cuando no existen documentos para procesar.
        """
        service = self._service()

        real_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name.startswith("pdf2image"):
                raise ImportError("blocked")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded_import):
            excs = service._page_count_exceptions()
        self.assertTrue(any(issubclass(e, Exception) for e in excs))

        self.assertEqual(service._sort_docs_by_page_count([]), [])

    def test_update_vector_db_propagates_job_cancelled_error(self):
        """
        Comprueba que las cancelaciones producidas durante la actualización de la base de datos vectorial se propagan correctamente 
        hacia los niveles superiores de la aplicación.
        """
        service = self._service()
        doc = self.create_document(nombre="cancelled.pdf", status="cargado")

        with patch.object(service, "_index_vector_document", side_effect=JobCancelledError("cancel")), patch(
            "app.main.code.services.documentos.Documento.query"
        ) as mock_query:
            mock_query.filter.return_value.all.return_value = [doc]
            with self.assertRaises(JobCancelledError):
                service.update_vector_db()



