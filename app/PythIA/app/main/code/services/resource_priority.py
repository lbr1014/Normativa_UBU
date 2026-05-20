"""
Utilidades para priorizar respuestas del modelo (RAG/LLM) sobre procesos largos (OCR/Markdown).
Cuando hay una generación RAG en curso, se marca un "busy flag" global y los procesos largos pueden 
consultar ese flag y esperar hasta que se libere.

Esto no fuerza el scheduler de Ollama, pero reduce la contención evitando que
el OCR lance más peticiones mientras el usuario espera una respuesta.
"""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager, contextmanager

_rag_active_lock = threading.Lock()
_rag_active_count = 0
_rag_active_event = threading.Event()


def is_rag_active() -> bool:
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
