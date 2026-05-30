"""
Autora: Lydia Blanco Ruiz
Prueba de integración del bloque `if __name__ == "__main__":` de evaluacion_RAGAS.py.
"""

import json
import os
import runpy
from pathlib import Path

from app.test.support import BaseAppTestCase


class EvaluacionRAGASMainGuardIntegrationTest(BaseAppTestCase):
    def test_main_guard_writes_artifacts_on_failure(self):
        tmp = self._tmpdir
        results = tmp / "results.json"
        rows = tmp / "rows.json"
        config = tmp / "config.json"

        # Fuerza un fallo temprano dentro de main() (no existe el fichero de preguntas).
        os.environ["RAGAS_QUESTIONS_PATH"] = str(tmp / "missing_questions.json")
        os.environ["RAGAS_RESULTS_PATH"] = str(results)
        os.environ["RAGAS_ROW_RESULTS_PATH"] = str(rows)
        os.environ["CONFIGURACION_PATH"] = str(config)

        script = Path("app/main/code/services/evaluation/evaluacion_RAGAS.py").resolve()

        with self.assertRaises(Exception):
            runpy.run_path(str(script), run_name="__main__")

        self.assertTrue(results.exists())
        self.assertTrue(rows.exists())
        self.assertTrue(config.exists())

        payload = json.loads(results.read_text(encoding="utf-8"))
        self.assertIn("ragas_error", payload)

