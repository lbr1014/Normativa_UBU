"""
Autora: Lydia Blanco Ruiz
Script con pruebas unitarias para el módulo de tareas asíncronas (async_tasks), encargado de gestionar la ejecución de tareas asíncronas 
dentro de la aplicación. Su objetivo es verificar el correcto registro de mecanismos de apagado, la finalización segura de los ejecutores 
de tareas, el seguimiento de trabajos en ejecución y la liberación adecuada de recursos cuando la aplicación finaliza. Las pruebas se centran 
especialmente en la robustez del sistema frente a errores durante el cierre y en la correcta gestión del ciclo de vida de las tareas asíncronas.
"""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class AsyncTasksShutdownUnitTest(unittest.TestCase):
    def _load_async_tasks_module(self):
        """
        Carga el módulo async_tasks para pruebas.
        """
        module_path = (
            Path(__file__).resolve().parents[2]
            / "main"
            / "code"
            / "services"
            / "async_tasks.py"
        )
        spec = importlib.util.spec_from_file_location("async_tasks_testshim", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module

    def test_register_executor_shutdown_registers_atexit(self):
        """
        Verifica que el mecanismo de apagado de los ejecutores se registra correctamente para ejecutarse al finalizar la aplicación.
        """
        async_tasks = self._load_async_tasks_module()
        async_tasks._shutdown_done = False
        with patch.object(async_tasks.atexit, "register") as mock_register:
            async_tasks.register_executor_shutdown(app=None)
        mock_register.assert_called()

    def test_shutdown_executors_is_idempotent(self):
        """
        Comprueba que la operación de cierre de los ejecutores puede ejecutarse varias veces sin producir efectos secundarios ni errores adicionales.
        """
        async_tasks = self._load_async_tasks_module()
        async_tasks._shutdown_done = False
        with patch.object(async_tasks.executor, "shutdown") as rag_shutdown, patch.object(
            async_tasks.markdown_executor, "shutdown"
        ) as md_shutdown:
            async_tasks.shutdown_executors()
            async_tasks.shutdown_executors()
        self.assertEqual(rag_shutdown.call_count, 1)
        self.assertEqual(md_shutdown.call_count, 1)

    def test_shutdown_executors_falls_back_on_type_error_and_logs_other_shutdown_errors(self):
        """
        Verifica la gestión de errores durante el apagado de los ejecutores, incluyendo mecanismos alternativos de cierre y 
        el registro de incidencias en el sistema de logs.
        """
        async_tasks = self._load_async_tasks_module()
        async_tasks._shutdown_done = False

        # TypeError al llamar con cancel_futures -> se intenta shutdown sin argumentos.
        md_shutdown = MagicMock(side_effect=[TypeError("no kw"), None])
        # RuntimeError -> se ignora y se deja rastro en logger.debug.
        rag_shutdown = MagicMock(side_effect=RuntimeError("boom"))

        with patch.object(async_tasks, "markdown_executor") as md_pool, patch.object(
            async_tasks, "executor"
        ) as rag_pool, patch.object(async_tasks.logger, "debug") as mock_debug:
            md_pool.shutdown = md_shutdown
            rag_pool.shutdown = rag_shutdown
            async_tasks.shutdown_executors(wait=True)

        self.assertEqual(md_shutdown.call_count, 2)
        mock_debug.assert_called()

    def test_submit_tracked_cleanup_callback_removes_future(self):
        """
        Comprueba que las tareas registradas son eliminadas correctamente del sistema de seguimiento una vez finalizan su ejecución.
        """
        async_tasks = self._load_async_tasks_module()
        async_tasks._shutdown_done = False

        class _FakeFuture:
            def __init__(self):
                self._cb = None

            def add_done_callback(self, cb):
                self._cb = cb

            def trigger_done(self):
                assert self._cb
                self._cb(self)

        fake_future = _FakeFuture()
        pool = MagicMock()
        pool.submit.return_value = fake_future

        fut = async_tasks.submit_tracked(pool, "rag", 7, lambda: None)
        self.assertIs(fut, fake_future)
        self.assertIn(("rag", 7), async_tasks._job_futures)

        fake_future.trigger_done()
        self.assertNotIn(("rag", 7), async_tasks._job_futures)

    def test_register_executor_shutdown_registers_after_serving_when_available(self):
        """
        Verifica que el apagado de los ejecutores se integra correctamente con los eventos del ciclo de vida de la aplicación cuando 
        existe soporte para callbacks posteriores al servicio.
        """
        async_tasks = self._load_async_tasks_module()

        class _App:
            def __init__(self):
                """
                Simula una aplicación con soporte para callbacks posteriores al servicio.
                """
                self._after_serving_callbacks = []

            def after_serving(self, fn):
                """
                Registra un callback para ejecutarse después de que la aplicación deje de servir solicitudes.
                """
                self._after_serving_callbacks.append(fn)
                return fn

        app = _App()
        with patch.object(async_tasks.atexit, "register") as mock_register, patch.object(
            async_tasks, "shutdown_executors"
        ) as mock_shutdown:
            async_tasks.register_executor_shutdown(app=app)
            self.assertEqual(len(app._after_serving_callbacks), 1)
            app._after_serving_callbacks[0]()

        mock_register.assert_called()
        mock_shutdown.assert_called_once()
