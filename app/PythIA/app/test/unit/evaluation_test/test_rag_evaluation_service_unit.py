"""
Autora: Lydia Blanco Ruiz
Pruebas unitarias para `rag_evaluation_service.py`.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.test.support import BaseAppTestCase


class RAGEvaluationServiceUnitTest(BaseAppTestCase):
    def test_timestamp_slug_is_deterministic(self):
        from app.main.code.services.evaluation import rag_evaluation_service as svc

        now = datetime(2026, 5, 30, 12, 0, 1)
        self.assertEqual(svc._timestamp_slug(now), "20260530_120001")

    def test_run_rag_evaluation_in_testing_mode_writes_minimal_artifacts(self):
        from app.main.code.services.evaluation import rag_evaluation_service as svc

        data_dir = self._tmpdir / "data"
        with patch.dict(os.environ, {"PYTHIA_TESTING": "1"}, clear=False):
            artifacts = svc.run_rag_evaluation(data_dir=data_dir)

        self.assertTrue(artifacts.output_dir.exists())
        for path in (
            artifacts.ares_questions_json_path,
            artifacts.ares_dataset_json_path,
            artifacts.ares_dataset_tsv_path,
            artifacts.results_json_path,
            artifacts.row_results_json_path,
            artifacts.config_json_path,
        ):
            self.assertTrue(path.exists())

    def test_run_rag_evaluation_calls_scripts_and_restores_env(self):
        from app.main.code.services.evaluation import rag_evaluation_service as svc

        data_dir = self._tmpdir / "data"
        os.environ.pop("PYTHIA_TESTING", None)
        old = os.environ.get("RAGAS_RESULTS_PATH")

        calls = []

        def fake_run_path(path, run_name="__main__"):
            calls.append(Path(path).name)

        with patch("app.main.code.services.evaluation.rag_evaluation_service.runpy.run_path", side_effect=fake_run_path):
            artifacts = svc.run_rag_evaluation(data_dir=data_dir)

        self.assertEqual(calls[:2], ["generar_preguntas_ARES.py", "generar_dataset_ARES.py"])
        self.assertIn("evaluacion_RAGAS.py", calls)
        self.assertTrue(artifacts.output_dir.exists())
        self.assertEqual(os.environ.get("RAGAS_RESULTS_PATH"), old)

    def test_run_rag_evaluation_writes_fallback_when_ragas_fails(self):
        from app.main.code.services.evaluation import rag_evaluation_service as svc

        data_dir = self._tmpdir / "data"

        def fake_run_path(path, run_name="__main__"):
            if str(path).endswith("evaluacion_RAGAS.py"):
                raise RuntimeError("boom-ragas")

        with patch("app.main.code.services.evaluation.rag_evaluation_service.runpy.run_path", side_effect=fake_run_path):
            with self.assertRaises(RuntimeError):
                artifacts = svc.run_rag_evaluation(data_dir=data_dir)

        eval_root = data_dir / "evaluations"
        dirs = sorted([p for p in eval_root.iterdir() if p.is_dir()])
        self.assertTrue(dirs)
        output_dir = dirs[-1]

        results_path = output_dir / "ragas_results.json"
        rows_path = output_dir / "ragas_results_rows.json"
        config_path = output_dir / "configuracion.json"

        self.assertTrue(results_path.exists())
        self.assertTrue(rows_path.exists())
        self.assertTrue(config_path.exists())
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        self.assertIn("ragas_error", payload)

