"""
Autora: Lydia Blanco Ruiz
Script con pruebas unitarias complementarias de las rutas RAG de la aplicación. 
Su objetivo es verificar el correcto funcionamiento de diversas funciones auxiliares utilizadas durante la
gestión de consultas guiadas, la carga de configuraciones, el procesamiento de resultados, 
la validación de rutas de archivos y la generación de datos para la interfaz de usuario. 
Las pruebas cubren casos relacionados con la lectura de ficheros JSON, la construcción de estadísticas,
el tratamiento de expedientes y tipos documentales, así como la protección frente a accesos fuera del directorio de 
datos autorizado.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.main.code.controllers.rag import routes as rag_routes
from app.test.support import BaseAppTestCase


class RagRoutesAdditionalCoverageUnitTest(BaseAppTestCase):
    def test_resolve_paths_and_json_helpers(self):
        """
        Verifica la resolución de rutas de trabajo, la validación de accesos dentro del directorio de datos 
        permitido y la carga segura de archivos JSON, incluyendo la gestión de errores y valores por defecto.
        """
        tmpdir = Path(self.app.config["DATA_DIR"]).resolve()
        with self.app.app_context():
            self.assertEqual(rag_routes._resolve_data_dir(), tmpdir)

            job = SimpleNamespace(
                results_json_path=str(tmpdir / "r.json"),
                row_results_json_path=str(tmpdir / "rows.json"),
                config_json_path=str(tmpdir / "cfg.json"),
            )
            results_path, rows_path, cfg_path = rag_routes._resolve_job_paths(job)
            rag_routes._ensure_paths_inside_data_dir(tmpdir, results_path, rows_path, cfg_path)
            rag_routes._ensure_paths_inside_data_dir(tmpdir, results_path, rows_path, None)

            bad_path = tmpdir.parent / "escape.json"
            with self.assertRaises(Exception) as raised:
                rag_routes._ensure_paths_inside_data_dir(tmpdir, bad_path, rows_path, cfg_path)
            self.assertEqual(getattr(raised.exception, "code", None), 400)

            ok = tmpdir / "ok.json"
            ok.write_text(json.dumps({"a": 1}), encoding="utf-8")
            self.assertEqual(rag_routes._load_json_file(ok), {"a": 1})

            bad_json = tmpdir / "bad.json"
            bad_json.write_text("{", encoding="utf-8")
            with self.assertRaises(Exception) as raised2:
                rag_routes._load_json_file(bad_json)
            self.assertEqual(getattr(raised2.exception, "code", None), 500)

            self.assertEqual(rag_routes._load_json_file_or_default(bad_json, []), [])

    def test_legacy_expediente_helpers_are_noops_and_document_choices_use_names(self):
        """
        Comprueba el procesamiento de registros asociados a expedientes, filtrando valores vacíos,
        agrupando tipos documentales y generando etiquetas descriptivas para la interfaz.
        """
        by = {}
        rag_routes.process_rows(by, [("", "a", "n"), (None, "a", "n"), ("  ", "a", "n")])
        self.assertEqual(by, {})

        by2 = {}
        rag_routes.process_rows(by2, [("EXP", "administrativo", "A.pdf"), ("EXP", "", "")])
        self.assertEqual(by2, {})

        with patch("app.main.code.controllers.rag.routes.t", side_effect=lambda key, **_k: key):
            self.assertEqual(rag_routes.type_label("heading"), "heading")
            self.assertEqual(rag_routes.type_label(""), "-")

    def test_model_usage_index_edge_cases(self):
        """
        Verifica estadisticas de uso de modelos con datos incompletos o fuera de rango.
        """
        job_missing = SimpleNamespace(created_at=None, result_payload=None, model_name=None)
        job_old = SimpleNamespace(
            created_at=__import__("datetime").datetime(1900, 1, 1),
            result_payload=None,
            model_name="m",
        )
        fake_query = SimpleNamespace(
            filter=lambda *_a, **_k: SimpleNamespace(
                order_by=lambda *_a2, **_k2: SimpleNamespace(all=lambda: [job_missing, job_old])
            )
        )
        class _StatusExpr:
            def __eq__(self, _other):
                return True

        fake_rag_query_state = SimpleNamespace(query=fake_query, status=_StatusExpr())
        fake_rag_query_state.created_at = SimpleNamespace(asc=lambda: None)

        with patch("app.main.code.controllers.rag.routes.RAGQueryState", fake_rag_query_state):
            out = rag_routes.build_model_usage_index_payload(months=1)
        self.assertEqual(out["series"], {})

    def test_get_expediente_choices_shows_document_title_and_date(self):
        """
        Comprueba la generacion de opciones de documentos mostrando nombre, titulo y fecha.
        """
        doc = SimpleNamespace(
            id=7,
            nombre="file.pdf",
            markdown_content="# NORMATIVA DE PRUEBA\n\nFECHA : 08/09/2026 10:00",
        )
        fake_query = SimpleNamespace(order_by=lambda *_a, **_k: SimpleNamespace(all=lambda: [doc]))
        with patch("app.main.code.controllers.rag.routes.t", side_effect=lambda key, **_k: key), patch(
            "app.main.code.controllers.rag.routes.Documento.query", fake_query
        ):
            choices = rag_routes.get_expediente_choices()
        self.assertIn(("7", "file | NORMATIVA DE PRUEBA | 08/09/2026"), choices)
