"""
Autora: Lydia Blanco Ruiz
Script con pruebas unitarias para la gestión de prioridad de recursos (resource_priority), encargado de gestionar 
las prioridades de uso de recursos compartidos dentro de la aplicación. 
Su objetivo es verificar los mecanismos que otorgan prioridad a las consultas RAG frente a otras tareas 
en segundo plano, así como la correcta sincronización entre procesos síncronos y asíncronos. 
Las pruebas comprueban la activación y liberación de bloqueos, la espera de recursos disponibles y 
el comportamiento de los contextos de prioridad utilizados para coordinar el acceso a servicios como Ollama.
"""

import asyncio
import threading
import unittest

from app.main.code.services import resource_priority


class ResourcePriorityUnitTest(unittest.TestCase):
    def tearDown(self) -> None:
        """
        Asegura que no quedan flags activos entre tests.
        """
        resource_priority._rag_active_event.clear()
        resource_priority._rag_active_count = 0

    def test_rag_priority_sets_and_clears_flag(self):
        """
        Verifica que la prioridad asignada a las consultas RAG activa y libera correctamente los 
        indicadores de uso de recursos, incluso cuando existen contextos anidados.
        """
        self.assertFalse(resource_priority.is_rag_active())
        with resource_priority.rag_priority():
            self.assertTrue(resource_priority.is_rag_active())
            with resource_priority.rag_priority():
                self.assertTrue(resource_priority.is_rag_active())
        self.assertFalse(resource_priority.is_rag_active())

    def test_wait_for_rag_idle_returns_false_on_timeout(self):
        """
        Comprueba que la espera de recursos disponibles finaliza correctamente cuando se supera el tiempo 
        máximo de espera establecido.
        """
        resource_priority._rag_active_event.set()
        self.assertFalse(resource_priority.wait_for_rag_idle(timeout=0.01))

    def test_wait_for_rag_idle_returns_true_after_event_clears(self):
        """
        Verifica que la espera finaliza con éxito cuando los recursos ocupados por consultas RAG quedan liberados
        antes del tiempo límite.
        """
        resource_priority._rag_active_event.set()

        def clear_later():
            resource_priority._rag_active_event.clear()

        threading.Timer(0.02, clear_later).start()
        self.assertTrue(resource_priority.wait_for_rag_idle(timeout=0.5))

    def test_wait_for_rag_idle_async_waits_until_idle(self):
        """
        Comprueba el funcionamiento de la espera asíncrona hasta que no existan consultas RAG activas 
        utilizando recursos compartidos.
        """
        async def _run():
            resource_priority._rag_active_event.set()
            asyncio.get_running_loop().call_later(0.02, resource_priority._rag_active_event.clear)
            await resource_priority.wait_for_rag_idle_async(poll_timeout_s=0.01)

        asyncio.run(_run())

    def test_ollama_request_slot_background_async_waits_for_idle(self):
        """
        Verifica que las tareas en segundo plano que utilizan Ollama esperan correctamente a que finalicen las consultas prioritarias antes de ejecutarse.
        """
        async def _run():
            resource_priority._rag_active_event.set()
            asyncio.get_running_loop().call_later(0.02, resource_priority._rag_active_event.clear)
            async with resource_priority.ollama_request_slot_background_async(poll_timeout_s=0.01):
                self.assertFalse(resource_priority.is_rag_active())

        asyncio.run(_run())

    def test_rag_priority_async_sets_and_clears_flag(self):
        """
        Comprueba que la gestión asíncrona de prioridades RAG activa y libera correctamente los indicadores de ocupación de recursos.
        """
        async def _run():
            self.assertFalse(resource_priority.is_rag_active())
            async with resource_priority.rag_priority_async():
                self.assertTrue(resource_priority.is_rag_active())
            self.assertFalse(resource_priority.is_rag_active())

        asyncio.run(_run())

    def test_wait_for_rag_idle_returns_true_when_not_active(self):
        """
        Verifica que la espera de recursos finaliza inmediatamente cuando no existen consultas RAG activas utilizando recursos compartidos.
        """
        resource_priority._rag_active_event.clear()
        self.assertTrue(resource_priority.wait_for_rag_idle(timeout=0.01))
