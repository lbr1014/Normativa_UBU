"""
Autora: Lydia Blanco Ruiz
Utilidades para priorizar respuestas del modelo (RAG/LLM) sobre procesos largos (OCR/Markdown).
Cuando hay una generación RAG en curso, se marca un "busy flag" global y los procesos largos pueden 
consultar ese flag y esperar hasta que se libere.
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager, contextmanager

_rag_active_lock = threading.Lock()
_rag_active_count = 0
_rag_active_event = threading.Event()
_ollama_slot: asyncio.Semaphore | None = None


def _get_ollama_slot() -> asyncio.Semaphore:
    """
    Obtiene el semáforo para controlar el acceso a las peticiones a Ollama. Si no existe, lo crea de forma segura para evitar condiciones de carrera.

    Returns:
        asyncio.Semaphore: Un semáforo que controla el acceso a las peticiones a Ollama, para reducir la contención en GPU.
    """
    global _ollama_slot  
    if _ollama_slot is None:
        # Serializa peticiones a Ollama para reducir contención en GPU.
        _ollama_slot = asyncio.Semaphore(1)
    return _ollama_slot


def is_rag_active() -> bool:
    """
    Indica si actualmente hay una generación RAG/LLM activa.
    Los procesos largos (OCR/Markdown) pueden usar esta información para decidir esperar antes de hacer peticiones a Ollama, 
    reduciendo la latencia percibida por el usuario.
    
    Returns:
        bool: ``True`` si hay una generación RAG activa, ``False`` en caso contrario.
    """
    return _rag_active_event.is_set()


@contextmanager
def rag_priority():
    """
    Marca una sección como prioritaria (RAG/LLM).
    Mientras esté activa, los procesos largos deberían pausar sus peticiones a Ollama.
    """
    global _rag_active_count
    with _rag_active_lock:
        _rag_active_count += 1
        _rag_active_event.set()
    try:
        yield
    finally:
        with _rag_active_lock:
            _rag_active_count = max(0, _rag_active_count - 1)
            if _rag_active_count == 0:
                _rag_active_event.clear()


@asynccontextmanager
async def rag_priority_async():
    """
    Marca una sección como prioritaria (RAG/LLM) de forma asíncrona.
    """
    with rag_priority():
        yield


@asynccontextmanager
async def ollama_request_slot_async():
    """
    Serializa peticiones a Ollama (RAG + OCR) para que, en condiciones normales,
    solo haya una generación activa usando GPU/servidor.
    """
    slot = _get_ollama_slot()
    async with slot:
        yield


@asynccontextmanager
async def ollama_request_slot_background_async(*, poll_timeout_s: float = 0.25):
    """
    Variante para procesos largos (OCR/Markdown).

    Garantiza que si hay una consulta RAG activa, el background job espere y no
    "se cuele" con una nueva petición a Ollama. Esto no puede interrumpir una
    petición ya en vuelo, pero reduce el impacto en latencia al impedir que se
    inicien nuevas peticiones de OCR mientras el usuario espera respuesta.
    
    Args:
        poll_timeout_s: Intervalo entre comprobaciones de si RAG sigue activo, en segundos.
    """
    slot = _get_ollama_slot()
    while True:
        await wait_for_rag_idle_async(poll_timeout_s=poll_timeout_s)
        await slot.acquire()
        # Re-check: puede haberse activado RAG justo después de adquirir el slot.
        if not _rag_active_event.is_set():
            break
        slot.release()
        await asyncio.sleep(0)
    try:
        yield
    finally:
        slot.release()


def wait_for_rag_idle(timeout: float | None = None) -> bool:
    """
    Espera a que no haya RAG activo.
    
    Args:
        timeout: Tiempo máximo a esperar en segundos. Si es None, esperará indefinidamente.

    Returns:
        True si quedó libre, False si expiró el timeout.
    """
    import time

    if not _rag_active_event.is_set():
        return True

    deadline = None if timeout is None else (time.monotonic() + float(timeout))
    while _rag_active_event.is_set():
        if deadline is not None and time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    return True


async def wait_for_rag_idle_async(*, poll_timeout_s: float = 0.5) -> None:
    """
    Espera de forma async-friendly hasta que no haya RAG activo.
    
    Args:
        poll_timeout_s: Intervalo entre comprobaciones en segundos.
        
    """
    import asyncio

    while _rag_active_event.is_set():
        await asyncio.to_thread(_rag_active_event.wait, poll_timeout_s)
