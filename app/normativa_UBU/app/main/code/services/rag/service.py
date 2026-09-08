"""
Autora: Lydia Blanco Ruiz
Script con la lÃ³gica de servicio para validar preguntas, consultar el sistema RAG y persistir resultados.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from typing import Any

from flask_login import current_user

from app.main.code.extensions import db
from app.main.code.inetrnacionalizacion.tarduccion import translate_for
from app.main.code.model.chunk import Chunk
from app.main.code.model.consulta import Consulta

logger = logging.getLogger(__name__)

from .PrototipoRAG import (
    OllamaModelNotFoundError,
    OllamaTimeoutError,
    QueryCancelledError,
    get_ollama_execution_device,
    obtener_mejor_chunk,
)

EMPTY_ANSWER: dict[str, Any] = {
    "answer": "",
    "title": "",
    "filename": "",
    "segment_index": -1,
    "chunk": "",
}

QUESTION_MIN_CHUNKS = 5
QUESTION_MAX_CHUNKS = 20

GUIDED_QUERY_PROFILES = {
    "summary": {
        "phrases": ("resumen general y detallado del documento", "resumen detallado del documento"),
        "retrieval_k": 80,
    },
    "amounts": {
        "phrases": ("cantidades economicas", "importes", "presupuestos", "umbrales"),
        "retrieval_k": 18,
    },
    "deadlines": {
        "phrases": ("plazos importantes", "fecha limite", "presentacion de ofertas"),
        "retrieval_k": 18,
    },
    "solvency": {
        "phrases": ("requisitos de solvencia",),
        "retrieval_k": 14,
    },
    "criteria": {
        "phrases": ("criterios de adjudicacion", "ponderacion"),
        "retrieval_k": 16,
    },
    "guarantees": {
        "phrases": ("garantias provisionales", "garantias definitivas"),
        "retrieval_k": 12,
    },
    "budget": {
        "phrases": ("presupuesto base", "valor estimado"),
        "retrieval_k": 14,
    },
    "duration": {
        "phrases": ("duracion del contrato", "posibles prorrogas"),
        "retrieval_k": 12,
    },
    "penalties": {
        "phrases": ("penalizaciones", "causas de resolucion", "incumplimientos"),
        "retrieval_k": 16,
    },
    "submission": {
        "phrases": ("presentar la oferta", "documentacion requerida", "sobres o archivos"),
        "retrieval_k": 16,
    },
}

QUESTION_MIN_SIMILARITY = 0.5

DOCUMENT_REFERENCE_KEYWORDS = {
    "pliego",
    "pliegos",
    "documento",
    "documentos",
    "norma",
    "normas",
    "normativa",
    "sobre",
    "del",
    "de",
    "que",
    "y",
    "o",
}


def normalize_text(value: str | None) -> str:
    """
    Normaliza un texto para comparaciÃ³n: minÃºsculas, sin acentos, espacios normalizados.

    Args:
        value: Texto a normalizar. Puede ser None.

    Returns:
        Texto normalizado: minÃºsculas, sin caracteres diacrÃ­ticos,
        espacios consecutivos convertidos a uno solo, y sin espacios al inicio/fin.
        Retorna string vacÃ­o si el valor es None o vacÃ­o.
    """

    value = (value or "").strip().lower()

    if not value:

        return ""

    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", normalized).strip()


def detect_tipo_documento(question: str) -> str | None:
    """
    Detecta si la pregunta se refiere a pliegos administrativos o tÃ©cnicos.
    Analiza el texto de la pregunta para determinar si solicita informaciÃ³n
    especÃ­fica sobre pliegos administrativos o tÃ©cnicos basÃ¡ndose en palabras clave.

    Args:
        question: Texto de la pregunta del usuario.

    Returns:
        "administrativo" si la pregunta menciona pliegos administrativos,
        "tecnico" si menciona pliegos tÃ©cnicos,
        None si no se detecta un tipo especÃ­fico o se mencionan ambos.
    """

    return None

def normalize_guided_retrieval_k(profile_name: str, retrieval_k: int | None) -> int:
    """
    Normaliza el numero de chunks que se pediran a Qdrant para un perfil.

    Todas las preguntas tienen un minimo de 5. El resumen puede pedir mas
    contexto; el resto queda limitado a 20 para mantener prompts razonables.
    """
    normalized_k = max(QUESTION_MIN_CHUNKS, int(retrieval_k or QUESTION_MAX_CHUNKS))
    if profile_name != "summary":
        normalized_k = min(normalized_k, QUESTION_MAX_CHUNKS)
    return normalized_k


def detect_guided_query_profile(question: str) -> tuple[str, int]:
    """
    Detecta las preguntas generadas por el formulario guiado y devuelve el
    perfil de prompt junto con el nÃºmero de chunks recomendado.
    
    Args:
        question: Texto de la pregunta del usuario.

    Returns:
        Una tupla con el nombre del perfil y el nÃºmero de chunks recomendado.
    """
    normalized = normalize_text(question)
    for profile_name, config in GUIDED_QUERY_PROFILES.items():
        if any(phrase in normalized for phrase in config["phrases"]):
            return profile_name, normalize_guided_retrieval_k(profile_name, config["retrieval_k"])
    return "general", normalize_guided_retrieval_k("general", QUESTION_MAX_CHUNKS)


def extract_expediente_candidate(question: str) -> str | None:
    """
    Extrae un posible nÃºmero de expediente de una pregunta usando expresiones regulares.
    Busca patrones comunes de referencia a expedientes en el texto de la pregunta,
    tanto entre comillas como en formatos estÃ¡ndar de expediente.

    Args:
        question: Texto de la pregunta que puede contener una referencia a expediente.

    Returns:
        NÃºmero de expediente candidato si se encuentra un patrÃ³n vÃ¡lido,
        None si no se encuentra ningÃºn patrÃ³n o el candidato estÃ¡ vacÃ­o.
    """
    
    expediente_prefix = r"expediente(?:\s+n[uÃº]mero|\s+n[Âºo]?)?"
    expediente_separator = r"\s*[:#-]?\s*"
    expediente_token = r"[A-Za-z0-9][A-Za-z0-9/_.-]*"
    expediente_smulti = rf"{expediente_token}(?:\s+{expediente_token}){{0,5}}"

    question = (question or "").strip()

    if not question:
        return None

    quoted_pattern = rf"{expediente_prefix}{expediente_separator}[\"â€œ](.+?)[\"â€]"
    quoted = re.search(quoted_pattern, question, re.IGNORECASE)

    if quoted:
        return quoted.group(1).strip() or None

    normal_pattern = rf"{expediente_prefix}{expediente_separator}({expediente_smulti})"
    match = re.search(normal_pattern, question, re.IGNORECASE)

    if not match:
        return None

    words = match.group(1).strip().split()

    while words and normalize_text(words[-1]) in DOCUMENT_REFERENCE_KEYWORDS:
        words.pop()

    candidate = " ".join(words).strip(" ,.;:")
    return candidate or None

def resolve_numero_expediente(question: str) -> str | None:
    """
    Resuelve un nÃºmero de expediente vÃ¡lido a partir de una pregunta.
    Extrae un candidato de expediente de la pregunta y lo valida contra
    los expedientes existentes en la base de datos, intentando coincidencias
    exactas y normalizadas.

    Args:
        question: Texto de la pregunta que puede contener una referencia a expediente.

    Returns:
        NÃºmero de expediente vÃ¡lido de la base de datos si se encuentra coincidencia,
        el candidato original si no se encuentra en BD pero tiene formato vÃ¡lido,
        None si no se puede extraer ningÃºn candidato.
    """

    return None

DOC_TYPE_MARKERS = {
    "[doc_type=administrativo]": "administrativo",
    "[doc_type = administrativo]": "administrativo",
    "[doc_type=tecnico]": "tecnico",
    "[doc_type = tecnico]": "tecnico",
}


def extract_doc_type_override(text: str) -> tuple[str, str | None]:
    """
    Extrae una posible selecciÃ³n de tipo de documento desde la pregunta.
    Permite que el usuario indique explÃ­citamente el tipo de documento (administrativo o tÃ©cnico)

    Args:
        text (str): texto de la pregunta que puede contener un marcador de tipo de documento.

    Returns:
        tuple[str, str | None]: Una tupla con el texto de la pregunta limpio de marcadores y el tipo de documento indicado ("administrativo" o "tecnico") o None si no se indicÃ³ ningÃºn tipo.
    """

    cleaned = (text or "").strip()
    lower_text = cleaned.lower()

    for marker in DOC_TYPE_MARKERS:
        pos = lower_text.find(marker)
        if pos >= 0:
            cleaned = (
                cleaned[:pos]
                + " "
                + cleaned[pos + len(marker):]
            ).strip()
            return cleaned, None

    return cleaned, None

async def rag_answer(
    question: str,
    model: str | None = None,
    should_cancel=None,
    on_status=None,
    user_id: int | None = None,
    lang: str = "es",
) -> dict[str, Any]:
    """
    Procesa una pregunta usando el sistema RAG y guarda la consulta en BD.
    Valida la pregunta, extrae metadatos (expediente, tipo documento),
    consulta el sistema RAG para obtener la mejor respuesta, mide el tiempo
    de respuesta y guarda toda la informaciÃ³n en la base de datos.

    Args:
        question: Texto de la pregunta del usuario.
        should_cancel: FunciÃ³n opcional que retorna True para cancelar la consulta.
        on_status: FunciÃ³n opcional callback para reportar progreso/status.
        user_id: ID del usuario que realiza la consulta. Si None, usa current_user.
        lang: CÃ³digo de idioma para mensajes de error ("es", "en"). Defaults to "es".

    Returns:
        Diccionario con respuesta RAG y metadatos adicionales:
        - answer: Respuesta generada por el sistema
        - title: TÃ­tulo del documento fuente
        - filename: Nombre del archivo fuente
        - segment_index: Ãndice del segmento en el documento
        - chunk: Texto del fragmento relevante
        - qdrant_point_id: ID del punto en Qdrant
        - elapsed_s: Tiempo de procesamiento en segundos

    Raises:
        QueryCancelledError: Si should_cancel retorna True durante el procesamiento.
    """

    question, _legacy_doc_type = extract_doc_type_override(question)
    invalid = validate_question(question, lang=lang)

    if invalid:
        return invalid

    start = time.perf_counter()
    data: dict[str, Any]
    query_profile, retrieval_k = detect_guided_query_profile(question)

    async def _run_query() -> dict[str, Any]:
        """
        Ejecuta la consulta al sistema RAG con los parÃ¡metros adecuados.
        Muestra un mensaje de preparaciÃ³n si se proporciona on_status.

        Returns:
            dict[str, Any]: Diccionario con la respuesta del sistema RAG o un mensaje de error si ocurre una excepciÃ³n durante la consulta.
        """
        if on_status:
            on_status(translate_for(lang, "rag.preparing"))
        return await obtener_mejor_chunk(
            question,
            model=model,
            should_cancel=should_cancel,
            on_status=on_status,
            query_profile=query_profile,
            retrieval_k=retrieval_k,
            min_similarity=QUESTION_MIN_SIMILARITY,
        )

    try:
        data = await _run_query()
    except QueryCancelledError:
        raise
    except OllamaTimeoutError as e:
        logger.warning("Timeout consultando Ollama: %s", e)
        data = message_error(translate_for(lang, "rag.timeout_error"))
    except OllamaModelNotFoundError as e:
        logger.warning("Modelo de Ollama no disponible: %s", e)
        data = message_error(translate_for(lang, "rag.model_not_found_error"))
    except Exception:
        logger.exception("Error en rag_answer")
        data = message_error(translate_for(lang, "rag.system_error"))

    elapsed = time.perf_counter() - start
    # `obtener_mejor_chunk` intenta rellenar `execution_device` con el dispositivo real
    data.setdefault("execution_device", get_ollama_execution_device())

    # Guardado en BBDD
    try_persist(question, data, elapsed, user_id=user_id)
    data["elapsed_s"] = round(elapsed, 4)

    # Mejor chunk (ranking 1) para el front
    retrieved = data.get("retrieved") or []
    data["qdrant_point_id"] = (
        (retrieved[0].get("qdrant_point_id") or "").strip() if retrieved else ""
    )
    return data


def message_error(msg: str) -> dict[str, Any]:
    """
    Crea un diccionario de respuesta de error para el sistema RAG.

    Args:
        msg: Mensaje de error descriptivo.

    Returns:
        Diccionario con estructura de respuesta RAG pero con campos vacÃ­os
        excepto el campo 'answer' que contiene el mensaje de error.
    """

    out = dict(EMPTY_ANSWER)
    out["answer"] = msg
    return out

def validate_question(question: str, lang: str = "es") -> dict[str, Any] | None:
    """
    Valida una pregunta antes de procesarla en el sistema RAG.
    Verifica que la pregunta no estÃ© vacÃ­a y no exceda la longitud mÃ¡xima permitida.

    Args:
        question: Texto de la pregunta a validar.
        lang: CÃ³digo de idioma para los mensajes de error. Defaults to "es".

    Returns:
        Diccionario de error si la validaciÃ³n falla (pregunta vacÃ­a o demasiado larga),
        None si la pregunta es vÃ¡lida.
    """

    if not question:
        return message_error(translate_for(lang, "rag.empty_question"))

    if len(question) > 2000:
        return message_error(translate_for(lang, "rag.question_too_long"))

    return None

def try_persist(question: str, data: dict[str, Any], elapsed: float, user_id: int | None = None) -> None:
    """
    Intenta guardar una consulta en la base de datos con manejo de errores.
    Envuelve la funciÃ³n persist_consulta en un try-catch para evitar que
    errores de base de datos interrumpan el flujo principal de respuesta RAG.

    Args:
        question: Texto de la pregunta realizada.
        data: Diccionario con la respuesta y metadatos del sistema RAG.
        elapsed: Tiempo transcurrido en segundos para procesar la consulta.
        user_id: ID del usuario que realizÃ³ la consulta. Si None, usa current_user.

    Returns:
        None: La funciÃ³n no retorna valor. Los errores se loggean.
    """

    try:
        persist_consulta(question, data, elapsed, user_id=user_id)

    except Exception:
        logger.exception("No se pudo guardar la consulta en BBDD")
        db.session.rollback()
        

def persist_consulta(question: str, data: dict[str, Any], elapsed: float, user_id: int | None = None) -> None:
    """
    Guarda una consulta completa en la base de datos con todos sus metadatos.
    Crea una entidad Consulta con la pregunta, respuesta, tiempo de procesamiento,
    fragmentos recuperados y enlaces a chunks. TambiÃ©n crea las entidades
    ConsultaChunk para mantener las relaciones many-to-many.

    Args:
        question: Texto de la pregunta realizada.
        data: Diccionario con la respuesta y metadatos del sistema RAG.
        elapsed: Tiempo transcurrido en segundos para procesar la consulta.
        user_id: ID del usuario que realizÃ³ la consulta. Si es None, usa current_user.

    Returns:
        None: Los datos se guardan en la base de datos.

    Raises:
        Exception: Si ocurre un error durante el guardado (se propaga desde try_persist).

    """

    owner_id = user_id

    if owner_id is None and current_user and getattr(current_user, "is_authenticated", False):
        owner_id = int(current_user.id)

    if owner_id is not None:
        Consulta.from_rag_result(
            user_id=int(owner_id),
            question=question,
            data=data,
            elapsed=elapsed,
        )
        db.session.commit()
