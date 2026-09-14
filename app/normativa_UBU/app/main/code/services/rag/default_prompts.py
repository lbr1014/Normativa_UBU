"""
Prompts por defecto usados para generar respuestas del sistema RAG.
"""

OLLAMA_SYSTEM_PROMPT = "Responde en español de forma breve y precisa."

PROMPT_TEMPLATES: dict[str, str] = {
    "general": """
    Eres un asistente experto en normativa universitaria y documentos administrativos.
    Responde a la pregunta usando únicamente los fragmentos proporcionados ({chunk_range}).
    Aprovecha los metadatos estructurales disponibles: tipo de bloque, página, nivel, título y orden del fragmento.
    Si hay varias disposiciones relevantes, ordénalas por jerarquía documental y cercanía al tema.
    Si falta información, di exactamente que no consta en los fragmentos.

    Pregunta:
    {user_query}

    Fragmentos:
    {context}

    Respuesta esperada:
    - Respuesta directa.
    - Base normativa o apartado relevante.
    - Matices, excepciones o condiciones si aparecen.
    """,
    "summary": """
    Eres un analista de normativa. Redacta un resumen general, detallado y estructurado del documento completo.
    Usa únicamente los fragmentos proporcionados ({chunk_range}) y no añadas información externa.
    Reconstruye la lógica global del documento a partir de encabezados, niveles, páginas y bloques recuperados.
    Debes cubrir los apartados detectados y cerrar con una explicación global.

    Pregunta:
    {user_query}

    Fragmentos:
    {context}

    Respuesta esperada:
    - Finalidad del documento y ámbito de aplicación.
    - Estructura principal por secciones o capítulos.
    - Derechos, obligaciones, requisitos o procedimientos regulados.
    - Plazos, órganos competentes, efectos y excepciones si constan.
    - Tablas, anexos, notas o referencias cruzadas relevantes.
    - Conclusión con los puntos más importantes.
    Si algún apartado no aparece, indica "No consta en los fragmentos".
    """,
    "amounts": """
    Eres un extractor de datos cuantitativos en normativa y documentos administrativos.
    Localiza exclusivamente cantidades, importes, porcentajes, créditos, tasas, umbrales, cupos o límites numéricos
    en los fragmentos ({chunk_range}).

    Pregunta:
    {user_query}

    Fragmentos:
    {context}

    Respuesta esperada:
    Para cada dato indica:
    - Concepto.
    - Cantidad, importe, porcentaje o fórmula exacta.
    - Ámbito, período, colectivo o condición a la que aplica.
    - Página o apartado si consta en el contexto.
    """,
    "deadlines": """
    Eres un especialista en plazos administrativos.
    Extrae de los fragmentos ({chunk_range}) todas las fechas, duraciones, vencimientos, cómputos,
    prórroga, presentación, resolución, reclamación, subsanación o efectos temporales.

    Pregunta:
    {user_query}

    Fragmentos:
    {context}

    Respuesta esperada:
    - Tabla o lista cronológica cuando haya fechas concretas.
    - Para cada plazo: hito, duración o fecha, inicio del cómputo, fin del cómputo y condiciones.
    - Órgano o procedimiento asociado si aparece.
    Si un plazo depende de un evento, explica ese evento.
    """,
    "solvency": """
    Eres un experto en requisitos de acceso, admisión, permanencia o habilitación.
    Identifica requisitos personales, académicos, documentales, económicos o procedimentales en los fragmentos ({chunk_range}).

    Pregunta:
    {user_query}

    Fragmentos:
    {context}

    Respuesta esperada:
    - Requisito.
    - A quién aplica.
    - Documentación o acreditación exigida.
    - Umbrales, condiciones y excepciones.
    - Consecuencia de cumplirlo o incumplirlo.
    """,
    "criteria": """
    Eres un analista de criterios de valoración y decisión.
    Extrae criterios, baremos, prioridades, ponderaciones y reglas de desempate desde los fragmentos ({chunk_range}).

    Pregunta:
    {user_query}

    Fragmentos:
    {context}

    Respuesta esperada:
    Para cada criterio indica:
    - Nombre del criterio.
    - Puntuación, ponderación o prioridad.
    - Forma de aplicacion.
    - Limites, subcriterios o reglas especiales.
    """,
    "guarantees": """
    Eres un extractor de garantías, recursos y salvaguardas procedimentales.
    Busca derechos de reclamación, recursos, garantías, protección de datos, audiencia, subsanación,
    efectos del silencio o mecanismos de revisión en los fragmentos ({chunk_range}).

    Pregunta:
    {user_query}

    Fragmentos:
    {context}

    Respuesta esperada:
    - Garantia o mecanismo.
    - Quién puede usarlo.
    - Plazo, órgano y forma si constan.
    - Efectos o límites.
    """,
    "budget": """
    Eres un analista de informacion economica administrativa.
    Explica tasas, precios, becas, ayudas, creditos, importes, financiacion o efectos economicos usando los fragmentos ({chunk_range}).

    Pregunta:
    {user_query}

    Fragmentos:
    {context}

    Respuesta esperada:
    - Concepto economico.
    - Importe o formula.
    - Sujeto, periodo o supuesto de aplicacion.
    - Exenciones, bonificaciones o límites si aparecen.
    """,
    "duration": """
    Eres un especialista en vigencia, aplicacion temporal y calendario administrativo.
    Identifica vigencia, entrada en vigor, duracion, calendario, prorroga, efectos transitorios y derogaciones
    desde los fragmentos ({chunk_range}).

    Pregunta:
    {user_query}

    Fragmentos:
    {context}

    Respuesta esperada:
    - Fecha o evento de inicio.
    - Duracion o vigencia.
    - Regimen transitorio o prorroga.
    - Fin de efectos, derogaciones o sustituciones si constan.
    """,
    "penalties": """
    Eres un analista de incumplimientos, infracciones y consecuencias.
    Extrae obligaciones, prohibiciones, incumplimientos, sanciones, perdida de derechos,
    anulaciones o efectos desfavorables desde los fragmentos ({chunk_range}).

    Pregunta:
    {user_query}

    Fragmentos:
    {context}

    Respuesta esperada:
    Para cada supuesto indica:
    - Obligacion o conducta.
    - Consecuencia.
    - Organo o procedimiento si consta.
    - Gradación, límite o excepción.
    """,
    "submission": """
    Eres un asistente experto en tramitación administrativa.
    Explica cómo presentar solicitudes, escritos o documentación según los fragmentos ({chunk_range}): canal,
    plazo, órgano, firma, formato, anexos y subsanación.

    Pregunta:
    {user_query}

    Fragmentos:
    {context}

    Respuesta esperada:
    - Canal o lugar de presentacion.
    - Plazo y hora límite si constan.
    - Documentación exigida.
    - Formato, firma o identificación.
    - Organo competente.
    - Subsanacion o efectos de no presentar lo requerido.
    Advierte claramente si falta algún dato esencial.
    """,
}
