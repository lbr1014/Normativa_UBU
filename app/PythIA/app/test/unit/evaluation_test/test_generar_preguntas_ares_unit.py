"""
Autora: Lydia Blanco Ruiz
Pruebas unitarias para `generar_preguntas_ARES.py`.
"""

import importlib
import json
import sys
import types
from types import SimpleNamespace
from unittest.mock import patch

from app.test.support import BaseAppTestCase


def _install_fake_prototipo_rag(*, chunks=None, ollama_payload=None):
    module = types.ModuleType("app.main.code.services.rag.PrototipoRAG")

    class VectorBaseDocument:
        @staticmethod
        def bulk_find(limit=100, offset=None):
            items = chunks or []
            start = int(offset or 0)
            batch = items[start : start + limit]
            next_offset = None if start + limit >= len(items) else start + limit
            return batch, next_offset

    async def ask_ollama(_prompt, model=None):
        if isinstance(ollama_payload, str):
            return ollama_payload
        return json.dumps(ollama_payload or [], ensure_ascii=False)

    module.VectorBaseDocument = VectorBaseDocument
    module.ask_ollama = ask_ollama
    return module


class GenerarPreguntasARESUnitTest(BaseAppTestCase):
    def _module(self, *, chunks=None, ollama_payload=None):
        fake = _install_fake_prototipo_rag(chunks=chunks, ollama_payload=ollama_payload)
        with patch.dict(sys.modules, {"app.main.code.services.rag.PrototipoRAG": fake}):
            sys.modules.pop("app.main.code.services.evaluation.generar_preguntas_ARES", None)
            return importlib.import_module("app.main.code.services.evaluation.generar_preguntas_ARES")

    def test_clean_chunk_and_good_chunk_thresholds(self):
        m = self._module()
        self.assertEqual(m.clean_chunk("  hola \n mundo\t"), "hola mundo")
        self.assertFalse(m.good_chunk(""))
        self.assertFalse(m.good_chunk("x" * 499))
        self.assertFalse(m.good_chunk("x" * 4001))
        self.assertFalse(m.good_chunk(("a " * 600) + ("Pagina " * 6)))
        self.assertTrue(m.good_chunk("a" * 600))

    def test_iter_chunks_paginates_until_offset_none(self):
        docs = [SimpleNamespace(content=f"c{i}") for i in range(5)]
        m = self._module(chunks=docs)
        out = m.iter_chunks(limit_total=10, batch=2)
        self.assertEqual([d.content for d in out], [f"c{i}" for i in range(5)])

    def test_iter_chunks_stops_when_empty_batch(self):
        m = self._module(chunks=[])
        out = m.iter_chunks(limit_total=10, batch=2)
        self.assertEqual(out, [])

    def test_generate_qas_for_chunk_parses_json_list_of_dicts(self):
        m = self._module(ollama_payload=[{"question": "q", "answer": "a", "evidence": "e"}, "bad", 1])
        out = m.generate_qas_for_chunk("chunk" * 200, n=2, model="fake")
        self.assertEqual(out, [{"question": "q", "answer": "a", "evidence": "e"}])

        m = self._module(ollama_payload="not-json")
        self.assertEqual(m.generate_qas_for_chunk("chunk" * 200), [])

        m = self._module(ollama_payload={"not": "a list"})
        self.assertEqual(m.generate_qas_for_chunk("chunk" * 200), [])

    def test_pass_quality_requires_min_words_and_evidence_in_chunk(self):
        m = self._module()
        chunk = "Este es el texto base con evidencia literal."
        self.assertFalse(m.pass_quality("", "a", "e", chunk))
        self.assertFalse(m.pass_quality("una dos tres cuatro cinco", "a", "e", chunk))
        self.assertFalse(m.pass_quality("una dos tres cuatro cinco seis", "a", "NO", chunk))
        self.assertTrue(m.pass_quality("una dos tres cuatro cinco seis", "a", "evidencia literal", chunk))

    def test_accumulate_questions_dedup_and_stops_at_target(self):
        chunk = ("texto " * 200) + "evidencia A"
        m = self._module(
            ollama_payload=[
                {"question": "una dos tres cuatro cinco seis", "answer": "A", "evidence": "evidencia A"}
            ]
        )

        with patch.dict("os.environ", {"ARES_NUM_QUESTIONS": "1", "ARES_MAX_SOURCE_CHUNKS": "10", "ARES_QAS_PER_CHUNK": "2"}):
            out = m._accumulate_questions([chunk, chunk])

        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["question"], "una dos tres cuatro cinco seis")

    def test_try_add_question_skips_duplicates_and_low_quality(self):
        m = self._module()
        questions = []
        seen = set()
        chunk = "Texto con evidencia literal."
        item = {"question": "una dos tres cuatro cinco seis", "answer": "A", "evidence": "evidencia literal"}

        m._try_add_question(questions=questions, seen=seen, chunk=chunk, item=item)
        self.assertEqual(len(questions), 1)

        # duplicado -> return temprano
        m._try_add_question(questions=questions, seen=seen, chunk=chunk, item=item)
        self.assertEqual(len(questions), 1)

        # mala calidad (evidence no está en chunk) -> return temprano
        bad_item = {"question": "otra pregunta con seis palabras exactas", "answer": "A", "evidence": "NO"}
        m._try_add_question(questions=questions, seen=seen, chunk=chunk, item=bad_item)
        self.assertEqual(len(questions), 1)

    def test_accumulate_questions_prints_every_10_chunks_and_returns_when_under_target(self):
        # Fuerza ruta y termina sin alcanzar target por falta de preguntas válidas
        chunk = ("texto " * 200) + "evidencia A"
        m = self._module(ollama_payload=[])
        chunks = [chunk for _ in range(10)]

        with patch.dict("os.environ", {"ARES_NUM_QUESTIONS": "5", "ARES_MAX_SOURCE_CHUNKS": "10", "ARES_QAS_PER_CHUNK": "1"}):
            out = m._accumulate_questions(chunks)

        self.assertEqual(out, [])

    def test_main_skips_when_questions_file_exists(self):
        m = self._module()
        questions_path = self._tmpdir / "questions.json"
        questions_path.write_text("[]", encoding="utf-8")

        with patch.object(m, "QUESTIONS_PATH", questions_path), patch.object(m, "FORCE_REGENERATE", False):
            m.main()

    def test_build_shuffle_rng_uses_seed_when_configured(self):
        m = self._module()
        with patch.dict("os.environ", {"ARES_SHUFFLE_SEED": "123"}):
            rng = m._build_shuffle_rng()
        self.assertEqual(rng.randint(0, 1000), m.random.Random(123).randint(0, 1000))

    def test_main_generates_questions_file(self):
        chunk = ("texto " * 200) + "evidencia A"
        docs = [SimpleNamespace(content=chunk)]
        m = self._module(chunks=docs, ollama_payload=[{"question": "una dos tres cuatro cinco seis", "answer": "A", "evidence": "evidencia A"}])
        out_path = self._tmpdir / "questions_out.json"

        with patch.object(m, "QUESTIONS_PATH", out_path), patch.object(m, "FORCE_REGENERATE", True), patch.dict(
            "os.environ", {"ARES_NUM_QUESTIONS": "1", "ARES_MAX_SOURCE_CHUNKS": "10", "ARES_QAS_PER_CHUNK": "1"}
        ):
            m.main()

        self.assertTrue(out_path.exists())

    def test_main_raises_system_exit_when_no_questions_generated(self):
        chunk = ("texto " * 200) + "sin evidencia"
        docs = [SimpleNamespace(content=chunk)]
        m = self._module(chunks=docs, ollama_payload=[])
        out_path = self._tmpdir / "questions_empty.json"

        with patch.object(m, "QUESTIONS_PATH", out_path), patch.object(m, "FORCE_REGENERATE", True), patch.dict(
            "os.environ", {"ARES_NUM_QUESTIONS": "1", "ARES_MAX_SOURCE_CHUNKS": "1", "ARES_QAS_PER_CHUNK": "1"}
        ):
            with self.assertRaises(SystemExit):
                m.main()
