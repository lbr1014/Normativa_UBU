"""
Autora: Lydia Blanco Ruiz
Script con pruebas unitarias para la conversión de documentos PDF a Markdown.
Verifica el correcto funcionamiento de todas las etapas del proceso de conversión, incluyendo la configuración del entorno OCR, el procesamiento de imágenes,
la comunicación con Ollama, la extracción de texto mediante OCR, la normalización de encabezados, el tratamiento de errores y la generación final de documentos Markdown. 
Las pruebas cubren tanto escenarios normales de ejecución como condiciones excepcionales relacionadas con dependencias externas, concurrencia, fallos de OCR y procesamiento de archivos.
"""

import asyncio
import importlib
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


def _module_available(name):
    """
    Verifica si un módulo está disponible para importación.
    """
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _install_optional_dependency_stubs():
    """
    Verifica la disponibilidad de módulos opcionales y crea stubs si no están presentes para permitir la importación de Conversion_markdown sin fallar.
    """
    if not _module_available("httpx") and "httpx" not in sys.modules:
        httpx = types.ModuleType("httpx")
        httpx.TimeoutException = TimeoutError
        httpx.HTTPError = RuntimeError
        httpx.HTTPStatusError = RuntimeError
        httpx.AsyncClient = object
        httpx.Response = object
        sys.modules["httpx"] = httpx

    if not _module_available("PIL") and "PIL" not in sys.modules:
        pil = types.ModuleType("PIL")
        image = types.ModuleType("PIL.Image")
        pil.Image = image
        sys.modules["PIL"] = pil
        sys.modules["PIL.Image"] = image

    if not _module_available("pdf2image") and "pdf2image" not in sys.modules:
        pdf2image = types.ModuleType("pdf2image")
        pdf2image.convert_from_path = MagicMock()
        pdf2image.pdfinfo_from_path = MagicMock()
        sys.modules["pdf2image"] = pdf2image


_install_optional_dependency_stubs()
conversion = importlib.import_module("app.main.code.services.markdown.Conversion_markdown")


def _fake_torch(cuda_available):
    """
    Crea un módulo torch falso con la funcionalidad cuda simulada para pruebas.
    """
    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = MagicMock()
    fake_torch.cuda.is_available.return_value = cuda_available
    return fake_torch


def _import_conversion_with_torch(cuda_available):
    """
    Importa el módulo Conversion_markdown con un módulo torch simulado para probar la configuración automática de GPU
    """
    original_torch = sys.modules.get("torch")
    sys.modules["torch"] = _fake_torch(cuda_available)
    sys.modules.pop("app.main.code.services.markdown.Conversion_markdown", None)
    try:
        with patch.dict(os.environ, {"OLLAMA_NUM_GPU": ""}):
            return importlib.import_module("app.main.code.services.markdown.Conversion_markdown")
    finally:
        sys.modules.pop("app.main.code.services.markdown.Conversion_markdown", None)
        if original_torch is None:
            sys.modules.pop("torch", None)
        else:
            sys.modules["torch"] = original_torch
        sys.modules["app.main.code.services.markdown.Conversion_markdown"] = conversion


class ConversionMarkdownUnitTest(unittest.TestCase):
    def setUp(self):
        """
        Configura el entorno de prueba antes de cada test, asegurando que el módulo Conversion_markdown esté limpio para pruebas de importación.
        """
        sys.modules["app.main.code.services.markdown.Conversion_markdown"] = conversion
        import app.main.code.services.markdown as markdown_pkg

        markdown_pkg.Conversion_markdown = conversion

    def test_import_paths_cover_torch_missing_env_gpu_and_main_guard(self):
        """
        Verifica el comportamiento del módulo durante la importación cuando faltan dependencias, se configura el uso de GPU mediante variables de entorno y se ejecuta como programa principal.
        """
        real_import = __import__

        def import_without_torch(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("torch missing")
            return real_import(name, *args, **kwargs)

        sys.modules.pop("app.main.code.services.markdown.Conversion_markdown", None)
        with patch("builtins.__import__", side_effect=import_without_torch):
            imported = importlib.import_module("app.main.code.services.markdown.Conversion_markdown")
        self.assertIsNone(imported.torch)

        sys.modules.pop("app.main.code.services.markdown.Conversion_markdown", None)
        with patch.dict(os.environ, {"OLLAMA_NUM_GPU": "2"}):
            imported = importlib.import_module("app.main.code.services.markdown.Conversion_markdown")
        self.assertEqual(imported.DEFAULT_NUM_GPU, 2)
        self.assertEqual(imported.OLLAMA_NUM_GPU_SOURCE, "env")

        sys.modules["app.main.code.services.markdown.Conversion_markdown"] = conversion

        import runpy

        with patch.object(sys, "argv", ["Conversion_markdown.py"]), self.assertRaises(SystemExit):
            runpy.run_module("app.main.code.services.markdown.Conversion_markdown", run_name="__main__")

    def test_import_auto_gpu_configuration_requests_gpu_when_env_is_missing_even_without_cuda(self):
        """
        Comprueba la configuración automática del uso de GPU cuando no existe configuración explícita y CUDA no está disponible
        """
        imported = _import_conversion_with_torch(cuda_available=False)

        self.assertEqual(imported.DEFAULT_NUM_GPU, -1)
        self.assertEqual(imported.OLLAMA_NUM_GPU_SOURCE, "auto-ollama")

    def test_import_auto_gpu_configuration_requests_gpu_when_env_is_missing_with_cuda(self):
        """
        Verifica la configuración automática del uso de GPU cuando CUDA está disponible y no existe configuración previa.
        """
        imported = _import_conversion_with_torch(cuda_available=True)

        self.assertEqual(imported.DEFAULT_NUM_GPU, -1)
        self.assertEqual(imported.OLLAMA_NUM_GPU_SOURCE, "auto-ollama")

    def test_build_chat_payload_sets_model_image_and_gpu_options(self):
        """
        Comprueba que las peticiones enviadas al modelo OCR incluyen correctamente el modelo, la imagen y las opciones de GPU configuradas.
        """
        payload = conversion._build_chat_payload("contenido", "base64", num_gpu=0)

        self.assertEqual(payload["model"], conversion.MODEL_NAME)
        self.assertEqual(payload["messages"][0]["images"], ["base64"])
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["options"]["num_gpu"], 0)

    def test_pct_returns_zero_when_values_is_empty(self):
        """
       Verifica que el cálculo de percentiles devuelve cero cuando la colección de valores está vacía.
        """
        self.assertEqual(conversion._pct([], 0.5), 0.0)

    def test_log_timing_summary_returns_when_no_parts(self):
        """
        Comprueba que el registro de estadísticas temporales no genera errores cuando faltan datos de temporización.
        """
        with patch.object(conversion.logger, "info") as mock_info:
            conversion._log_timing_summary(Path("x.pdf"), 2, {"unknown": [1.0]})
        mock_info.assert_not_called()

    def test_process_pdf_async_runs_pages_with_concurrency_and_preserves_order(self):
        """
        Verifica que el procesamiento asíncrono de páginas PDF mantiene el orden correcto de salida incluso utilizando concurrencia.
        """
        async def fake_ocr(_client, _img, page, total_pages, model_name=None):
            await asyncio.sleep(0)
            return f"page-{page}/{total_pages}"

        with patch.object(conversion, "get_pdf_page_count", return_value=2), patch.object(
            conversion, "pdf_page_to_image", return_value=Path("fake.png")
        ), patch.object(conversion, "ocr_page_with_nanonets_async", side_effect=fake_ocr), patch.object(
            conversion, "OCR_CONCURRENCY", 2
        ):
            out = asyncio.run(conversion.process_pdf_async(Path("x.pdf")))

        self.assertEqual(out.splitlines()[0], "page-1/2")
        self.assertIn("page-2/2", out)

    def test_response_error_details_prefers_json_error_fields(self):
        """
        Comprueba que los detalles de error se extraen correctamente de respuestas JSON devueltas por servicios externos.
        """
        response = MagicMock()
        response.json.return_value = {"detail": "detalle de error"}

        self.assertEqual(conversion._response_error_details(response), "detalle de error")

    def test_response_error_details_uses_text_when_json_is_invalid(self):
        """
        Verifica la obtención de mensajes de error cuando la respuesta recibida no contiene un JSON válido.
        """
        response = MagicMock(text="error plano")
        response.json.side_effect = ValueError

        self.assertEqual(conversion._response_error_details(response), "error plano")

        empty = MagicMock(text="")
        empty.json.side_effect = ValueError
        self.assertEqual(conversion._response_error_details(empty), "sin cuerpo de respuesta")

        list_response = MagicMock()
        list_response.json.return_value = ["x"]
        self.assertEqual(conversion._response_error_details(list_response), "['x']")

    def test_ocr_backend_and_page_failure_markdown(self):
        """
        Comprueba la detección del backend OCR utilizado y la generación de mensajes Markdown descriptivos cuando falla el procesamiento de una página.
        """
        original_gpu = conversion.DEFAULT_NUM_GPU
        original_source = conversion.OLLAMA_NUM_GPU_SOURCE
        original_torch = conversion.torch
        try:
            conversion.DEFAULT_NUM_GPU = -1
            conversion.OLLAMA_NUM_GPU_SOURCE = "test"
            conversion.torch = None
            self.assertIn("GPU solicitada", conversion._ocr_execution_backend())

            fake_cuda = MagicMock()
            fake_cuda.is_available.return_value = True
            fake_cuda.get_device_name.return_value = "GPU Fake"
            fake_cuda.device_count.return_value = 2
            conversion.torch = MagicMock(cuda=fake_cuda)
            self.assertIn("GPU Fake", conversion._ocr_execution_backend())

            conversion.DEFAULT_NUM_GPU = 3
            self.assertIn("GPU parcial", conversion._ocr_execution_backend())

            conversion.DEFAULT_NUM_GPU = 0
            self.assertIn("CPU", conversion._ocr_execution_backend())
        finally:
            conversion.DEFAULT_NUM_GPU = original_gpu
            conversion.OLLAMA_NUM_GPU_SOURCE = original_source
            conversion.torch = original_torch

        markdown = conversion._page_failure_markdown(1, 3, RuntimeError("linea 1\nlinea 2"))
        self.assertIn("linea 1 linea 2", markdown)

    def test_service_url_from_env_handles_scheme_and_existing_url(self):
        """
        Verifica que las URL se generan correctamente para servicios OCR a partir de variables de entorno.
        """
        with patch.dict(os.environ, {"OCR_URL": "host:123", "OCR_URL_SCHEME": "https"}):
            self.assertEqual(conversion._service_url_from_env("OCR_URL", "fallback"), "https://host:123")
        with patch.dict(os.environ, {"OCR_URL": "http://ready/"}):
            self.assertEqual(conversion._service_url_from_env("OCR_URL", "fallback"), "http://ready")

    def test_clean_index_dots_removes_dot_leaders_and_dot_only_lines(self):
        """
        Comprueba la eliminación de puntos de relleno y líneas innecesarias presentes en índices extraídos de documentos.
        """
        markdown = "1. OBJETO............. 3\n.....\nTexto normal"

        self.assertEqual(conversion.clean_index_dots(markdown), "1. OBJETO 3\nTexto normal")

    def test_heading_helpers_cover_invalid_and_skip_paths(self):
        """
        Verifica el comportamiento de las funciones auxiliares encargadas de identificar y procesar encabezados válidos e inválidos.
        """
        self.assertTrue(conversion._should_skip_line("", ""))
        self.assertTrue(conversion._should_skip_line("# Title", "# Title"))
        self.assertTrue(conversion._should_skip_line(" line", "line"))
        self.assertFalse(conversion._should_skip_line("line", "line"))
        self.assertFalse(conversion._is_mostly_upper("1234"))
        self.assertFalse(conversion._is_mostly_upper("Titulo normal"))

        self.assertIsNone(conversion._split_numeric_heading("1 Title", 1))
        self.assertIsNone(conversion._split_numeric_heading("1.", 1))
        self.assertIsNone(conversion._split_numeric_heading("1.1. Title", 1))
        self.assertIsNone(conversion._split_numeric_heading("123. Title", 1))
        self.assertEqual(conversion._split_numeric_heading("1. Title", 1), ("1", "Title"))

        self.assertIsNone(conversion._split_letter_code_heading("G. Texto"))
        self.assertIsNone(conversion._split_letter_code_heading("g.1. Texto"))
        self.assertIsNone(conversion._split_letter_code_heading("G-1. Texto"))
        self.assertIsNone(conversion._split_letter_code_heading("G.a. Texto"))
        self.assertEqual(conversion._split_letter_code_heading("G.2. Texto"), ("G.2.", "Texto"))

        self.assertIsNone(conversion._process_single_level_heading("1. titulo minuscula"))
        self.assertIsNone(conversion._process_level2_heading("1. Texto"))
        self.assertIsNone(conversion._process_level3_heading("1.1. Texto"))
        self.assertIsNone(conversion._process_letter_code_heading("Texto"))

    def test_normalize_headings_converts_supported_heading_patterns(self):
        """
        Comprueba la conversión automática de distintos patrones de encabezados a la sintaxis Markdown correspondiente.
        """
        markdown = "\n# Ya\n1. OBJETO DEL CONTRATO\n1.1. Alcance\n1.1.1. Detalle\nG.2.2. Codigo\n- 1. Lista\nTexto normal"

        normalized = conversion.normalize_headings(markdown)

        self.assertIn("# 1. OBJETO DEL CONTRATO", normalized)
        self.assertIn("## 1.1. Alcance", normalized)
        self.assertIn("### 1.1.1. Detalle", normalized)
        self.assertIn("### G.2.2. Codigo", normalized)
        self.assertIn("- 1. Lista", normalized)
        self.assertIn("Texto normal", normalized)

    def test_post_ollama_chat_async_returns_json_payload(self):
        """
        Verifica que las peticiones asíncronas al servicio Ollama devuelven correctamente el contenido JSON esperado.
        """
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"message": {"content": "ok"}}
        client = MagicMock()
        client.post = AsyncMock(return_value=response)

        result = conversion.asyncio.run(conversion._post_ollama_chat_async(client, {"payload": True}))

        self.assertEqual(result, {"message": {"content": "ok"}})
        client.post.assert_awaited_once_with("/api/chat", json={"payload": True})

    def test_post_ollama_chat_async_wraps_timeout_http_status_and_json_errors(self):
        """
        Comprueba la gestión de errores producidos durante las comunicaciones con Ollama, incluyendo tiempos de espera, errores HTTP y respuestas inválidas.
        """
        client = MagicMock()
        client.post = AsyncMock(side_effect=conversion.httpx.TimeoutException("slow"))
        with self.assertRaises(conversion.OllamaOCRException):
            conversion.asyncio.run(conversion._post_ollama_chat_async(client, {}))

        client.post = AsyncMock(side_effect=conversion.httpx.HTTPError("down"))
        with self.assertRaises(conversion.OllamaOCRException):
            conversion.asyncio.run(conversion._post_ollama_chat_async(client, {}))

        response = MagicMock(status_code=500)
        response.json.return_value = {"error": "boom"}
        response.raise_for_status.side_effect = conversion.httpx.HTTPStatusError(
            "bad",
            request=MagicMock(),
            response=response,
        )
        client.post = AsyncMock(return_value=response)
        with self.assertRaises(conversion.OllamaOCRException) as ctx:
            conversion.asyncio.run(conversion._post_ollama_chat_async(client, {}))
        self.assertIn("HTTP 500", str(ctx.exception))

        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.side_effect = ValueError
        client.post = AsyncMock(return_value=response)
        with self.assertRaises(conversion.OllamaOCRException):
            conversion.asyncio.run(conversion._post_ollama_chat_async(client, {}))

    def test_pdf_info_page_render_and_resize_helpers(self):
        """
        Verifica la obtención de información de documentos PDF, la generación de imágenes de páginas y el redimensionamiento de imágenes para OCR.
        """
        pdf_path = Path("doc.pdf")
        with patch("app.main.code.services.markdown.Conversion_markdown.pdfinfo_from_path", return_value={"Pages": "2"}):
            self.assertEqual(conversion.get_pdf_page_count(pdf_path), 2)
        with patch("app.main.code.services.markdown.Conversion_markdown.pdfinfo_from_path", return_value={"Pages": "0"}), self.assertRaises(RuntimeError):
            conversion.get_pdf_page_count(pdf_path)

        output_dir = Path(tempfile.mkdtemp())
        image = MagicMock()
        with patch("app.main.code.services.markdown.Conversion_markdown.convert_from_path", return_value=[image]) as mock_convert:
            img_path = conversion.pdf_page_to_image(pdf_path, 3, output_dir, dpi=150)
        self.assertEqual(img_path, output_dir / "doc_page_3.png")
        image.save.assert_called_once_with(img_path, "PNG")
        self.assertEqual(mock_convert.call_args.kwargs["first_page"], 3)

        with patch("app.main.code.services.markdown.Conversion_markdown.convert_from_path", return_value=[]), self.assertRaises(RuntimeError):
            conversion.pdf_page_to_image(pdf_path, 1, output_dir)

    def test_resize_image_for_ocr_returns_original_or_resized_file(self):
        """
        Comprueba que las imágenes se reutilizan o redimensionan correctamente en función de sus dimensiones.
        """
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "page.png"
            image_path.write_bytes(b"fake")
            small = MagicMock()
            small.__enter__.return_value = small
            small.__exit__.return_value = False
            small.size = (100, 80)
            with patch("app.main.code.services.markdown.Conversion_markdown.Image.open", return_value=small):
                self.assertEqual(conversion.resize_image_for_ocr(image_path, 200), image_path)

            large = MagicMock()
            large.__enter__.return_value = large
            large.__exit__.return_value = False
            large.size = (2000, 1000)
            resized = MagicMock()
            large.resize.return_value = resized
            with patch("app.main.code.services.markdown.Conversion_markdown.Image.open", return_value=large):
                resized_path = conversion.resize_image_for_ocr(image_path, 1000)
            self.assertEqual(resized_path.name, "page_max1000.png")
            large.resize.assert_called_once()
            resized.save.assert_called_once_with(resized_path, "PNG", optimize=True)

    def test_ocr_page_success_retries_fallback_and_final_failure(self):
        """
        Verifica el procesamiento OCR de páginas individuales, incluyendo reintentos, mecanismos de respaldo y gestión de errores.
        """
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "page.png"
            image_path.write_bytes(b"image")
            resized_path = Path(tmp) / "page_small.png"
            resized_path.write_bytes(b"small")
            original_sides = conversion.OCR_RETRY_MAX_IMAGE_SIDES
            original_gpu = conversion.DEFAULT_NUM_GPU
            try:
                conversion.OCR_RETRY_MAX_IMAGE_SIDES = [1000]
                conversion.DEFAULT_NUM_GPU = -1
                with patch("app.main.code.services.markdown.Conversion_markdown.resize_image_for_ocr", return_value=resized_path), patch(
                    "app.main.code.services.markdown.Conversion_markdown._post_ollama_chat_async",
                    AsyncMock(return_value={"message": {"content": "markdown"}}),
                ) as mock_post:
                    result = conversion.asyncio.run(conversion.ocr_page_with_nanonets_async(MagicMock(), image_path, 1, 2))
                self.assertEqual(result, "markdown")
                self.assertFalse(resized_path.exists())
                self.assertEqual(mock_post.call_args.args[1]["options"]["num_gpu"], -1)

                resized_path.write_bytes(b"small")
                with patch("app.main.code.services.markdown.Conversion_markdown.resize_image_for_ocr", return_value=image_path), patch(
                    "app.main.code.services.markdown.Conversion_markdown._post_ollama_chat_async",
                    AsyncMock(side_effect=[KeyError("message"), {"message": {"content": "cpu ok"}}]),
                ) as mock_post:
                    result = conversion.asyncio.run(conversion.ocr_page_with_nanonets_async(MagicMock(), image_path, 1, 2))
                self.assertEqual(result, "cpu ok")
                self.assertEqual(mock_post.call_count, 2)

                with patch("app.main.code.services.markdown.Conversion_markdown.resize_image_for_ocr", return_value=resized_path), \
                     patch("app.main.code.services.markdown.Conversion_markdown._post_ollama_chat_async", AsyncMock(side_effect=conversion.OllamaOCRException("nope"))), \
                     patch.object(Path, "unlink", side_effect=OSError), \
                     self.assertRaises(conversion.OllamaOCRException):
                    conversion.asyncio.run(conversion.ocr_page_with_nanonets_async(MagicMock(), image_path, 1, 2))
            finally:
                conversion.OCR_RETRY_MAX_IMAGE_SIDES = original_sides
                conversion.DEFAULT_NUM_GPU = original_gpu

    def test_process_pdf_async_success_placeholder_raise_and_unlink_error(self):
        """
        Comprueba el comportamiento del procesamiento asíncrono de PDFs ante conversiones correctas, fallos gestionados mediante marcadores de posición y errores críticos.
        """
        class AsyncClientContext:
            def __init__(self, **_kwargs):
                # El constructor puede aceptar cualquier argumento pero no hace nada con ellos, ya que es un stub para httpx.AsyncClient
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

        pdf_path = Path("doc.pdf")
        callbacks = []
        image_path = Path(tempfile.mkdtemp()) / "page.png"
        image_path.write_text("img")
        with patch("app.main.code.services.markdown.Conversion_markdown.get_pdf_page_count", return_value=1), patch(
            "app.main.code.services.markdown.Conversion_markdown.pdf_page_to_image",
            return_value=image_path,
        ), patch(
            "app.main.code.services.markdown.Conversion_markdown.ocr_page_with_nanonets_async",
            AsyncMock(return_value="1. TITULO............. 3"),
        ), patch("app.main.code.services.markdown.Conversion_markdown.httpx.AsyncClient", AsyncClientContext):
            result = conversion.asyncio.run(conversion.process_pdf_async(pdf_path, on_page_start=lambda *args: callbacks.append(args)))
        self.assertIn("# 1. TITULO 3", result)
        self.assertEqual(callbacks, [(1, 1)])

        image_path.write_text("img")
        original_mode = conversion.OCR_PAGE_FAILURE_MODE
        try:
            conversion.OCR_PAGE_FAILURE_MODE = "placeholder"
            with patch("app.main.code.services.markdown.Conversion_markdown.get_pdf_page_count", return_value=1), patch(
                "app.main.code.services.markdown.Conversion_markdown.pdf_page_to_image",
                return_value=image_path,
            ), patch(
                "app.main.code.services.markdown.Conversion_markdown.ocr_page_with_nanonets_async",
                AsyncMock(side_effect=conversion.OllamaOCRException("fallo")),
            ), patch("app.main.code.services.markdown.Conversion_markdown.httpx.AsyncClient", AsyncClientContext), patch.object(
                Path,
                "unlink",
                side_effect=OSError,
            ):
                result = conversion.asyncio.run(conversion.process_pdf_async(pdf_path))
            self.assertIn("OCR no disponible", result)

            conversion.OCR_PAGE_FAILURE_MODE = "raise"
            with patch("app.main.code.services.markdown.Conversion_markdown.get_pdf_page_count", return_value=1), patch(
                "app.main.code.services.markdown.Conversion_markdown.pdf_page_to_image",
                return_value=image_path,
            ), patch(
                "app.main.code.services.markdown.Conversion_markdown.ocr_page_with_nanonets_async",
                AsyncMock(side_effect=conversion.OllamaOCRException("fallo")),
            ), patch("app.main.code.services.markdown.Conversion_markdown.httpx.AsyncClient", AsyncClientContext), self.assertRaises(
                conversion.OllamaOCRException
            ):
                conversion.asyncio.run(conversion.process_pdf_async(pdf_path))
        finally:
            conversion.OCR_PAGE_FAILURE_MODE = original_mode

    def test_process_pdf_save_markdown_and_main_paths(self):
        """
        Verifica la generación y almacenamiento de archivos Markdown, así como el funcionamiento de los distintos modos de ejecución del programa principal.
        """
        pdf_path = Path("doc.pdf")
        with patch("app.main.code.services.markdown.Conversion_markdown.process_pdf_async", AsyncMock(return_value="md")):
            self.assertEqual(conversion.process_pdf(pdf_path), "md")

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "out"
            with patch("app.main.code.services.markdown.Conversion_markdown.process_pdf", return_value="# Markdown") as mock_process:
                out_path = conversion.save_markdown_to_file(pdf_path, output_dir)
            self.assertEqual(out_path.read_text(encoding="utf-8"), "# Markdown")
            mock_process.assert_called_once()

            in_dir = Path(tmp) / "in"
            in_dir.mkdir()
            with patch.dict(os.environ, {"MARKDOWN_CLI_BASE_DIR": tmp}), patch.object(
                sys,
                "argv",
                ["cmd", str(in_dir), str(output_dir)],
            ), self.assertRaises(SystemExit):
                conversion.main()

            (in_dir / "a.pdf").write_text("pdf")
            (in_dir / "b.pdf").write_text("pdf")
            with patch.dict(os.environ, {"MARKDOWN_CLI_BASE_DIR": tmp}), patch.object(
                sys,
                "argv",
                ["cmd", str(in_dir), str(output_dir)],
            ), patch(
                "app.main.code.services.markdown.Conversion_markdown.save_markdown_to_file",
            ) as mock_save:
                conversion.main()
            self.assertEqual(mock_save.call_count, 2)

            outside_dir = Path(tmp).parent / "outside"
            with patch.dict(os.environ, {"MARKDOWN_CLI_BASE_DIR": tmp}), patch.object(
                sys,
                "argv",
                ["cmd", str(outside_dir), str(output_dir)],
            ), self.assertRaises(SystemExit):
                conversion.main()

        with patch.object(sys, "argv", ["cmd"]), self.assertRaises(SystemExit):
            conversion.main()
