"""
Autora: Lydia Blanco Ruiz
Prueba de integración del bloque `if __name__ == "__main__":` de generar_dataset_ARES.py.
"""

import json
import os
import runpy
import sys
import types
from pathlib import Path

from app.test.support import BaseAppTestCase


class GenerarDatasetARESMainGuardIntegrationTest(BaseAppTestCase):
    def test_main_guard_executes_and_writes_outputs(self):
        tmp = self._tmpdir
        questions_path = tmp / "questions.json"
        out_json = tmp / "out.json"
        out_tsv = tmp / "out.tsv"

        questions_path.write_text(
            json.dumps([{"question": "Q1", "ground_truth": "GT", "evidence": "EV"}], ensure_ascii=False),
            encoding="utf-8",
        )

        os.environ["ARES_QUESTIONS_PATH"] = str(questions_path)
        os.environ["ARES_DATASET_JSON_PATH"] = str(out_json)
        os.environ["ARES_DATASET_TSV_PATH"] = str(out_tsv)
        os.environ["ARES_FORCE_REGENERATE"] = "1"

        fake_rag = types.ModuleType("app.main.code.services.rag.PrototipoRAG")

        async def obtener_mejor_chunk(_question: str, *args, **kwargs):
            return {"answer": "A1", "retrieved": [{"chunk": "Doc"}]}

        fake_rag.obtener_mejor_chunk = obtener_mejor_chunk

        fake_pandas = types.ModuleType("pandas")

        class _FakeSeries(list):
            def astype(self, _type):
                return self

            def apply(self, fn):
                return [fn(item) for item in self]

        class _FakeDF:
            def __init__(self, data):
                self._data = data
                self.columns = ["Query", "Document", "Answer"]

            def __len__(self):
                return len(self._data)

            def __getitem__(self, key):
                if key == "question":
                    return _FakeSeries([row["question"] for row in self._data])
                if key == "documents":
                    return _FakeSeries([row["documents"] for row in self._data])
                if key == "answer":
                    return _FakeSeries([row["answer"] for row in self._data])
                return _FakeSeries([])

            def to_csv(self, path, sep="\t", index=False):
                Path(path).write_text("Query\tDocument\tAnswer\n", encoding="utf-8")

        def DataFrame(data):
            return _FakeDF(data)

        fake_pandas.DataFrame = DataFrame

        script = Path("app/main/code/services/evaluation/generar_dataset_ARES.py").resolve()
        with _patch_modules(
            {
                "app.main.code.services.rag.PrototipoRAG": fake_rag,
                "pandas": fake_pandas,
            }
        ):
            runpy.run_path(str(script), run_name="__main__")

        self.assertTrue(out_json.exists())
        self.assertTrue(out_tsv.exists())


class _patch_modules:
    def __init__(self, mapping):
        self.mapping = mapping
        self.old = {}

    def __enter__(self):
        for key, value in self.mapping.items():
            self.old[key] = sys.modules.get(key)
            sys.modules[key] = value
        sys.modules.pop("app.main.code.services.evaluation.generar_dataset_ARES", None)
        return self

    def __exit__(self, exc_type, exc, tb):
        for key, old_value in self.old.items():
            if old_value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = old_value
        return False
