"""
Autora: Lydia Blanco Ruiz
Prueba de integración del bloque `if __name__ == "__main__":` de generar_preguntas_ARES.py.
"""

import os
import runpy
import sys
import types
from pathlib import Path

from app.test.support import BaseAppTestCase


class GenerarPreguntasARESMainGuardIntegrationTest(BaseAppTestCase):
    def test_main_guard_executes_without_generating_when_file_exists(self):
        out_path = self._tmpdir / "questions.json"
        out_path.write_text("[]", encoding="utf-8")

        os.environ["ARES_QUESTIONS_PATH"] = str(out_path)
        os.environ["ARES_FORCE_REGENERATE"] = "0"

        fake_rag = types.ModuleType("app.main.code.services.rag.PrototipoRAG")

        class VectorBaseDocument:
            @staticmethod
            def bulk_find(limit=100, offset=None):
                return [], None

        async def ask_ollama(_prompt, model=None):
            return "[]"

        fake_rag.VectorBaseDocument = VectorBaseDocument
        fake_rag.ask_ollama = ask_ollama

        script = Path("app/main/code/services/evaluation/generar_preguntas_ARES.py").resolve()
        with _patch_modules({"app.main.code.services.rag.PrototipoRAG": fake_rag}):
            runpy.run_path(str(script), run_name="__main__")


class _patch_modules:
    def __init__(self, mapping):
        self.mapping = mapping
        self.old = {}

    def __enter__(self):
        for key, value in self.mapping.items():
            self.old[key] = sys.modules.get(key)
            sys.modules[key] = value
        sys.modules.pop("app.main.code.services.evaluation.generar_preguntas_ARES", None)
        return self

    def __exit__(self, exc_type, exc, tb):
        for key, old_value in self.old.items():
            if old_value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = old_value
        return False

