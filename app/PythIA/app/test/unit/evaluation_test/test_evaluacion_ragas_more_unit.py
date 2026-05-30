"""
Autora: Lydia Blanco Ruiz
Pruebas unitarias adicionales para cubrir ramas en `evaluacion_RAGAS.py`.
"""

import importlib
from types import SimpleNamespace
from unittest.mock import patch

from app.test.support import BaseAppTestCase


class EvaluacionRAGASMoreUnitTest(BaseAppTestCase):
    def _module(self):
        from app.main.code.services.evaluation import evaluacion_RAGAS

        return importlib.reload(evaluacion_RAGAS)

    def test_cosine_similarity_handles_zero_norm(self):
        m = self._module()
        self.assertEqual(m.cosine_similarity([0.0, 0.0], [1.0, 2.0]), 0.0)
        self.assertEqual(m.cosine_similarity([1.0, 2.0], [0.0, 0.0]), 0.0)

    def test_batch_embeddings_normalizes_empty_texts(self):
        m = self._module()

        class FakeEmb:
            def embed_documents(self, texts):
                self.texts = texts
                return [[1.0, 0.0, 0.0] for _ in texts]

        emb = FakeEmb()
        m.batch_embeddings(emb, ["", None, "hola"])
        self.assertEqual(emb.texts[0], " ")
        self.assertEqual(emb.texts[1], " ")
        self.assertEqual(emb.texts[2], "hola")

    def test_resolve_embeddings_device_respects_requested_cuda_without_torch(self):
        m = self._module()
        with patch.object(m, "RAGAS_EMBEDDINGS_DEVICE", "cuda"), patch.object(m, "torch", None):
            self.assertEqual(m.resolve_embeddings_device(), "cpu")

    def test_ragas_timeout_fallback_removes_answer_correctness_metric(self):
        m = self._module()

        metric_ok = SimpleNamespace(name="faithfulness")
        metric_drop = SimpleNamespace(name="answer_correctness")
        metrics = [metric_ok, metric_drop]
        aliases = {"answer_correctness": "answer_correctness"}
        diagnostics = {"issues": []}

        with patch.object(m, "_ragas_evaluate_dataset", side_effect=[TimeoutError(), "RESULT"]):
            result, active_aliases = m._ragas_evaluate_with_timeout_fallback(
                dataset_local=object(),
                metrics_local=metrics,
                aliases_local=aliases,
                ragas_llm_local=object(),
                ragas_embeddings_local=object(),
                run_config_local=object(),
                diagnostics_local=diagnostics,
            )

        self.assertEqual(result, "RESULT")
        self.assertNotIn("answer_correctness", active_aliases)
        self.assertTrue(any("Timeout en RAGAS" in issue for issue in diagnostics["issues"]))

