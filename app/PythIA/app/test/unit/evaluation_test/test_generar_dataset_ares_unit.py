"""
Autora: Lydia Blanco Ruiz
Pruebas unitarias para `generar_dataset_ARES.py`.
"""

import importlib
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

from app.test.support import BaseAppTestCase


def _install_fake_prototipo_rag(*, results=None, raise_for=None):
    module = types.ModuleType("app.main.code.services.rag.PrototipoRAG")

    async def obtener_mejor_chunk(question: str, *args, **kwargs):
        if raise_for and question in raise_for:
            raise RuntimeError("boom")
        payload = (results or {}).get(question) or {"answer": "A", "retrieved": [{"chunk": "C1"}]}
        return payload

    module.obtener_mejor_chunk = obtener_mejor_chunk
    return module


class GenerarDatasetARESUnitTest(BaseAppTestCase):
    def _import_module(self, fake_rag):
        fake_pandas = types.ModuleType("pandas")

        class _FakeDF:
            def __init__(self, data):
                self._data = data
                self._series = {
                    "question": _FakeSeries([row.get("question") for row in data]),
                    "documents": _FakeSeries([row.get("documents") for row in data]),
                    "answer": _FakeSeries([row.get("answer") for row in data]),
                }
                self.columns = list(self._series.keys())

            def __len__(self):
                return len(self._data)

            def __getitem__(self, key):
                return self._series.get(key, _FakeSeries([]))

        class _FakeSeries(list):
            def astype(self, _type):
                return self

            def apply(self, fn):
                return [_FakeSeriesItem(fn(item)) for item in self]

        class _FakeSeriesItem(str):
            pass

        def _DataFrame(data):
            # Simula lo mínimo usado por el script.
            if isinstance(data, list):
                return _FakeDF(data)
            return _FakeDF([])

        fake_pandas.DataFrame = _DataFrame

        def _to_csv(self, path, sep="\t", index=False):
            Path(path).write_text("Query\tDocument\tAnswer\n", encoding="utf-8")

        _FakeDF.to_csv = _to_csv

        with patch.dict(
            sys.modules,
            {"app.main.code.services.rag.PrototipoRAG": fake_rag, "pandas": fake_pandas},
        ):
            sys.modules.pop("app.main.code.services.evaluation.generar_dataset_ARES", None)
            return importlib.import_module("app.main.code.services.evaluation.generar_dataset_ARES")

    def _module(self):
        fake = _install_fake_prototipo_rag()
        return self._import_module(fake)

    def test_main_skips_when_outputs_exist_and_no_force(self):
        m = self._module()
        out_json = self._tmpdir / "out.json"
        out_tsv = self._tmpdir / "out.tsv"
        questions_path = self._tmpdir / "questions.json"
        out_json.write_text("[]", encoding="utf-8")
        out_tsv.write_text("", encoding="utf-8")
        questions_path.write_text("[]", encoding="utf-8")

        with patch.object(m, "OUT_JSON", out_json), patch.object(m, "OUT_TSV", out_tsv), patch.object(
            m, "QUESTIONS_PATH", questions_path
        ), patch.object(m, "FORCE_REGENERATE", False):
            m.main()

    def test_main_builds_dataset_and_writes_json_and_tsv(self):
        results = {"Q1": {"answer": "A1", "retrieved": [{"chunk": "Doc 1"}, {"chunk": "Doc 2"}]}}
        fake = _install_fake_prototipo_rag(results=results)
        m = self._import_module(fake)
        out_json = self._tmpdir / "out.json"
        out_tsv = self._tmpdir / "out.tsv"
        questions_path = self._tmpdir / "questions.json"
        questions_path.write_text(
            json.dumps([{"question": "Q1", "ground_truth": "GT", "evidence": "EV"}, {"question": ""}], ensure_ascii=False),
            encoding="utf-8",
        )

        with patch.object(m, "OUT_JSON", out_json), patch.object(m, "OUT_TSV", out_tsv), patch.object(
            m, "QUESTIONS_PATH", questions_path
        ), patch.object(m, "FORCE_REGENERATE", True):
            with patch.dict(sys.modules, {"app.main.code.services.rag.PrototipoRAG": fake}):
                m.main()

        data = json.loads(out_json.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["question"], "Q1")
        self.assertEqual(data[0]["answer"], "A1")
        self.assertTrue(out_tsv.exists())

    def test_main_raises_system_exit_when_dataset_empty(self):
        fake = _install_fake_prototipo_rag(results={})
        m = self._import_module(fake)
        out_json = self._tmpdir / "out.json"
        out_tsv = self._tmpdir / "out.tsv"
        questions_path = self._tmpdir / "questions.json"
        questions_path.write_text(json.dumps([{"question": ""}]), encoding="utf-8")

        with patch.object(m, "OUT_JSON", out_json), patch.object(m, "OUT_TSV", out_tsv), patch.object(
            m, "QUESTIONS_PATH", questions_path
        ), patch.object(m, "FORCE_REGENERATE", True):
            with self.assertRaises(SystemExit):
                with patch.dict(sys.modules, {"app.main.code.services.rag.PrototipoRAG": fake}):
                    m.main()

    def test_main_skips_failed_questions(self):
        fake = _install_fake_prototipo_rag(raise_for={"Q-bad"})
        m = self._import_module(fake)
        out_json = self._tmpdir / "out.json"
        out_tsv = self._tmpdir / "out.tsv"
        questions_path = self._tmpdir / "questions.json"
        questions_path.write_text(json.dumps([{"question": "Q-bad"}]), encoding="utf-8")

        with patch.object(m, "OUT_JSON", out_json), patch.object(m, "OUT_TSV", out_tsv), patch.object(
            m, "QUESTIONS_PATH", questions_path
        ), patch.object(m, "FORCE_REGENERATE", True):
            with self.assertRaises(SystemExit):
                with patch.dict(sys.modules, {"app.main.code.services.rag.PrototipoRAG": fake}):
                    m.main()
